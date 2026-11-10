"""Local/Manual ten-minute maintenance, with offline transport and real state."""
import contextlib
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest import mock
from urllib.parse import urlparse

import test_update_prototype as P
import test_b2_hosted as B
from test_update_path_fixes import ReleaseHTTP, Response


class BoundedReleaseHTTP(ReleaseHTTP):
    """Exercise real fetch bounds with synthetic tag chains and asset redirects."""
    def __init__(self, depths):
        super().__init__(0)
        self.tags[0] = '2026.11.10'
        self.depths = depths
        self.ref_count = 0
        self.depth = 0
        self.hop = 0

    def request(self, method, url, **kwargs):
        path = urlparse(url).path
        if '/git/ref/tags/' in path:
            self.calls.append(url)
            self.depth = self.depths[self.ref_count % 2]
            self.ref_count += 1
            self.hop = 0
            return Response({'object': {'type': 'tag', 'sha': 'a' * 40}})
        if '/git/tags/' in path:
            self.calls.append(url)
            self.hop += 1
            return Response({'object': {'type': 'commit' if self.hop == self.depth else 'tag',
                                         'sha': self.commits[0] if self.hop == self.depth else 'a' * 40}})
        if '/releases/download/' in path or urlparse(url).hostname == 'release-assets.githubusercontent.com':
            self.calls.append(url)
            hop = int(path.rsplit('/', 1)[-1]) if path.startswith('/hop/') else 0
            if hop < 3:
                response = Response(status=302)
                response.headers = {'Location': 'https://release-assets.githubusercontent.com/hop/' + str(hop + 1)}
                response.close = lambda: None
                return response
            return Response(content=self.archive(0))
        return super().request(method, url, **kwargs)


class MeteredReleaseHTTP(ReleaseHTTP):
    def __init__(self):
        super().__init__(0)
        self.tags[0] = '2026.11.10'
        self.bodies = []

    def request(self, method, url, **kwargs):
        response = super().request(method, url, **kwargs)
        self.bodies.append((url, len(response.content)))
        return response


class LocalCheckTests(P.Offline):
    def setUp(self):
        super().setUp()
        self.now = datetime(2026, 11, 9, 1, tzinfo=timezone.utc)
        owner = self

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return owner.now.astimezone(tz) if tz else owner.now.replace(tzinfo=None)

        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(P.SYNC, 'datetime', Clock))
        self.stack.enter_context(mock.patch.object(P.SYNC.Path, 'cwd', return_value=self.root))
        self.stack.enter_context(mock.patch.dict(os.environ, {'GITHUB_ACTIONS': ''}))
        self.stack.enter_context(mock.patch('subprocess.run', side_effect=AssertionError('real subprocess prohibited')))
        self.release = B.release('2026.11.08', '11.108')
        self.install_release(self.release)
        self.state = self.root / '.section11-state'
        self.claim = self.state / 'local-check.json'
        self.legacy = self.state / 'auto-update.json'
        P.write(self.root, {'latest.json': b'last good data', 'history.json': b'last good history',
                            'state/private.json': b'private state', 'custom/personal.txt': b'personal'})

    def install_release(self, release):
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release), \
                mock.patch('builtins.input', return_value='y'), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertTrue(P.SYNC.do_update(timer_choice=False), out.getvalue())

    def check(self, enabled=False):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            P.SYNC.auto_update_local(self.root, enabled, advisory_only=not enabled)
        return out.getvalue()

    def legacy_functions(self):
        namespace = dict(vars(P.SYNC))
        source = P.ROOT / 'dev/fixtures/local-check-3aa3700.py'
        exec(compile(source.read_text(), str(source), 'exec'), namespace)
        return namespace

    def test_both_modes_failures_claim_before_request_and_retry_at_600_seconds(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.claim.unlink(missing_ok=True)
                start = self.now
                protected = {p: (self.root / p).read_bytes() for p in
                             ('latest.json', 'history.json', 'state/private.json', 'custom/personal.txt')}

                def fail(**kwargs):
                    self.assertEqual(json.loads(self.claim.read_bytes()), {'last_attempt_at': self.now.isoformat()})
                    self.assertEqual(P.SYNC._auto_update_state(self.state)['last_attempt'], self.now.date().isoformat())
                    raise RuntimeError('synthetic failed check')

                with mock.patch.object(P.SYNC, '_fetch_verified_release', side_effect=fail) as fetch:
                    self.assertIn('sync result retained', self.check(enabled))
                    claimed = self.claim.read_bytes(), self.claim.stat().st_mtime_ns
                    self.now = start + timedelta(seconds=599)
                    self.assertIn('not due', self.check(enabled))
                    self.assertEqual((self.claim.read_bytes(), self.claim.stat().st_mtime_ns), claimed)
                    self.assertEqual(fetch.call_count, 1)
                    self.now = start + timedelta(seconds=600)
                    self.assertIn('synthetic failed check', self.check(enabled))
                    self.assertEqual(fetch.call_count, 2)
                self.assertEqual({p: (self.root / p).read_bytes() for p in protected}, protected)

    def test_no_0400_gate_and_advisory_to_automatic_shares_one_claim(self):
        newer = B.release('2026.11.09', '11.109')
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=newer) as fetch:
            self.assertIn('available', self.check(False))
            self.assertEqual(P.SYNC._local_identity(self.root / 'section11')['tag'], self.release[2]['tag'])
            self.now += timedelta(seconds=599)
            self.assertIn('not due', self.check(True))
            self.now += timedelta(seconds=1)
            self.assertIn('installed', self.check(True))
            self.assertEqual(fetch.call_count, 2)
        self.assertEqual(P.SYNC._local_identity(self.root / 'section11')['tag'], newer[2]['tag'])
        self.assertEqual((self.root / 'latest.json').read_bytes(), b'last good data')

    def test_backward_clock_is_rebased_once_then_due_after_ten_minutes(self):
        for ahead in (timedelta(seconds=1), timedelta(days=36500)):
            with self.subTest(ahead=ahead):
                self.claim.write_text(json.dumps({'last_attempt_at': (self.now + ahead).isoformat()}))
                original = self.now
                with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=self.release) as fetch:
                    self.assertIn('not due', self.check())
                    self.assertEqual(json.loads(self.claim.read_bytes())['last_attempt_at'], original.isoformat())
                    self.now += timedelta(seconds=599)
                    self.check()
                    fetch.assert_not_called()
                    self.now += timedelta(seconds=1)
                    self.check()
                    fetch.assert_called_once()

    def test_malformed_legacy_or_new_record_preserves_all_files_and_stops(self):
        cases = [
            (self.legacy, b'{"last_attempt":"2026-02-30"}'),
            (self.legacy, b'{"last_attempt":"2026-11-09T01:00:00+00:00"}'),
            (self.legacy, b'{"unknown":1}'),
            (self.claim, b'not json'), (self.claim, b'[]'), (self.claim, b'{}'),
            (self.claim, b'{"last_attempt_at":false}'),
            (self.claim, b'{"last_attempt_at":"2026-11-09T01:00:00"}'),
            (self.claim, b'{"last_attempt_at":"2026-11-09T01:00:00+01:00"}'),
            (self.claim, b'{"last_attempt_at":"2026-02-30T01:00:00+00:00"}'),
            (self.claim, b'{"last_attempt_at":"bad","extra":1}'),
            (self.claim, b'{"last_attempt_at":"bad","last_attempt_at":"bad"}'),
        ]
        for path, raw in cases:
            for enabled in (False, True):
                with self.subTest(path=path.name, raw=raw, enabled=enabled):
                    self.legacy.unlink(missing_ok=True)
                    self.claim.unlink(missing_ok=True)
                    path.write_bytes(raw)
                    before = P.inventory(self.root)
                    with mock.patch.object(P.SYNC, '_fetch_verified_release') as fetch:
                        self.assertIn('stopped; sync result retained', self.check(enabled))
                        fetch.assert_not_called()
                    self.assertEqual(P.inventory(self.root), before)

    def test_old_format_including_same_day_and_future_dates_is_accepted(self):
        for day in (None, '2026-11-08', '2026-11-09', '2099-01-01'):
            with self.subTest(day=day):
                self.claim.unlink(missing_ok=True)
                old = {'skip_release': '2026.11.07'}
                if day:
                    old['last_attempt'] = day
                self.legacy.write_text(json.dumps(old))
                with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=self.release) as fetch:
                    self.check()
                    fetch.assert_called_once()
                self.assertEqual(P.SYNC._auto_update_state(self.state)['skip_release'], '2026.11.07')
                self.assertEqual(json.loads(self.claim.read_bytes())['last_attempt_at'], self.now.isoformat())

    def test_previous_release_reads_new_state_and_still_checks_next_day(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.claim.unlink(missing_ok=True)
                with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=self.release):
                    self.check(enabled)
                before = self.claim.read_bytes()
                old = self.legacy_functions()
                self.assertEqual(old['_auto_update_state'](self.state), P.SYNC._auto_update_state(self.state))
                fetch = mock.Mock(return_value=self.release)
                old['_fetch_verified_release'] = fetch
                with contextlib.redirect_stdout(io.StringIO()):
                    old['auto_update_local'](self.root, enabled, advisory_only=not enabled,
                                             started_at=self.now.replace(hour=12))
                    fetch.assert_not_called()
                    self.now += timedelta(days=1)
                    old['auto_update_local'](self.root, enabled, advisory_only=not enabled,
                                             started_at=self.now.replace(hour=12))
                    fetch.assert_called_once()
                self.assertEqual(self.claim.read_bytes(), before)
                with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=self.release) as new_fetch:
                    self.check(enabled)
                    new_fetch.assert_called_once()

    def test_previous_reader_rejects_timestamp_and_unknown_key_negative_controls(self):
        old = self.legacy_functions()
        for value in ({'last_attempt': self.now.isoformat()}, {'last_attempt_at': self.now.isoformat()}):
            self.legacy.write_text(json.dumps(value))
            with self.assertRaises(P.SYNC.DistributionError):
                old['_auto_update_state'](self.state)

    def test_rollback_retains_sidecar_and_skips_rejected_release(self):
        newer = B.release('2026.11.09', '11.109')
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=newer):
            self.check(True)
        before = self.claim.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(P.SYNC.do_rollback())
        self.assertEqual(self.claim.read_bytes(), before)
        old = self.legacy_functions()
        self.assertEqual(old['_auto_update_state'](self.state)['skip_release'], newer[2]['tag'])
        self.now += timedelta(minutes=10)
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=newer):
            self.assertIn('remains skipped', self.check(True))
        self.assertEqual(P.SYNC._local_identity(self.root / 'section11')['tag'], self.release[2]['tag'])

    def test_content_ahead_is_not_replaced(self):
        (self.root / 'section11/examples/sync.py').write_bytes(b'class IntervalsSync:\n    VERSION = "99.1"\n')
        before = P.inventory(self.root / 'section11')
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=self.release):
            self.assertIn('installed content is newer', self.check(True))
        self.assertEqual(P.inventory(self.root / 'section11'), before)

    def test_hosted_early_return_does_not_read_or_write_local_state(self):
        self.claim.write_bytes(b'malformed but hosted never reads this')
        before = P.inventory(self.root)
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), \
                mock.patch.object(P.SYNC, '_auto_update_state', side_effect=AssertionError('local state read')), \
                mock.patch.object(P.SYNC, '_fetch_verified_release') as fetch:
            self.check(False)
            self.check(True)
            fetch.assert_not_called()
        self.assertEqual(P.inventory(self.root), before)

    def test_advisory_entry_point_uses_shared_throttle(self):
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=self.release) as fetch, \
                contextlib.redirect_stdout(io.StringIO()):
            P.SYNC.notify_if_updates_available()
            self.now += timedelta(seconds=599)
            P.SYNC.notify_if_updates_available()
            self.assertEqual(fetch.call_count, 1)
            self.now += timedelta(seconds=1)
            P.SYNC.notify_if_updates_available()
            self.assertEqual(fetch.call_count, 2)

    def test_post_data_time_and_data_outcomes_survive_maintenance_failure(self):
        for outcome in (None, RuntimeError, P.SYNC.RequestBudgetRefused, P.SYNC.PublishOutcomeUnknown):
            with self.subTest(outcome=outcome):
                self.claim.unlink(missing_ok=True)
                started = self.now
                finished = started + timedelta(hours=3)
                producer = mock.Mock()
                producer._publication_uncertain = False

                def data_work(*args):
                    self.now = finished
                    (self.root / 'latest.json').write_bytes(b'completed data phase')
                    if outcome:
                        raise outcome('synthetic data outcome')

                def failed_check(**kwargs):
                    self.assertEqual((self.root / 'latest.json').read_bytes(), b'completed data phase')
                    self.assertEqual(json.loads(self.claim.read_bytes())['last_attempt_at'], finished.isoformat())
                    raise RuntimeError('synthetic maintenance outcome')

                argv = ['sync.py', '--athlete-id', 'synthetic', '--intervals-key', 'synthetic', '--output', str(self.root / 'latest.json')]
                with mock.patch.object(sys, 'argv', argv), \
                        mock.patch.object(P.SYNC, '_rotate_log_if_needed'), \
                        mock.patch.object(P.SYNC, 'IntervalsSync', return_value=producer), \
                        mock.patch.object(P.SYNC, '_run_sync', side_effect=data_work), \
                        mock.patch.object(P.SYNC, '_fetch_verified_release', side_effect=failed_check) as fetch, \
                        contextlib.redirect_stdout(io.StringIO()):
                    if outcome in (RuntimeError, P.SYNC.PublishOutcomeUnknown):
                        with self.assertRaisesRegex(outcome, 'synthetic data outcome'):
                            P.SYNC._main(installation_root=self.root, started_at=started)
                    else:
                        self.assertIsNone(P.SYNC._main(installation_root=self.root, started_at=started))
                self.assertEqual(fetch.call_count, 0 if outcome is P.SYNC.PublishOutcomeUnknown else 1)
                self.assertEqual(self.claim.exists(), outcome is not P.SYNC.PublishOutcomeUnknown)
                self.assertEqual((self.root / 'latest.json').read_bytes(), b'completed data phase')

    def test_explicit_status_and_update_ignore_recent_automatic_claim(self):
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=self.release):
            self.check()
        before = self.claim.read_bytes()
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=self.release) as fetch, \
                mock.patch('builtins.input', return_value='y'), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(P.SYNC.do_update(status_only=True))
            self.assertTrue(P.SYNC.do_update(timer_choice=False))
            self.assertEqual(fetch.call_count, 2)
        self.assertEqual(self.claim.read_bytes(), before)

    def test_both_modes_one_minute_timer_counts_real_release_request_paths(self):
        wire = ReleaseHTTP(0)
        wire.tags[0] = '2026.11.10'
        self.install_release((wire.raw[0], wire.files[0], wire.identity(0)))
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.claim.unlink(missing_ok=True)
                wire.calls.clear()
                with wire.intercepted():
                    for _ in range(60):
                        self.check(enabled)
                        self.now += timedelta(minutes=1)
                self.assertEqual(len(wire.calls), 15)
                self.assertEqual(sum(url.startswith(P.D.API + '/') for url in wire.calls), 13)

    def test_maximum_tag_and_redirect_paths_fit_the_hourly_api_ceiling(self):
        for depths, requests_per_check, api_per_check in (((3, 3), 14, 9), ((3, 4), 15, 10)):
            wire = BoundedReleaseHTTP(depths)
            self.install_release((wire.raw[0], wire.files[0], wire.identity(0)))
            for enabled in (False, True):
                with self.subTest(depths=depths, enabled=enabled):
                    self.claim.unlink(missing_ok=True)
                    wire.calls.clear()
                    with wire.intercepted():
                        for _ in range(60):
                            message = self.check(enabled)
                            if 'not due' not in message:
                                self.assertIn('unresolved release tag' if depths[1] == 4 else 'already current', message)
                            self.now += timedelta(minutes=1)
                    self.assertEqual(len(wire.calls), 39 if depths[1] == 3 else requests_per_check * 6)
                    api_count = sum(url.startswith(P.D.API + '/') for url in wire.calls)
                    self.assertEqual(api_count, 34 if depths[1] == 3 else api_per_check * 6)
                    self.assertLessEqual(api_count, 60)

    def wire_install(self):
        wire = MeteredReleaseHTTP()
        self.install_release((wire.raw[0], wire.files[0], wire.identity(0)))
        return wire

    def next_wire_check(self, wire, enabled=False):
        self.now += timedelta(minutes=10)
        wire.calls.clear()
        wire.bodies.clear()
        with wire.intercepted():
            return self.check(enabled)

    def assert_full_fetch(self, wire):
        self.assertEqual(sum('/releases/download/' in url for url in wire.calls), 1, wire.calls)
        self.assertEqual(sum(urlparse(url).hostname == 'raw.githubusercontent.com' for url in wire.calls), 1)
        self.assertEqual(sum(url.startswith(P.D.API + '/') for url in wire.calls), 3)

    def assert_reused(self, wire):
        self.assertEqual(len(wire.calls), 2, wire.calls)
        self.assertTrue(all(url.startswith(P.D.API + '/') for url in wire.calls))

    def test_current_reuse_has_no_asset_or_raw_download_for_both_modes(self):
        wire = self.wire_install()
        for enabled in (False, True):
            self.claim.unlink(missing_ok=True)
            first = self.next_wire_check(wire, enabled)
            self.assertIn('already current', first)
            self.assert_full_fetch(wire)
            self.assertEqual(json.loads(self.claim.read_bytes())['verified']['outcome'], 'current')
            self.assertEqual(self.next_wire_check(wire, enabled), first)
            self.assert_reused(wire)

    def test_new_tag_and_same_tag_new_commit_each_force_one_full_fetch(self):
        wire = self.wire_install()
        self.next_wire_check(wire)
        wire.tags[0] = '2026.11.11'
        self.assertIn('available', self.next_wire_check(wire))
        self.assert_full_fetch(wire)
        wire.commits[0] = 'c' * 40
        self.assertIn('available', self.next_wire_check(wire))
        self.assert_full_fetch(wire)
        self.assertEqual(json.loads(self.claim.read_bytes())['verified']['commit'], 'c' * 40)
        self.next_wire_check(wire)
        self.assert_reused(wire)

    def test_local_tree_change_forces_full_fetch_then_reuses_advisory_notice(self):
        wire = self.wire_install()
        self.next_wire_check(wire)
        (self.root / 'section11/LICENSE').write_bytes(b'local change')
        notice = self.next_wire_check(wire)
        self.assertIn('available', notice)
        self.assert_full_fetch(wire)
        data = {}
        P.SYNC._local_update_notice(data, self.root)
        self.assertEqual(data['update_notice'], P.SYNC.LOCAL_UPDATE_NOTICE)
        self.assertEqual(self.next_wire_check(wire), notice)
        self.assert_reused(wire)
        again = {}
        P.SYNC._local_update_notice(again, self.root)
        self.assertEqual(again, data)

    def test_install_after_cached_available_fetches_fresh_bytes_and_caches_result(self):
        wire = self.wire_install()
        wire.tags[0] = '2026.11.11'
        self.assertIn('available', self.next_wire_check(wire))
        self.assertIn('available', self.next_wire_check(wire))
        self.assert_reused(wire)
        with mock.patch.object(P.SYNC, '_install_local', wraps=P.SYNC._install_local) as install:
            self.assertIn('installed', self.next_wire_check(wire, True))
            install.assert_called_once()
        self.assert_full_fetch(wire)
        installed = P.SYNC._local_identity(self.root / 'section11')
        self.assertEqual({key: installed[key] for key in ('tag', 'commit', 'repository')},
                         {key: wire.identity(0)[key] for key in ('tag', 'commit', 'repository')})
        self.assertIn('already current', self.next_wire_check(wire, True))
        self.assert_reused(wire)

    def test_failed_full_fetch_clears_prior_verification_and_consumes_interval(self):
        wire = self.wire_install()
        self.next_wire_check(wire)
        wire.tags[0] = '2026.11.11'
        with mock.patch.object(wire, 'archive', return_value=b'corrupt archive'):
            self.assertIn('stopped; sync result retained', self.next_wire_check(wire))
        self.assertEqual(json.loads(self.claim.read_bytes()), {'last_attempt_at': self.now.isoformat()})
        count = len(wire.calls)
        with wire.intercepted():
            self.now += timedelta(seconds=599)
            self.assertIn('not due', self.check())
        self.assertEqual(len(wire.calls), count)
        self.assertIn('available', self.next_wire_check(wire))
        self.assert_full_fetch(wire)

    def test_failed_metadata_does_not_keep_verified_outcome(self):
        wire = self.wire_install()
        self.next_wire_check(wire)
        wire.failure = 429
        self.assertIn('stopped', self.next_wire_check(wire))
        self.assertEqual(json.loads(self.claim.read_bytes()), {'last_attempt_at': self.now.isoformat()})
        wire.failure = None
        self.next_wire_check(wire)
        self.assert_full_fetch(wire)

    def test_moved_installed_tag_is_fetched_then_refused_without_record(self):
        wire = self.wire_install()
        self.next_wire_check(wire)
        before = P.inventory(self.root / 'section11')
        wire.commits[0] = 'd' * 40
        self.assertIn('same-date changed release refused', self.next_wire_check(wire, True))
        self.assert_full_fetch(wire)
        self.assertNotIn('verified', json.loads(self.claim.read_bytes()))
        self.assertEqual(P.inventory(self.root / 'section11'), before)

    def test_failed_install_does_not_cache_available_as_install_authority(self):
        wire = self.wire_install()
        wire.tags[0] = '2026.11.11'
        self.next_wire_check(wire)
        with mock.patch.object(P.SYNC, '_install_local', side_effect=RuntimeError('synthetic install failure')):
            self.assertIn('synthetic install failure', self.next_wire_check(wire, True))
        self.assert_full_fetch(wire)
        self.assertNotIn('verified', json.loads(self.claim.read_bytes()))
        self.assertIn('installed', self.next_wire_check(wire, True))
        self.assert_full_fetch(wire)

    def test_data_changes_reuse_but_timer_plan_change_requires_verification(self):
        wire = self.wire_install()
        self.next_wire_check(wire)
        (self.root / 'latest.json').write_bytes(b'next data result')
        self.next_wire_check(wire)
        self.assert_reused(wire)
        original = P.SYNC.LocalTimers.plan

        def changed_timer(timer, *args, **kwargs):
            plan = original(timer, *args, **kwargs)
            plan['before']['resources']['synthetic-resource'] = 'changed'
            return plan

        with mock.patch.object(P.SYNC.LocalTimers, 'plan', changed_timer):
            self.assertIn('available', self.next_wire_check(wire))
            self.assert_full_fetch(wire)
            self.assertIn('available', self.next_wire_check(wire))
            self.assert_reused(wire)

    def test_root_tools_config_custom_and_new_release_names_invalidate_reuse(self):
        wire = self.wire_install()
        wire.files[0]['examples/new-tool.md'] = b'new official file\n'
        wire.raw[0] = P.manifest(wire.files[0])
        wire.tags[0] = '2026.11.11'
        self.assertIn('available', self.next_wire_check(wire))
        changes = [('sync.py', b'legacy root tool'), ('new-tool.md', b'stale same-name copy'),
                   ('.sync_config', b'{"auto_sync":false,"private_setting":"changed"}')]
        for name, content in changes:
            with self.subTest(name=name):
                P.write(self.root, {name: content})
                self.assertIn('available', self.next_wire_check(wire))
                self.assert_full_fetch(wire)
                self.next_wire_check(wire)
                self.assert_reused(wire)
        (self.root / 'custom/README.md').unlink()
        self.next_wire_check(wire)
        self.assert_full_fetch(wire)
        self.assertTrue((self.root / 'custom/README.md').is_file())
        self.assertNotIn('private_setting', self.claim.read_text())

    def test_skip_and_content_ahead_reuse_exact_outcome_without_install(self):
        wire = self.wire_install()
        for outcome in ('skipped', 'ahead'):
            if outcome == 'skipped':
                P.SYNC._write_install_state(self.state, 'auto-update.json', {'skip_release': wire.tags[0]})
            else:
                P.SYNC._write_install_state(self.state, 'auto-update.json', {})
                (self.root / 'section11/examples/sync.py').write_bytes(b'class IntervalsSync:\n    VERSION = "99.1"\n')
            with mock.patch.object(P.SYNC, '_install_local', side_effect=AssertionError('unexpected install')):
                first = self.next_wire_check(wire, True)
                self.assert_full_fetch(wire)
                self.assertEqual(json.loads(self.claim.read_bytes())['verified']['outcome'], outcome)
                self.assertEqual(self.next_wire_check(wire, True), first)
                self.assert_reused(wire)

    def test_malformed_verified_record_preserves_state_without_requests(self):
        wire = self.wire_install()
        self.next_wire_check(wire)
        valid = json.loads(self.claim.read_bytes())
        cases = [None, {}, dict(valid['verified'], extra=True)]
        for key, value in [('tag', 'bad'), ('commit', 'x' * 40), ('tree', None), ('context', ''),
                           ('outcome', 'installed'), ('basenames', ['../outside']), ('basenames', []),
                           ('basenames', ['sync.py', 'sync.py'])]:
            cases.append(dict(valid['verified'], **{key: value}))
        for record in cases:
            with self.subTest(record=record):
                self.claim.write_text(json.dumps(dict(valid, verified=record)))
                before = P.inventory(self.root)
                self.assertIn('stopped; sync result retained', self.next_wire_check(wire))
                self.assertEqual(wire.calls, [])
                self.assertEqual(P.inventory(self.root), before)

    def test_daily_request_and_body_byte_budget_steady_and_release_day(self):
        wire = self.wire_install()
        self.next_wire_check(wire)
        for release_day in (False, True):
            if release_day:
                wire.tags[0] = '2026.11.11'
            wire.calls.clear()
            wire.bodies.clear()
            with wire.intercepted():
                for _ in range(144):
                    self.now += timedelta(minutes=10)
                    self.assertNotIn('stopped', self.check(True))
            api = sum(url.startswith(P.D.API + '/') for url in wire.calls)
            payload = sum(size for url, size in wire.bodies if not url.startswith(P.D.API + '/'))
            self.assertEqual(api, 289 if release_day else 288)
            self.assertEqual(payload, len(wire.archive(0)) + len(wire.raw[0]) if release_day else 0)
            self.assertEqual(sum('/releases/download/' in url for url in wire.calls), int(release_day))
            print('CP5a synthetic daily bytes: release_day=' + str(release_day) +
                  ' API=' + str(api) + ' payload=' + str(payload) +
                  ' total_body=' + str(sum(size for _, size in wire.bodies)))

    def test_failed_http_checks_count_for_both_modes(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.claim.unlink(missing_ok=True)
                wire = ReleaseHTTP(0, failure=429)
                with wire.intercepted():
                    for _ in range(60):
                        self.check(enabled)
                        self.now += timedelta(minutes=1)
                self.assertEqual(len(wire.calls), 6)

    def test_shared_release_request_and_time_bounds_remain_enforced(self):
        with mock.patch.object(P.SYNC.requests, 'get', return_value=Response({})) as get:
            with P.SYNC._release_request_budget():
                for _ in range(40):
                    P.D.request(P.D.API + '/synthetic')
                with self.assertRaisesRegex(P.SYNC.DistributionError, 'request/time bound'):
                    P.D.request(P.D.API + '/synthetic')
                self.assertEqual(get.call_count, 40)
                self.assertTrue(all(call.kwargs['timeout'] <= 10 for call in get.call_args_list))
            self.assertIsNone(P.SYNC._RELEASE_REQUEST_BUDGET.get())
            with mock.patch('time.monotonic', side_effect=[100, 161]), P.SYNC._release_request_budget():
                with self.assertRaisesRegex(P.SYNC.DistributionError, 'request/time bound'):
                    P.D.request(P.D.API + '/synthetic')
            self.assertEqual(get.call_count, 40)


if __name__ == '__main__':
    import unittest
    unittest.main()
