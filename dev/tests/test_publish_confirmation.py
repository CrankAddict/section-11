"""Bounded publication readback against synthetic remotes; no live requests."""
import ast
import contextlib
import copy
import io
import sys
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import Offline, MAINT
from test_b2_hosted import Remote
import direct_commit as C
import hosted
import hosted_runtime as R


SECRET = 'https://signed.invalid/file?token=synthetic-secret\n::error::injected'


class Clock:
    now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class PublishCase(Offline):
    def setUp(self):
        super().setUp()
        self.clock = Clock()
        for target, replacement in (('monotonic', self.clock.monotonic), ('sleep', self.clock.sleep)):
            patcher = mock.patch.object(C.time, target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.remote = Remote({'latest.json': b'old', 'custom/keep': b'owner'})
        self.pub = C.DirectPublisher(self.remote)
        self.before = self.pub.snapshot()
        self.out, self.err = io.StringIO(), io.StringIO()
        for redirect in (contextlib.redirect_stdout(self.out), contextlib.redirect_stderr(self.err)):
            redirect.__enter__()
            self.addCleanup(redirect.__exit__, None, None, None)

    def publish(self):
        changes = {'latest.json': b'new'}
        return self.pub.publish(self.before, changes, 'Synthetic publication',
                                hosted.update.exact_validator(changes))

    def after_patch(self):
        calls = self.remote.calls
        indices = [i for i, c in enumerate(calls) if c[0] == 'PATCH']
        self.assertEqual(len(indices), 1)
        self.assertIs(calls[indices[0]][2]['force'], False)
        later = calls[indices[0] + 1:]
        self.assertTrue(all(c[0] == 'GET' for c in later))
        self.assertLessEqual(len(later), 12)
        return later

    def fault_reads(self, faults, *, suffix='/git/ref/heads/main'):
        original = self.remote.get
        pending = list(faults)

        def get(path):
            applied = any(c[0] == 'PATCH' for c in self.remote.calls)
            if applied and path.startswith(suffix) and pending:
                item = pending.pop(0)
                self.remote.calls.append(('GET', path))
                if isinstance(item, Exception):
                    raise item
                return copy.deepcopy(item)
            return original(path)

        self.remote.get = get

    def stale(self):
        return {'object': {'type': 'commit', 'sha': self.before['commit']}}


class ConfirmationTests(PublishCase):
    def test_stale_tip_then_fresh_confirms_exact_tree_without_second_patch(self):
        self.fault_reads([self.stale()])
        after = self.publish()
        self.assertEqual(after, self.pub.snapshot(self.remote.tip))
        self.assertEqual(after['parents'], [self.before['commit']])
        self.assertEqual(self.remote.inventory(), {'latest.json': b'new', 'custom/keep': b'owner'})
        self.assertIn('Confirmed publication: ' + after['commit'], self.out.getvalue())
        self.assertEqual(self.err.getvalue(), '')
        self.assertEqual(self.clock.now, 1)
        self.after_patch()

    def test_readback_errors_then_success_at_tip_and_snapshot(self):
        for suffix, faults in (
            ('/git/ref/', [hosted.APIError(502, SECRET)]),
            ('/git/ref/', [hosted.requests.exceptions.Timeout(SECRET)]),
            ('/git/ref/', [hosted.requests.exceptions.ConnectionError(SECRET)]),
            ('/git/ref/', [hosted.APIError(404, SECRET)]),
            ('/git/commits/', [hosted.APIError(503, SECRET)]),
        ):
            with self.subTest(suffix=suffix, fault=type(faults[0]).__name__):
                self.remote.calls.clear()
                self.before = self.pub.snapshot()
                self.fault_reads(faults, suffix=suffix)
                # A distinct payload ensures every subcase actually publishes.
                self.remote.tip = self.remote.commit({'latest.json': b'old'},
                                                     [self.remote.tip], 'Reset fixture')
                self.before = self.pub.snapshot()
                self.assertEqual(self.publish()['commit'], self.remote.tip)
                self.after_patch()
        self.assertNotIn(SECRET, self.out.getvalue() + self.err.getvalue())

    def test_ancestry_read_error_then_success_restarts_at_tip(self):
        self.fault_reads([self.stale()])
        self.fault_reads([hosted.APIError(502, SECRET)], suffix='/compare/')
        self.assertEqual(self.publish()['commit'], self.remote.tip)
        self.assertEqual(len(self.after_patch()), 5)
        self.assertEqual(self.clock.now, 1)

    def test_stale_forever_stays_unknown_and_never_repeats_any_write(self):
        self.fault_reads([self.stale()] * 3)
        with self.assertRaisesRegex(C.UnknownOutcome, 'acknowledged publication absent'):
            self.publish()
        later = self.after_patch()
        self.assertEqual(len(later), 6)
        self.assertEqual(self.clock.now, 3)
        self.assertNotIn('Confirmed publication:', self.out.getvalue())
        self.assertIn('acknowledged-not-visible; commit=' + self.remote.tip, self.err.getvalue())

    def test_failed_patch_response_gets_only_one_readback(self):
        for fault in ('denied', 'unknown', 'lost'):
            with self.subTest(fault=fault):
                self.remote = Remote({'latest.json': b'old'})
                self.remote.ref_fault = fault
                self.pub = C.DirectPublisher(self.remote)
                self.before = self.pub.snapshot()
                if fault == 'lost':
                    self.assertEqual(self.publish()['commit'], self.remote.tip)
                else:
                    with self.assertRaises(RuntimeError) as caught:
                        self.publish()
                    if fault == 'denied':
                        self.assertIs(type(caught.exception), RuntimeError)
                later = self.after_patch()
                self.assertEqual(sum(c[1] == '/git/ref/heads/main' for c in later), 1)
        self.assertEqual(self.clock.now, 0)

    def test_unacknowledged_applied_write_with_stale_readback_is_not_reconfirmed(self):
        self.remote.ref_fault = 'lost'
        self.fault_reads([self.stale()])
        with self.assertRaisesRegex(RuntimeError, 'not on observed default history') as caught:
            self.publish()
        self.assertIs(type(caught.exception), RuntimeError)
        self.assertEqual(len(self.after_patch()), 2)
        self.assertEqual(self.clock.now, 0)

    def test_default_advanced_remains_unknown_after_ancestry_confirmation(self):
        self.remote.ref_fault = 'later'
        with self.assertRaisesRegex(C.UnknownOutcome, 'default advanced'):
            self.publish()
        self.assertEqual(len(self.after_patch()), 4)
        self.assertIn('default-advanced; commit=', self.err.getvalue())

    def test_invalid_snapshot_is_not_retried_or_confirmed(self):
        self.fault_reads([{'sha': 'f' * 40}], suffix='/git/commits/')
        with self.assertRaisesRegex(C.UnknownOutcome, 'readback validation failed'):
            self.publish()
        self.assertEqual(len(self.after_patch()), 2)
        self.assertEqual(self.clock.now, 0)
        self.assertNotIn('Confirmed publication:', self.out.getvalue())

    def test_policy_and_rate_refusals_are_not_repeated(self):
        for status in (401, 403, 429):
            with self.subTest(status=status):
                self.remote = Remote({'latest.json': b'old'})
                self.pub = C.DirectPublisher(self.remote)
                self.before = self.pub.snapshot()
                self.fault_reads([hosted.APIError(status, SECRET)])
                with self.assertRaisesRegex(C.UnknownOutcome, 'readback request failed'):
                    self.publish()
                self.assertEqual(len(self.after_patch()), 1)
        self.assertEqual(self.clock.now, 0)

    def test_unknown_holds_maintenance_and_recovered_confirmation_clears_hold(self):
        info = {'base': self.before['commit'], 'run_sync': True}

        def context(value=None):
            if value is not None:
                info.clear()
                info.update(value)
            return dict(info)

        def publish():
            after = self.publish()
            info.update(base=after['commit'], published=True)

        controller = SimpleNamespace(context=context, publish_data=publish,
                                     cache_prepare=None, run_sync=None, finalize_export=None,
                                     validate_generated=None, cache_promote=None)
        self.fault_reads([self.stale()] * 3)
        with self.assertRaises(C.UnknownOutcome):
            R.run_phase(controller, 'publish')
        self.assertIs(info['publication_uncertain'], True)
        self.assertNotIn('published', info)
        with mock.patch.object(hosted, 'context', context), mock.patch.object(hosted, 'publisher') as factory:
            with self.assertRaisesRegex(C.UnknownOutcome, 'no maintenance attempted'):
                hosted.maintain()
            factory.assert_not_called()
        # Independent new fixture for recovery, not a replay of the unknown write.
        self.remote = Remote({'latest.json': b'old'})
        self.pub = C.DirectPublisher(self.remote)
        self.before = self.pub.snapshot()
        self.fault_reads([self.stale()])
        R.run_phase(controller, 'publish')
        self.assertIs(info['published'], True)
        self.assertNotIn('publication_uncertain', info)
        self.after_patch()

    def run_entry(self, module, main):
        # Execute the actual CLI exception handler with an injected offline main.
        tree = ast.parse((MAINT / (module.__name__ + '.py')).read_text())
        entry = ast.Module(body=[tree.body[-1]], type_ignores=[])
        namespace = dict(vars(module), __name__='__main__', main=main)
        with mock.patch.object(sys, 'argv', ['hosted.py', 'publish']), self.assertRaises(SystemExit):
            exec(compile(entry, '<actual-cli-handler>', 'exec'), namespace)

    def test_safe_reason_and_sha_survive_both_cli_handlers_without_exception_text(self):
        for module in (R, hosted):
            with self.subTest(entry=module.__name__):
                self.remote = Remote({'latest.json': b'old'})
                self.pub = C.DirectPublisher(self.remote)
                self.before = self.pub.snapshot()
                self.fault_reads([hosted.APIError(502, SECRET)] * 3)
                with mock.patch.object(hosted, 'context', return_value={}):
                    self.run_entry(module, self.publish)
                self.assertIn('readback-error; commit=' + self.remote.tip, self.err.getvalue())
                self.assertEqual(len(self.after_patch()), 3)
        text = self.out.getvalue() + self.err.getvalue()
        for forbidden in ('signed.invalid', 'synthetic-secret', 'injected', 'Traceback'):
            self.assertNotIn(forbidden, text)
        self.assertIn('Hosted acquisition or phase verification failed', text)

    def test_unrelated_runtime_error_remains_suppressed(self):
        def fail():
            raise ValueError(SECRET)
        self.run_entry(R, fail)
        self.assertNotIn('signed.invalid', self.err.getvalue())
        self.assertNotIn('Publication confirmation:', self.err.getvalue())


class HostedBoundsTests(PublishCase):
    def use_hosted_transport(self, on_patch=None):
        api = hosted.HostedGitHub('synthetic/data', 'synthetic-token')

        def request(method, url, **kwargs):
            self.assertLessEqual(kwargs['timeout'], 10)
            self.assertFalse(kwargs['allow_redirects'])
            path = url.removeprefix(hosted.D.API + api.prefix)
            if method != 'GET':
                result = self.remote.write(method, path, kwargs['json'])
                if method == 'PATCH' and on_patch:
                    on_patch(api)
            elif path == '':
                result = self.remote.metadata()
            elif path.startswith('/git/trees/'):
                identity = path.split('/git/trees/')[1].split('?')[0]
                result = {'tree': list(self.remote.tree(identity).values()), 'truncated': False}
            else:
                result = self.remote.get(path)
            return SimpleNamespace(status_code=200, content=b'{}', json=lambda: result)

        patcher = mock.patch.object(hosted.requests, 'request', side_effect=request)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pub = C.DirectPublisher(api)
        self.before = self.pub.snapshot()
        return api

    def test_real_hosted_transport_recovers_stale_tip_and_transient_error(self):
        api = self.use_hosted_transport()
        self.fault_reads([self.stale(), hosted.requests.exceptions.Timeout(SECRET)])
        self.assertEqual(self.publish()['commit'], self.remote.tip)
        self.assertEqual(len(self.after_patch()), 6)
        self.assertEqual(api.confirm_count, 6)
        self.assertEqual(self.clock.now, 3)

    def test_snapshot_tree_read_error_is_reconfirmed_without_rewriting_objects(self):
        self.use_hosted_transport()
        original = self.remote.tree
        failed = False

        def tree(identity):
            nonlocal failed
            if not failed and any(c[0] == 'PATCH' for c in self.remote.calls):
                failed = True
                self.remote.calls.append(('GET', 'tree'))
                raise hosted.APIError(502, SECRET)
            return original(identity)

        self.remote.tree = tree
        self.assertEqual(self.publish()['commit'], self.remote.tip)
        self.assertEqual(len(self.after_patch()), 6)
        self.assertEqual(self.clock.now, 1)

    def test_shared_request_bound_stops_before_request_1201(self):
        api = self.use_hosted_transport(lambda api: setattr(api, 'count', 1199))
        self.fault_reads([self.stale()])
        with self.assertRaisesRegex(C.UnknownOutcome, 'request bound reached'):
            self.publish()
        self.assertEqual(api.count, 1200)
        self.assertEqual(len(self.after_patch()), 1)
        self.assertIn('readback-request-bound', self.err.getvalue())

    def test_phase_deadline_reserves_time_and_does_not_start_a_read(self):
        def near_deadline(api):
            self.clock.now = 231
        api = self.use_hosted_transport(near_deadline)
        with self.assertRaisesRegex(C.UnknownOutcome, 'readback deadline reached'):
            self.publish()
        self.assertEqual(self.after_patch(), [])
        self.assertEqual(api.publication_deadline, 240)
        self.assertLess(self.clock.now, 270)

    def test_nearby_deadline_case_confirms_with_margin(self):
        def enough_time(api):
            self.clock.now = 229
        self.use_hosted_transport(enough_time)
        self.assertEqual(self.publish()['commit'], self.remote.tip)
        self.assertEqual(len(self.after_patch()), 3)
        self.assertLess(self.clock.now, 240)

    def test_phase_budget_includes_work_before_publisher_creation(self):
        self.clock.now = 200
        with mock.patch.object(hosted, 'PUBLICATION_DEADLINE', 240):
            api = self.use_hosted_transport(lambda api: setattr(self.clock, 'now', 231))
        self.assertEqual(api.deadline, 500)
        self.assertEqual(api.publication_deadline, 240)
        with self.assertRaisesRegex(C.UnknownOutcome, 'readback deadline reached'):
            self.publish()
        self.assertEqual(self.after_patch(), [])

    def test_confirmation_window_exhaustion_and_late_response_stay_unknown(self):
        self.use_hosted_transport()
        original = self.remote.get

        def late(path):
            result = original(path)
            if any(c[0] == 'PATCH' for c in self.remote.calls):
                self.clock.now += 46
            return result

        self.remote.get = late
        with self.assertRaisesRegex(C.UnknownOutcome, 'readback deadline reached'):
            self.publish()
        self.assertEqual(len(self.after_patch()), 1)
        self.assertNotIn('Confirmed publication:', self.out.getvalue())

    def test_existing_transport_deadline_is_never_extended(self):
        api = self.use_hosted_transport(lambda api: setattr(api, 'deadline', 9))
        with self.assertRaisesRegex(C.UnknownOutcome, 'readback deadline reached'):
            self.publish()
        self.assertEqual(api.deadline, 9)
        self.assertEqual(self.after_patch(), [])

    def test_confirmation_has_its_own_request_cap_and_forbids_mutation(self):
        api = self.use_hosted_transport()
        with api.confirmation_reads():
            for _ in range(12):
                api.get('/git/ref/heads/main')
            count = api.count
            with self.assertRaisesRegex(C.ConfirmationBound, 'request-bound'):
                api.get('/git/ref/heads/main')
            self.assertEqual(api.count, count)
            with self.assertRaisesRegex(ValueError, 'read-only'):
                api.write('PATCH', '/git/refs/heads/main', {'sha': self.remote.tip, 'force': False})
            self.assertEqual(api.count, count)
        self.assertFalse(any(c[0] == 'PATCH' for c in self.remote.calls))
