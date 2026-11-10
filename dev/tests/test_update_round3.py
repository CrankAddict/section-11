"""Offline refresh ownership and opt-in local installation lifecycle."""
import contextlib
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from unittest import mock

from test_update_prototype import D, SYNC, ROOT, Offline, install, inventory, write
from test_update_path_fixes import ReleaseHTTP
from test_alignment_recovery import recovery_bytes


# RefreshTests PR contracts are replaced by direct-commit acceptance in test_b2_hosted.py.


class LocalAutoTests(Offline):
    def setUp(self):
        super().setUp()
        self.wire = ReleaseHTTP(2)
        self.target = self.root / 'section11'
        install(self.target, self.wire.raw[0], self.wire.files[0])
        (self.target / D.RECEIPT).write_bytes(D.receipt(self.wire.raw[0], self.wire.identity(0)))
        self.protected = {'latest.json': b'new successful sync', 'history.json': b'keep history',
                          'custom/patch.py': b'custom', 'DOSSIER.md': b'dossier',
                          'maps/weather/page.png': b'map', 'archive/day.json': b'archive',
                          '.sync_config.json': b'{"auto_update": true}'}
        write(self.root, self.protected)
        self.clock = mock.patch.object(SYNC, 'datetime', wraps=datetime).start()
        self.addCleanup(mock.patch.stopall)
        self.clock.now.return_value = datetime(2026, 10, 24, 23, 59, tzinfo=timezone.utc)
        self.env = mock.patch.dict(os.environ, {'GITHUB_ACTIONS': ''}).start()
        mock.patch.object(SYNC, '__file__', str(self.target / 'examples/sync.py')).start()

    def run_auto(self, enabled=True, index=1, error=None):
        output = io.StringIO()
        with mock.patch.object(SYNC, '_fetch_verified_release',
                               return_value=(self.wire.raw[index], self.wire.files[index], self.wire.identity(index)),
                               side_effect=error) as fetch, \
                mock.patch('builtins.input', side_effect=AssertionError('no prompt allowed')), \
                contextlib.redirect_stdout(output):
            SYNC.auto_update_local(self.root, enabled)
        self.assertLessEqual(len(output.getvalue().splitlines()), 1)
        for path, content in self.protected.items():
            self.assertEqual((self.root / path).read_bytes(), content)
        return output.getvalue(), fetch

    def rollback(self):
        with mock.patch.object(SYNC.Path, 'cwd', return_value=self.root), contextlib.redirect_stdout(io.StringIO()):
            return SYNC.do_rollback()

    def test_disabled_and_actions_have_no_requests_or_state(self):
        before = inventory(self.root)
        self.run_auto(False)[1].assert_not_called()
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}):
            self.run_auto(True)[1].assert_not_called()
        self.assertEqual(inventory(self.root), before)

    def test_toggle_rejects_truthy_non_boolean(self):
        result, fetch = self.run_auto('false')
        self.assertIn('JSON boolean', result)
        fetch.assert_not_called()

    def test_verified_install_no_prompt_and_ten_minute_interval(self):
        before = inventory(self.target)
        result, _ = self.run_auto()
        self.assertIn('installed ' + self.wire.tags[0] + ' -> ' + self.wire.tags[1], result)
        self.assertEqual(D.tree(self.target), (self.wire.raw[1], self.wire.files[1]))
        record, _, _, _ = SYNC._previous_install(self.root)
        self.assertEqual(recovery_bytes(self.root, record), before)
        self.run_auto(index=2)[1].assert_not_called()
        self.clock.now.return_value = datetime(2026, 10, 25, 0, 8, 59, tzinfo=timezone.utc)
        self.run_auto(index=2)[1].assert_not_called()
        self.clock.now.return_value = datetime(2026, 10, 25, 0, 9, tzinfo=timezone.utc)
        self.assertIn('installed', self.run_auto(index=2)[0])
        self.assertEqual(len(list((self.root / '.section11-state').glob('transaction-*'))), 1)
        self.assertTrue(self.rollback())
        self.assertEqual(D.tree(self.target), (self.wire.raw[1], self.wire.files[1]))

    def test_real_bounded_fetch_transport_is_used(self):
        with self.wire.intercepted(), contextlib.redirect_stdout(io.StringIO()):
            SYNC.auto_update_local(self.root, True)
        self.assertEqual(D.tree(self.target), (self.wire.raw[2], self.wire.files[2]))
        self.assertEqual(len(self.wire.calls), 5)

    def test_receiptless_equal_release_needs_explicit_adoption(self):
        (self.target / D.RECEIPT).unlink()
        self.assertEqual(self.run_auto(index=0)[0], '')
        self.assertIsNone(D.read_receipt(self.target, self.wire.raw[0]))
        self.clock.now.return_value = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
        self.run_auto(index=1)[1].assert_not_called()

    def test_ordinary_orphan_and_unknown_file_removed_without_prompt(self):
        old = dict(self.wire.files[0], **{'obsolete.txt': b'old managed file'})
        from test_update_prototype import manifest
        raw = manifest(old)
        install(self.target, raw, old)
        (self.target / D.RECEIPT).write_bytes(D.receipt(raw, self.wire.identity(0)))
        write(self.target, {'personal-note.txt': b'keep'})
        self.assertIn('installed', self.run_auto()[0])
        self.assertFalse((self.target / 'obsolete.txt').exists())
        self.assertFalse((self.target / 'personal-note.txt').exists())
        self.assertTrue(self.rollback())
        self.assertEqual((self.target / 'obsolete.txt').read_bytes(), b'old managed file')
        self.assertEqual((self.target / 'personal-note.txt').read_bytes(), b'keep')

    def test_drift_after_update_refuses_rollback_and_preserves_edit(self):
        self.run_auto()
        (self.target / 'LICENSE').write_bytes(b'edited after update')
        self.assertFalse(self.rollback())
        self.assertEqual((self.target / 'LICENSE').read_bytes(), b'edited after update')

    def test_clock_regression_and_interrupted_journal_never_fetch(self):
        self.run_auto()
        self.clock.now.return_value = datetime(2026, 10, 23, tzinfo=timezone.utc)
        self.run_auto()[1].assert_not_called()
        (self.root / '.section11-state/transaction.json').write_text('{}')
        message, fetch = self.run_auto()
        self.assertIn('interrupted update', message)
        fetch.assert_not_called()

    def test_network_failure_preserves_install_and_counts_attempt(self):
        before = inventory(self.target)
        message, _ = self.run_auto(error=SYNC.requests.ConnectionError('synthetic\ntransport failure'))
        self.assertIn('sync result retained; synthetic transport failure', message)
        self.assertEqual(inventory(self.target), before)
        self.run_auto()[1].assert_not_called()

    def test_invalid_release_and_drift_do_not_install(self):
        before = inventory(self.target)
        self.wire.files[1]['LICENSE'] = b'wrong bytes'
        self.assertIn('hash mismatch', self.run_auto()[0])
        self.assertEqual(inventory(self.target), before)
        self.clock.now.return_value = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
        (self.target / 'LICENSE').write_bytes(b'local edit')
        self.assertIn('hash mismatch', self.run_auto()[0])
        self.assertEqual((self.target / 'LICENSE').read_bytes(), b'local edit')

    def test_never_downgrades_or_installs_changed_same_date(self):
        self.run_auto(index=2)
        before = inventory(self.target)
        self.clock.now.return_value = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
        self.assertIn('downgrade refused', self.run_auto(index=1)[0])
        self.assertEqual(inventory(self.target), before)
        self.clock.now.return_value = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        identity = dict(self.wire.identity(1), tag=self.wire.tags[2])
        with mock.patch.object(self.wire, 'identity', return_value=identity):
            self.assertIn('same-date changed release', self.run_auto(index=1)[0])
        self.assertEqual(inventory(self.target), before)

    def test_rollback_preserves_later_custom_edits_and_skips_rejected_release(self):
        write(self.root, {'custom/note.txt': b'before'})
        self.run_auto()
        write(self.root, {'custom/note.txt': b'after', 'custom/new.txt': b'new'})
        self.assertTrue(self.rollback())
        self.assertEqual(D.tree(self.target), (self.wire.raw[0], self.wire.files[0]))
        self.assertEqual((self.root / 'custom/note.txt').read_bytes(), b'after')
        self.assertEqual((self.root / 'custom/new.txt').read_bytes(), b'new')
        self.assertFalse((self.root / '.section11-state/previous.json').exists())
        self.clock.now.return_value = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
        self.assertIn('remains skipped', self.run_auto()[0])
        self.clock.now.return_value = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        self.assertIn('installed', self.run_auto(index=2)[0])

    def test_developer_checkout_or_changed_backup_refuses_rollback(self):
        self.run_auto()
        before = inventory(self.root)
        with mock.patch.object(SYNC, '_is_git_checkout', return_value=True):
            self.assertFalse(self.rollback())
        self.assertEqual(inventory(self.root), before)
        record = SYNC._previous_install(self.root)[0]
        (self.root / '.section11-state' / (record['transaction'] + '.zip')).write_bytes(b'corrupt')
        before = inventory(self.target)
        self.assertFalse(self.rollback())
        self.assertEqual(inventory(self.target), before)

    def test_rollback_cli_needs_neither_credentials_nor_network(self):
        self.run_auto()
        with mock.patch.object(SYNC.Path, 'cwd', return_value=self.root), \
                mock.patch.object(sys, 'argv', ['sync.py', '--rollback']), \
                mock.patch.object(SYNC, 'IntervalsSync', side_effect=AssertionError('no sync')), \
                contextlib.redirect_stdout(io.StringIO()):
            SYNC.main()
        self.assertEqual(D.tree(self.target), (self.wire.raw[0], self.wire.files[0]))

    def test_switch_failure_restores_old_install_without_blocking_next_sync(self):
        before = inventory(self.target)
        rename = SYNC.os.rename
        def fail_new(source, destination):
            if source.name == 'new':
                raise OSError('synthetic switch failure')
            return rename(source, destination)
        with mock.patch.object(SYNC.os, 'rename', side_effect=fail_new):
            self.assertIn('synthetic switch failure', self.run_auto()[0])
        self.assertEqual(inventory(self.target), before)
        self.assertFalse((self.root / '.section11-state/transaction.json').exists())
        with SYNC._distribution_lock(self.root):
            pass

    def test_post_switch_failure_without_timer_restores_old_tree_and_previous_pointer(self):
        self.protected['.sync_config.json'] = b'{"auto_update": true, "auto_sync": false}'
        (self.root / '.sync_config.json').write_bytes(self.protected['.sync_config.json'])
        self.run_auto()
        before = inventory(self.target)
        previous = (self.root / '.section11-state/previous.json').read_bytes()
        self.clock.now.return_value = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
        state_write = SYNC._write_install_state
        failed = False
        def fail_once(state, name, value):
            nonlocal failed
            if name == 'previous.json' and not failed:
                failed = True
                raise OSError('synthetic metadata failure')
            return state_write(state, name, value)
        with mock.patch.object(SYNC, '_write_install_state', side_effect=fail_once):
            self.assertIn('synthetic metadata failure', self.run_auto(index=2)[0])
        self.assertEqual(inventory(self.target), before)
        self.assertEqual((self.root / '.section11-state/previous.json').read_bytes(), previous)
        self.assertTrue(self.rollback())

    def test_post_refresh_metadata_failure_preserves_journal_without_another_write(self):
        self.run_auto()
        self.protected['.sync_config.json'] = b'{"auto_update":true,"check_interval_minutes":5}'
        write(self.root, {'.sync_config.json': self.protected['.sync_config.json']})
        previous = (self.root / '.section11-state/previous.json').read_bytes()
        self.clock.now.return_value = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
        state_write, command = SYNC._write_install_state, SYNC.LocalTimers.command
        writes = []
        def fail_previous(state, name, value):
            if name == 'previous.json':
                raise OSError('synthetic metadata failure')
            return state_write(state, name, value)
        def record(adapter, argv, input=None):
            if argv != ['crontab', '-l']:
                writes.append(argv)
            return command(adapter, argv, input=input)
        with mock.patch.object(SYNC, '_write_install_state', side_effect=fail_previous), \
                mock.patch.object(SYNC.LocalTimers, 'command', record):
            self.assertIn('synthetic metadata failure', self.run_auto(index=2)[0])
            self.assertEqual(writes, [['crontab', '-']])
            self.assertEqual(D.tree(self.target), (self.wire.raw[2], self.wire.files[2]))
            self.assertEqual((self.root / '.section11-state/previous.json').read_bytes(), previous)
            journal = self.root / '.section11-state/transaction.json'
            self.assertEqual(json.loads(journal.read_bytes())['phase'], 'timer-activation')
            before = inventory(self.root)
            message, fetch = self.run_auto(index=2)
            self.assertIn('interrupted update', message)
            fetch.assert_not_called()
            self.assertEqual(writes, [['crontab', '-']])
            self.assertEqual(inventory(self.root), before)

    def test_lock_contention_does_not_change_sync_or_install(self):
        before = inventory(self.target)
        with SYNC._distribution_lock(self.root):
            self.assertIn('sync result retained', self.run_auto()[0])
        self.assertEqual(inventory(self.target), before)


class SuccessfulSyncHookTests(Offline):
    def invoke(self, extra=(), config=None, fail=False):
        if config is not None:
            (self.root / '.sync_config').write_text(json.dumps(config))
        instance = mock.Mock()
        instance.should_generate_history.return_value = False
        instance.collect_training_data.return_value = {}
        instance.save_local_outputs.side_effect = RuntimeError('sync failed') if fail else None
        exists, open_file = os.path.exists, open
        def config_open(path, *args, **kwargs):
            return open_file(self.root / path if path == '.sync_config' else path, *args, **kwargs)
        with mock.patch.object(SYNC.Path, 'cwd', return_value=self.root), \
                mock.patch.object(SYNC.os.path, 'exists', side_effect=lambda p: config is not None if p == '.sync_config' else exists(p)), \
                mock.patch('builtins.open', side_effect=config_open), \
                mock.patch.object(SYNC, 'IntervalsSync', return_value=instance), \
                mock.patch.object(SYNC, '_rotate_log_if_needed'), \
                mock.patch.object(SYNC, 'auto_update_local') as auto, \
                mock.patch.object(SYNC, 'notify_if_updates_available') as notice, \
                mock.patch.object(sys, 'argv', ['sync.py', '--athlete-id', 'fixture', '--intervals-key', 'fake',
                                              '--output', str(self.root / 'latest.json'), *extra]), \
                contextlib.redirect_stdout(io.StringIO()):
            if fail:
                with self.assertRaisesRegex(RuntimeError, 'sync failed'):
                    SYNC._main(installation_root=self.root, distribution_locked=True)
            else:
                SYNC._main(installation_root=self.root, distribution_locked=True)
        return auto, notice

    def test_default_off_and_cli_config_overrides(self):
        self.invoke()[0].assert_called_once_with(self.root, False, _locked=True, advisory_only=True, started_at=SYNC.datetime.now(SYNC.timezone.utc))
        self.invoke(config={'auto_update': False})[0].assert_called_once_with(self.root, False, _locked=True, advisory_only=True, started_at=SYNC.datetime.now(SYNC.timezone.utc))
        self.invoke(config={'auto_update': True})[0].assert_called_once_with(self.root, True, _locked=True, advisory_only=False, started_at=SYNC.datetime.now(SYNC.timezone.utc))
        self.invoke(extra=['--auto-update'])[0].assert_called_once()
        self.invoke(extra=['--no-auto-update'], config={'auto_update': True})[0].assert_not_called()

    def test_failed_sync_still_attempts_auto_update(self):
        auto, notice = self.invoke(extra=['--auto-update'], fail=True)
        auto.assert_called_once_with(self.root, True, _locked=True, advisory_only=False, started_at=SYNC.datetime.now(SYNC.timezone.utc))
        notice.assert_not_called()
