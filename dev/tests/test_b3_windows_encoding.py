"""B3 r4: real timer adapter, byte-level subprocess fixtures, no OS commands."""
import contextlib
import csv
import ctypes
import io
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import D, SYNC, REAL_TIMERS, Offline, inventory, write
from test_update_path_fixes import ReleaseHTTP


class WindowsEncodingTests(Offline):
    def codepages(self, oem=850, ansi=1252):
        kernel = SimpleNamespace(GetOEMCP=mock.Mock(return_value=oem),
                                 GetACP=mock.Mock(return_value=ansi))
        return mock.patch.object(ctypes, 'windll', SimpleNamespace(kernel32=kernel), create=True)


    def task(self, root, script='sync.py'):
        task = ET.Element('Task')
        action = ET.SubElement(ET.SubElement(task, 'Actions'), 'Exec')
        ET.SubElement(action, 'Command').text = sys.executable
        ET.SubElement(action, 'Arguments').text = subprocess.list2cmdline(
            [str(root / script), '--output', 'latest.json'])
        ET.SubElement(action, 'WorkingDirectory').text = str(root)
        return ET.tostring(task, encoding='unicode')

    def result(self, argv, stdout=b'', stderr=b'', returncode=0):
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)

    def assert_binary(self, options):
        self.assertEqual(options, dict(input=None, capture_output=True, text=False,
                                       timeout=10, check=False))

    def test_all_schtasks_operations_capture_and_decode_both_streams(self):
        for operation in ('/Query', '/Create', '/Delete'):
            with self.subTest(operation=operation), self.codepages():
                argv = ['schtasks', operation]
                with mock.patch('subprocess.run', return_value=self.result(
                        argv, 'æøå'.encode('cp850'), 'é'.encode('utf-16'))) as run:
                    result = REAL_TIMERS.command(argv)
                self.assert_binary(run.call_args.kwargs)
                self.assertEqual((result.stdout, result.stderr), ('æøå', 'é'))

    def test_other_scheduler_commands_keep_text_transport(self):
        with mock.patch('subprocess.run', return_value=self.result([], '', '')) as run:
            REAL_TIMERS.command(['crontab', '-'], input='literal cron\n')
        self.assertEqual(run.call_args.kwargs, dict(input='literal cron\n', capture_output=True,
                                                    text=True, timeout=10, check=False))


    def test_utf8_precedes_oem_and_oem_precedes_ansi(self):
        with self.codepages():
            self.assertEqual(REAL_TIMERS.windows_decode('æøå'.encode()), 'æøå')
            self.assertEqual(REAL_TIMERS.windows_decode(b'\x9d'), 'Ø')
        with self.codepages(oem=932):
            self.assertEqual(REAL_TIMERS.windows_decode(b'\xe9'), 'é')

    def test_missing_oem_api_and_unknown_codec_fall_back_to_ansi(self):
        for kernel in (SimpleNamespace(GetACP=lambda: 1252),
                       SimpleNamespace(GetOEMCP=lambda: 999999, GetACP=lambda: 1252)):
            with mock.patch.object(ctypes, 'windll', SimpleNamespace(kernel32=kernel), create=True):
                self.assertEqual(REAL_TIMERS.windows_decode(b'\xe9'), 'é')
        with mock.patch.object(ctypes, 'windll', None, create=True):
            self.assertEqual(REAL_TIMERS.windows_decode('æøå'.encode()), 'æøå')


    def test_unreadable_write_response_preserves_unknown_outcome_without_retry(self):
        adapter = REAL_TIMERS(self.root, home=self.root, platform='win32')
        for operation in ('/Create', '/Delete'):
            with self.subTest(operation=operation), self.codepages(oem=932):
                with mock.patch('subprocess.run', return_value=self.result([], b'\x81')) as run:
                    with self.assertRaisesRegex(SYNC.TimerOutcomeUnknown, 'write outcome unknown'):
                        adapter.call(['schtasks', operation], write=True)
                self.assertEqual(run.call_count, 1)





    def scheduler(self, tasks, writes, tamper=None):
        def run(argv, **options):
            self.assert_binary(options)
            self.assertEqual(argv[0], 'schtasks')
            if argv[1] == '/Query':
                self.assertEqual(argv[2:], ['/TN', '\\Section11Sync', '/XML', '/HRESULT'])
                return self.result(argv, tasks.get(argv[3], b''),
                                   returncode=0 if argv[3] in tasks else 0x80070002)
            writes.append(argv)
            if argv[1] == '/Create':
                data = Path(argv[5]).read_bytes()
                self.assertTrue(data.startswith((b'\xff\xfe', b'\xfe\xff')))
                self.assertIn("encoding='utf-16'", data.decode('utf-16'))
                tree = ET.fromstring(data)
                ET.SubElement(tree, 'RegistrationInfo')
                if tamper:
                    tamper(tree)
                tasks[argv[3]] = ET.tostring(tree, encoding='utf-16', xml_declaration=True)
            elif argv[1] == '/Delete':
                del tasks[argv[3]]
            else:
                self.fail('unexpected scheduler operation')
            return self.result(argv, 'Fuldført æøå'.encode('cp850'))
        return run

    def test_fresh_install_non_ascii_folder_creates_utf16_and_reads_back_once(self):
        root = self.root / 'Fictional æøå data'
        sentinels = {'.sync_config.json': b'{"check_interval_minutes":5}', 'latest.json': b'fictional data',
                     'custom/keep.txt': b'preserve', 'DOSSIER.md': b'fictional private'}
        write(root, sentinels)
        wire = ReleaseHTTP(4)
        tasks, writes = {}, []
        adapter = REAL_TIMERS(root, home=self.root / 'home', platform='win32')
        home = self.root / 'home'
        class WindowsTimers(REAL_TIMERS):
            def __init__(self, data_dir):
                super().__init__(data_dir, home=home, platform='win32')
        output = io.StringIO()
        with self.codepages(), mock.patch('subprocess.run', side_effect=self.scheduler(tasks, writes)), \
                mock.patch.object(SYNC, 'LocalTimers', WindowsTimers), \
                mock.patch.object(SYNC.Path, 'cwd', return_value=root), \
                mock.patch.dict(os.environ, {'GITHUB_ACTIONS': ''}), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(wire.raw[4], wire.files[4], wire.identity(4))), \
                mock.patch('builtins.input', return_value='y') as prompt, contextlib.redirect_stdout(output):
            self.assertTrue(SYNC.do_init(), output.getvalue())
            self.assertEqual(prompt.call_count, 1)
            plan = adapter.plan({'check_interval_minutes': 5})
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][1], '/Create')
        self.assertEqual(set(tasks), {'\\Section11Sync'})
        self.assertEqual(set(plan['before']['resources']), {'task:\\Section11Sync'})
        self.assertIsNone(plan['create'])
        xml = tasks['\\Section11Sync'].decode('utf-16')
        for value in (str(root), 'PT5M', '--lockfile', 'local_scheduled'):
            self.assertIn(value, xml)
        self.assertEqual(D.tree(root / 'section11'), (wire.raw[4], wire.files[4]))
        for path, data in sentinels.items():
            self.assertEqual((root / path).read_bytes(), data)


    def test_altered_non_ascii_readback_is_unknown_and_does_not_retry(self):
        for bad in ('path', 'extra_action'):
            with self.subTest(bad=bad):
                adapter = REAL_TIMERS(self.root / 'æøå', home=self.root, platform='win32')
                tasks, writes = {}, []
                def tamper(tree):
                    if bad == 'path':
                        next(e for e in tree.iter() if e.tag.split('}')[-1] == 'WorkingDirectory').text += 'changed'
                    else:
                        ET.SubElement(next(e for e in tree.iter() if e.tag.split('}')[-1] == 'Actions'), 'Exec')
                with self.codepages(), mock.patch('subprocess.run', side_effect=self.scheduler(tasks, writes, tamper)):
                    plan = adapter.plan({})
                    with self.assertRaisesRegex(SYNC.TimerOutcomeUnknown, 'readback mismatch'):
                        adapter.apply(plan, self.root)
                self.assertEqual(len(writes), 1)

    def test_only_standard_task_is_replaced_and_rollback_restores_its_xml(self):
        original = self.task(self.root / 'Fictional æøå data').encode()
        tasks = {'\\Section11Sync': original, '\\Unrelated': b'unreadable neighbor'}
        writes = []
        adapter = REAL_TIMERS(self.root, home=self.root, platform='win32')
        with self.codepages(), mock.patch('subprocess.run', side_effect=self.scheduler(tasks, writes)):
            plan = adapter.plan({})
            adapter.apply(plan, self.root)
            adapter.apply(REAL_TIMERS.recovery(plan), self.root, reverse=True)
        self.assertEqual(tasks['\\Unrelated'], b'unreadable neighbor')
        self.assertTrue(adapter.resource_matches('task:\\Section11Sync', tasks['\\Section11Sync'].decode('utf-16'), original.decode()))
        self.assertEqual([c[1] for c in writes], ['/Delete', '/Create', '/Delete', '/Create'])

    def test_unreadable_standard_readback_cannot_confirm_deletion(self):
        tasks = {'\\Section11Sync': self.task(self.root).encode()}
        writes = []
        adapter = REAL_TIMERS(self.root, home=self.root, platform='win32')
        scheduler = self.scheduler(tasks, writes)
        def run(argv, **options):
            if writes and argv[1] == '/Query':
                return self.result(argv, b'\xff\xfeX')
            return scheduler(argv, **options)
        with self.codepages(), mock.patch('subprocess.run', side_effect=run):
            plan = adapter.plan({}, choice=False)
            with self.assertRaisesRegex(SYNC.TimerOutcomeUnknown, 'readback mismatch'):
                adapter.apply(plan, self.root)
        self.assertEqual([c[1] for c in writes], ['/Delete'])
