"""Exact-name hosted cleanup shares the local rule and preserves Git recovery."""
import contextlib
import io
from unittest import mock
from test_update_prototype import D, Offline, manifest
from test_b2_hosted import H, Remote, DirectPublisher, release


class HostedAlignmentTests(Offline):
    def test_readme_only_edit_does_not_trigger_automatic_installation(self):
        remote = Remote()
        publisher = DirectPublisher(remote)
        updater = H.HostedUpdater(publisher, mock.Mock(return_value=release()),
                                  {'SECTION11_AUTO_UPDATE': 'true'})
        with contextlib.redirect_stdout(io.StringIO()):
            updater.install(publisher.snapshot(), accepted=True)
            standard = remote.inventory()['README.md']
            edited = standard + b'\nLater README note\n'
            remote.tip = remote.commit({'README.md': edited}, [remote.tip], 'Later edit')
            after, status = updater.maintain(publisher.snapshot(), '2026.10.31', True)
            self.assertIn('README.md', status['plan']['changed'])
            self.assertEqual(remote.inventory()['README.md'], edited)
            self.assertIsNone(H.control(remote.inventory()[H.CONTROL])['available_date'])
            self.assertFalse(after['message'].startswith(H.MARKER))
            updater.install(after, accepted=True)
        self.assertEqual(remote.inventory()['README.md'], standard)

    def test_install_and_hosted_rollback_replace_readme_but_keep_current_timestamp(self):
        remote = Remote({'README.md': b'arbitrary old README\xff'})
        publisher = DirectPublisher(remote)
        updater = H.HostedUpdater(publisher, mock.Mock(return_value=release()), {})
        with contextlib.redirect_stdout(io.StringIO()):
            before = publisher.snapshot()
            self.assertNotIn('README.md', H.cleanup_paths(before))
            self.assertIn('README.md', updater.status(before)['plan']['changed'])
            updater.install(before, accepted=True)
            self.assertEqual(publisher.read(before, 'README.md'), b'arbitrary old README\xff')
            first = remote.inventory()['README.md']
            self.assertIn(b'synthetic/data', first)
            self.assertIn(b'## Sync Now', first)
            self.assertNotIn(b'YOUR_GITHUB_USER', first)
            self.assertNotIn(b'arbitrary old README', first)
            self.assertIn(b'**Last successful sync:** _updated automatically_', first)
            remote.tip = remote.commit({'README.md': b'notes\n**Last successful sync:** previous UTC\n',
                                        'SKILL.md': b'old copy'}, [remote.tip], 'Before update')
            updater.install(publisher.snapshot(), accepted=True)
            current = remote.inventory()['README.md'].replace(b'previous UTC', b'later UTC') + b'\nLater note\n'
            remote.tip = remote.commit({'README.md': current, 'latest.json': b'new data'},
                                       [remote.tip], 'Later data sync')
            updater.rollback(publisher.snapshot())
        self.assertEqual(remote.inventory()['README.md'], current.removesuffix(b'\nLater note\n'))
        self.assertEqual(remote.inventory()['SKILL.md'], b'old copy')
        self.assertEqual(remote.inventory()['latest.json'], b'new data')

    def test_unknown_installed_root_name_does_not_establish_outside_ownership(self):
        remote = Remote({'personal.txt': b'unrelated root file'})
        publisher = DirectPublisher(remote)
        updater = H.HostedUpdater(publisher, mock.Mock(return_value=release()), {})
        with contextlib.redirect_stdout(io.StringIO()):
            updater.install(publisher.snapshot(), accepted=True)
            remote.tip = remote.commit({'section11/personal.txt': b'unknown old extra'},
                                       [remote.tip], 'Personal extra')
            updater.install(publisher.snapshot(), accepted=True)
            self.assertNotIn('section11/personal.txt', remote.inventory())
            self.assertEqual(remote.inventory()['personal.txt'], b'unrelated root file')
            updater.rollback(publisher.snapshot())
        self.assertEqual(remote.inventory()['section11/personal.txt'], b'unknown old extra')
        self.assertEqual(remote.inventory()['personal.txt'], b'unrelated root file')

    def test_verified_manifest_supplements_exact_names_and_rollback_scope(self):
        remote = Remote({'ADDITIONAL_OFFICIAL.md': b'edited outside copy'})
        publisher = DirectPublisher(remote)
        initial = release()
        updater = H.HostedUpdater(publisher, mock.Mock(return_value=initial), {})
        with contextlib.redirect_stdout(io.StringIO()):
            updater.install(publisher.snapshot(), accepted=True)
            files = dict(initial[1], **{'ADDITIONAL_OFFICIAL.md': b'new official file'})
            updater._release = (manifest(files), files,
                                dict(initial[2], tag='2026.10.31', commit='d' * 40))
            updater.install(publisher.snapshot(), accepted=True)
            self.assertNotIn('ADDITIONAL_OFFICIAL.md', remote.inventory())
            updater.rollback(publisher.snapshot())
        self.assertEqual(remote.inventory()['ADDITIONAL_OFFICIAL.md'], b'edited outside copy')

    def test_cleanup_only_install_restores_all_names_after_many_data_commits(self):
        protected = {'custom/SKILL.md': b'custom', 'DOSSIER.md': b'dossier',
            '.gitignore': b'ignore',
            '.github/workflows/auto-sync.yml': b'active workflow',
            '.github/workflows/section11-old.yml': b'old workflow',
            'latest.json': b'data', 'state/private.json': b'state',
            '.sync_config.json': b'config', '.credentials': b'credential-like',
            '.venv/pyvenv.cfg': b'python environment', 'SKILL.md.notes': b'not owned',
            'reports/personal.md': b'not owned', 'examples/personal.py': b'not owned'}
        remote = Remote(protected)
        publisher = DirectPublisher(remote)
        updater = H.HostedUpdater(publisher, mock.Mock(return_value=release()), {})
        with contextlib.redirect_stdout(io.StringIO()):
            updater.install(publisher.snapshot(), accepted=True)
        removed = {name: b'edited arbitrary bytes' for name in D.HISTORICAL_NAMES}
        removed.update({'reports/' + n: b'edited template' for n in D.HISTORICAL_NAMES})
        removed['section11-legacy-dev-55/nested/old.txt'] = b'old developer file'
        removed['examples/sync.py'] = b'edited copied producer'
        remote.tip = remote.commit(removed, [remote.tip], 'Reintroduced copies')
        before = publisher.snapshot()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            after = updater.install(before, accepted=True)
        self.assertEqual(after['parents'], [before['commit']])
        for name in removed:
            self.assertNotIn(name, remote.inventory())
            self.assertIn(name, output.getvalue())
        self.assertIn('.github/workflows/section11-old.yml', output.getvalue())
        self.assertIn('token cannot remove', output.getvalue())
        for name, data in protected.items():
            self.assertEqual(remote.inventory()[name], data)
        for i in range(105):
            remote.tip = remote.commit({'latest.json': str(i).encode()}, [remote.tip], 'Data')
        with contextlib.redirect_stdout(io.StringIO()):
            updater.rollback(publisher.snapshot())
        for name, data in removed.items():
            self.assertEqual(remote.inventory()[name], data)
        self.assertEqual(remote.inventory()['latest.json'], b'104')

    def test_legacy_only_cleanup_has_a_bounded_history_anchor(self):
        remote = Remote({'latest.json': b'data'})
        publisher = DirectPublisher(remote)
        updater = H.HostedUpdater(publisher, mock.Mock(return_value=release()), {})
        path = 'section11-legacy-github-9/ordinary/old.yml'
        with contextlib.redirect_stdout(io.StringIO()):
            updater.install(publisher.snapshot(), accepted=True)
            remote.tip = remote.commit({path: b'old'}, [remote.tip], 'Old copy')
            updater.install(publisher.snapshot(), accepted=True)
            self.assertEqual(H.control(remote.inventory()[H.CONTROL])['history_path'], path.split('/')[0])
            remote.calls.clear()
            updater.rollback(publisher.snapshot())
        self.assertEqual(remote.inventory()[path], b'old')
        queries = [call for call in remote.calls if '/commits?' in call[1]]
        self.assertEqual(len(queries), 5)

    def test_later_copy_edit_is_preserved_and_rollback_stops(self):
        remote = Remote({'latest.json': b'data'})
        publisher = DirectPublisher(remote)
        updater = H.HostedUpdater(publisher, mock.Mock(return_value=release()), {})
        with contextlib.redirect_stdout(io.StringIO()):
            updater.install(publisher.snapshot(), accepted=True)
            remote.tip = remote.commit({'SKILL.md': b'old'}, [remote.tip], 'Copy')
            updater.install(publisher.snapshot(), accepted=True)
            remote.tip = remote.commit({'SKILL.md': b'later edit'}, [remote.tip], 'Later edit')
            with self.assertRaisesRegex(ValueError, 'changed after update'):
                updater.rollback(publisher.snapshot())
        self.assertEqual(remote.inventory()['SKILL.md'], b'later edit')
