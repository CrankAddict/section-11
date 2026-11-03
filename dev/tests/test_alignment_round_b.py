"""Round B: copied release paths, protected neighbours and exact recovery."""
import contextlib
import io
from pathlib import Path
from unittest import mock

from test_update_prototype import D, SYNC, Offline, fixture, install, manifest, write
from test_alignment_recovery import recovery_bytes
from test_b2_hosted import H, Remote, DirectPublisher


class RoundBCleanupTests(Offline):
    def setUp(self):
        super().setUp()
        _, self.files = fixture()
        self.files.update({
            'README.md': b'release readme',
            'examples/agentic/push.py': b'new push',
            'examples/workout-library/WORKOUT_REFERENCE.md': b'new library',
            'examples/reports/POST_WORKOUT_REPORT_EXAMPLES.md': b'new examples',
            'examples/requirements.txt': b'requests',
            'examples/json-examples/latest.json': b'fictional data',
            'examples/env/sync.py': b'example',
            'examples/conda/sync.py': b'example',
            'examples/custom/sync.py': b'example',
        })
        self.raw = manifest(self.files)
        self.identity = {'tag': '2026.10.31', 'commit': 'a' * 40}
        self.removed = {
            'examples/sync.py': b'edited old producer\r\n',
            'examples/agentic/push.py': b'older push, no final newline',
            'WORKOUT_REFERENCE.md': b'edited root library',
            'reports/POST_WORKOUT_REPORT_EXAMPLES.md': b'old report examples',
            'requirements.txt': b'my edited requirements',
            'LICENSE': b'my edited license',
            'SECURITY.md': b'my edited security document',
            'manifest.json': b'edited manifest',
            'INSTRUCTIONS.md': b'historical root',
            'gitignore.txt': b'historical root',
            'section11-legacy-dev-1/nested/old.py': b'legacy',
            'other/sync.py': b'now covered in every folder',
        }
        self.kept = {name: ('private:' + name).encode() for name in (
            'DOSSIER.md', 'latest.json', 'history.json', 'intervals.json', 'routes.json',
            'saved_workouts.json', 'ftp_history.json', 'route_eta_history.json',
            '.sync_config.json', 'sync.log', 'maps/map.png', 'archive/old.json',
            'state/private.json', '.section11-state/owner-note', '.git/config',
            '.github/workflows/auto-sync.yml', '.gitignore', '.secrets',
            'custom/sync.py', 'examples/custom/sync.py',
            'examples/env/pyvenv.cfg', 'examples/env/sync.py',
            'examples/conda/conda-meta/history', 'examples/conda/sync.py',
            '.venv/sync.py', 'section11-legacy-dev-1/custom/old.py',
            'section11-legacy-dev-1/.hidden/old.py',
            'section11-legacy-dev-1/state/old.py',
            'reports/personal.md', 'examples/personal.py',
            'section11-legacy-dev-not-a-directory',
        )}
        self.kept['.sync_config.json'] = b'{"auto_sync":false}'

    def test_local_plan_prunes_only_empty_parents_and_zip_restores_exact_files(self):
        removed = dict(self.removed, **{'README.md': b'old local README'})
        write(self.root, dict(self.kept, **removed))
        (self.root / 'examples/unrelated-empty').mkdir()
        (self.root / 'section11-legacy-dev-empty').mkdir()
        (self.root / 'examples/agentic/push.py').chmod(0o751)
        install(self.root / 'section11', self.raw, self.files)
        plan = SYNC._local_plan(self.root, self.raw, self.files)
        self.assertTrue(set(removed) <= set(plan['cleanup_names']))
        self.assertIn('examples/agentic/', plan['cleanup_names'])
        self.assertNotIn('examples/', plan['cleanup_names'])
        self.assertNotIn('section11-legacy-dev-1/', plan['cleanup_names'])
        self.assertFalse(set(self.kept) & set(plan['cleanup_names']))
        SYNC._install_local(self.root, self.raw, self.files, self.identity, plan)
        record = SYNC._previous_install(self.root)[0]
        self.assertEqual(recovery_bytes(self.root, record, 'entries/'), removed)
        self.assertFalse((self.root / 'examples/agentic').exists())
        self.assertFalse((self.root / 'section11-legacy-dev-empty').exists())
        self.assertTrue((self.root / 'examples/unrelated-empty').is_dir())
        for name, data in self.kept.items():
            self.assertEqual((self.root / name).read_bytes(), data, name)
        write(self.root, {'latest.json': b'newer user data', 'examples/later-note': b'later'})
        SYNC._rollback_local(self.root, record)
        for name, data in removed.items():
            self.assertEqual((self.root / name).read_bytes(), data, name)
        self.assertEqual((self.root / 'examples/agentic/push.py').stat().st_mode & 0o777, 0o751)
        self.assertEqual((self.root / 'latest.json').read_bytes(), b'newer user data')
        self.assertEqual((self.root / 'examples/later-note').read_bytes(), b'later')
        self.assertTrue((self.root / 'section11-legacy-dev-empty').is_dir())

    def test_hosted_parity_plans_and_history_restore_nested_copies(self):
        remote = Remote(self.kept)
        publisher = DirectPublisher(remote)
        updater = H.HostedUpdater(publisher, mock.Mock(return_value=(self.raw, self.files, self.identity)), {})
        with contextlib.redirect_stdout(io.StringIO()):
            updater.install(publisher.snapshot(), accepted=True)
        remote.tip = remote.commit(self.removed, [remote.tip], 'Edited outside copies')
        before = publisher.snapshot()
        write(self.root, dict(self.kept, **self.removed))
        self.assertEqual(set(SYNC._cleanup_paths(self.root, self.files, hosted=True)), set(H.cleanup_paths(before, self.files)))
        self.assertEqual(set(H.cleanup_paths(before, self.files)), set(self.removed))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            status = updater.status(before)
            self.assertTrue(set(self.removed) <= set(status['plan']['removed']))
            updater.install(before, accepted=True)
        for name in self.removed:
            self.assertNotIn(name, remote.inventory())
            self.assertIn(name, output.getvalue())
        for name, data in self.kept.items():
            self.assertEqual(remote.inventory()[name], data, name)
        remote.tip = remote.commit({'latest.json': b'newer data'}, [remote.tip], 'Data')
        with contextlib.redirect_stdout(io.StringIO()):
            updater.rollback(publisher.snapshot())
        for name, data in self.removed.items():
            self.assertEqual(remote.inventory()[name], data, name)
        self.assertEqual(remote.inventory()['latest.json'], b'newer data')

    def test_nested_cleanup_preimage_change_refuses_before_activation(self):
        write(self.root, {'examples/sync.py': b'old', '.sync_config.json': b'{"auto_sync":false}'})
        plan = SYNC._local_plan(self.root, self.raw, self.files)
        write(self.root, {'examples/sync.py': b'later edit'})
        with self.assertRaisesRegex(ValueError, 'changed'):
            SYNC._install_local(self.root, self.raw, self.files, self.identity, plan)
        self.assertEqual((self.root / 'examples/sync.py').read_bytes(), b'later edit')
        self.assertFalse((self.root / 'section11').exists())

    def test_every_removed_file_and_empty_parent_precedes_acceptance(self):
        write(self.root, {'examples/agentic/push.py': b'edited old copy'})
        output = io.StringIO()
        def decline(prompt):
            self.assertIn('examples/agentic/push.py', output.getvalue())
            self.assertIn('examples/agentic/', output.getvalue())
            self.assertIn('examples/', output.getvalue())
            return 'n'
        with mock.patch.object(Path, 'cwd', return_value=self.root), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(self.raw, self.files, self.identity)), \
                mock.patch('builtins.input', side_effect=decline), contextlib.redirect_stdout(output):
            self.assertFalse(SYNC.do_update())
        self.assertEqual((self.root / 'examples/agentic/push.py').read_bytes(), b'edited old copy')
        self.assertFalse((self.root / 'section11').exists())

    def test_prior_directory_recovery_record_is_not_reclassified(self):
        write(self.root, {'section11/old.py': b'old producer', '.sync_config.json': b'{"auto_sync":false}',
                          'section11-legacy-dev-old/.hidden/old.py': b'old archived hidden file'})
        # Round A selected the whole legacy directory, including hidden files.
        original = SYNC._cleanup_paths
        def previous_policy(root, release_paths=(), hosted=False):
            result = original(root, release_paths, hosted)
            name = 'section11-legacy-dev-old'
            if (Path(root) / name).exists():
                result[name] = 'legacy Section 11 directory'
            return result
        with mock.patch.object(SYNC, '_cleanup_paths', side_effect=previous_policy):
            plan = SYNC._local_plan(self.root, self.raw, self.files)
            SYNC._install_local(self.root, self.raw, self.files, self.identity, plan)
        record = SYNC._previous_install(self.root)[0]
        SYNC._rollback_local(self.root, record)
        self.assertEqual((self.root / 'section11-legacy-dev-old/.hidden/old.py').read_bytes(), b'old archived hidden file')

    def test_notice_binds_expanded_cleanup_names(self):
        install(self.root / 'section11', self.raw, self.files)
        write(self.root, {'examples/agentic/push.py': b'old copied tool'})
        saved = {'available_release': self.identity['tag'],
                 'available_tree': SYNC._ordinary_tree_digest(self.root / 'section11'),
                 'available_entries': SYNC._entry_digests(self.root, self.files)}
        self.assertTrue(SYNC._local_notice_matches(self.root, saved))
        (self.root / 'examples/agentic/push.py').unlink()
        self.assertFalse(SYNC._local_notice_matches(self.root, saved))

    def test_timer_adapter_stays_within_rev4_ceiling(self):
        lines = (Path(__file__).resolve().parents[2] / 'examples/sync.py').read_text().splitlines()
        start = lines.index('class LocalTimers:')
        end = next(i for i in range(start + 1, len(lines)) if lines[i] and not lines[i][0].isspace())
        self.assertLessEqual(end - start, 283)
