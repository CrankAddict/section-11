"""Owner-approved regressions derived from all twelve undecided-audit probes."""
import contextlib
import io
import json
import os
from datetime import datetime, timezone
from unittest import mock

import test_update_prototype as P
import test_b2_hosted as B
import hosted
import publish_release
from github_api import APIError


class Noon(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 31, 12, tzinfo=timezone.utc)


class FixRound(P.Offline):
    def setUp(self):
        super().setUp()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(P.SYNC.Path, 'cwd', return_value=self.root))
        self.stack.enter_context(mock.patch.object(P.SYNC, '__file__', str(self.root / 'section11/examples/sync.py')))
        self.stack.enter_context(mock.patch.object(P.SYNC, 'datetime', Noon))
        self.stack.enter_context(mock.patch.dict(os.environ, {'GITHUB_ACTIONS': ''}))
        self.stack.enter_context(mock.patch('urllib.request.OpenerDirector.open',
                                           side_effect=AssertionError('network prohibited')))
        self.stack.enter_context(mock.patch('subprocess.run', side_effect=AssertionError('real subprocess prohibited')))

    def local_install(self, release, choice=False):
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release), \
                mock.patch('builtins.input', return_value='y'), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertTrue(P.SYNC.do_update(timer_choice=choice), output.getvalue())

    def hosted_pair(self, edited=False):
        remote = B.Remote({'latest.json': b'{}'})
        publisher = B.DirectPublisher(remote)
        old = B.release('2026.10.28', '11.101')
        new = B.release('2026.10.29', '11.102')
        B.H.HostedUpdater(publisher, lambda: old, {}).install(publisher.snapshot(), accepted=True)
        if edited:
            remote.tip = remote.commit({'section11/LICENSE': b'personal pre-update edit',
                                        'section11/personal.txt': b'extra'}, [remote.tip], 'Owner edit')
        updater = B.H.HostedUpdater(publisher, lambda: new, {})
        updater.install(publisher.snapshot(), accepted=True)
        return remote, publisher, updater

    def test_01_unchanged_reinstall_preserves_previous_on_both_platforms(self):
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        self.local_install(old)
        self.local_install(new)
        previous = (self.root / '.section11-state/previous.json').read_bytes()
        self.local_install(new)
        self.assertEqual((self.root / '.section11-state/previous.json').read_bytes(), previous)
        self.assertTrue(P.SYNC.do_rollback())
        self.assertEqual(P.SYNC._local_identity(self.root / 'section11')['tag'], '2026.10.28')
        remote, publisher, updater = self.hosted_pair()
        before = remote.tip
        updater.install(publisher.snapshot(), accepted=True)
        self.assertEqual(remote.tip, before)
        updater.rollback(publisher.snapshot())
        self.assertEqual(B.H.installed_identity(publisher, publisher.snapshot())['tag'], '2026.10.28')

    def test_02_edited_manifest_remains_converted_and_full_mode_repairs(self):
        release = B.release('2026.10.28', '11.101')
        self.local_install(release)
        root = self.root / 'section11'
        (root / 'LICENSE').write_bytes(b'personal edit')
        self.assertTrue(P.SYNC._converted_installation(self.root))
        (root / 'manifest.json').write_bytes(b'{"edited":true}')
        self.assertTrue(P.SYNC._converted_installation(self.root))
        data = {}
        P.SYNC._installation_notice(data, self.root)
        self.assertNotIn('installation_notice', data)
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release) as fetch:
            P.SYNC.auto_update_local(self.root, True)
        fetch.assert_called_once()
        self.assertEqual((root / 'manifest.json').read_bytes(), release[0])

    def test_03_output_subfolder_uses_actual_installation_and_running_entry(self):
        self.local_install(B.release())
        for output in (self.root, self.root / 'exports'):
            data = {}
            P.SYNC._installation_notice(data, output)
            self.assertNotIn('installation_notice', data)
        with mock.patch.object(P.SYNC, '__file__', str(self.root / 'sync.py')):
            data = {}
            P.SYNC._installation_notice(data, self.root / 'exports')
            self.assertIn('installation_notice', data)

    def test_04_hosted_rollback_is_independent_of_unrelated_history_length(self):
        for count in (99, 100, 1001):
            remote, publisher, updater = self.hosted_pair()
            for i in range(count):
                remote.tip = remote.commit({'latest.json': str(i).encode()}, [remote.tip], 'Data sync')
            remote.calls.clear()
            updater.rollback(publisher.snapshot())
            self.assertEqual(remote.inventory()['latest.json'], str(count - 1).encode())
            self.assertEqual(B.H.installed_identity(publisher, publisher.snapshot())['tag'], '2026.10.28')
            queries = [c[1] for c in remote.calls if c[1].startswith('/commits?')]
            self.assertEqual(len(queries), 4)
            self.assertTrue(all('&path=' in p and '&per_page=1' in p for p in queries))

    def test_05_previous_personal_edits_and_extras_restore_both_platforms(self):
        self.local_install(B.release('2026.10.28', '11.101'))
        (self.root / 'section11/LICENSE').write_bytes(b'personal pre-update edit')
        (self.root / 'section11/personal.txt').write_bytes(b'extra')
        self.local_install(B.release('2026.10.29', '11.102'))
        self.assertTrue(P.SYNC.do_rollback())
        remote, publisher, updater = self.hosted_pair(edited=True)
        updater.rollback(publisher.snapshot())
        for name in ('LICENSE', 'personal.txt'):
            self.assertEqual(remote.inventory()['section11/' + name],
                             (self.root / 'section11' / name).read_bytes())

    def test_prior_executable_file_mode_is_restored_exactly(self):
        remote = B.Remote({'latest.json': b'{}'})
        publisher = B.DirectPublisher(remote)
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        B.H.HostedUpdater(publisher, lambda: old, {}).install(publisher.snapshot(), accepted=True)
        expected = {'section11/personal.sh': b'#!/bin/sh\\nexit 0\\n'}
        publisher.publish(publisher.snapshot(), expected, 'Owner script',
                          B.H.exact_validator(expected), modes={'section11/personal.sh': '100755'})
        prior = B.H.installation_paths(publisher.snapshot())
        updater = B.H.HostedUpdater(publisher, lambda: new, {})
        updater.install(publisher.snapshot(), accepted=True)
        updater.rollback(publisher.snapshot())
        self.assertEqual(B.H.installation_paths(publisher.snapshot()), prior)

    def test_bad_maintenance_setting_claims_day_before_failing(self):
        self.local_install(B.release('2026.10.28', '11.101'))
        with mock.patch.object(P.SYNC, '_fetch_verified_release') as fetch:
            P.SYNC.auto_update_local(self.root, 'invalid')
            self.assertEqual(P.SYNC._auto_update_state(self.root / '.section11-state')['last_attempt'],
                             '2026-10-31')
            P.SYNC.auto_update_local(self.root, 'invalid')
            fetch.assert_not_called()
        remote, publisher, updater = self.hosted_pair()
        updater.env = {'SECTION11_AUTO_UPDATE': 'invalid'}
        with self.assertRaises(ValueError):
            updater.maintain(publisher.snapshot(), '2026.10.31', False)
        claimed = remote.tip
        updater.maintain(publisher.snapshot(), '2026.10.31', False, run_attempt=2)
        self.assertEqual(remote.tip, claimed)

    def test_06_rerun_claims_only_an_unclaimed_day_even_after_data_failure(self):
        for success in (True, False):
            self.assertEqual(B.H.eligible_day('2026-10-31T04:00:00Z', 'schedule', success, 2), '2026.10.31')
        remote, publisher, updater = self.hosted_pair()
        updater.maintain(publisher.snapshot(), '2026.10.31', False, run_attempt=2)
        self.assertEqual(updater.state(publisher.snapshot())['attempted_day'], '2026.10.31')
        with mock.patch.object(updater, 'latest', side_effect=AssertionError('duplicate discovery')):
            updater.maintain(publisher.snapshot(), '2026.10.31', True, run_attempt=3)

    def test_07_failed_data_uses_daily_rule_without_inventing_success(self):
        for run_sync in (True,):
            info = {'base': 'a' * 40, 'run_sync': run_sync, 'published': False,
                    'created_at': '2026-10-31T04:07:00Z', 'event': 'schedule',
                    'attempt': 2, 'scheduled': True, 'source_is_latest': False}
            pub, controller = mock.Mock(), mock.Mock()
            controller.maintain.return_value = ({'commit': 'b' * 40}, None)
            with mock.patch.object(hosted, 'context', return_value=info), \
                    mock.patch.object(hosted, 'publisher', return_value=pub), \
                    mock.patch.object(hosted.update, 'HostedUpdater', return_value=controller):
                hosted.maintain()
            controller.maintain.assert_called_once_with(pub.snapshot.return_value, '2026.10.31', False, run_attempt=2)

    def test_08_same_date_verified_repair_notice_reaches_json_and_clears(self):
        release = B.release()
        self.local_install(release)
        (self.root / 'section11/LICENSE').write_bytes(b'edited')
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release):
            P.SYNC.auto_update_local(self.root, False, advisory_only=True)
        data = {}
        P.SYNC._local_update_notice(data, self.root)
        self.assertEqual(data['update_notice'], P.SYNC.LOCAL_UPDATE_NOTICE)
        P.SYNC._local_update_notice(data, self.root, suppressed=True)
        self.assertNotIn('update_notice', data)
        self.local_install(release)
        P.SYNC._local_update_notice(data, self.root)
        self.assertNotIn('update_notice', data)
        latest = self.root / 'latest.json'
        latest.write_bytes(b'{}')
        info = {'run_sync': True, 'available_date': '2026.10.30',
                'source_identity': {'tag': '2026.10.30'}}
        with mock.patch.object(hosted, 'context', return_value=info), \
                mock.patch.dict(os.environ, {'GITHUB_WORKSPACE': str(self.root)}):
            hosted.finalize_export()
            self.assertEqual(json.loads(latest.read_bytes())['update_notice'], B.H.NOTICE)
            info['available_date'] = None
            hosted.finalize_export()
            self.assertNotIn('update_notice', json.loads(latest.read_bytes()))



    def test_11_fresh_readme_has_link_timestamp_and_personal_readme_is_preserved(self):
        result = hosted.readme(None, P.ROOT, '2026-10-31 05:00:00 UTC', 'example/data', 'main')
        self.assertIn(b'Sync Now', result)
        self.assertIn(b'Last successful sync:** 2026-10-31 05:00:00 UTC', result)
        generic = b'# personal training notes\n'
        self.assertEqual(hosted.readme(generic, P.ROOT, 'now', 'example/data', 'main'), generic)
        for guide in ('json-auto-sync', 'json-on-demand'):
            text = (P.ROOT / 'examples' / guide / 'SETUP.md').read_text()
            self.assertIn('Leave **Add a README file** unchecked', text)

    def test_12_publisher_discovery_reads_only_one_page_and_two_date_prefixes(self):
        from _release_fakes import ReleaseAPI
        raw, files, identity = B.release()
        for count in (0, 1):
            api = ReleaseAPI()
            if count:
                api.seed('2026.10.30', 'a' * 40, raw, files)
                self.assertEqual(publish_release.publish(api, 'c' * 40, raw, files, '2026.10.31'), 'unchanged')
            else:
                with mock.patch.object(publish_release, 'build', side_effect=ValueError('reached build')), \
                        self.assertRaisesRegex(ValueError, 'reached build'):
                    publish_release.publish(api, 'c' * 40, raw, files, '2026.10.31')
            self.assertEqual([c[1] for c in api.calls if c[0] == 'PAGES'],
                             [])
            self.assertEqual([c[1] for c in api.calls if c[0] == 'GET' and '?' in c[1]],
                             ['/releases?per_page=100&page=1',
                              '/git/matching-refs/tags/2026.10.31?per_page=100&page=1',
                              '/git/matching-refs/tags/2026.10.30?per_page=100&page=1'])
            self.assertEqual(api.writes, [])
        api = ReleaseAPI()
        api.tags = {'2026.10.31-' + str(i): 'a' * 40 for i in range(2, 102)}
        with self.assertRaisesRegex(ValueError, 'date tag discovery limit'):
            publish_release.publish(api, 'c' * 40, raw, files, '2026.10.31')
        self.assertEqual(api.writes, [])

    def test_utc_threshold_is_legacy_hosted_only(self):
        for event, scheduled in (('schedule', True), ('workflow_dispatch', True), ('workflow_dispatch', False)):
            self.assertIsNone(B.H.eligible_day('2026-10-31T03:59:59Z', event, False, 2, scheduled))
            self.assertEqual(B.H.eligible_day('2026-10-31T04:00:00Z', event, False, 2, scheduled), '2026.10.31')
        self.local_install(B.release())
        for hour, expected in ((3, 1), (4, 1)):
            class Clock(Noon):
                @classmethod
                def now(cls, tz=None):
                    return cls(2026, 10, 31, hour, tzinfo=timezone.utc)
            with mock.patch.object(P.SYNC, 'datetime', Clock), \
                    mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=B.release()) as fetch:
                P.SYNC.auto_update_local(self.root, False, advisory_only=True)
            self.assertEqual(fetch.call_count, expected)

    def test_explicit_updates_clear_rollback_skip_without_control_edits(self):
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        self.local_install(old)
        self.local_install(new)
        self.assertTrue(P.SYNC.do_rollback())
        self.local_install(new)
        self.assertNotIn('skip_release', P.SYNC._auto_update_state(self.root / '.section11-state'))
        remote, publisher, updater = self.hosted_pair()
        updater.rollback(publisher.snapshot())
        with self.assertRaisesRegex(ValueError, 'skipped'):
            B.H.HostedUpdater(publisher, lambda: new, {'SECTION11_AUTO_UPDATE': 'true'}).install(
                publisher.snapshot(), automatic=True)
        updater.install(publisher.snapshot(), accepted=True)
        self.assertIsNone(updater.state(publisher.snapshot())['skip_release'])

    def test_missing_custom_guidance_recreated_from_official_text(self):
        release = B.release()
        self.local_install(release)
        (self.root / 'custom/README.md').unlink()
        with self.assertRaisesRegex(ValueError, 'verified release'):
            P.SYNC._ensure_custom(self.root, {})
        P.SYNC._ensure_custom(self.root, release[1])
        self.assertEqual((self.root / 'custom/README.md').read_bytes(),
                         release[1]['examples/maintenance/CUSTOM_README.md'])
