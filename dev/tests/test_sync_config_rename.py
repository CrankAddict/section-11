"""Local filename compatibility, synthetic credentials and offline rollback."""
import contextlib
import errno
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from _harness import load_module_by_path
from test_update_prototype import D, SYNC, ROOT, Offline, fixture, write, inventory, validate_data

PUSH = load_module_by_path('rename_push', ROOT / 'examples/agentic/push.py')
PULL = load_module_by_path('rename_pull', ROOT / 'examples/agentic/pull.py')
OLD = ROOT / 'dev/fixtures/b1-legacy/sync-7db221d8.py'
CONFIG = b'{"athlete_id":"i123", "intervals_key":"synthetic-key", "auto_sync":false, "custom_option":17}\n'


class ConfigRename(Offline):
    def setUp(self):
        super().setUp()
        self.old = self.root / '.sync_config.json'
        self.new = self.root / '.sync_config'
        patch = mock.patch.dict(os.environ, {'GITHUB_ACTIONS': '', 'ATHLETE_ID': '', 'INTERVALS_KEY': '',
                                            'GITHUB_TOKEN': '', 'GITHUB_REPO': ''})
        patch.start()
        self.addCleanup(patch.stop)

    def normal_run(self, extra=()):
        instance = mock.Mock()
        instance.request_budget.degraded = True
        output = io.StringIO()
        with contextlib.chdir(self.root), \
                mock.patch.object(sys, 'argv', ['sync.py', '--output', 'latest.json', '--no-auto-update', *extra]), \
                mock.patch.object(SYNC, 'IntervalsSync', return_value=instance) as constructor, \
                mock.patch.object(SYNC, '_run_sync') as run, \
                mock.patch.object(SYNC, '_rotate_log_if_needed'), contextlib.redirect_stdout(output):
            SYNC._main()
        run.assert_called_once()
        return constructor.call_args, output.getvalue()

    def test_old_only_atomic_migration_and_idempotence(self):
        self.old.write_bytes(CONFIG)
        before = self.old.stat()
        args, output = self.normal_run()
        self.assertEqual(args.args[:2], ('i123', 'synthetic-key'))
        self.assertFalse(self.old.exists())
        self.assertEqual(self.new.read_bytes(), CONFIG)
        self.assertEqual(self.new.stat().st_ino, before.st_ino)
        self.assertEqual(self.new.stat().st_mode, before.st_mode)
        self.assertIn('renamed .sync_config.json to .sync_config.', output)
        with mock.patch.object(SYNC.os, 'rename') as rename:
            self.normal_run()
        rename.assert_not_called()
        self.assertEqual(self.new.read_bytes(), CONFIG)

    def test_new_only_and_cli_override(self):
        self.new.write_bytes(CONFIG)
        args, _ = self.normal_run(['--athlete-id', 'i456', '--intervals-key', 'synthetic-cli'])
        self.assertEqual(args.args[:2], ('i456', 'synthetic-cli'))
        self.assertFalse(self.old.exists())
        self.assertEqual(self.new.read_bytes(), CONFIG)

    def test_both_files_new_wins_and_neither_is_changed(self):
        self.old.write_bytes(b'{"athlete_id":"i999", "intervals_key":"synthetic-other"}')
        self.new.write_bytes(CONFIG)
        before = inventory(self.root)
        args, output = self.normal_run()
        self.assertEqual(args.args[:2], ('i123', 'synthetic-key'))
        self.assertEqual(inventory(self.root), before)
        self.assertIn('.sync_config.json was kept', output)

    def test_failed_rename_uses_old_retries_and_then_migrates(self):
        self.old.write_bytes(CONFIG)
        # Injected failures only: no actual filesystem permission boundary is probed.
        for error in (PermissionError(errno.EACCES, 'synthetic refusal'),
                      OSError(errno.EROFS, 'synthetic read-only folder'),
                      OSError(errno.EIO, 'synthetic IO error')):
            with self.subTest(error=error.errno), mock.patch.object(SYNC.os, 'rename', side_effect=error) as rename:
                for _ in range(2):
                    args, output = self.normal_run()
                    self.assertEqual(args.args[:2], ('i123', 'synthetic-key'))
                    self.assertIn('using it for this run. Will retry next run', output)
                self.assertEqual(rename.call_count, 2)
                self.assertEqual(self.old.read_bytes(), CONFIG)
                self.assertFalse(self.new.exists())
        self.normal_run()
        self.assertEqual(self.new.read_bytes(), CONFIG)
        self.assertFalse(self.old.exists())

    def test_new_file_appearing_before_locked_rename_is_used_and_preserved(self):
        self.old.write_bytes(CONFIG)
        other = b'{"athlete_id":"i789", "intervals_key":"synthetic-concurrent"}'
        @contextlib.contextmanager
        def lock(*args, **kwargs):
            self.new.write_bytes(other)
            yield True
        with mock.patch.object(SYNC, '_distribution_lock', lock), mock.patch.object(SYNC.os, 'rename') as rename:
            args, _ = self.normal_run()
        rename.assert_not_called()
        self.assertEqual(args.args[:2], ('i789', 'synthetic-concurrent'))
        self.assertEqual(self.old.read_bytes(), CONFIG)
        self.assertEqual(self.new.read_bytes(), other)

    def test_environment_only_does_not_create_config_and_hosted_does_not_migrate(self):
        with mock.patch.dict(os.environ, {'ATHLETE_ID': 'i789', 'INTERVALS_KEY': 'synthetic-env'}):
            args, _ = self.normal_run()
        self.assertEqual(args.args[:2], ('i789', 'synthetic-env'))
        self.assertEqual(inventory(self.root), {})
        self.old.write_bytes(CONFIG)
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), mock.patch.object(SYNC.os, 'rename') as rename:
            self.normal_run()
        rename.assert_not_called()
        self.assertFalse(self.new.exists())

    def test_setup_writes_new_name_and_preserves_optional_fields_and_old_file(self):
        self.old.write_bytes(CONFIG)
        with contextlib.chdir(self.root), mock.patch.object(sys, 'argv', ['sync.py', '--setup']), \
                mock.patch('builtins.input', side_effect=['i456', 'synthetic-setup', '', '', 'sun', 'run:hr']), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            SYNC._main()
        config = json.loads(self.new.read_bytes())
        self.assertEqual(config['intervals_key'], 'synthetic-setup')
        self.assertEqual(config['custom_option'], 17)
        self.assertEqual(config['week_start'], 'sun')
        self.assertFalse(config['auto_sync'])
        self.assertEqual(self.old.read_bytes(), CONFIG)
        self.assertIn('Config saved to .sync_config', output.getvalue())

    def test_push_and_pull_new_first_legacy_fallback_and_no_migration(self):
        args = SimpleNamespace(athlete_id=None, api_key=None)
        for module in (PUSH, PULL):
            with self.subTest(module=module.__name__), contextlib.chdir(self.root):
                self.new.unlink(missing_ok=True)
                self.old.write_bytes(CONFIG)
                self.assertEqual(module._load_credentials(args), ('i123', 'synthetic-key'))
                self.assertFalse(self.new.exists())
                self.new.write_text('{"athlete_id":"i456","intervals_key":"synthetic-new"}')
                self.assertEqual(module._load_credentials(args), ('i456', 'synthetic-new'))
                self.assertEqual(self.old.read_bytes(), CONFIG)
                self.old.unlink()
                self.assertEqual(module._load_credentials(args), ('i456', 'synthetic-new'))
                self.assertEqual(module._load_credentials(SimpleNamespace(athlete_id='i789', api_key='synthetic-cli')),
                                 ('i789', 'synthetic-cli'))

    @contextlib.contextmanager
    def compatible_config(self, path, kind):
        content = CONFIG
        target = self.root / '.synthetic-config-target'
        if kind == 'duplicate':
            content = CONFIG.replace(b'"athlete_id":"i123"',
                                     b'"athlete_id":"i999", "athlete_id":"i123"')
            content = content.replace(b'{', b'{"week_start":"mon", "week_start":"sun", ', 1)
        elif kind == 'large':
            content += b' ' * (1024 * 1024)
        if kind in ('symlink', 'hardlink'):
            target.write_bytes(content)
            if kind == 'symlink':
                path.symlink_to(target.name)
            else:
                os.link(target, path)
        else:
            path.write_bytes(content)
        try:
            yield content
        finally:
            path.unlink(missing_ok=True)
            target.unlink(missing_ok=True)

    def test_legacy_linked_configs_sync_without_migration(self):
        for kind in ('symlink', 'hardlink'):
            with self.subTest(kind=kind), self.compatible_config(self.old, kind) as content:
                before = self.old.lstat()
                args, output = self.normal_run()
                self.assertEqual(args.args[:2], ('i123', 'synthetic-key'))
                self.assertFalse(self.new.exists())
                self.assertEqual(self.old.read_bytes(), content)
                after = self.old.lstat()
                self.assertEqual((after.st_ino, after.st_mode, after.st_nlink),
                                 (before.st_ino, before.st_mode, before.st_nlink))
                self.assertNotIn('Section 11:', output)

    def test_new_symlink_wins_and_keeps_one_both_files_warning(self):
        self.old.write_bytes(b'{"athlete_id":"i999", "intervals_key":"synthetic-unused"}')
        with self.compatible_config(self.new, 'symlink') as content:
            before = inventory(self.root)
            args, output = self.normal_run()
            self.assertEqual(args.args[:2], ('i123', 'synthetic-key'))
            self.assertTrue(self.new.is_symlink())
            self.assertEqual(self.new.read_bytes(), content)
            self.assertEqual(inventory(self.root), before)
            self.assertEqual(output.count('.sync_config.json was kept'), 1)

    def test_duplicate_keys_sync_with_last_value_and_no_migration(self):
        for path in (self.old, self.new):
            with self.subTest(name=path.name), self.compatible_config(path, 'duplicate') as content:
                args, _ = self.normal_run()
                self.assertEqual(args.args[:2], ('i123', 'synthetic-key'))
                self.assertEqual(args.kwargs['week_start_day'], 6)
                self.assertEqual(path.read_bytes(), content)
                self.assertFalse((self.new if path == self.old else self.old).exists())

    def test_large_configs_sync_without_a_new_size_limit(self):
        for path in (self.old, self.new):
            with self.subTest(name=path.name), self.compatible_config(path, 'large') as content:
                args, _ = self.normal_run()
                self.assertEqual(args.args[:2], ('i123', 'synthetic-key'))
                self.assertEqual(path.read_bytes(), content)
                self.assertFalse((self.new if path == self.old else self.old).exists())

    def test_push_and_pull_keep_link_duplicate_and_large_config_compatibility(self):
        args = SimpleNamespace(athlete_id=None, api_key=None)
        for module in (PUSH, PULL):
            for path in (self.old, self.new):
                for kind in ('symlink', 'hardlink', 'duplicate', 'large'):
                    with self.subTest(module=module.__name__, name=path.name, kind=kind), \
                            self.compatible_config(path, kind) as content, contextlib.chdir(self.root):
                        self.assertEqual(module._load_credentials(args), ('i123', 'synthetic-key'))
                        self.assertEqual(path.read_bytes(), content)
                        self.assertFalse((self.new if path == self.old else self.old).exists())

    def test_install_and_rollback_keep_strict_config_checks(self):
        write(self.root, {'sync.py': OLD.read_bytes()})
        self.install_release()
        for path in (self.old, self.new):
            for kind in ('symlink', 'hardlink', 'duplicate', 'large'):
                with self.subTest(name=path.name, kind=kind), self.compatible_config(path, kind):
                    before = inventory(self.root)
                    with self.assertRaises(SYNC.DistributionError):
                        SYNC._local_config(self.root)
                    with self.assertRaises(SYNC.DistributionError):
                        self.install_release()
                    with mock.patch.object(SYNC.Path, 'cwd', return_value=self.root), \
                            contextlib.redirect_stdout(io.StringIO()):
                        self.assertFalse(SYNC.do_rollback())
                    self.assertEqual(inventory(self.root), before)

    def install_release(self, timer_choice=None):
        raw, files = fixture()
        identity = {'tag': '2026.11.09', 'commit': 'a' * 40, 'url': 'offline'}
        plan = SYNC._local_plan(self.root, raw, files, timer_choice)
        SYNC._install_local(self.root, raw, files, identity, plan)

    def test_install_update_protect_both_names_and_write_preferences_to_new(self):
        self.old.write_bytes(CONFIG)
        self.new.write_bytes(CONFIG)
        write(self.root, {'sync.py': b'old tool'})
        self.install_release()
        self.assertEqual(self.old.read_bytes(), CONFIG)
        self.assertEqual(self.new.read_bytes(), CONFIG)
        self.install_release(timer_choice=True)
        self.assertTrue(json.loads(self.new.read_bytes())['auto_sync'])
        self.assertEqual(self.old.read_bytes(), CONFIG)

    def test_install_failure_restores_exact_new_preimage_and_legacy(self):
        self.old.write_bytes(CONFIG)
        for new_bytes in (None, CONFIG):
            with self.subTest(new_exists=new_bytes is not None):
                if new_bytes is not None:
                    self.new.write_bytes(new_bytes)
                with mock.patch.object(SYNC, '_ensure_custom', side_effect=RuntimeError('synthetic pre-timer failure')):
                    with self.assertRaisesRegex(RuntimeError, 'synthetic pre-timer failure'):
                        self.install_release(timer_choice=True)
                self.assertEqual(self.old.read_bytes(), CONFIG)
                self.assertEqual(self.new.read_bytes() if self.new.exists() else None, new_bytes)

    def test_pre_rename_producer_reads_current_credentials_after_rollback(self):
        write(self.root, {'sync.py': OLD.read_bytes()})
        self.old.write_bytes(CONFIG)
        self.install_release()
        self.normal_run()
        self.new.write_bytes(CONFIG.replace(b'synthetic-key', b'synthetic-later-key'))
        with mock.patch.object(SYNC.Path, 'cwd', return_value=self.root), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_rollback())
        self.assertFalse(self.new.exists())
        self.assertIn(b'synthetic-later-key', self.old.read_bytes())
        legacy = load_module_by_path('rename_restored_sync', self.root / 'sync.py')
        class CredentialsReached(BaseException):
            pass
        with contextlib.chdir(self.root), mock.patch.object(sys, 'argv', ['sync.py', '--output', 'latest.json']), \
                mock.patch.object(legacy, 'IntervalsSync', side_effect=CredentialsReached) as constructor, \
                mock.patch.object(legacy, '_rotate_log_if_needed'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(CredentialsReached):
                legacy.main()
        self.assertEqual(constructor.call_args.args[:2], ('i123', 'synthetic-later-key'))

    def test_rollback_preserves_differing_old_config_and_restores_timer_preference(self):
        write(self.root, {'sync.py': OLD.read_bytes()})
        self.old.write_bytes(b'{"athlete_id":"i999","intervals_key":"synthetic-unused"}')
        self.new.write_bytes(CONFIG)
        self.install_release(timer_choice=True)
        with mock.patch.object(SYNC.Path, 'cwd', return_value=self.root), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertTrue(SYNC.do_rollback())
        self.assertFalse(self.new.exists())
        self.assertFalse(json.loads(self.old.read_bytes())['auto_sync'])
        self.assertEqual(json.loads(self.old.read_bytes())['intervals_key'], 'synthetic-key')
        saved = list(self.root.glob('.sync_config.saved-*'))
        self.assertEqual(len(saved), 1)
        self.assertEqual(json.loads(saved[0].read_bytes())['intervals_key'], 'synthetic-unused')
        self.assertIn(saved[0].name, output.getvalue())
        self.assertNotIn(saved[0], list(self.root.glob('*.json')))

    def test_rollback_config_error_keeps_current_producer_and_journal(self):
        write(self.root, {'sync.py': OLD.read_bytes()})
        self.new.write_bytes(CONFIG)
        self.install_release()
        before = inventory(self.root / 'section11')
        replace = SYNC.os.replace
        def fail_config(src, dst):
            if Path(dst) == self.old:
                raise OSError(errno.EIO, 'synthetic config restore failure')
            return replace(src, dst)
        with mock.patch.object(SYNC.os, 'replace', side_effect=fail_config), \
                mock.patch.object(SYNC.Path, 'cwd', return_value=self.root), contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(SYNC.do_rollback())
        self.assertEqual(inventory(self.root / 'section11'), before)
        self.assertEqual(self.new.read_bytes(), CONFIG)
        self.assertEqual(json.loads((self.root / '.section11-state/transaction.json').read_bytes())['phase'],
                         'rollback-config')

    def test_ignore_and_release_publication_exclusions_protect_both_names(self):
        for name in ('.sync_config', '.sync_config.json'):
            with self.subTest(name=name):
                self.assertIn(name, (ROOT / 'dev/demo/templates/.gitignore').read_text().splitlines())
                self.assertIn(name, D.KEEP_ROOT)
                self.assertTrue(D.cleanup_protected('nested/' + name))
                with self.assertRaises(ValueError):
                    D.path(name)
                with self.assertRaises(ValueError):
                    validate_data.checked_path(self.root, name)
        self.assertEqual(D.path('examples/agentic/push.py'), 'examples/agentic/push.py')
        self.assertEqual(validate_data.checked_path(self.root, 'latest.json'), self.root / 'latest.json')
