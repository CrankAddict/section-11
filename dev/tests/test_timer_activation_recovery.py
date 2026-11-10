"""Verified activation completion using captured, sanitized macOS readbacks.

Fixtures were captured read-only on macOS 26.6.2 arm64 on 2026-11-10.
Only home/UID and inherited environment were sanitized by the operator.
Tests substitute the synthetic installation paths and PID, never call launchd.
"""
import contextlib
import copy
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import SYNC, Offline, fixture, install, inventory, write
from test_timer_selfstop import platform_timers, scheduler_writes

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures/local-timer'


def readback(root, filename='loaded-running.txt'):
    content = (FIXTURES / filename).read_text()
    header, content = content.split('\n', 1)
    content = content.replace('/Users/USER/section11-data/.venv/bin/python3', sys.executable)
    content = content.replace('/Users/USER/section11-data', str(root))
    content = content.replace('/Users/USER', str(root / 'synthetic-home'))
    content = content.replace('UID', str(os.getuid())).replace('pid = 77681', 'pid = ' + str(os.getpid()))
    # The missing fixture queried a deliberately nonexistent label. Exercise
    # that captured diagnostic shape for the synthetic standard job.
    content = content.replace('com.section11.nonexistent-label', 'com.section11.sync')
    return SimpleNamespace(returncode=int(header.split()[-1]), stdout=content, stderr='')


class ActivationRecoveryTests(Offline):
    def setUp(self):
        super().setUp()
        base = platform_timers('darwin')
        class Timers(base):
            legacy = False
            response = None
            responses = []

            def plan(self, config, choice=None):
                plan = super().plan(config, choice)
                if self.legacy:
                    standard = self.standard(config)
                    plan.update(remove=[standard], create=standard)
                return plan

            def command(self, argv, input=None):
                if argv[:2] == ['launchctl', 'print']:
                    self.calls.append((argv, input))
                    if self.responses:
                        return self.responses.pop(0)
                    return self.response or readback(self.root)
                return super().command(argv, input)
        self.timer_class = Timers
        patcher = mock.patch.object(SYNC, 'LocalTimers', Timers)
        patcher.start()
        self.addCleanup(patcher.stop)
        environment = mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': '', 'GITHUB_ACTIONS': ''})
        environment.start()
        self.addCleanup(environment.stop)

    def interrupted(self, prior=True, module=SYNC):
        root = self.root
        timer = self.timer_class(root)
        timer.apply(timer.plan({}), root)
        raw, files = fixture()
        install(root / 'section11', raw, files)
        write(root, {'latest.json': b'newer private data', 'custom/personal': b'keep',
                     '.sync_config': b'{"auto_update":false}'})
        if prior:
            raw, files = fixture('9000.1')
            SYNC._install_local(root, raw, files, {'tag': '2026.10.24', 'commit': 'a' * 40},
                                SYNC._local_plan(root, raw, files))
        raw, files = fixture('9000.2')
        # Preserve old installer remove/create records even though unchanged.
        self.timer_class.legacy = True
        real_write = module._write_install_state
        def interrupted_write(state, name, value):
            real_write(state, name, value)
            if name == 'transaction.json' and value.get('phase') == 'timer-activation':
                raise SystemExit('synthetic abrupt activation stop')
        with mock.patch.object(module, 'LocalTimers', self.timer_class), \
                mock.patch.object(module, '_write_install_state', interrupted_write), \
                self.assertRaisesRegex(SystemExit, 'synthetic abrupt'):
            module._install_local(root, raw, files, {'tag': '2026.10.25', 'commit': 'b' * 40},
                                  module._local_plan(root, raw, files))
        self.timer_class.legacy = False
        self.timer_class.calls.clear()
        state = root / '.section11-state'
        record = json.loads((state / 'transaction.json').read_bytes())
        SYNC._write_install_state(state, 'auto-update.json', {
            'last_attempt': '2026-11-10', 'available_release': '2026.10.25',
            'available_tree': 'old preimage', 'available_entries': {}, 'available_timer_only': False})
        return state, record

    def assert_blocked(self, state):
        before = inventory(self.root)
        with self.assertRaisesRegex(SYNC.DistributionError, 'interrupted update: preserve transaction.json before sync'):
            SYNC._cleanup_staging(state)
        self.assertEqual(inventory(self.root), before)
        self.assertEqual(scheduler_writes(self.timer_class.calls), [])

    def assert_completed(self, state, record):
        self.assertFalse((state / 'transaction.json').exists())
        self.assertFalse((state / record['transaction']).exists())
        self.assertEqual(SYNC._previous_install(self.root)[0], {k: v for k, v in record.items() if k != 'phase'})
        self.assertEqual(json.loads((state / 'auto-update.json').read_bytes()), {'last_attempt': '2026-11-10'})
        if record['obsolete_archive']:
            self.assertFalse((state / record['obsolete_archive']).exists())
        self.assertEqual((self.root / 'latest.json').read_bytes(), b'newer private data')
        self.assertEqual((self.root / 'custom/personal').read_bytes(), b'keep')
        self.assertEqual(scheduler_writes(self.timer_class.calls), [])
        with SYNC._distribution_lock(self.root):
            pass

    def test_timer_started_run_completes_and_unblocks_without_scheduler_writes(self):
        state, record = self.interrupted()
        with mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': 'local_scheduled'}):
            with SYNC._distribution_lock(self.root):
                pass
        self.assert_completed(state, record)

    def test_first_install_without_previous_pointer_completes(self):
        state, record = self.interrupted(prior=False)
        SYNC._cleanup_staging(state)
        self.assert_completed(state, record)

    def test_terminal_bootstrap_update_completes_old_transaction_then_installs_fix(self):
        state, record = self.interrupted()
        self.timer_class.response = readback(self.root, 'loaded-idle.txt')
        raw, files = fixture('9000.3')
        with mock.patch.object(SYNC.Path, 'cwd', return_value=self.root), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(raw, files, {'tag': '2026.10.26', 'commit': 'c' * 40})), \
                mock.patch('builtins.input', return_value='y'), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertTrue(SYNC.do_update(), output.getvalue())
        self.assertEqual(SYNC._known_local_identity(self.root / 'section11')['tag'], '2026.10.26')
        self.assertFalse((state / 'transaction.json').exists())
        self.assertEqual(scheduler_writes(self.timer_class.calls), [])
        self.assertEqual((self.root / 'latest.json').read_bytes(), b'newer private data')

    def test_status_never_reconciles(self):
        state, record = self.interrupted()
        before = inventory(self.root)
        raw, files = fixture('9000.3')
        with mock.patch.object(SYNC.Path, 'cwd', return_value=self.root), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(raw, files, {'tag': '2026.10.26', 'commit': 'c' * 40})), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(SYNC.do_update(status_only=True))
        self.assertEqual(inventory(self.root), before)
        self.assertEqual(self.timer_class.calls, [])

    def test_terminal_bootstrap_single_command_loads_missing_job_and_installs_fix(self):
        state, record = self.interrupted()
        self.timer_class.responses = [readback(self.root, 'not-loaded.txt'), readback(self.root, 'loaded-idle.txt')]
        raw, files = fixture('9000.3')
        with mock.patch.object(SYNC.Path, 'cwd', return_value=self.root), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(raw, files, {'tag': '2026.10.26', 'commit': 'c' * 40})), \
                mock.patch('builtins.input', return_value='y'), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertTrue(SYNC.do_update(), output.getvalue())
        self.assertEqual(SYNC._known_local_identity(self.root / 'section11')['tag'], '2026.10.26')
        self.assertFalse((state / 'transaction.json').exists())
        writes = scheduler_writes(self.timer_class.calls)
        self.assertEqual(writes, [['launchctl', 'bootstrap', 'gui/' + str(os.getuid()),
                                  str(self.root / 'synthetic-home/Library/LaunchAgents/com.section11.sync.plist')]])
        self.assertEqual([a[1] for a, _ in self.timer_class.calls[:3]], ['print', 'bootstrap', 'print'])
        self.assertEqual((self.root / 'latest.json').read_bytes(), b'newer private data')

    def test_missing_job_is_not_loaded_before_all_preimages_pass(self):
        state, record = self.interrupted()
        self.timer_class.response = readback(self.root, 'not-loaded.txt')
        SYNC._write_install_state(state, 'transaction.json', dict(record, archive_digest='0' * 64))
        self.assert_blocked(state)
        self.assertEqual(self.timer_class.calls, [])

    def test_activation_without_confirming_readback_preserves_transaction(self):
        state, record = self.interrupted()
        before = inventory(self.root)
        self.timer_class.responses = [readback(self.root, 'not-loaded.txt'),
                                     SimpleNamespace(returncode=1, stdout='', stderr='synthetic ambiguous readback')]
        with self.assertRaisesRegex(SYNC.DistributionError, 'interrupted update'):
            SYNC._cleanup_staging(state)
        self.assertEqual(inventory(self.root), before)
        self.assertEqual(len(scheduler_writes(self.timer_class.calls)), 1)

    def test_each_record_digest_inventory_and_shape_mismatch_keeps_block(self):
        state, record = self.interrupted()
        changes = {
            'installed_tree': '0' * 64, 'installed_entries': {}, 'installed_inventory': {},
            'previous_tree': '0' * 64, 'previous_entries': {}, 'archive_digest': '0' * 64,
            'archive_members': {}, 'timers_digest': '0' * 64, 'installed_tag': 'not-a-date',
            'config_after': False, 'config_changed': 'false', 'schema': True,
            'transaction': '../unsafe', 'phase': 'prepared', 'cleanup': [],
            'obsolete_archive': 'transaction-' + 'f' * 32 + '.zip'}
        for key, value in changes.items():
            with self.subTest(field=key):
                SYNC._write_install_state(state, 'transaction.json', dict(record, **{key: value}))
                self.assert_blocked(state)
        for bad in ([record], {}, {k: v for k, v in record.items() if k != 'archive_digest'},
                    dict(record, unknown=True), dict(record, installed_tag='2026.10.26')):
            with self.subTest(record=type(bad).__name__):
                SYNC._write_install_state(state, 'transaction.json', bad)
                self.assert_blocked(state)
        (state / 'transaction.json').write_text('{malformed')
        self.assert_blocked(state)

    def test_bytes_and_modes_changed_after_interruption_keep_block(self):
        state, record = self.interrupted()
        transaction = state / record['transaction']
        for path in (self.root / 'section11/LICENSE', transaction / 'timers.json',
                     transaction / 'recovery.zip', transaction / 'old/LICENSE'):
            with self.subTest(path=path.relative_to(self.root)):
                original = path.read_bytes()
                path.write_bytes(original + b'changed')
                self.assert_blocked(state)
                path.write_bytes(original)
        path = self.root / 'section11/LICENSE'
        mode = path.stat().st_mode & 0o7777
        path.chmod(mode ^ 0o100)
        self.assert_blocked(state)
        path.chmod(mode)
        (self.root / 'sync.py').write_text('later root tool')
        self.assert_blocked(state)

    def test_missing_or_different_valid_previous_pointer_keeps_block(self):
        state, record = self.interrupted()
        previous = json.loads((state / 'previous.json').read_bytes())
        alternate = 'transaction-' + 'e' * 32
        os.rename(state / (previous['transaction'] + '.zip'), state / (alternate + '.zip'))
        SYNC._write_install_state(state, 'previous.json', dict(previous, transaction=alternate))
        self.assert_blocked(state)
        (state / 'previous.json').unlink()
        self.assert_blocked(state)

    def test_ambiguous_missing_disk_drift_or_wrong_loaded_definition_keeps_block(self):
        state, record = self.interrupted()
        self.timer_class.response = readback(self.root, 'not-loaded.txt')
        self.timer_class.response.stdout = self.timer_class.response.stdout.replace('com.section11.sync', 'different.job')
        self.assert_blocked(state)
        actual = readback(self.root)
        for old, new in (('run interval = 60 seconds', 'run interval = 300 seconds'),
                         ('--lockfile', '--other'), ('local_scheduled', 'manual'),
                         ('properties = runatload | inferred program', 'properties = inferred program'),
                         ('working directory = ' + str(self.root), 'working directory = /different'),
                         ('program = ' + sys.executable, 'program = /different'),
                         ('stdout path = ', 'wrong stdout path = '),
                         ('XPC_SERVICE_NAME => com.section11.sync', 'XPC_SERVICE_NAME => different.job'),
                         ('\tenvironment = {', '\tenvironment = {\n\t\tSECTION11_EXPORT_MODE => local_scheduled'),
                         ('\tactive count = 1', '\textra block = {\n\t\textra = 1\n\t\textra = 2\n\t}\n\tactive count = 1'),
                         ('\tactive count = 1', '\textra block = {\n\t\tmalformed\n\t}\n\tactive count = 1'),
                         ('\tpath = ', '\tpath = /duplicate\n\tpath = ')):
            with self.subTest(change=old):
                self.timer_class.response = SimpleNamespace(returncode=0, stdout=actual.stdout.replace(old, new), stderr='')
                self.assert_blocked(state)
        self.timer_class.response = SimpleNamespace(returncode=0, stdout=actual.stdout[:-3], stderr='')
        self.assert_blocked(state)
        self.timer_class.response = actual
        plist = self.root / 'synthetic-home/Library/LaunchAgents/com.section11.sync.plist'
        plist.write_text(plist.read_text().replace('<integer>60</integer>', '<integer>300</integer>'))
        self.assert_blocked(state)

    def test_runtime_extensions_do_not_change_definition_proof(self):
        state, record = self.interrupted()
        response = readback(self.root)
        response.stdout = response.stdout.replace('active count = 1',
            'future runtime field = 42\n\tevent triggers = {\n\t\tinterval = {\n\t\t\ttype = timer\n\t\t}\n\t}\n\tactive count = 1', 1)
        response.stdout = response.stdout.replace('OSLogRateLimit => 64', 'OSLogRateLimit => 64\n\t\tLAUNCHD_ADDED_KEY => value')
        response.stdout = response.stdout.replace('runatload | inferred program', 'runatload | inferred program | extra property')
        response.stdout = response.stdout.replace('\t\tXPC_SERVICE_NAME => com.section11.sync\n', '')
        self.timer_class.response = response
        SYNC._cleanup_staging(state)
        self.assert_completed(state, record)

    def test_scheduled_recovery_requires_own_pid_and_running_state(self):
        state, record = self.interrupted()
        with mock.patch.dict(os.environ, {'SECTION11_EXPORT_MODE': 'local_scheduled'}):
            self.timer_class.response = readback(self.root, 'not-loaded.txt')
            self.assert_blocked(state)
            self.timer_class.response = readback(self.root, 'loaded-idle.txt')
            self.assert_blocked(state)
            self.timer_class.response = readback(self.root)
            self.timer_class.response.stdout = self.timer_class.response.stdout.replace('pid = ' + str(os.getpid()), 'pid = 999999')
            self.assert_blocked(state)

    def test_rename_completed_before_crash_is_reconciled_without_overwrite(self):
        state, record = self.interrupted()
        os.rename(state / record['transaction'] / 'recovery.zip', state / (record['transaction'] + '.zip'))
        SYNC._cleanup_staging(state)
        self.assert_completed(state, record)

    def test_crash_after_previous_publication_finishes_normal_cleanup(self):
        state, record = self.interrupted()
        original = SYNC._write_install_state
        def crash(state, name, value):
            original(state, name, value)
            if name == 'previous.json':
                raise SystemExit('synthetic completion crash')
        with mock.patch.object(SYNC, '_write_install_state', crash), self.assertRaises(SystemExit):
            SYNC._cleanup_staging(state)
        SYNC._cleanup_staging(state)
        self.assert_completed(state, record)

    def test_readback_inspection_failure_keeps_every_byte(self):
        state, record = self.interrupted()
        with mock.patch.object(self.timer_class, 'command', side_effect=RuntimeError('synthetic inspection failure')):
            self.assert_blocked(state)

    def test_changed_or_malformed_timer_policy_keeps_block(self):
        state, record = self.interrupted()
        for value in (False, 1, 'true'):
            with self.subTest(policy=value):
                (self.root / '.sync_config').write_text(json.dumps({'auto_sync': value}))
                self.assert_blocked(state)


if __name__ == '__main__':
    import unittest
    unittest.main()
