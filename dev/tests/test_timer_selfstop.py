"""Offline scheduler semantics, timer preservation and interrupted activation."""
import contextlib
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

# The isolated subprocess uses the same protected interpreter as discovery.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_update_prototype import (SYNC, REAL_TIMERS, Offline, fixture, install,
                                   inventory, write)


def platform_timers(platform):
    class Timers(REAL_TIMERS):
        calls = []
        tasks = {}
        crontabs = {}
        active = True
        enabled = True

        def __init__(self, root, **kwargs):
            super().__init__(root, home=root / 'synthetic-home', platform=platform)

        def command(self, argv, input=None):
            self.calls.append((argv, input))
            code, out, err = 0, '', ''
            if argv[0] == 'crontab':
                if argv[1] == '-l':
                    out = self.crontabs.get(str(self.root))
                    if out is None:
                        code, out, err = 1, '', 'no crontab'
                elif argv[1] == '-':
                    self.crontabs[str(self.root)] = input
                elif argv[1] == '-r':
                    self.crontabs.pop(str(self.root), None)
                else:
                    raise AssertionError(argv)
            elif argv[0] == 'schtasks':
                if argv[1] == '/Query':
                    out = self.tasks.get(str(self.root))
                    if out is None:
                        code, out = 0x80070002, ''
                elif argv[1] == '/Delete':
                    self.tasks.pop(str(self.root), None)
                elif argv[1] == '/Create':
                    self.tasks[str(self.root)] = Path(argv[argv.index('/XML') + 1]).read_text(encoding='utf-16')
                else:
                    raise AssertionError(argv)
            elif argv[0] == 'launchctl':
                if argv[1] not in ('bootout', 'bootstrap', 'print'):
                    raise AssertionError(argv)
                if argv[1] == 'bootout':
                    type(self).active = False
                elif argv[1] == 'bootstrap':
                    type(self).active = True
                else:
                    from test_timer_activation_recovery import readback
                    return readback(self.root, 'loaded-running.txt' if self.active else 'not-loaded.txt')
            elif argv[0] == 'systemctl':
                if argv[2] == 'is-enabled':
                    code, out = (0, 'enabled\n') if self.enabled else (1, 'disabled\n')
                elif argv[2] == 'is-active':
                    code, out = (0, 'active\n') if self.active else (3, 'inactive\n')
                elif argv[2] in ('enable', 'disable'):
                    type(self).enabled = type(self).active = argv[2] == 'enable'
                elif argv[2] not in ('show-environment', 'daemon-reload'):
                    raise AssertionError(argv)
            else:
                raise AssertionError('unmocked scheduler: ' + repr(argv))
            return SimpleNamespace(returncode=code, stdout=out, stderr=err)

    return Timers


def scheduler_writes(calls):
    return [argv for argv, _ in calls if not (
        argv[:2] in (['crontab', '-l'], ['schtasks', '/Query'], ['launchctl', 'print']) or
        argv[:3] in (['systemctl', '--user', operation] for operation in ('show-environment', 'is-enabled', 'is-active')))]


class TimerSelfStopTests(Offline):
    def select(self, platform, name):
        root = self.root / name
        root.mkdir()
        timers = platform_timers(platform)
        return root, timers

    def seed(self, root, timers, config=None):
        timer = timers(root)
        with mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': ''}):
            timer.apply(timer.plan(config or {}), root)
        timers.calls.clear()
        return timer

    def test_unchanged_plan_and_legacy_rollback_never_write_any_scheduler(self):
        for platform in ('darwin', 'linux', 'win32', 'test-cron'):
            with self.subTest(platform=platform), mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                root, timers = self.select(platform, platform)
                timer = self.seed(root, timers)
                before = inventory(root)
                plan = timer.plan({})
                self.assertEqual(plan['remove'], [])
                self.assertIsNone(plan['create'])
                for scheduled in ('', 'local_scheduled'):
                    with mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': scheduled}):
                        timer.apply(plan, root)
                        legacy = dict(plan, remove=[timer.standard({})], create=timer.standard({}))
                        timer.apply(legacy, root)
                        timer.apply(REAL_TIMERS.recovery(legacy), root, reverse=True)
                self.assertEqual(scheduler_writes(timers.calls), [])
                self.assertEqual(inventory(root), before)

    def test_changed_timer_inside_job_refuses_install_and_preserves_notice(self):
        for platform in ('darwin', 'linux', 'win32', 'test-cron'):
            for config in ({'check_interval_minutes': 5}, {'auto_sync': False}):
                with self.subTest(platform=platform, config=config), mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                    root, timers = self.select(platform, platform + str(len(list(self.root.iterdir()))))
                    self.seed(root, timers)
                    old_raw, old_files = fixture()
                    install(root / 'section11', old_raw, old_files)
                    write(root / 'section11', {SYNC.Distribution.RECEIPT: SYNC.Distribution.receipt(old_raw, {'tag': '2026.10.23', 'commit': 'a' * 40})})
                    write(root, {'.sync_config': json.dumps(config).encode(), 'latest.json': b'preserved data'})
                    raw, files = fixture('9000.1')
                    identity = {'tag': '2026.10.24', 'commit': 'b' * 40}
                    before = inventory(root / 'section11')
                    with mock.patch.object(SYNC, 'LocalTimers', timers), \
                            mock.patch.object(SYNC, '_fetch_verified_release', return_value=(raw, files, identity)), \
                            mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': 'local_scheduled', 'GITHUB_ACTIONS': ''}), \
                            contextlib.redirect_stdout(io.StringIO()) as output:
                        SYNC.auto_update_local(root, True)
                    self.assertIn('timer change requires a terminal', output.getvalue())
                    self.assertEqual(inventory(root / 'section11'), before)
                    self.assertFalse((root / '.section11-state/transaction.json').exists())
                    saved = json.loads((root / '.section11-state/auto-update.json').read_text())
                    self.assertEqual(saved['available_release'], identity['tag'])
                    self.assertEqual((root / 'latest.json').read_bytes(), b'preserved data')
                    self.assertEqual(scheduler_writes(timers.calls), [])

    def test_terminal_update_refresh_and_rollback_preserve_unchanged_timers(self):
        for platform in ('darwin', 'linux', 'win32', 'test-cron'):
            with self.subTest(platform=platform), mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                root, timers = self.select(platform, platform)
                self.seed(root, timers)
                raw, files = fixture()
                install(root / 'section11', raw, files)
                raw, files = fixture('9000.1')
                identity = {'tag': '2026.10.24', 'commit': 'b' * 40}
                with mock.patch.object(SYNC, 'LocalTimers', timers), \
                        mock.patch.object(SYNC.Path, 'cwd', return_value=root), \
                        mock.patch.object(SYNC, '_fetch_verified_release', return_value=(raw, files, identity)), \
                        mock.patch('builtins.input', return_value='y'), \
                        mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': ''}), \
                        contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertTrue(SYNC.do_update(), output.getvalue())
                    previous = (root / '.section11-state/previous.json').read_bytes()
                    self.assertTrue(SYNC.do_update(), output.getvalue())
                    self.assertEqual((root / '.section11-state/previous.json').read_bytes(), previous)
                    self.assertTrue(SYNC.do_update(status_only=True), output.getvalue())
                    self.assertTrue(SYNC.do_rollback(), output.getvalue())
                self.assertEqual(scheduler_writes(timers.calls), [])

    def test_terminal_changed_timer_keeps_current_activation_behaviour(self):
        for platform in ('darwin', 'linux', 'win32', 'test-cron'):
            with self.subTest(platform=platform), mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                root, timers = self.select(platform, platform)
                timer = self.seed(root, timers)
                with mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': ''}):
                    timer.apply(timer.plan({'check_interval_minutes': 5}), root)
                self.assertTrue(scheduler_writes(timers.calls))
                self.assertEqual(timer.plan({'check_interval_minutes': 5})['before']['resources'], timer.plan({'check_interval_minutes': 5})['after'])

    def test_terminal_missing_identical_timer_only_activates_and_confirms(self):
        for platform in ('darwin', 'linux'):
            with self.subTest(platform=platform), mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                root, timers = self.select(platform, platform)
                timer = self.seed(root, timers)
                before = inventory(root)
                timers.active = timers.enabled = False
                with mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': ''}):
                    timer.apply(timer.plan({}), root)
                expected = (['launchctl', 'bootstrap', 'gui/' + str(os.getuid()),
                             str(root / 'synthetic-home/Library/LaunchAgents/com.section11.sync.plist')]
                            if platform == 'darwin' else ['systemctl', '--user', 'enable', '--now', 'section11-sync.timer'])
                self.assertEqual(scheduler_writes(timers.calls), [expected])
                self.assertEqual(timers.calls[-1][0][:2 if platform == 'darwin' else 3],
                                 ['launchctl', 'print'] if platform == 'darwin' else ['systemctl', '--user', 'is-active'])
                self.assertEqual(inventory(root), before)
                self.assertTrue(timers.active)

    def test_scheduled_identical_timer_never_attempts_reactivation(self):
        for platform in ('darwin', 'linux'):
            with self.subTest(platform=platform), mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                root, timers = self.select(platform, platform)
                timer = self.seed(root, timers)
                timers.active = timers.enabled = False
                with mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': 'local_scheduled'}):
                    timer.apply(timer.plan({}), root)
                    timer.restore_unchanged({})
                self.assertEqual(scheduler_writes(timers.calls), [])
                self.assertFalse(any(a[:2] == ['launchctl', 'print'] or a[2:3] in (['is-enabled'], ['is-active'])
                                     for a, _ in timers.calls))

    def test_terminal_update_restores_missing_without_consuming_previous_slot(self):
        for platform in ('darwin', 'linux'):
            with self.subTest(platform=platform), mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                root, timers = self.select(platform, platform)
                self.seed(root, timers)
                raw, files = fixture()
                identity = {'tag': '2026.10.24', 'commit': 'b' * 40}
                with mock.patch.object(SYNC, 'LocalTimers', timers), mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': ''}), \
                        mock.patch.object(SYNC.Path, 'cwd', return_value=root), \
                        mock.patch.object(SYNC, '_fetch_verified_release', return_value=(raw, files, identity)), \
                        mock.patch('builtins.input', return_value='y'), contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertTrue(SYNC.do_update(), output.getvalue())
                    previous = (root / '.section11-state/previous.json').read_bytes()
                    timers.calls.clear()
                    timers.active = timers.enabled = False
                    self.assertTrue(SYNC.do_update(), output.getvalue())
                self.assertEqual((root / '.section11-state/previous.json').read_bytes(), previous)
                self.assertFalse((root / '.section11-state/transaction.json').exists())
                writes = scheduler_writes(timers.calls)
                self.assertEqual(len(writes), 1)
                self.assertIn('bootstrap' if platform == 'darwin' else 'enable', writes[0])

    def test_uncertain_activation_during_install_keeps_journal_and_new_tree(self):
        root, timers = self.select('darwin', 'data')
        self.seed(root, timers)
        raw, files = fixture()
        install(root / 'section11', raw, files)
        raw, files = fixture('9000.1')
        timers.active = False
        original = timers.command
        bootstrapped = []
        def command(timer, argv, input=None):
            if argv[:2] == ['launchctl', 'print'] and bootstrapped:
                return SimpleNamespace(returncode=1, stdout='', stderr='synthetic uncertain activation')
            result = original(timer, argv, input)
            if argv[:2] == ['launchctl', 'bootstrap']:
                bootstrapped.append(True)
            return result
        with mock.patch.object(SYNC, 'LocalTimers', timers), mock.patch.object(timers, 'command', command), \
                mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': ''}), self.assertRaises(SYNC.TimerOutcomeUnknown):
            SYNC._install_local(root, raw, files, {'tag': '2026.10.24', 'commit': 'b' * 40},
                                SYNC._local_plan(root, raw, files))
        self.assertEqual(SYNC._known_local_identity(root / 'section11')['tag'], '2026.10.24')
        state = root / '.section11-state'
        self.assertEqual(json.loads((state / 'transaction.json').read_bytes())['phase'], 'timer-activation')
        self.assertFalse((state / 'previous.json').exists())
        self.assertEqual(len(scheduler_writes(timers.calls)), 1)

    def test_terminal_ambiguous_activity_continues_without_activation(self):
        for platform in ('darwin', 'linux'):
            with self.subTest(platform=platform), mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                root, timers = self.select(platform, platform)
                timer = self.seed(root, timers)
                plan = timer.plan({})
                original = timer.command
                def command(argv, input=None):
                    if argv[:2] == ['launchctl', 'print'] or argv[2:3] == ['is-enabled']:
                        timers.calls.append((argv, input))
                        return SimpleNamespace(returncode=1, stdout='', stderr='synthetic ambiguous readback')
                    return original(argv, input)
                with mock.patch.object(timer, 'command', side_effect=command), \
                        mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': ''}), \
                        contextlib.redirect_stdout(io.StringIO()) as output:
                    timer.apply(plan, root)
                self.assertEqual(scheduler_writes(timers.calls), [])
                self.assertEqual(output.getvalue().strip(),
                    'Section 11: timer left unchanged; could not confirm its loaded state')

    def test_ordinary_commands_succeed_with_unproven_loaded_state(self):
        cases = [('darwin', 'different'), ('darwin', 'unparseable'), ('darwin', 'unexpected-exit'),
                 ('linux', 'enabled-inactive'), ('linux', 'unexpected-exit')]
        for platform, condition in cases:
            for operation in ('update', 'refresh', 'rollback', 'setup'):
                with self.subTest(platform=platform, condition=condition, operation=operation), \
                        mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                    root, timers = self.select(platform, platform + '-' + condition + '-' + operation)
                    timer = self.seed(root, timers)
                    old_raw, old_files = fixture()
                    raw, files = fixture('9000.1')
                    identity = {'tag': '2026.10.24', 'commit': 'b' * 40}
                    with mock.patch.object(SYNC, 'LocalTimers', timers), \
                            mock.patch.object(SYNC.Path, 'cwd', return_value=root), \
                            mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': '', 'GITHUB_ACTIONS': ''}):
                        SYNC._install_local(root, old_raw, old_files, {'tag': '2026.10.23', 'commit': 'a' * 40},
                                            SYNC._local_plan(root, old_raw, old_files))
                        SYNC._install_local(root, raw, files, identity, SYNC._local_plan(root, raw, files))
                        write(root, {'latest.json': b'preserved export'})
                        definitions = timer.read(timer.standard({}))
                        state = root / '.section11-state'
                        previous = (state / 'previous.json').read_bytes()
                        timers.calls.clear()
                        original = timers.command
                        def command(adapter, argv, input=None):
                            result = original(adapter, argv, input)
                            if argv[:2] == ['launchctl', 'print']:
                                if condition == 'different':
                                    result.stdout = result.stdout.replace('run interval = 60 seconds', 'run interval = 300 seconds')
                                elif condition == 'unparseable':
                                    result.stdout = 'unrecognized loaded-job format\n'
                                elif condition == 'unexpected-exit':
                                    result = SimpleNamespace(returncode=2, stdout='', stderr='synthetic unexpected exit')
                            elif condition == 'enabled-inactive' and argv[2:3] == ['is-active']:
                                result = SimpleNamespace(returncode=3, stdout='inactive\n', stderr='')
                            elif condition == 'unexpected-exit' and argv[2:3] == ['is-enabled']:
                                result = SimpleNamespace(returncode=2, stdout='unknown\n', stderr='')
                            return result
                        if operation == 'update':
                            raw, files = fixture('9000.2')
                            identity = {'tag': '2026.10.25', 'commit': 'c' * 40}
                        answers = ['synthetic', 'synthetic', '', '', '', ''] if operation == 'setup' else None
                        with mock.patch.object(timers, 'command', command), \
                                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(raw, files, identity)), \
                                mock.patch('builtins.input', side_effect=answers, return_value='y'), \
                                mock.patch.object(sys, 'argv', ['sync.py', '--setup']), \
                                contextlib.redirect_stdout(io.StringIO()) as output:
                            if operation == 'setup':
                                SYNC._main()
                                self.assertIn('Config saved', output.getvalue())
                            else:
                                self.assertTrue((SYNC.do_rollback if operation == 'rollback' else SYNC.do_update)(), output.getvalue())
                        expected_tag = {'update': '2026.10.25', 'rollback': '2026.10.23'}.get(operation, '2026.10.24')
                        self.assertEqual(SYNC._known_local_identity(root / 'section11')['tag'], expected_tag)
                        self.assertFalse((state / 'transaction.json').exists())
                        if operation in ('refresh', 'setup'):
                            self.assertEqual((state / 'previous.json').read_bytes(), previous)
                        self.assertEqual(timer.read(timer.standard({})), definitions)
                        self.assertEqual((root / 'latest.json').read_bytes(), b'preserved export')
                        self.assertEqual(scheduler_writes(timers.calls), [])
                        note = 'Section 11: timer left unchanged; could not confirm its loaded state'
                        self.assertEqual(output.getvalue().count(note), 1, output.getvalue())

    def test_metadata_failure_after_confirmed_activation_preserves_install(self):
        root, timers = self.select('darwin', 'data')
        self.seed(root, timers)
        raw, files = fixture()
        install(root / 'section11', raw, files)
        raw, files = fixture('9000.1')
        timers.active = False
        original = SYNC._write_install_state
        def write_state(state, name, value):
            if name == 'previous.json':
                raise KeyboardInterrupt('synthetic metadata interruption')
            original(state, name, value)
        with mock.patch.object(SYNC, 'LocalTimers', timers), mock.patch.object(SYNC, '_write_install_state', write_state), \
                mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': ''}), self.assertRaises(KeyboardInterrupt):
            SYNC._install_local(root, raw, files, {'tag': '2026.10.24', 'commit': 'b' * 40},
                                SYNC._local_plan(root, raw, files))
        self.assertEqual(SYNC._known_local_identity(root / 'section11')['tag'], '2026.10.24')
        state = root / '.section11-state'
        self.assertEqual(json.loads((state / 'transaction.json').read_bytes())['phase'], 'timer-activation')
        self.assertFalse((state / 'previous.json').exists())
        self.assertEqual(len(scheduler_writes(timers.calls)), 1)

    def test_setup_restores_existing_identical_timer_without_unloading(self):
        for platform in ('darwin', 'linux'):
            with self.subTest(platform=platform), mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                root, timers = self.select(platform, platform)
                self.seed(root, timers)
                timers.active = timers.enabled = False
                with mock.patch.object(SYNC, 'LocalTimers', timers), mock.patch.object(SYNC.Path, 'cwd', return_value=root), \
                        mock.patch.object(sys, 'argv', ['sync.py', '--setup']), \
                        mock.patch('builtins.input', side_effect=['synthetic', 'synthetic', '', '', '', '']), \
                        mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': ''}), contextlib.redirect_stdout(io.StringIO()):
                    SYNC._main()
                writes = scheduler_writes(timers.calls)
                self.assertEqual(len(writes), 1)
                self.assertIn('bootstrap' if platform == 'darwin' else 'enable', writes[0])

    def test_interrupted_changed_refresh_retains_crash_record_and_notice(self):
        root, timers = self.select('darwin', 'data')
        self.seed(root, timers)
        raw, files = fixture()
        identity = {'tag': '2026.10.24', 'commit': 'b' * 40}
        with mock.patch.object(SYNC, 'LocalTimers', timers), mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': ''}):
            SYNC._install_local(root, raw, files, identity, SYNC._local_plan(root, raw, files))
            state = root / '.section11-state'
            previous = (state / 'previous.json').read_bytes()
            write(root, {'.sync_config': b'{"check_interval_minutes":5}'})
            SYNC._write_install_state(state, 'auto-update.json', {'available_release': identity['tag']})
            expected = SYNC._local_plan(root, raw, files)
            self.assertTrue(SYNC._local_install_needed(root, raw, identity, expected))
            original = timers.command
            def command(timer, argv, input=None):
                if argv[:2] == ['launchctl', 'bootout']:
                    self.assertEqual(json.loads((state / 'transaction.json').read_bytes())['phase'], 'timer-activation')
                    raise KeyboardInterrupt('synthetic interrupted scheduler write')
                return original(timer, argv, input)
            with mock.patch.object(timers, 'command', command), self.assertRaises(KeyboardInterrupt):
                SYNC._install_local(root, raw, files, identity, expected)
            record = json.loads((state / 'transaction.json').read_bytes())
            self.assertEqual(record['phase'], 'timer-activation')
            saved_timer = (state / record['transaction'] / 'timers.json').read_bytes()
            self.assertEqual(json.loads(saved_timer), timers.recovery(expected['timer']))
            self.assertEqual(SYNC.Distribution.digest(saved_timer), record['timers_digest'])
            self.assertEqual((state / 'previous.json').read_bytes(), previous)
            self.assertEqual(json.loads((state / 'auto-update.json').read_bytes())['available_release'], identity['tag'])
            before = inventory(root)
            # bootout interrupted before replacing the old one-minute plist;
            # the recorded five-minute after-definition cannot be proven.
            with self.assertRaisesRegex(SYNC.DistributionError, 'interrupted update'):
                SYNC._cleanup_staging(state)
            self.assertEqual(inventory(root), before)

    def test_setup_restoration_requires_boolean_enabled_policy(self):
        for platform in ('darwin', 'linux'):
            with self.subTest(platform=platform), mock.patch.object(SYNC.shutil, 'which', return_value='/synthetic/systemctl'):
                root, timers = self.select(platform, platform)
                timer = self.seed(root, timers)
                timers.active = timers.enabled = False
                for policy in (False, 0, 1, 'true', 'false', None):
                    with self.subTest(policy=policy), mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': ''}):
                        timer.restore_unchanged({'auto_sync': policy})
                self.assertEqual(timers.calls, [])
                self.assertFalse(timers.active)

    def test_fake_bootout_kills_job_tree_but_automatic_install_survives(self):
        if os.name == 'nt':
            self.skipTest('process-group signal semantics require POSIX; all transports remain mocked')
        result = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--job', str(self.root)],
                                capture_output=True, text=True, timeout=30, start_new_session=True)
        evidence = (self.root / 'scheduler-events.txt').read_text()
        self.assertEqual(result.returncode, 0, 'isolated job exit: ' + str(result.returncode) + '\n' + result.stdout + result.stderr + evidence)
        self.assertNotIn('bootout', evidence)
        self.assertNotIn('bootstrap', evidence)
        self.assertEqual((self.root / 'timer-active').read_text(), 'yes')
        self.assertTrue((self.root / 'completed').is_file())
        self.assertTrue((self.root / 'next-sync').is_file())
        self.assertFalse((self.root / 'data/.section11-state/transaction.json').exists())


def isolated_job(root):
    """The fake launchctl is a real subprocess in this isolated job group."""
    data = root / 'data'
    data.mkdir()
    home = root / 'synthetic-home'
    events = root / 'scheduler-events.txt'
    events.write_text('')
    (root / 'timer-active').write_text('yes')
    timer = REAL_TIMERS(data, home=home, platform='darwin')
    standard = timer.standard({})
    for key, value in standard['resources'].items():
        path = Path(key[5:])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    class Launchd(REAL_TIMERS):
        def __init__(self, data_dir):
            super().__init__(data_dir, home=home, platform='darwin')

        def command(self, argv, input=None):
            if argv[0] != 'launchctl':
                raise AssertionError(argv)
            return subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()),
                                   '--launchctl', str(root), *argv[1:]], capture_output=True, text=True, timeout=10)
    raw, files = fixture()
    install(data / 'section11', raw, files)
    write(data / 'section11', {SYNC.Distribution.RECEIPT: SYNC.Distribution.receipt(raw, {'tag': '2026.10.23', 'commit': 'a' * 40})})
    new_raw, new_files = fixture('9000.1')
    # A second descendant must also die if bootout is attempted.
    descendant = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(25)'])
    (root / 'descendant-pid').write_text(str(descendant.pid))
    try:
        with mock.patch.object(SYNC, 'LocalTimers', Launchd), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(new_raw, new_files, {'tag': '2026.10.24', 'commit': 'b' * 40})), \
                mock.patch('requests.sessions.Session.request', side_effect=AssertionError('no network')), \
                mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': 'local_scheduled', 'GITHUB_ACTIONS': ''}):
            (data / 'latest.json').write_text('data completed before maintenance')
            SYNC.auto_update_local(data, True, started_at=SYNC.datetime(2026, 11, 10, 12, tzinfo=SYNC.timezone.utc))
            assert SYNC._known_local_identity(data / 'section11')['tag'] == '2026.10.24'
            assert not (data / '.section11-state/transaction.json').exists()
            (root / 'completed').write_text('yes')
            with SYNC._distribution_lock(data):
                (root / 'next-sync').write_text('unblocked')
    finally:
        descendant.terminate()
        descendant.wait(timeout=5)


if __name__ == '__main__':
    if sys.argv[1:2] == ['--job']:
        isolated_job(Path(sys.argv[2]))
    elif sys.argv[1:2] == ['--launchctl']:
        root = Path(sys.argv[2])
        operation = sys.argv[3]
        with (root / 'scheduler-events.txt').open('a') as stream:
            stream.write(operation + '\n')
        if operation == 'bootout':
            (root / 'timer-active').write_text('no')
            os.killpg(os.getpgrp(), signal.SIGTERM)
        elif operation == 'bootstrap':
            (root / 'timer-active').write_text('yes')
        elif operation != 'print':
            raise AssertionError(operation)
    else:
        import unittest
        unittest.main()
