"""20a/21a: exact removal spelling at any depth, protected spelling everywhere."""
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import D, SYNC, Offline, fixture, install, manifest, write
from test_alignment_recovery import recovery_bytes
from test_b2_hosted import H, Remote, DirectPublisher


class ScandirEntries:
    """In-memory scandir result: next(result) works even inside with result."""
    def __init__(self, entries):
        self.entries = iter(entries)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration
        try:
            return next(self.entries)
        except StopIteration:
            self.close()
            raise

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class NameRuleTests(Offline):
    def setUp(self):
        super().setUp()
        _, self.files = fixture()
        self.files.update({'README.md': b'release readme',
                          'examples/workout-library/WORKOUT_REFERENCE.md': b'library'})
        self.raw = manifest(self.files)
        self.identity = {'tag': '2026.10.31', 'commit': 'a' * 40}
        self.removed = {
            'old/SECTION_11.md': b'edited\r\nno final newline',
            'backup/examples/sync.py': b'older producer',
            'notes/README.md': b'my own notes',
            'a/b/c/WORKOUT_REFERENCE.md': b'older library',
            'reports/PRE_WORKOUT_TEMPLATE.md': b'retired template',
            'elsewhere/POST_WORKOUT_TEMPLATE.md': b'other retired template',
            'plain/PRE_WORKOUT_REPORT_TEMPLATE.md': b'report without special folder',
            'reports/LICENSE': b'unrelated license still reserved',
        }
        self.kept = {name: b'keep:' + name.encode() for name in (
            'readme.md', 'License', 'other/readme.md', 'other/License',
            'Custom/y/SECTION_11.md', 'custom/x/SECTION_11.md',
            'Archive/2026-10/SECTION_11.md', 'archive/2026-10/sync.py',
            'nested/MAPS/README.md', 'maps/sync.py', 'state/README.md',
            'a/State/sync.py', 'a/.hidden/sync.py', '.venv/lib/pkg/sync.py',
            'notes/latest.json', 'notes/DOSSIER.md', 'elsewhere/dossier.md',
            'deep/LATEST.JSON', 'deep/Sync.Log', 'deep/.SYNC_CONFIG.JSON',
            'nested/env/pyvenv.cfg', 'nested/env/lib/sync.py',
            'other/environment/PYVENV.CFG', 'other/environment/LICENSE',
            'nested/conda/Conda-Meta/history', 'nested/conda/sync.py',
            'reports/my-report.md', 'old/personal.py', 'section11-legacy-dev-file',
        )}
        self.kept['.sync_config.json'] = b'{"auto_sync":false}'

    @contextlib.contextmanager
    def cleanup_scandir(self, scan):
        """Override only the cleanup function's os lookup, never os.scandir."""
        cleanup = SYNC._cleanup_paths
        real_os = SYNC.os
        scanner_os = SimpleNamespace(**dict(vars(real_os), scandir=scan))
        def run(*args, **kwargs):
            with mock.patch.object(SYNC, 'os', scanner_os):
                return cleanup(*args, **kwargs)
        with mock.patch.object(SYNC, '_cleanup_paths', side_effect=run):
            yield

    def test_scandir_double_supports_original_iterator_and_context_protocol(self):
        result = ScandirEntries(['first', 'second'])
        self.assertIs(iter(result), result)
        with result as entered:
            self.assertIs(entered, result)
            # Python 3.11/3.12 os.walk advances the original scandir object,
            # not an iterator returned by its __enter__ method.
            self.assertEqual(next(result), 'first')
            self.assertEqual(next(result), 'second')
            with self.assertRaises(StopIteration):
                next(result)
        self.assertTrue(result.closed)
        result.close()
        with self.assertRaises(StopIteration):
            next(result)
        partial = ScandirEntries(['first', 'second'])
        with self.assertRaisesRegex(RuntimeError, 'stop scan'), partial:
            self.assertEqual(next(partial), 'first')
            raise RuntimeError('stop scan')
        self.assertTrue(partial.closed)
        with self.assertRaises(StopIteration):
            next(partial)

    def test_cleanup_scandir_hook_does_not_leak_into_walk_or_other_callers(self):
        write(self.root, {'old/SECTION_11.md': b'old'})
        real_os, scan = SYNC.os, SYNC.os.scandir
        def guarded(path):
            self.assertIs(real_os.scandir, scan)
            self.assertEqual(len(list(real_os.walk(self.root, followlinks=False))), 2)
            return scan(path)
        hook = mock.Mock(side_effect=guarded)
        with self.cleanup_scandir(hook):
            with SYNC.os.scandir(self.root) as entries:
                self.assertEqual(next(entries).name, 'old')
            self.assertEqual(len(list(SYNC.os.walk(self.root, followlinks=False))), 2)
            hook.assert_not_called()
            self.assertEqual(set(SYNC._cleanup_paths(self.root, self.files)), {'old/SECTION_11.md'})
            self.assertEqual(hook.call_count, 2)
            hook.reset_mock()
            self.assertIs(SYNC.os, real_os)
            self.assertIs(real_os.scandir, scan)
            list(SYNC.os.walk(self.root, followlinks=False))
            hook.assert_not_called()

    def test_nested_removals_exact_zip_bytes_modes_and_protected_neighbours(self):
        write(self.root, dict(self.kept, **self.removed))
        (self.root / 'untouched-empty').mkdir()
        (self.root / 'backup/examples/sync.py').chmod(0o751)
        install(self.root / 'section11', self.raw, self.files)
        plan = SYNC._local_plan(self.root, self.raw, self.files)
        self.assertEqual(set(plan['cleanup']), set(self.removed))
        self.assertIn('a/b/c/', plan['cleanup_names'])
        self.assertNotIn('old/', plan['cleanup_names'])
        SYNC._install_local(self.root, self.raw, self.files, self.identity, plan)
        record = SYNC._previous_install(self.root)[0]
        self.assertEqual(recovery_bytes(self.root, record, 'entries/'), self.removed)
        self.assertFalse((self.root / 'a/b').exists())
        self.assertTrue((self.root / 'untouched-empty').is_dir())
        for name, content in self.kept.items():
            self.assertEqual((self.root / name).read_bytes(), content, name)
        for name in self.removed:
            self.assertFalse((self.root / name).exists(), name)
        write(self.root, {'notes/latest.json': b'newer data'})
        SYNC._rollback_local(self.root, record)
        for name, content in self.removed.items():
            self.assertEqual((self.root / name).read_bytes(), content, name)
        self.assertEqual((self.root / 'backup/examples/sync.py').stat().st_mode & 0o777, 0o751)
        self.assertEqual((self.root / 'notes/latest.json').read_bytes(), b'newer data')

    def test_hosted_parity_disclosure_install_commit_and_rollback(self):
        # Git rejects case aliases; use separate paths for each protected example.
        kept = {p: b for p, b in self.kept.items() if p != 'readme.md'}
        remote = Remote(kept)
        publisher = DirectPublisher(remote)
        updater = H.HostedUpdater(publisher, mock.Mock(return_value=(self.raw, self.files, self.identity)), {})
        with contextlib.redirect_stdout(io.StringIO()):
            updater.install(publisher.snapshot(), accepted=True)
        remote.tip = remote.commit(self.removed, [remote.tip], 'Outside copies')
        before = publisher.snapshot()
        write(self.root, dict(kept, **self.removed))
        self.assertEqual(set(SYNC._cleanup_paths(self.root, self.files, hosted=True)), set(self.removed))
        self.assertEqual(set(H.cleanup_paths(before, self.files)), set(self.removed))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            status = updater.status(before)
            self.assertEqual(set(status['plan']['removed']), set(self.removed))
            after = updater.install(before, accepted=True)
        self.assertEqual(after['parents'], [before['commit']])
        for name in self.removed:
            self.assertIn(name, output.getvalue())
            self.assertNotIn(name, remote.inventory())
        for name, content in kept.items():
            self.assertEqual(remote.inventory()[name], content)
        remote.tip = remote.commit({'notes/latest.json': b'newer'}, [remote.tip], 'New data')
        with contextlib.redirect_stdout(io.StringIO()):
            updater.rollback(publisher.snapshot())
        for name, content in self.removed.items():
            self.assertEqual(remote.inventory()[name], content)
        self.assertEqual(remote.inventory()['notes/latest.json'], b'newer')

    def test_all_nested_names_are_listed_before_half_mode_acceptance(self):
        write(self.root, self.removed)
        output = io.StringIO()
        def decline(prompt):
            for name in self.removed:
                self.assertIn(name, output.getvalue())
            return 'n'
        with mock.patch.object(Path, 'cwd', return_value=self.root), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(self.raw, self.files, self.identity)), \
                mock.patch('builtins.input', side_effect=decline), contextlib.redirect_stdout(output):
            self.assertFalse(SYNC.do_update())
        for name, content in self.removed.items():
            self.assertEqual((self.root / name).read_bytes(), content)
        self.assertFalse((self.root / 'section11').exists())

    def test_matching_reads_no_contents_and_never_enters_protected_subtrees(self):
        write(self.root, dict(self.kept, **self.removed,
                              **{'section11-legacy-dev-1/Custom/deep/pyvenv.cfg': b'protected marker',
                                 'section11-legacy-dev-1/old.py': b'remove'}))
        scan = SYNC.os.scandir
        visited = []
        def guarded(path):
            name = Path(path).relative_to(self.root).as_posix()
            self.assertFalse(name != '.' and D.cleanup_protected(name))
            visited.append(name)
            return scan(path)
        with self.cleanup_scandir(guarded), \
                mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('matching read bytes')), \
                mock.patch.object(Path, 'read_text', side_effect=AssertionError('matching read text')):
            removed = SYNC._cleanup_paths(self.root, self.files)
        self.assertEqual(set(removed), set(self.removed) | {'section11-legacy-dev-1/old.py'})
        self.assertFalse(any(p.startswith(('nested/env/', 'other/environment/', 'nested/conda/')) for p in visited))

    def test_every_keep_component_wins_in_mixed_case_and_exact_names_only(self):
        for name in D.KEEP_ROOT - {'README.md'}:
            path = 'any/' + name.swapcase() + '/SECTION_11.md'
            self.assertIsNone(D.cleanup_reason(path, self.files), path)
            self.assertNotIn(path, H.cleanup_paths({'entries': {path: {'mode': '100644'}}}, self.files))
        for name in ('readme.md', 'License', 'section_11.md', 'pre_workout_template.md'):
            self.assertIsNone(D.cleanup_reason('any/' + name, self.files))
        for name in ('README.md', 'LICENSE', 'SECTION_11.md', 'PRE_WORKOUT_TEMPLATE.md'):
            self.assertIsNotNone(D.cleanup_reason('any/' + name, self.files))
        self.assertIsNone(D.cleanup_reason('README.md', self.files, hosted=True))
        self.assertIsNotNone(D.cleanup_reason('README.md', self.files))
        self.assertIsNone(D.cleanup_reason('README.md', self.files, directory=True, hosted=True))

    def test_unrelated_file_and_directory_links_stay_without_blocking_update(self):
        write(self.root, {'old/SECTION_11.md': b'old', 'custom/target/sync.py': b'keep'})
        (self.root / 'linked').symlink_to(self.root / 'custom/target', target_is_directory=True)
        (self.root / 'personal-link').symlink_to(self.root / 'custom/target/sync.py')
        (self.root / 'section11-legacy-dev-1').mkdir()
        (self.root / 'section11-legacy-dev-1/linked').symlink_to(self.root / 'custom/target', target_is_directory=True)
        scan = SYNC.os.scandir
        def guarded(path):
            if not isinstance(path, int):
                self.assertFalse(Path(path).is_symlink())
            return scan(path)
        with self.cleanup_scandir(guarded):
            plan = SYNC._local_plan(self.root, self.raw, self.files)
            self.assertEqual(set(plan['cleanup']), {'old/SECTION_11.md'})
            SYNC._install_local(self.root, self.raw, self.files, self.identity, plan)
        self.assertFalse((self.root / 'old/SECTION_11.md').exists())
        for name in ('linked', 'personal-link', 'section11-legacy-dev-1/linked'):
            self.assertTrue((self.root / name).is_symlink())
        self.assertEqual((self.root / 'custom/target/sync.py').read_bytes(), b'keep')

    def test_matching_name_file_and_directory_symlinks_stop_before_deletion(self):
        write(self.root, {'old/SECTION_11.md': b'old', 'custom/target/personal': b'keep'})
        link = self.root / 'old/sync.py'
        for directory in (False, True):
            with self.subTest(directory=directory):
                target = self.root / ('custom/target' if directory else 'custom/target/personal')
                link.symlink_to(target, target_is_directory=directory)
                with self.assertRaisesRegex(ValueError, 'non-ordinary cleanup'):
                    SYNC._local_plan(self.root, self.raw, self.files)
                self.assertEqual((self.root / 'old/SECTION_11.md').read_bytes(), b'old')
                self.assertEqual((self.root / 'custom/target/personal').read_bytes(), b'keep')
                self.assertTrue(link.is_symlink())
                self.assertFalse((self.root / 'section11').exists())
                link.unlink()

    def test_unreadable_folder_stops_before_deletion(self):
        write(self.root, {'old/SECTION_11.md': b'old', 'unreadable/personal': b'keep'})
        scan = SYNC.os.scandir
        def guarded(path):
            if Path(path) == self.root / 'unreadable':
                raise PermissionError('synthetic unreadable directory')
            return scan(path)
        with self.cleanup_scandir(guarded):
            with self.assertRaisesRegex(PermissionError, 'synthetic unreadable'):
                SYNC._local_plan(self.root, self.raw, self.files)
        self.assertEqual((self.root / 'old/SECTION_11.md').read_bytes(), b'old')
        self.assertFalse((self.root / 'section11').exists())

    @contextlib.contextmanager
    def windows_reparse_metadata(self, tags, scan=None):
        """Simulate Windows lstat/DirEntry metadata without native cloud services."""
        original = Path.lstat
        scan = SYNC.os.scandir if scan is None else scan
        def tagged(path, value):
            tag = tags.get(Path(path))
            if tag is None:
                return value
            fields = {k: getattr(value, k) for k in dir(value) if k.startswith('st_')}
            fields.update(st_file_attributes=0x400, st_reparse_tag=tag)
            return SimpleNamespace(**fields)
        def metadata(path):
            return tagged(path, original(path))
        class Entry:
            def __init__(self, entry):
                self.entry = entry
            def __getattr__(self, name):
                return getattr(self.entry, name)
            def stat(self, *, follow_symlinks=True):
                value = self.entry.stat(follow_symlinks=follow_symlinks)
                return value if follow_symlinks else tagged(self.entry.path, value)
        def listing(path):
            with scan(path) as entries:
                rows = [Entry(e) for e in entries]
            return ScandirEntries(rows)
        with mock.patch.object(Path, 'lstat', metadata), self.cleanup_scandir(listing):
            yield

    def test_cloud_placeholder_root_folder_and_selected_file_install_and_rollback(self):
        removed = {'cloud/SECTION_11.md': b'cloud bytes\r\n', 'cloud/personal': b'keep'}
        write(self.root, removed)
        install(self.root / 'section11', self.raw, self.files)
        target = self.root / 'cloud/SECTION_11.md'
        target.chmod(0o751)
        tags = {p: 0x9000001A for p in (self.root, self.root / 'cloud', target)}
        with self.windows_reparse_metadata(tags):
            plan = SYNC._local_plan(self.root, self.raw, self.files)
            self.assertEqual(set(plan['cleanup']), {'cloud/SECTION_11.md'})
            SYNC._install_local(self.root, self.raw, self.files, self.identity, plan)
            record = SYNC._previous_install(self.root)[0]
            self.assertEqual(recovery_bytes(self.root, record, 'entries/'),
                             {'cloud/SECTION_11.md': removed['cloud/SECTION_11.md']})
            self.assertFalse(target.exists())
            self.assertEqual((self.root / 'cloud/personal').read_bytes(), b'keep')
            SYNC._rollback_local(self.root, record)
        self.assertEqual(target.read_bytes(), removed['cloud/SECTION_11.md'])
        self.assertEqual(target.stat().st_mode & 0o777, 0o751)

    def test_junction_and_other_name_surrogate_tags_are_links(self):
        write(self.root, {'junction/SECTION_11.md': b'target', 'old/sync.py': b'old'})
        scan = SYNC.os.scandir
        def guarded(path):
            self.assertNotEqual(Path(path), self.root / 'junction')
            return scan(path)
        for tag in (0xA0000003, 0xA000000C, 0x20000001):
            with self.subTest(tag=tag), self.windows_reparse_metadata({self.root / 'junction': tag}, scan=guarded):
                self.assertEqual(set(SYNC._cleanup_paths(self.root, self.files)), {'old/sync.py'})
        (self.root / 'sync.py').mkdir()
        with self.windows_reparse_metadata({self.root / 'sync.py': 0xA0000003}):
            with self.assertRaisesRegex(ValueError, 'non-ordinary cleanup'):
                SYNC._local_plan(self.root, self.raw, self.files)
        self.assertEqual((self.root / 'old/sync.py').read_bytes(), b'old')
        self.assertEqual((self.root / 'junction/SECTION_11.md').read_bytes(), b'target')
        self.assertFalse((self.root / 'section11').exists())

    def test_junction_data_root_stops_without_scanning(self):
        trap = mock.Mock(side_effect=AssertionError('followed junction root'))
        with self.windows_reparse_metadata({self.root: 0xA0000003}, scan=trap):
            with self.assertRaisesRegex(ValueError, 'non-ordinary cleanup directory'):
                SYNC._cleanup_paths(self.root, self.files)

    def test_hosted_unrelated_opaque_entries_stay_and_matching_ones_stop_installation(self):
        for mode, kind in (('120000', 'blob'), ('160000', 'commit')):
            with self.subTest(mode=mode):
                remote = Remote({'old/SECTION_11.md': b'old'})
                publisher = DirectPublisher(remote)
                entries = publisher.snapshot()['entries']
                opaque = {p: {'path': p, 'mode': mode, 'type': kind, 'sha': 'b' * 40}
                          for p in ('linked', 'section11-legacy-dev-1/linked', 'Custom/sync.py')}
                entries.update(opaque)
                remote.tip = remote.commit_tree(remote.tree_id(entries), [remote.tip], 'Opaque entries')
                updater = H.HostedUpdater(publisher, mock.Mock(return_value=(self.raw, self.files, self.identity)), {})
                with contextlib.redirect_stdout(io.StringIO()):
                    updater.install(publisher.snapshot(), accepted=True)
                after = publisher.snapshot()['entries']
                for path, entry in opaque.items():
                    self.assertEqual(after[path], entry)
                self.assertNotIn('old/SECTION_11.md', after)
                self.assertIn('section11/SECTION_11.md', after)
                self.assertFalse(any(call[:2] == ('GET', '/git/blobs/' + 'b' * 40) for call in remote.calls))
                after['nested/sync.py'] = {'path': 'nested/sync.py', 'mode': mode, 'type': kind, 'sha': 'b' * 40}
                after['old/SECTION_11.md'] = entries['old/SECTION_11.md']
                remote.tip = remote.commit_tree(remote.tree_id(after), [remote.tip], 'Matching opaque entry')
                before = remote.tip
                remote.calls.clear()
                with self.assertRaisesRegex(ValueError, 'non-ordinary cleanup'):
                    updater.install(publisher.snapshot(), accepted=True)
                self.assertEqual(remote.tip, before)
                self.assertTrue(all(call[0] == 'GET' for call in remote.calls))

    def test_selected_nonordinary_file_stops(self):
        write(self.root, {'old/SECTION_11.md': b'old'})
        scan = SYNC.os.scandir
        class FakeEntry:
            name = 'sync.py'
            def stat(self, follow_symlinks=True):
                self_outer.assertFalse(follow_symlinks)
                return SimpleNamespace(st_mode=0o010600)
        self_outer = self
        def guarded(path):
            with scan(path) as entries:
                rows = list(entries)
            return ScandirEntries(rows + ([FakeEntry()] if Path(path) == self.root else []))
        with self.cleanup_scandir(guarded):
            with self.assertRaisesRegex(ValueError, 'non-ordinary cleanup file'):
                SYNC._cleanup_paths(self.root, self.files)
        self.assertEqual((self.root / 'old/SECTION_11.md').read_bytes(), b'old')
