"""Rev 4 verification regressions, with synthetic locks and schedulers only."""
import contextlib
import errno
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import D, SYNC, REAL_TIMERS, Offline, fixture, inventory, write
from test_b2_hosted import H, Remote, DirectPublisher


class VerifyFixTests(Offline):
    def setUp(self):
        super().setUp()
        self.raw, self.files = fixture()
        self.identity = {'tag': '2026.10.31', 'commit': 'a' * 40}

    def update(self, root=None, **kwargs):
        output = io.StringIO()
        with mock.patch.object(Path, 'cwd', return_value=root or self.root), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(self.raw, self.files, self.identity)), \
                mock.patch('builtins.input', return_value='y'), contextlib.redirect_stdout(output):
            result = SYNC.do_update(**kwargs)
        return result, output.getvalue()

    def test_busy_posix_and_windows_all_entry_points_are_single_line_no_write(self):
        write(self.root, {'section11/old': b'old', '.section11-state/operation.lock': b''})
        before = inventory(self.root)
        failures = [('posix', BlockingIOError(errno.EAGAIN, 'synthetic busy')),
                    ('posix', OSError(errno.EWOULDBLOCK, 'synthetic busy')),
                    ('nt', PermissionError(errno.EACCES, 'synthetic busy')),
                    ('nt', OSError(errno.EDEADLK, 'synthetic busy'))]
        for platform, error in failures:
            for args in ([], ['--lockfile'], ['--init'], ['--update'], ['--rollback'], ['--status']):
                with self.subTest(platform=platform, error=type(error).__name__, args=args):
                    output = io.StringIO()
                    acquire = mock.Mock(side_effect=error)
                    modules = {'fcntl': SimpleNamespace(flock=acquire, LOCK_EX=2, LOCK_NB=4, LOCK_UN=8),
                               'msvcrt': SimpleNamespace(locking=acquire, LK_NBLCK=2, LK_UNLCK=0)}
                    with mock.patch.dict(sys.modules, modules), \
                            mock.patch.object(SYNC, 'os', mock.Mock(wraps=os, name=platform)), \
                            mock.patch.object(SYNC.os, 'name', platform), \
                            mock.patch.object(sys, 'argv', ['sync.py', *args]), \
                            mock.patch.object(Path, 'cwd', return_value=self.root), \
                            mock.patch.object(SYNC, '_installation_root', return_value=self.root), \
                            mock.patch.object(SYNC, '_fetch_verified_release') as fetch, \
                            mock.patch.object(SYNC, '_cleanup_staging') as cleanup, \
                            mock.patch.object(SYNC, '_rotate_log_if_needed') as rotate, \
                            contextlib.redirect_stdout(output):
                        if args and args[0] != '--lockfile':
                            with self.assertRaises(SystemExit) as caught:
                                SYNC.main()
                            self.assertEqual(caught.exception.code, 1)
                        else:
                            self.assertIsNone(SYNC.main())
                        fetch.assert_not_called()
                        cleanup.assert_not_called()
                        rotate.assert_not_called()
                    self.assertEqual(output.getvalue(), str(SYNC.DistributionBusy()) + '\n')
                    self.assertEqual(acquire.call_count, 1)
                    self.assertEqual(inventory(self.root), before)

    def test_uncontended_lock_releases_and_other_errors_are_not_busy(self):
        write(self.root, {'.section11-state/operation.lock': b''})
        for platform in ('posix', 'nt'):
            acquire = mock.Mock()
            modules = {'fcntl': SimpleNamespace(flock=acquire, LOCK_EX=2, LOCK_NB=4, LOCK_UN=8),
                       'msvcrt': SimpleNamespace(locking=acquire, LK_NBLCK=2, LK_UNLCK=0)}
            with mock.patch.dict(sys.modules, modules), \
                    mock.patch.object(SYNC, 'os', mock.Mock(wraps=os)), \
                    mock.patch.object(SYNC.os, 'name', platform):
                with self.assertRaisesRegex(RuntimeError, 'synthetic body'):
                    with SYNC._distribution_lock(self.root):
                        raise RuntimeError('synthetic body')
                self.assertEqual(acquire.call_count, 2)
                acquire.side_effect = OSError(errno.EIO, 'synthetic I/O failure')
                with self.assertRaises(OSError) as caught:
                    with SYNC._distribution_lock(self.root):
                        self.fail('lock failed')
                self.assertEqual(caught.exception.errno, errno.EIO)

    def test_status_and_declined_fresh_review_do_not_create_lock_state(self):
        with mock.patch('builtins.input', return_value='n'), \
                mock.patch.object(Path, 'cwd', return_value=self.root), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(self.raw, self.files, self.identity)), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_update(status_only=True))
            self.assertFalse(SYNC.do_init())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_nested_environments_local_hosted_parity_and_exact_rollback(self):
        kept = {'section11-legacy-dev-venv/deep/env/pyvenv.cfg': b'home = synthetic',
                'section11-legacy-dev-venv/edited.py': b'keep whole tree',
                'section11-legacy-github-conda/nested/conda-meta/history': b'environment',
                'section11-legacy-github-conda/old.py': b'keep whole tree',
                'examples/old.py': b'outside cleanup scope'}
        removed = {'section11-legacy-dev-old/nested/old.py': b'remove ordinary legacy',
                   'section11-legacy-github-old/conda-metadata/old': b'nearby name is not a marker'}
        write(self.root, dict(kept, **removed))
        local = SYNC._cleanup_paths(self.root, self.files)
        hosted = H.cleanup_paths(DirectPublisher(Remote(dict(kept, **removed))).snapshot(), self.files)
        self.assertEqual(set(hosted), set(removed))
        self.assertEqual(set(local), set(removed))
        write(self.root, {'section11/old-producer.py': b'previous installation'})
        ok, output = self.update(timer_choice=False)
        self.assertTrue(ok, output)
        for name, content in kept.items():
            self.assertEqual((self.root / name).read_bytes(), content)
        for name in removed:
            self.assertFalse((self.root / name).exists())
        with mock.patch.object(Path, 'cwd', return_value=self.root), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_rollback())
        for name, content in dict(kept, **removed).items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_empty_conda_marker_and_active_python_paths_are_protected(self):
        (self.root / 'section11-legacy-dev-conda/nested/conda-meta').mkdir(parents=True)
        write(self.root, {'section11-legacy-dev-runtime/bin/python': b'fake executable',
                          'section11-legacy-github-prefix/lib/keep': b'prefix',
                          'section11-legacy-dev-ordinary/old': b'delete'})
        with mock.patch.object(sys, 'executable', str(self.root / 'section11-legacy-dev-runtime/bin/python')), \
                mock.patch.object(sys, 'prefix', str(self.root / 'section11-legacy-github-prefix')):
            self.assertEqual(set(SYNC._cleanup_paths(self.root)), {'section11-legacy-dev-ordinary/old'})
            command = self.timers(self.root).standard({})['line']
            self.assertIn(sys.executable, command)
            ok, output = self.update(timer_choice=False)
        self.assertTrue(ok, output)
        self.assertTrue((self.root / 'section11-legacy-dev-runtime/bin/python').is_file())
        self.assertTrue((self.root / 'section11-legacy-github-prefix/lib/keep').is_file())
        self.assertTrue((self.root / 'section11-legacy-dev-conda/nested/conda-meta').is_dir())

    def test_active_interpreter_in_managed_tree_refuses_before_replacement(self):
        write(self.root, {'section11/env/bin/python': b'fake executable'})
        before = inventory(self.root)
        with mock.patch.object(sys, 'executable', str(self.root / 'section11/env/bin/python')):
            ok, output = self.update(timer_choice=False)
            self.assertFalse(ok)
            self.assertIn('Python interpreter is inside section11/', output)
            with self.assertRaisesRegex(SYNC.DistributionError, 'Python interpreter'):
                SYNC._rollback_local(self.root, {})
        self.assertEqual(inventory(self.root), before)

    def test_missing_schedulers_opt_out_installs_and_enabled_refuses(self):
        home = self.root / 'home'
        class MissingTimers(REAL_TIMERS):
            def __init__(adapter, data_dir):
                super().__init__(data_dir, home=home, platform='linux')
            def command(adapter, argv, input=None):
                if argv == ['systemctl', '--user', 'show-environment']:
                    return SimpleNamespace(returncode=1)
                if argv == ['crontab', '-l']:
                    raise FileNotFoundError(errno.ENOENT, 'synthetic missing crontab')
                raise AssertionError('unexpected scheduler write: ' + repr(argv))
        for tool in (None, '/synthetic/systemctl'):
            root = self.root / ('no-tools' if tool is None else 'no-session')
            root.mkdir()
            with mock.patch.object(SYNC, 'LocalTimers', MissingTimers), \
                    mock.patch.object(SYNC.shutil, 'which', return_value=tool):
                ok, output = self.update(root, timer_choice=True)
                self.assertFalse(ok)
                self.assertIn('timer inspection unavailable: crontab', output)
                self.assertEqual(list(root.iterdir()), [])
                ok, output = self.update(root, timer_choice=False, _init=True)
                self.assertTrue(ok, output)
                self.assertFalse(json.loads((root / '.sync_config').read_bytes())['auto_sync'])
                self.assertEqual(D.tree(root / 'section11'), (self.raw, self.files))
                # Persisted auto_sync:false also permits the next update.
                ok, output = self.update(root)
                self.assertTrue(ok, output)

    def test_missing_scheduler_does_not_hide_existing_timer_or_permission_failure(self):
        timer = REAL_TIMERS(self.root, home=self.root, platform='linux')
        with mock.patch.object(SYNC.shutil, 'which', return_value=None):
            for error in (PermissionError(errno.EACCES, 'synthetic denied'), OSError(errno.EIO, 'synthetic unreadable')):
                with mock.patch.object(timer, 'command', side_effect=error):
                    with self.assertRaisesRegex(SYNC.DistributionError, 'timer inspection unavailable'):
                        timer.plan({}, choice=False)
            with mock.patch.object(timer, 'command', side_effect=FileNotFoundError(errno.ENOENT, 'synthetic missing')):
                with self.assertRaisesRegex(SYNC.DistributionError, 'existing standard timer'):
                    timer.plan({'auto_sync': True}, choice=False)
                write(self.root, {'.section11-state/previous.json': b'{"config_after":true}'})
                with self.assertRaisesRegex(SYNC.DistributionError, 'existing standard timer'):
                    timer.plan({}, choice=False)
                for suffix in ('.timer', '.service'):
                    unit = self.root / ('.config/systemd/user/section11-sync' + suffix)
                    write(self.root, {unit.relative_to(self.root).as_posix(): b'[Unit]\n'})
                    with self.assertRaisesRegex(SYNC.DistributionError, 'normal login session'):
                        timer.plan({}, choice=False)
                    unit.unlink()
            with mock.patch.object(timer, 'file_bytes', side_effect=PermissionError(errno.EACCES, 'synthetic unreadable unit')):
                with self.assertRaises(PermissionError):
                    timer.plan({}, choice=False)

    def test_newcomer_and_conversion_messages_follow_actual_content(self):
        cases = ({}, {'section11/edited.md': b'edited'}, {'sync.py': b'old'},
                 {'section11/.git/config': b'[core]\nrepositoryformatversion=0\n'})
        for i, files in enumerate(cases):
            root = self.root / str(i)
            write(root, files)
            ok, output = self.update(root)
            self.assertTrue(ok, output)
            self.assertEqual(SYNC.CONVERSION_WARNING in output, any(p.startswith('section11/') for p in files))
            self.assertEqual('Root sync.py will be removed.' in output, 'sync.py' in files)
            self.assertNotIn('Root sync.py, push.py and pull.py', output)
            self.assertEqual('Git clone:' in output, 'section11/.git/config' in files)
            self.assertEqual('New installation: section11/ and custom/ will be created.' in output, not files)
            self.assertIn('every 1 minute)', output)
