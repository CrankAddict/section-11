"""Standard timer contract; every scheduler call is synthetic."""
import contextlib
import io
import json
import plistlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import SYNC, REAL_TIMERS, Offline, inventory
from _local_timer_fakes import fake_timers


class SimpleTimerTests(Offline):
    def test_cron_exact_marker_preserves_other_lines_and_rollback_bytes(self):
        timer = self.timers(self.root)
        unrelated = ('# private comment\r\n0 0 * * * strange $(command) # section11-sync-extra\r\n'
                     '* * * * * python3 sync.py\n* * * * * sh wrapper-sync.sh\n'
                     '0 1 * * * unrelated synthetic-secret')
        old = '*/10 * * * * old-standard # section11-sync\n'
        original = unrelated[:unrelated.index('0 1')] + old + unrelated[unrelated.index('0 1'):]
        self.timers.crontabs[str(self.root)] = original
        plan = timer.plan({'check_interval_minutes': 5})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            timer.describe(plan)
        self.assertEqual(output.getvalue(), 'Auto sync will be installed (every 5 minutes). If you set up your own timer before, remove it.\n')
        timer.apply(plan, self.root)
        current = self.timers.crontabs[str(self.root)]
        self.assertTrue(current.startswith('*/5 '))
        self.assertTrue(current.endswith(unrelated))
        self.assertEqual(current.count(' # section11-sync\n'), 1)
        recovery = REAL_TIMERS.recovery(plan)
        self.assertNotIn('synthetic-secret', json.dumps(recovery))
        timer.apply(recovery, self.root, reverse=True)
        self.assertEqual(self.timers.crontabs[str(self.root)], original)
        disabled = timer.plan({}, choice=False)
        timer.apply(disabled, self.root)
        self.assertEqual(self.timers.crontabs[str(self.root)], unrelated)
        timer.apply(REAL_TIMERS.recovery(disabled), self.root, reverse=True)
        self.assertEqual(self.timers.crontabs[str(self.root)], original)

    def test_interval_refresh_opt_out_and_literal_cron_paths(self):
        timer = self.timers(self.root / '100% data')
        for minutes in (1, 2, 5, 10):
            plan = timer.plan({'check_interval_minutes': minutes})
            self.assertEqual(plan['minutes'], minutes)
            self.assertIn(r'100\% data', plan['after']['cron'])
            self.assertIn('--lockfile', plan['after']['cron'])
            timer.apply(plan, self.root)
            repeat = timer.plan({'check_interval_minutes': minutes})
            self.assertIsNone(repeat['create'])
            self.assertEqual(repeat['remove'], [])
            self.assertEqual(repeat['after'], repeat['before']['resources'])
        for value in (True, '5', 3, None):
            self.assertEqual(timer.plan({'check_interval_minutes': value})['minutes'], 1)
        disabled = timer.plan({'auto_sync': False})
        timer.apply(disabled, self.root)
        self.assertEqual(self.timers.crontabs[str(timer.root)], '')
        self.assertIsNone(timer.plan({'auto_sync': False})['create'])
        self.assertIsNotNone(timer.plan({'auto_sync': False}, choice=True)['create'])

    def test_cron_read_failure_and_preimage_race_do_not_write(self):
        timer = REAL_TIMERS(self.root, home=self.root, platform='test-cron')
        for code, err in ((1, 'synthetic unreadable table'), (2, 'synthetic failed read')):
            with mock.patch.object(timer, 'command', return_value=SimpleNamespace(
                    returncode=code, stdout='', stderr=err)) as command:
                with self.assertRaisesRegex(SYNC.DistributionError, 'unreadable'):
                    timer.plan({})
                self.assertEqual(command.call_count, 1)
        timer = self.timers(self.root)
        plan = timer.plan({})
        self.timers.crontabs[str(self.root)] = '# later user edit\n'
        with self.assertRaisesRegex(SYNC.DistributionError, 'changed after review'):
            timer.apply(plan, self.root)
        self.assertEqual(self.timers.crontabs[str(self.root)], '# later user edit\n')

    def test_launchd_and_systemd_only_read_and_restore_standard_files(self):
        for platform in ('darwin', 'linux'):
            with self.subTest(platform=platform):
                home = self.root / platform
                timer = REAL_TIMERS(self.root / '100% $ data\\', home=home, platform=platform)
                def command(argv, input=None):
                    self.assertIn(argv[0], ('launchctl', 'systemctl'))
                    self.assertNotIn('list-timers', argv)
                    return SimpleNamespace(returncode=0, stdout='', stderr='')
                with mock.patch.object(timer, 'command', side_effect=command), \
                        mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                    standard = timer.standard({'check_interval_minutes': 10})
                    for key, value in standard['resources'].items():
                        path = Path(key[5:])
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(value)
                    neighbor = path.parent / ('own.plist' if platform == 'darwin' else 'own.service')
                    neighbor.write_bytes(b'invalid neighboring definition must never be read')
                    before = inventory(home)
                    original_read = timer.file_bytes
                    def read(path):
                        self.assertIn('file:' + str(path), standard['resources'])
                        return original_read(path)
                    with mock.patch.object(timer, 'file_bytes', side_effect=read), \
                            mock.patch.object(Path, 'glob', side_effect=AssertionError('no enumeration')):
                        plan = timer.plan({'check_interval_minutes': 5})
                        timer.apply(plan, self.root)
                        self.assertEqual(neighbor.read_bytes(), b'invalid neighboring definition must never be read')
                        timer.apply(REAL_TIMERS.recovery(plan), self.root, reverse=True)
                    self.assertEqual(inventory(home), before)

    def test_standard_formats_keep_mode_lockfile_and_configured_interval(self):
        for platform in ('darwin', 'linux', 'win32'):
            with self.subTest(platform=platform), \
                    mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'), \
                    mock.patch.object(REAL_TIMERS, 'command', return_value=SimpleNamespace(returncode=0)):
                timer = REAL_TIMERS(self.root, home=self.root / 'home', platform=platform)
                value = timer.standard({'check_interval_minutes': 5})
                text = '\n'.join(value['resources'].values())
                self.assertIn('local_scheduled', text)
                self.assertIn('--lockfile', text)
                self.assertIn('section11/examples/sync.py', text)
                if platform == 'darwin':
                    plist = plistlib.loads(text.encode())
                    self.assertEqual(plist['StartInterval'], 300)
                    self.assertEqual(plist['WorkingDirectory'], str(self.root))
                    self.assertEqual(plist['ProgramArguments'], [sys.executable, str(self.root / 'section11/examples/sync.py'),
                                                                 '--output', 'latest.json', '--lockfile'])
                elif platform == 'linux':
                    self.assertIn('OnBootSec=60\nOnUnitActiveSec=300\n', text)
                    self.assertIn('WorkingDirectory=' + str(self.root) + '\n', text)
                else:
                    self.assertIn('PT5M', text)
                    self.assertIn('IgnoreNew', text)
                api = timer.standard({'github_repo': 'synthetic/repo', 'github_token': 'synthetic'})
                self.assertNotIn('--output', '\n'.join(api['resources'].values()))

    def test_windows_only_queries_standard_and_refuses_unknown_absence(self):
        timer = REAL_TIMERS(self.root, home=self.root, platform='win32')
        for status in (0x80070002, -2147024894):
            with mock.patch.object(timer, 'command', return_value=SimpleNamespace(
                    returncode=status, stdout='', stderr='localized missing message')) as calls:
                plan = timer.plan({})
                self.assertIsNotNone(plan['create'])
                self.assertEqual(calls.call_args.args[0], ['schtasks', '/Query', '/TN', '\\Section11Sync', '/XML', '/HRESULT'])
        for status in (1, 0x80070005):
            with mock.patch.object(timer, 'command', return_value=SimpleNamespace(
                    returncode=status, stdout='', stderr='synthetic refusal')) as calls:
                with self.assertRaisesRegex(SYNC.DistributionError, 'unreadable'):
                    timer.plan({})
                self.assertEqual(calls.call_count, 1)

    def test_systemd_unavailable_uses_cron_unless_systemd_timer_exists(self):
        timer = REAL_TIMERS(self.root, home=self.root, platform='linux')
        with mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'), \
                mock.patch.object(timer, 'command', return_value=SimpleNamespace(returncode=1)) as command:
            self.assertEqual(timer.standard({})['kind'], 'cron')
            self.assertEqual(command.call_args.args[0], ['systemctl', '--user', 'show-environment'])
            unit = self.root / '.config/systemd/user/section11-sync.timer'
            unit.parent.mkdir(parents=True)
            unit.write_text('[Timer]\n', encoding='utf-8')
            for choice in (None, True, False):
                with self.assertRaisesRegex(SYNC.DistributionError, 'normal login session'):
                    timer.plan({}, choice)
            self.assertFalse(any(c.args[0][0] == 'crontab' for c in command.call_args_list))
        with mock.patch.object(SYNC.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(SYNC.DistributionError, 'normal login session'):
                timer.standard({})

    def test_windows_standard_readback_rejects_changed_actions_and_interval(self):
        timer = REAL_TIMERS(self.root, home=self.root, platform='win32')
        xml = timer.standard({})['resources']['task:\\Section11Sync']
        tree = ET.fromstring(xml)
        ET.SubElement(next(n for n in tree.iter() if n.tag.split('}')[-1] == 'Actions'), 'Exec')
        self.assertFalse(timer.resource_matches('task:x', ET.tostring(tree, encoding='unicode'), xml))
        self.assertFalse(timer.resource_matches('task:x', xml.replace('PT1M', 'PT5M'), xml))
        tree = ET.fromstring(xml)
        ET.SubElement(tree, 'RegistrationInfo')
        self.assertTrue(timer.resource_matches('task:x', ET.tostring(tree, encoding='unicode'), xml))

    def test_rollback_rejects_old_other_timer_records_before_reading(self):
        timer = REAL_TIMERS(self.root, home=self.root, platform='win32')
        plan = {'before': {'resources': {'task:\\Other': '<Task/>'}},
                'after': {'task:\\Other': None}, 'remove': [{'kind': 'windows', 'name': '\\Other'}], 'create': None}
        with mock.patch.object(timer, 'read') as read:
            with self.assertRaisesRegex(SYNC.DistributionError, 'limited to the standard'):
                timer.apply(plan, self.root, reverse=True)
            read.assert_not_called()
