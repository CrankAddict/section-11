"""Round-two acceptance regressions adapted from independent R01-R10 probes."""
import contextlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from unittest import mock

import test_update_prototype as P
import test_b2_hosted as B
import hosted


class Noon(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 31, 12, tzinfo=timezone.utc)


class FixRound2(P.Offline):
    def setUp(self):
        super().setUp()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        for patch in (
            mock.patch.object(P.SYNC.Path, 'cwd', return_value=self.root),
            mock.patch.object(P.SYNC, '__file__', str(self.root / 'section11/examples/sync.py')),
            mock.patch.object(P.SYNC, 'datetime', Noon),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('audit network forbidden')),
            mock.patch('subprocess.run', side_effect=AssertionError('audit real subprocess forbidden')),
        ):
            self.stack.enter_context(patch)

    def install(self, release):
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release), \
                mock.patch('builtins.input', return_value='y'), contextlib.redirect_stdout(io.StringIO()) as log:
            self.assertTrue(P.SYNC.do_update(timer_choice=False), log.getvalue())

    def hosted_install(self, release):
        remote = B.Remote({'latest.json': b'{}'})
        publisher = B.DirectPublisher(remote)
        updater = B.H.HostedUpdater(publisher, lambda: release, {})
        updater.install(publisher.snapshot(), accepted=True)
        return remote, publisher, updater

    def test_R01_valid_edited_manifest_gets_local_and_hosted_repair(self):
        release = B.release()
        self.install(release)
        target = self.root / 'section11/manifest.json'
        edited = b' \n' + release[0]
        target.write_bytes(edited)
        self.assertIsNone(P.SYNC._local_identity(target.parent))
        self.assertTrue(P.SYNC._converted_installation(self.root))
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release):
            P.SYNC.auto_update_local(self.root, True)
        self.assertEqual(target.read_bytes(), release[0])
        notice = {}
        P.SYNC._local_update_notice(notice, self.root)
        self.assertNotIn('update_notice', notice)
        remote, publisher, updater = self.hosted_install(release)
        remote.tip = remote.commit({'section11/manifest.json': edited}, [remote.tip], 'Synthetic metadata edit')
        updater.env = {'SECTION11_AUTO_UPDATE': 'true'}
        updater.maintain(publisher.snapshot(), '2026.10.31', True)
        self.assertEqual(remote.inventory()['section11/manifest.json'], release[0])
        self.install(release)
        self.assertEqual(target.read_bytes(), release[0])

    def test_R02_recreated_custom_guidance_uses_verified_release(self):
        release = B.release()
        self.install(release)
        guide = self.root / 'section11/examples/maintenance/CUSTOM_README.md'
        guide.write_bytes(b'personal altered managed guidance')
        (self.root / 'custom/README.md').unlink()
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release):
            P.SYNC.auto_update_local(self.root, True)
        self.assertEqual(guide.read_bytes(), release[1]['examples/maintenance/CUSTOM_README.md'])
        self.assertEqual((self.root / 'custom/README.md').read_bytes(), release[1]['examples/maintenance/CUSTOM_README.md'])

    def test_R03_missing_both_guides_claims_once_and_repairs(self):
        release = B.release()
        self.install(release)
        guide = self.root / 'section11/examples/maintenance/CUSTOM_README.md'
        guide.unlink()
        (self.root / 'custom/README.md').unlink()
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release) as fetch:
            P.SYNC.auto_update_local(self.root, True)
            P.SYNC.auto_update_local(self.root, True)
        fetch.assert_called_once()
        self.assertEqual(P.SYNC._auto_update_state(self.root / '.section11-state')['last_attempt'], '2026-10-31')
        self.assertEqual(guide.read_bytes(), release[1]['examples/maintenance/CUSTOM_README.md'])
        self.install(release)
        self.assertEqual((self.root / 'custom/README.md').read_bytes(), release[1]['examples/maintenance/CUSTOM_README.md'])


    def invoke_main(self, credentials=True, fail=None):
        args = ['sync.py', '--output', str(self.root / 'latest.json')]
        if credentials:
            args += ['--athlete-id', 'synthetic', '--intervals-key', 'synthetic']
        instance = mock.Mock()
        instance.request_budget.degraded = True
        exists = os.path.exists
        with mock.patch.object(sys, 'argv', args), \
                mock.patch.object(P.SYNC.os.path, 'exists', side_effect=lambda p: False if p == '.sync_config.json' else exists(p)), \
                mock.patch.object(P.SYNC, '_rotate_log_if_needed'), \
                mock.patch.object(P.SYNC, 'IntervalsSync', return_value=instance), \
                mock.patch.object(P.SYNC, '_run_sync', side_effect=fail, return_value=False), \
                mock.patch.object(P.SYNC, 'auto_update_local') as hook, \
                contextlib.redirect_stdout(io.StringIO()):
            if fail:
                with self.assertRaises(type(fail)):
                    P.SYNC._main(installation_root=self.root, distribution_locked=True)
            else:
                P.SYNC._main(installation_root=self.root, distribution_locked=True)
        return hook

    def test_R05_missing_credentials_reaches_post_data_maintenance(self):
        self.invoke_main(credentials=False).assert_called_once()
        self.invoke_main(fail=RuntimeError('synthetic data failure')).assert_called_once()
        info = {'base': 'a' * 40, 'run_sync': True, 'published': False,
                'created_at': '2026-10-31T04:10:00Z', 'event': 'workflow_dispatch',
                'attempt': 1, 'scheduled': False, 'source_is_latest': False}
        pub, controller = mock.Mock(), mock.Mock()
        controller.maintain.return_value = ({'commit': 'b' * 40}, None)
        with mock.patch.object(hosted, 'context', return_value=info), \
                mock.patch.object(hosted, 'publisher', return_value=pub), \
                mock.patch.object(hosted.update, 'HostedUpdater', return_value=controller):
            hosted.maintain()
        controller.maintain.assert_called_once()

    def test_R06_uncertain_data_publication_holds_both_adapters(self):
        self.invoke_main(fail=P.SYNC.PublishOutcomeUnknown('synthetic unknown data result')).assert_not_called()
        info = {'publication_uncertain': True, 'published': False}
        with mock.patch.object(hosted, 'context', return_value=info), \
                mock.patch.object(hosted, 'publisher') as pub, \
                self.assertRaisesRegex(hosted.UnknownOutcome, 'reconciliation'):
            hosted.maintain()
        pub.assert_not_called()

    def test_R07_bad_auto_policy_does_not_block_explicit_update(self):
        release = B.release()
        self.install(release)
        (self.root / '.sync_config.json').write_text('{"auto_sync":false,"auto_update":"bad"}')
        self.install(release)
        remote, publisher, updater = self.hosted_install(release)
        tip = remote.tip
        updater.env = {'SECTION11_AUTO_UPDATE': 'bad'}
        updater.install(publisher.snapshot(), accepted=True)
        self.assertEqual(remote.tip, tip)
        updater.env = {'SECTION11_AUTO_UPDATE': 'false'}
        updater.install(publisher.snapshot(), accepted=True)

    def test_R08_custom_only_reinstall_preserves_both_previous_installations(self):
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        self.install(old)
        self.install(new)
        (self.root / 'custom/README.md').unlink()
        self.install(new)
        self.assertTrue(P.SYNC.do_rollback())
        self.assertEqual(P.SYNC._local_identity(self.root / 'section11')['tag'], '2026.10.28')
        remote, publisher, updater = self.hosted_install(old)
        updater = B.H.HostedUpdater(publisher, lambda: new, {})
        updater.install(publisher.snapshot(), accepted=True)
        remote.tip = remote.commit({'custom/README.md': None}, [remote.tip], 'Synthetic missing guidance')
        updater.install(publisher.snapshot(), accepted=True)
        updater.rollback(publisher.snapshot())
        self.assertEqual(B.H.installed_identity(publisher, publisher.snapshot())['tag'], '2026.10.28')

    def test_R09_failed_discovery_retains_verified_outstanding_notices(self):
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        self.install(old)
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=new):
            P.SYNC.auto_update_local(self.root, False, advisory_only=True)
        before = {}
        P.SYNC._local_update_notice(before, self.root)
        self.assertIn('update_notice', before)
        saved = P.SYNC._auto_update_state(self.root / '.section11-state')
        saved['last_attempt'] = '2026-10-30'
        P.SYNC._write_install_state(self.root / '.section11-state', 'auto-update.json', saved)
        with mock.patch.object(P.SYNC, '_fetch_verified_release', side_effect=ValueError('synthetic release outage')):
            P.SYNC.auto_update_local(self.root, False, advisory_only=True)
        after = {}
        P.SYNC._local_update_notice(after, self.root)
        self.assertIn('update_notice', after)
        remote, publisher, updater = self.hosted_install(old)
        updater = B.H.HostedUpdater(publisher, lambda: new, {})
        updater.maintain(publisher.snapshot(), '2026.10.30', True)
        failed = B.H.HostedUpdater(publisher, mock.Mock(side_effect=ValueError('synthetic release outage')), {})
        with self.assertRaisesRegex(ValueError, 'synthetic release outage'):
            failed.maintain(publisher.snapshot(), '2026.10.31', True)
        state = failed.state(publisher.snapshot())
        self.assertEqual(state['available_date'], new[2]['tag'])
        self.assertEqual(state['available_tree'], B.H.installation_digest(publisher.snapshot()))

    def test_R10_local_claim_uses_post_data_time_legacy_hosted_keeps_threshold(self):
        release = B.release()
        self.install(release)
        class CrossingClock(Noon):
            clock_hour = 3
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 31, cls.clock_hour, 59 if cls.clock_hour == 3 else 1, tzinfo=timezone.utc)
        instance = mock.Mock()
        instance.request_budget.degraded = True
        def data_work(*args):
            self.assertEqual(CrossingClock.now().hour, 3)
            CrossingClock.clock_hour = 4
            return True
        exists = os.path.exists
        with mock.patch.object(P.SYNC, 'datetime', CrossingClock), \
                mock.patch.object(sys, 'argv', ['sync.py', '--athlete-id', 'synthetic',
                                               '--intervals-key', 'synthetic', '--output', str(self.root / 'latest.json')]), \
                mock.patch.object(P.SYNC.os.path, 'exists', side_effect=lambda p: False if p == '.sync_config.json' else exists(p)), \
                mock.patch.object(P.SYNC, '_rotate_log_if_needed'), \
                mock.patch.object(P.SYNC, 'IntervalsSync', return_value=instance), \
                mock.patch.object(P.SYNC, '_run_sync', side_effect=data_work), \
                mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release) as fetch, \
                contextlib.redirect_stdout(io.StringIO()):
            P.SYNC._main(installation_root=self.root, distribution_locked=True)
        fetch.assert_called_once()
        self.assertEqual(json.loads((self.root / '.section11-state/local-check.json').read_bytes())['last_attempt_at'],
                         '2026-10-31T04:01:00+00:00')
        self.assertIsNone(B.H.eligible_day('2026-10-31T03:59:00Z', 'workflow_dispatch', True))
        self.assertEqual(B.H.eligible_day('2026-10-31T04:00:00Z', 'workflow_dispatch', True), '2026.10.31')

    def test_N01_half_mode_detects_manifest_and_receipt_bytes_then_clears_after_repair(self):
        release = B.release()
        self.install(release)
        for day, name in enumerate(('manifest.json', P.D.RECEIPT), 1):
            with self.subTest(name=name):
                target = self.root / 'section11' / name
                original = target.read_bytes()
                target.write_bytes(b' \n' + original)
                with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release):
                    P.SYNC.auto_update_local(self.root, False, advisory_only=True,
                                            started_at=Noon(2026, 11, day, 12, tzinfo=timezone.utc))
                self.assertEqual(target.read_bytes(), b' \n' + original)
                notice = {}
                P.SYNC._local_update_notice(notice, self.root)
                self.assertIn('update_notice', notice)
                self.install(release)
                self.assertEqual(target.read_bytes(), original)
                P.SYNC._local_update_notice(notice, self.root)
                self.assertNotIn('update_notice', notice)

    def test_N02_existing_personal_guidance_survives_verified_managed_repair(self):
        release = B.release()
        self.install(release)
        personal = self.root / 'custom/README.md'
        personal.write_bytes(b'personal custom guide')
        managed = self.root / 'section11/examples/maintenance/CUSTOM_README.md'
        managed.write_bytes(b'edited managed guide')
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release):
            P.SYNC.auto_update_local(self.root, True)
        self.assertEqual(personal.read_bytes(), b'personal custom guide')
        self.assertEqual(managed.read_bytes(), release[1]['examples/maintenance/CUSTOM_README.md'])

    def test_N03_local_claim_precedes_failed_guidance_and_discovery_without_retry(self):
        release = B.release()
        self.install(release)
        (self.root / 'custom/README.md').unlink()
        def fail_guidance(*args):
            saved = P.SYNC._auto_update_state(self.root / '.section11-state')
            self.assertEqual(saved['last_attempt'], '2026-10-31')
            raise ValueError('synthetic guidance failure')
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release) as fetch, \
                mock.patch.object(P.SYNC, '_ensure_custom', side_effect=fail_guidance) as repair:
            P.SYNC.auto_update_local(self.root, True)
            P.SYNC.auto_update_local(self.root, True)
        fetch.assert_called_once()
        repair.assert_called_once()
        with mock.patch.object(P.SYNC, '_fetch_verified_release', side_effect=ValueError('synthetic outage')) as fetch:
            for _ in range(2):
                P.SYNC.auto_update_local(self.root, True, started_at=Noon(2026, 11, 1, 12, tzinfo=timezone.utc))
        fetch.assert_called_once()
        self.assertEqual(P.SYNC._auto_update_state(self.root / '.section11-state')['last_attempt'], '2026-11-01')
        self.assertFalse((self.root / 'custom/README.md').exists())

    def test_N03_hosted_claim_precedes_failed_guidance_without_retry(self):
        release = B.release()
        remote, publisher, updater = self.hosted_install(release)
        remote.tip = remote.commit({'custom/README.md': None}, [remote.tip], 'Synthetic absent guide')
        publish = publisher.publish
        repairs = []
        def fail_guidance(before, expected, message, validator):
            if set(expected) == {'custom/README.md'}:
                self.assertEqual(updater.state(publisher.snapshot())['attempted_day'], '2026.10.31')
                repairs.append(expected)
                raise ValueError('synthetic guidance failure')
            return publish(before, expected, message, validator)
        with mock.patch.object(publisher, 'publish', side_effect=fail_guidance):
            with self.assertRaisesRegex(ValueError, 'synthetic guidance failure'):
                updater.maintain(publisher.snapshot(), '2026.10.31', False)
            updater.maintain(publisher.snapshot(), '2026.10.31', False)
        self.assertEqual(repairs, [{'custom/README.md': release[1]['examples/maintenance/CUSTOM_README.md']}])
        self.assertNotIn('custom/README.md', remote.inventory())

    def test_N05_missing_credentials_really_claims_but_suppression_and_history_do_not(self):
        release = B.release()
        self.install(release)
        for flag in ('--no-auto-update', '--generate-history', None):
            args = ['sync.py', '--output', str(self.root / 'latest.json')]
            if flag:
                args.append(flag)
            with mock.patch.object(sys, 'argv', args), \
                    mock.patch.object(P.SYNC, '_rotate_log_if_needed'), \
                    mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release) as fetch, \
                    contextlib.redirect_stdout(io.StringIO()):
                P.SYNC._main(installation_root=self.root)
            self.assertEqual(fetch.call_count, 0 if flag else 1)
        self.assertEqual(P.SYNC._auto_update_state(self.root / '.section11-state')['last_attempt'], '2026-10-31')

    def test_N06_companion_unknown_reaches_outer_hold_and_is_never_retried(self):
        for path in ('history.json', 'intervals.json', 'routes.json', 'saved_workouts.json'):
            for unknown in (True, False):
                with self.subTest(path=path, unknown=unknown):
                    producer = mock.Mock()
                    producer.request_budget.degraded = True
                    producer.should_generate_history.return_value = path == 'history.json'
                    producer.generate_history.return_value = {}
                    producer.collect_training_data.return_value = {}
                    producer.data_dir = self.root
                    producer.INTERVALS_FILE, producer.ROUTES_FILE = 'intervals.json', 'routes.json'
                    producer._intervals_data = {'activities': []} if path == 'intervals.json' else None
                    producer._routes_data = {'events': []} if path == 'routes.json' else None
                    producer._saved_workouts_data = {} if path == 'saved_workouts.json' else None
                    attempted = []
                    def publish(data, filepath='latest.json', **kwargs):
                        attempted.append(filepath)
                        if filepath == path:
                            error = P.SYNC.PublishOutcomeUnknown if unknown else RuntimeError
                            raise error('synthetic data result')
                        return 'https://example.invalid/fictional'
                    producer.publish_to_github.side_effect = publish
                    args = ['sync.py', '--athlete-id', 'synthetic', '--intervals-key', 'synthetic',
                            '--github-token', 'synthetic', '--github-repo', 'example/data']
                    with mock.patch.object(sys, 'argv', args), \
                            mock.patch.object(P.SYNC, 'IntervalsSync', return_value=producer), \
                            mock.patch.object(P.SYNC, '_rotate_log_if_needed'), \
                            mock.patch.object(P.SYNC, 'auto_update_local') as hook, \
                            contextlib.redirect_stdout(io.StringIO()):
                        P.SYNC._main(installation_root=self.root)
                    self.assertEqual(attempted.count(path), 1)
                    self.assertEqual(hook.call_count, 0 if unknown else 1)
                    self.assertIs(producer._publication_uncertain, unknown)

    def test_N07_bad_automatic_preference_allows_first_acceptance_but_claims_failed_auto_day(self):
        release = B.release()
        remote = B.Remote({'latest.json': b'{}'})
        publisher = B.DirectPublisher(remote)
        fetch = mock.Mock(return_value=release)
        updater = B.H.HostedUpdater(publisher, fetch, {'SECTION11_AUTO_UPDATE': 'bad'})
        updater.install(publisher.snapshot(), accepted=True)
        self.assertEqual(B.H.installed_identity(publisher, publisher.snapshot())['tag'], release[2]['tag'])
        with self.assertRaisesRegex(ValueError, 'automatic update setting'):
            updater.maintain(publisher.snapshot(), '2026.10.31', False)
        updater.maintain(publisher.snapshot(), '2026.10.31', False)
        self.assertEqual(updater.state(publisher.snapshot())['attempted_day'], '2026.10.31')
        fetch.assert_called_once()

    def test_N08_automatic_custom_only_repair_preserves_previous_slot(self):
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        self.install(old)
        self.install(new)
        state = self.root / '.section11-state'
        before = (state / 'previous.json').read_bytes()
        (self.root / 'custom/README.md').unlink()
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=new):
            P.SYNC.auto_update_local(self.root, True)
        self.assertEqual((state / 'previous.json').read_bytes(), before)
        self.assertEqual((self.root / 'custom/README.md').read_bytes(), new[1]['examples/maintenance/CUSTOM_README.md'])
        self.assertTrue(P.SYNC.do_rollback())
        self.assertEqual(P.SYNC._local_identity(self.root / 'section11')['tag'], old[2]['tag'])

    def test_N09_changed_preimage_or_suppression_clears_notice_even_when_discovery_fails(self):
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        self.install(old)
        for index, change in enumerate(('tree', 'root', 'suppression')):
            with self.subTest(change=change):
                with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=new):
                    P.SYNC.auto_update_local(self.root, False, advisory_only=True,
                                            started_at=Noon(2026, 11, index * 2 + 1, 12, tzinfo=timezone.utc))
                saved = P.SYNC._auto_update_state(self.root / '.section11-state')
                self.assertEqual(saved['available_release'], new[2]['tag'])
                if change == 'tree':
                    (self.root / 'section11/LICENSE').write_bytes(b'new personal edit')
                elif change == 'root':
                    (self.root / 'sync.py').write_bytes(b'reappeared root tool')
                else:
                    saved['skip_release'] = new[2]['tag']
                    P.SYNC._write_install_state(self.root / '.section11-state', 'auto-update.json', saved)
                with mock.patch.object(P.SYNC, '_fetch_verified_release', side_effect=ValueError('synthetic outage')):
                    P.SYNC.auto_update_local(self.root, False, advisory_only=True,
                                            started_at=Noon(2026, 11, index * 2 + 2, 12, tzinfo=timezone.utc))
                notice = {}
                P.SYNC._local_update_notice(notice, self.root)
                self.assertNotIn('update_notice', notice)
                self.assertNotIn('available_release', P.SYNC._auto_update_state(self.root / '.section11-state'))

    def test_N10_legacy_hosted_keeps_original_day_local_uses_check_start(self):
        release = B.release()
        self.install(release)
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release), \
                mock.patch.object(sys, 'argv', ['sync.py', '--output', str(self.root / 'latest.json')]), \
                mock.patch.object(P.SYNC, '_rotate_log_if_needed'):
            P.SYNC._main(installation_root=self.root,
                         started_at=Noon(2026, 10, 30, 23, 59, tzinfo=timezone.utc))
        self.assertEqual(P.SYNC._auto_update_state(self.root / '.section11-state')['last_attempt'], '2026-10-31')
        self.assertEqual(json.loads((self.root / '.section11-state/local-check.json').read_bytes())['last_attempt_at'],
                         '2026-10-31T12:00:00+00:00')
        self.assertEqual(B.H.eligible_day('2026-10-30T23:59:00Z', 'workflow_dispatch', False), '2026.10.30')


    def test_N09_failed_full_install_keeps_verified_plan_for_unchanged_preimage(self):
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        self.install(old)
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=new), \
                mock.patch.object(P.SYNC, '_install_local', side_effect=ValueError('synthetic pre-activation failure')):
            P.SYNC.auto_update_local(self.root, True)
        notice = {}
        P.SYNC._local_update_notice(notice, self.root)
        self.assertIn('update_notice', notice)
        self.assertEqual(P.SYNC._local_identity(self.root / 'section11')['tag'], old[2]['tag'])
