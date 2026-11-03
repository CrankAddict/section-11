"""Owner decisions 11a/11c: exact-name cleanup and offline ZIP recovery."""
import contextlib
import errno
import io
import json
import os
import stat
import zipfile
from unittest import mock

from test_update_prototype import D, SYNC, Offline, install, inventory, write, fixture


def recovery_bytes(root, record, prefix='old/'):
    with zipfile.ZipFile(root / '.section11-state' / (record['transaction'] + '.zip')) as archive:
        return {i.filename[len(prefix):]: archive.read(i) for i in archive.infolist()
                if not i.is_dir() and i.filename.startswith(prefix)}


def writable_fsync(fd, fsync):
    # A zero-byte write enforces Windows' writable-descriptor requirement on
    # POSIX too, without changing file bytes or needing fcntl on Windows.
    os.write(fd, b'')
    return fsync(fd)


class AlignmentRecoveryTests(Offline):
    def setUp(self):
        super().setUp()
        self.raw, self.files = fixture()
        self.identity = {'tag': '2026.10.31', 'commit': 'a' * 40}
        write(self.root, {'.sync_config.json': b'{"auto_sync": false}'})

    def update(self):
        plan = SYNC._local_plan(self.root, self.raw, self.files)
        SYNC._install_local(self.root, self.raw, self.files, self.identity, plan)
        return SYNC._previous_install(self.root)[0]

    def rollback(self):
        with mock.patch.object(SYNC.Path, 'cwd', return_value=self.root), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertTrue(SYNC.do_rollback(), out.getvalue())

    def test_windows_fsync_guard_rejects_readonly_but_preserves_writable_bytes(self):
        path = self.root / 'descriptor-check'
        with path.open('wb') as stream:
            stream.write(b'unchanged bytes')
            stream.flush()
            writable_fsync(stream.fileno(), os.fsync)
        with path.open('rb') as stream:
            with self.assertRaises(OSError) as caught:
                writable_fsync(stream.fileno(), os.fsync)
        self.assertEqual(caught.exception.errno, errno.EBADF)
        self.assertEqual(path.read_bytes(), b'unchanged bytes')

    def test_install_update_and_rollback_fsync_writable_complete_archives(self):
        write(self.root, {'sync.py': b'legacy producer', 'DOSSIER.md': b'private dossier',
                          'latest.json': b'current data'})
        original_write, original_fsync = SYNC.LocalRecovery.write, os.fsync
        active, archived = [], []

        def checked_write(archive, roots):
            active.append(archive)
            try:
                return original_write(archive, roots)
            finally:
                active.pop()

        def checked_fsync(fd):
            result = writable_fsync(fd, original_fsync)
            if active:
                # The central directory and buffered contents must already be
                # readable at the durability point, before the writer closes.
                with zipfile.ZipFile(active[-1]) as archive:
                    self.assertIn('recovery.json', archive.namelist())
                    self.assertIsNone(archive.testzip())
                archived.append(active[-1])
            return result

        with mock.patch.object(SYNC.LocalRecovery, 'write', side_effect=checked_write), \
                mock.patch.object(SYNC.os, 'fsync', side_effect=checked_fsync) as fsynced:
            first = self.update()
            self.assertEqual(recovery_bytes(self.root, first, 'entries/')['sync.py'], b'legacy producer')
            installed = inventory(self.root / 'section11')
            write(self.root, {'SECTION_11.md': b'edited outside copy'})
            second = self.update()
            self.assertNotEqual(first['transaction'], second['transaction'])
            self.assertEqual(recovery_bytes(self.root, second, 'entries/')['SECTION_11.md'], b'edited outside copy')
            before_rollback = fsynced.call_count
            self.rollback()
            self.assertGreater(fsynced.call_count, before_rollback)
        self.assertEqual(len(archived), 2)
        self.assertEqual(inventory(self.root / 'section11'), installed)
        self.assertEqual((self.root / 'SECTION_11.md').read_bytes(), b'edited outside copy')
        self.assertEqual((self.root / 'DOSSIER.md').read_bytes(), b'private dossier')
        self.assertEqual((self.root / 'latest.json').read_bytes(), b'current data')

    def test_exact_names_removed_without_content_matching_and_all_negatives_preserved(self):
        removed = {name: b'edited arbitrary bytes' for name in D.HISTORICAL_NAMES}
        removed['README.md'] = b'edited root readme'
        removed.update({'reports/' + n: b'edited report' for n in D.HISTORICAL_NAMES})
        removed.update({'section11-legacy-github-2/old.yml': b'legacy',
                        'section11-legacy-dev-old/ordinary/old.py': b'old code',
                        'examples/sync.py': b'edited copied producer',
                        'other/SECTION_11.md': b'now in scope'})
        protected = {'custom/SECTION_11.md': b'custom', 'DOSSIER.md': b'dossier',
            'section11-legacy-dev-old/hidden/.git/config': b'ordinary git',
            'state/README.md': b'private state guide', '.gitignore': b'ignore', '.git/config': b'git',
            '.github/workflows/auto-sync.yml': b'workflow', 'latest.json': b'data',
            'history.json': b'data', 'intervals.json': b'data', 'routes.json': b'data',
            'saved_workouts.json': b'data', 'ftp_history.json': b'data',
            'route_eta_history.json': b'data', 'maps/map.png': b'map',
            'archive/old.json': b'archive', 'state/private.json': b'state', 'sync.log': b'log',
            '.credentials': b'credential-like', '.venv/pyvenv.cfg': b'environment',
            '.venv/bin/python': b'python', 'SKILL.md.notes': b'unrelated',
            'reports/own-template.md': b'personal'}
        write(self.root, dict(removed, **protected))
        install(self.root / 'section11', self.raw, self.files)
        record = self.update()
        for name in removed:
            self.assertFalse((self.root / name).exists(), name)
        for name, data in protected.items():
            self.assertEqual((self.root / name).read_bytes(), data, name)
        saved = recovery_bytes(self.root, record, 'entries/')
        self.assertEqual(saved, removed)
        self.assertFalse(any(p.is_dir() for p in (self.root / '.section11-state').iterdir()))
        self.rollback()
        for name, data in dict(removed, **protected).items():
            self.assertEqual((self.root / name).read_bytes(), data, name)

    def test_zip_round_trip_bytes_modes_empty_dirs_unknown_files_and_nested_git(self):
        old = self.root / 'section11'
        write(old, {'SECTION_11.md': b'edited\r\nno final newline',
                    'unknown/binary': bytes(range(256)), '.git/objects/ab/cd': b'git object'})
        (old / 'unknown/empty').mkdir()
        (old / 'SECTION_11.md').chmod(0o751)
        (old / 'unknown').chmod(0o750)
        (old / 'unknown/empty').chmod(0o711)
        old.chmod(0o750)
        write(self.root, {'sync.py': b'old tool'})
        (self.root / 'sync.py').chmod(0o711)
        expected = SYNC.LocalRecovery.inventory({'old': old, 'sync.py': self.root / 'sync.py'})
        record = self.update()
        self.assertIn('old/unknown/empty', record['archive_members'])
        self.assertEqual(len(list((self.root / '.section11-state').glob('*.zip'))), 1)
        archive = self.root / '.section11-state' / (record['transaction'] + '.zip')
        self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o600)
        self.rollback()
        self.assertEqual(SYNC.LocalRecovery.inventory({'old': old, 'sync.py': self.root / 'sync.py'}), expected)

    def test_local_readme_removed_and_restored_while_state_readme_is_preserved(self):
        self.update()
        original = b'edited local README\r\nno final newline'
        write(self.root, {'README.md': original, 'state/README.md': b'private state instructions'})
        (self.root / 'README.md').chmod(0o751)
        plan = SYNC._local_plan(self.root, self.raw, self.files)
        self.assertIn('README.md', plan['cleanup_names'])
        self.assertNotIn('state/README.md', plan['cleanup_names'])
        self.assertNotIn('README.md', SYNC._cleanup_paths(self.root, self.files, hosted=True))
        record = self.update()
        self.assertFalse((self.root / 'README.md').exists())
        self.assertEqual(recovery_bytes(self.root, record, 'entries/')['README.md'], original)
        self.assertEqual((self.root / 'state/README.md').read_bytes(), b'private state instructions')
        self.rollback()
        self.assertEqual((self.root / 'README.md').read_bytes(), original)
        self.assertEqual(stat.S_IMODE((self.root / 'README.md').stat().st_mode), 0o751)
        self.assertEqual((self.root / 'state/README.md').read_bytes(), b'private state instructions')

    def test_corrupt_archive_rejected_before_any_activation(self):
        write(self.root, {'sync.py': b'old'})
        record = self.update()
        archive = self.root / '.section11-state' / (record['transaction'] + '.zip')
        archive.write_bytes(archive.read_bytes()[:-9])
        before = inventory(self.root)
        with self.assertRaisesRegex(ValueError, 'archive changed'):
            SYNC._previous_install(self.root)
        self.assertEqual(inventory(self.root), before)

    def test_archive_preserves_old_tree_plus_three_previously_allowed_root_tools(self):
        # Scale the old per-tree and per-tool bounds, keeping their relationship.
        unit = 32 * 1024
        old = {'edited.bin': b'x' * (4 * unit - 1024)}
        tools = {name: b'y' * (unit - 1024) for name in SYNC._ROOT_ENTRIES}
        write(self.root / 'section11', old)
        write(self.root, tools)
        with mock.patch.object(D, 'MAX_BYTES', unit), \
                mock.patch.object(SYNC.LocalRecovery, 'MAX_BYTES', 8 * unit + 8192):
            record = self.update()
            self.assertEqual(recovery_bytes(self.root, record), old)
            self.assertEqual(recovery_bytes(self.root, record, 'entries/'), tools)
            self.rollback()
        self.assertEqual(inventory(self.root / 'section11'), old)
        for name, data in tools.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    def test_cleanup_bound_refuses_before_staging_without_narrowing_old_tree_bound(self):
        write(self.root, {'LICENSE': b'x' * 65})
        with mock.patch.object(D, 'MAX_BYTES', 16):
            with self.assertRaisesRegex(ValueError, 'size safety bound'):
                SYNC._local_plan(self.root, self.raw, self.files)
        self.assertFalse((self.root / '.section11-state').exists())
        self.assertEqual((self.root / 'LICENSE').read_bytes(), b'x' * 65)

    def test_journal_precedes_staging_and_next_lock_cleans_interrupted_staging(self):
        write(self.root, {'sync.py': b'old'})
        plan = SYNC._local_plan(self.root, self.raw, self.files)
        original = SYNC.LocalRecovery.write
        def killed(archive, roots):
            journal = json.loads((self.root / '.section11-state/transaction.json').read_text())
            self.assertEqual(journal['phase'], 'staging')
            self.assertEqual(journal['transaction'], archive.parent.name)
            original(archive, roots)
            raise SystemExit('synthetic process interruption')
        with mock.patch.object(SYNC.LocalRecovery, 'write', side_effect=killed):
            with self.assertRaises(SystemExit):
                SYNC._install_local(self.root, self.raw, self.files, self.identity, plan)
        self.assertEqual((self.root / 'sync.py').read_bytes(), b'old')
        self.assertFalse((self.root / 'section11').exists())
        with SYNC._distribution_lock(self.root):
            pass
        self.assertEqual([p.name for p in (self.root / '.section11-state').iterdir()], ['operation.lock'])
        self.update()

    def test_second_success_replaces_zip_identical_install_preserves_it(self):
        write(self.root, {'sync.py': b'old'})
        first = self.update()
        self.update()
        self.assertEqual(SYNC._previous_install(self.root)[0], first)
        write(self.root, {'SECTION_11.md': b'new stray copy'})
        second = self.update()
        self.assertNotEqual(first['transaction'], second['transaction'])
        self.assertEqual(len(list((self.root / '.section11-state').glob('*.zip'))), 1)
        self.rollback()
        self.assertEqual((self.root / 'SECTION_11.md').read_bytes(), b'new stray copy')

    def test_empty_extra_directory_is_removed_even_with_identical_release(self):
        self.update()
        (self.root / 'section11/extra-empty').mkdir()
        record = self.update()
        self.assertFalse((self.root / 'section11/extra-empty').exists())
        self.assertIn('old/extra-empty', record['archive_members'])
        self.rollback()
        self.assertTrue((self.root / 'section11/extra-empty').is_dir())

    def test_current_mode_change_refuses_rollback(self):
        write(self.root, {'sync.py': b'old'})
        self.update()
        path = self.root / 'section11/LICENSE'
        path.chmod(0o711)
        with self.assertRaisesRegex(ValueError, 'changed since rollback'):
            SYNC._previous_install(self.root)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o711)

    def test_interrupted_rollback_extraction_is_cleaned_without_consuming_zip(self):
        write(self.root, {'sync.py': b'old'})
        record = self.update()
        read = SYNC.LocalRecovery.read
        def killed(archive, digest, destination=None):
            result = read(archive, digest, destination)
            if destination is not None:
                raise SystemExit('synthetic extraction interruption')
            return result
        with mock.patch.object(SYNC.LocalRecovery, 'read', side_effect=killed):
            with self.assertRaises(SystemExit):
                SYNC._rollback_local(self.root, record)
        with SYNC._distribution_lock(self.root):
            pass
        self.assertEqual(SYNC._previous_install(self.root)[0], record)
        self.assertFalse(any(p.is_dir() for p in (self.root / '.section11-state').iterdir()))
        self.rollback()

    def test_committed_cleanup_interruption_is_finished_without_replaying_timer(self):
        write(self.root, {'sync.py': b'old'})
        original = SYNC.shutil.rmtree
        def killed(path, *args, **kwargs):
            if path.parent == self.root / '.section11-state':
                raise SystemExit('synthetic cleanup interruption')
            return original(path, *args, **kwargs)
        with mock.patch.object(SYNC.shutil, 'rmtree', side_effect=killed):
            with self.assertRaises(SystemExit):
                self.update()
        with mock.patch.object(SYNC.LocalTimers, 'apply', side_effect=AssertionError('no timer replay')):
            with SYNC._distribution_lock(self.root):
                pass
        self.assertFalse(any(p.is_dir() for p in (self.root / '.section11-state').iterdir()))
        self.rollback()

    def test_invalid_zip_members_rejected_before_extracting(self):
        write(self.root, {'sync.py': b'old'})
        record = self.update()
        original = self.root / '.section11-state' / (record['transaction'] + '.zip')
        with zipfile.ZipFile(original) as archive:
            members = [(i, archive.read(i)) for i in archive.infolist()]
        for index, bad_name in enumerate(('../escape', '/absolute', 'entries/../escape', 'entries\\escape')):
            path = self.root / ('bad-' + str(index) + '.zip')
            with zipfile.ZipFile(path, 'w') as archive:
                for info, data in members:
                    archive.writestr(info, data)
                archive.writestr(bad_name, b'not a safe member')
            destination = self.root / ('extract-' + str(index))
            with self.assertRaisesRegex(ValueError, 'unsafe recovery member'):
                SYNC.LocalRecovery.read(path, D.digest(path.read_bytes()), destination)
            self.assertFalse(destination.exists())
        for variant in ('hash', 'special-mode', 'missing', 'case-collision'):
            path = self.root / (variant + '.zip')
            with zipfile.ZipFile(path, 'w') as archive:
                for info, data in members:
                    if variant == 'missing' and info.filename == 'entries/sync.py':
                        continue
                    if info.filename == 'entries/sync.py':
                        if variant == 'hash':
                            data = b'wrong bytes'
                        elif variant == 'special-mode':
                            info = zipfile.ZipInfo(info.filename)
                            info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, data)
                if variant == 'case-collision':
                    archive.writestr('ENTRIES/SYNC.PY', b'duplicate')
            destination = self.root / ('extract-' + variant)
            with self.assertRaises(ValueError):
                SYNC.LocalRecovery.read(path, D.digest(path.read_bytes()), destination)
            self.assertFalse(destination.exists())

    def test_outside_copy_drift_after_review_refuses_install(self):
        write(self.root, {'SECTION_11.md': b'old copy'})
        plan = SYNC._local_plan(self.root, self.raw, self.files)
        write(self.root, {'SECTION_11.md': b'changed after review'})
        with self.assertRaisesRegex(ValueError, 'changed after review'):
            SYNC._install_local(self.root, self.raw, self.files, self.identity, plan)
        self.assertEqual((self.root / 'SECTION_11.md').read_bytes(), b'changed after review')
        self.assertFalse((self.root / 'section11').exists())
