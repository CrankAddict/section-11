"""Round-three regressions from Q01-Q05; synthetic services and job-local files only."""
import contextlib
import io
import json
import os
import re
import plistlib
import shlex
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest import mock

import test_update_prototype as P
import test_b2_hosted as B


class Noon(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 31, 12, tzinfo=timezone.utc)


class FixRound3(P.Offline):
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

    def local_install(self, release, choice=False):
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release), \
                mock.patch('builtins.input', return_value='y'), contextlib.redirect_stdout(io.StringIO()) as log:
            self.assertTrue(P.SYNC.do_update(timer_choice=choice), log.getvalue())

    def hosted_install(self, release):
        remote = B.Remote({'latest.json': b'{}'})
        publisher = B.DirectPublisher(remote)
        updater = B.H.HostedUpdater(publisher, lambda: release, {})
        updater.install(publisher.snapshot(), accepted=True)
        return remote, publisher, updater

    def test_Q01_failed_full_install_retains_plan_on_both_adapters(self):
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        self.local_install(old)
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=new), \
                mock.patch.object(P.SYNC, '_install_local', side_effect=ValueError('synthetic pre-activation stop')) as install:
            P.SYNC.auto_update_local(self.root, True)
            P.SYNC.auto_update_local(self.root, True)
        self.assertEqual(install.call_count, 1)
        notice = {}
        P.SYNC._local_update_notice(notice, self.root)
        self.assertIn('update_notice', notice)
        remote, publisher, _ = self.hosted_install(old)
        updater = B.H.HostedUpdater(publisher, lambda: new, {'SECTION11_AUTO_UPDATE': 'true'})
        with mock.patch.object(updater, 'install', side_effect=ValueError('synthetic pre-publication stop')) as install:
            with self.assertRaisesRegex(ValueError, 'synthetic pre-publication stop'):
                updater.maintain(publisher.snapshot(), '2026.10.31', True)
            updater.maintain(publisher.snapshot(), '2026.10.31', True)
        self.assertEqual(install.call_count, 1)
        state = updater.state(publisher.snapshot())
        self.assertEqual(state['attempted_day'], '2026.10.31')
        self.assertEqual(state['available_date'], new[2]['tag'])
        self.assertTrue(B.H.notice_matches(publisher.snapshot(), state))
        self.assertEqual(B.H.installed_identity(publisher, publisher.snapshot())['tag'], old[2]['tag'])
        half = B.H.HostedUpdater(publisher, lambda: new, {})
        half.maintain(publisher.snapshot(), '2026.11.01', True)
        self.assertTrue(B.H.notice_matches(publisher.snapshot(), half.state(publisher.snapshot())))
        half.install(publisher.snapshot(), accepted=True)
        self.assertIsNone(half.state(publisher.snapshot())['available_date'])


    def test_Q03_timer_only_notice_clears_without_a_second_release_lookup(self):
        release = B.release()
        self.local_install(release)
        (self.root / '.sync_config').write_text('{"auto_sync":true}')
        with mock.patch.object(P.SYNC, '_fetch_verified_release', return_value=release) as fetch:
            P.SYNC.auto_update_local(self.root, False, advisory_only=True)
            notice = {}
            P.SYNC._local_update_notice(notice, self.root)
            self.assertIn('update_notice', notice)
            adapter = P.SYNC.LocalTimers(self.root)
            adapter.apply(adapter.plan({'auto_sync': True}), self.root)
            P.SYNC._local_update_notice(notice, self.root)
            self.assertNotIn('update_notice', notice)
            P.SYNC.auto_update_local(self.root, False, advisory_only=True)
            self.assertEqual(fetch.call_count, 1)

    def test_Q04_more_than_366_rollbacks_keep_only_the_current_rejected_release(self):
        old = B.release('2026.10.28', '11.101')
        remote, publisher, _ = self.hosted_install(old)
        for i in range(367):
            tag = (Noon(2026, 10, 29, tzinfo=timezone.utc) + timedelta(days=i)).strftime('%Y.%m.%d')
            new = B.release(tag, '11.102')
            updater = B.H.HostedUpdater(publisher, lambda: new, {'SECTION11_AUTO_UPDATE': 'true'})
            with contextlib.redirect_stdout(io.StringIO()):
                updater.install(publisher.snapshot(), accepted=True)
                updater.rollback(publisher.snapshot())
            state = updater.state(publisher.snapshot())
            self.assertEqual(state['skip_release'], tag)
            self.assertNotIn('rejected_dates', state)
            self.assertLess(len(B.H.encoded(state)), 300)
            self.assertEqual(B.H.installed_identity(publisher, publisher.snapshot())['tag'], old[2]['tag'])
        with self.assertRaisesRegex(ValueError, 'remains skipped'):
            updater.install(publisher.snapshot(), automatic=True)
        updater.install(publisher.snapshot(), accepted=True)
        self.assertIsNone(updater.state(publisher.snapshot())['skip_release'])
        self.local_install(old)
        self.local_install(new)
        P.SYNC._write_install_state(self.root / '.section11-state', 'auto-update.json', {'skip_release': '2026.10.27'})
        self.assertTrue(P.SYNC.do_rollback())
        self.assertEqual(P.SYNC._auto_update_state(self.root / '.section11-state')['skip_release'], tag)

    def test_Q05_complete_schedule_examples_count_only_data_jobs(self):
        expected = {'SETUP_ASSISTANT.md': [1736],
                    'examples/json-auto-sync/SETUP.md': [1736, 1860, 1860]}
        for name, totals in expected.items():
            text = (P.ROOT / name).read_text()
            examples = re.findall(r'```yaml\n(on:\n  schedule:.*?\n  workflow_dispatch:.*?)```', text, re.S)
            self.assertEqual(len(examples), len(totals), name)
            for example, total in zip(examples, totals):
                self.assertNotIn("Section 11 maintenance backup", example)
                crons = re.findall(r"- cron: '([^']+)'", example)
                data = crons
                coverage = [0] * 24
                count = 0
                for cron in data:
                    minutes, hours, day, month, weekday = cron.split()
                    self.assertEqual((day, month, weekday), ('*', '*', '*'))
                    selected = []
                    for span in hours.split(','):
                        limits = list(map(int, span.split('-')))
                        selected.extend(range(limits[0], limits[-1] + 1))
                    for hour in selected:
                        coverage[hour] += 1
                    count += len(minutes.split(',')) * len(selected)
                self.assertEqual(coverage, [1] * 24)
                self.assertEqual(count * 31, total)
            for value in ('1,488', '2,976', '1,736', '1,860', '512', '264', '140'):
                self.assertIn(value, text)
            self.assertIn('monthly estimate = jobs/day × 31', text)
            self.assertIn('**140 to 263 minutes left:**', text)
            self.assertIn('**264 minutes or more left:**', text)
            self.assertIn('Standard hybrid', text)
            self.assertIn('Extended hybrid (lower headroom)', text)
            self.assertRegex(text, r'24 (minutes|left)')
        self.assertNotIn('schedule:', (P.ROOT / 'examples/json-on-demand/auto-sync.yml').read_text())
        self.assertNotIn('schedule:', (P.ROOT / '.github/workflows/release.yml').read_text())

    def test_4a_supported_prerequisite_matches_hosted_python_without_compatibility_edits(self):
        for name in ('json-local-sync', 'json-manual'):
            text = (P.ROOT / ('examples/' + name + '/SETUP.md')).read_text()
            self.assertIn('- Python 3.11 or newer', text)
            self.assertNotIn('- Python 3.8+', text)
        for name in ('examples/json-auto-sync/auto-sync.yml', 'examples/json-on-demand/auto-sync.yml',
                     '.github/workflows/release.yml'):
            self.assertIn("python-version: '3.11'", (P.ROOT / name).read_text())

    def test_M01_failed_discovery_retains_only_matching_unsuppressed_plan(self):
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        for mutation in (None, 'section11/LICENSE', 'sync.py', 'custom/README.md', 'skip'):
            with self.subTest(mutation=mutation):
                remote, publisher, _ = self.hosted_install(old)
                updater = B.H.HostedUpdater(publisher, lambda: new, {})
                updater.maintain(publisher.snapshot(), '2026.10.31', True)
                state = updater.state(publisher.snapshot())
                if mutation == 'skip':
                    state['skip_release'] = new[2]['tag']
                    updater.publish_control(publisher.snapshot(), state, 'Synthetic suppression')
                elif mutation:
                    remote.tip = remote.commit({mutation: b'changed preimage'}, [remote.tip], 'Synthetic edit')
                fetch = mock.Mock(side_effect=ValueError('synthetic discovery failure'))
                retry = B.H.HostedUpdater(publisher, fetch, {'SECTION11_AUTO_UPDATE': 'true'})
                with self.assertRaisesRegex(ValueError, 'discovery failure'):
                    retry.maintain(publisher.snapshot(), '2026.11.01', False)
                retry.maintain(publisher.snapshot(), '2026.11.01', False)
                fetch.assert_called_once()
                state = retry.state(publisher.snapshot())
                self.assertEqual(state['available_date'], new[2]['tag'] if mutation is None else None)

    def test_M01_unknown_pending_or_install_write_is_not_repeated(self):
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        for stage in ('Section 11 available release ', B.H.MARKER):
            with self.subTest(stage=stage):
                remote, publisher, _ = self.hosted_install(old)
                updater = B.H.HostedUpdater(publisher, lambda: new, {'SECTION11_AUTO_UPDATE': 'true'})
                def lose_response(remote):
                    body = remote.calls[-1][2]
                    if remote.commits[body['sha']]['message'].startswith(stage):
                        remote.ref_fault = 'unknown'
                remote.on_ref = lose_response
                with mock.patch.object(updater, 'install', wraps=updater.install) as install:
                    with self.assertRaises(B.UnknownOutcome):
                        updater.maintain(publisher.snapshot(), '2026.10.31', True)
                    self.assertEqual(install.call_count, int(stage == B.H.MARKER))
                    writes = len([c for c in remote.calls if c[0] == 'PATCH'])
                    # Model read-only visibility returning; no mutation is retried.
                    remote.fail_reads = False
                    updater.maintain(publisher.snapshot(), '2026.10.31', True)
                    self.assertEqual(len([c for c in remote.calls if c[0] == 'PATCH']), writes)
                    self.assertEqual(updater.state(publisher.snapshot())['attempted_day'], '2026.10.31')

    def test_M01_full_success_and_explicit_noop_clear_without_consuming_rollback(self):
        old, new = B.release('2026.10.28', '11.101'), B.release('2026.10.29', '11.102')
        remote, publisher, _ = self.hosted_install(old)
        updater = B.H.HostedUpdater(publisher, lambda: new, {'SECTION11_AUTO_UPDATE': 'true'})
        updater.maintain(publisher.snapshot(), '2026.10.31', False)
        self.assertIsNone(updater.state(publisher.snapshot())['available_date'])
        updater.install(publisher.snapshot(), accepted=True)
        updater.rollback(publisher.snapshot())
        self.assertEqual(B.H.installed_identity(publisher, publisher.snapshot())['tag'], old[2]['tag'])

    def test_M01_higher_content_holds_half_and_full_without_advertising_installation(self):
        old, new = B.release('2026.10.28', '11.105'), B.release('2026.10.29', '11.102')
        for full in ('false', 'true'):
            remote, publisher, _ = self.hosted_install(old)
            updater = B.H.HostedUpdater(publisher, lambda: new, {'SECTION11_AUTO_UPDATE': full})
            with mock.patch.object(updater, 'install', wraps=updater.install) as install:
                updater.maintain(publisher.snapshot(), '2026.10.31', True)
            install.assert_not_called()
            self.assertIsNone(updater.state(publisher.snapshot())['available_date'])

    def test_M03_rejects_invalid_scalar_and_retired_list_without_publication(self):
        default = B.H.control(None)
        for value in ([], {}, True, 1, '', '2026.02.30', '2026-10-31'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                B.H.control(B.H.encoded(dict(default, skip_release=value)))
        for value in (dict(default, rejected_dates=[]), dict(default, schema=True)):
            with self.assertRaises(ValueError):
                B.H.control(B.H.encoded(value))
        self.assertEqual(B.H.control(B.H.encoded(default)), default)

    def test_m01_policy_resolution_and_code_repairs_do_not_need_extra_discovery(self):
        release = B.release()
        self.local_install(release)
        (self.root / '.sync_config').write_text('{"auto_sync":true}')
        fetch = mock.Mock(return_value=release)
        with mock.patch.object(P.SYNC, '_fetch_verified_release', fetch):
            P.SYNC.auto_update_local(self.root, False, advisory_only=True)
            notice = {}
            P.SYNC._local_update_notice(notice, self.root)
            self.assertIn('update_notice', notice)
            (self.root / '.sync_config').write_text('{"auto_sync":false}')
            P.SYNC._local_update_notice(notice, self.root)
            self.assertNotIn('update_notice', notice)
            (self.root / 'section11/LICENSE').write_bytes(b'edited managed file')
            P.SYNC.auto_update_local(self.root, False, advisory_only=True,
                                    started_at=Noon(2026, 11, 1, 12, tzinfo=timezone.utc))
            adapter = P.SYNC.LocalTimers(self.root)
            adapter.apply(adapter.plan({'auto_sync': True}), self.root)
            P.SYNC._local_update_notice(notice, self.root)
            self.assertIn('update_notice', notice)
            self.assertEqual(fetch.call_count, 2)





