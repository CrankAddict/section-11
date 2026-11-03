"""Real controller phases against an offline content-addressed repository."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import D, ROOT, Offline, manifest, write, inventory
from test_b2_hosted import Remote, release
from test_data_overview import tiny_png
from direct_commit import DirectPublisher
import hosted
import hosted_update as H


class ControllerIntegration(Offline):
    def setUp(self):
        super().setUp()
        self.checkout = self.root / 'checkout'
        self.runner = self.root / 'runner'
        self.runner.mkdir()
        raw, files, identity = release()
        files = dict(files)
        files['examples/json-auto-sync/DATA_REPO_README_TEMPLATE.md'] = (
            ROOT / 'examples/json-auto-sync/DATA_REPO_README_TEMPLATE.md').read_bytes()
        self.target = manifest(files), files, identity
        self.source = self.runner / 'source'
        write(self.source, dict(files, **{'manifest.json': self.target[0],
                                        D.RECEIPT: D.receipt(self.target[0], identity)}))
        self.workflow = (ROOT / 'examples/json-auto-sync/auto-sync.yml').read_bytes()
        self.protected = {'DOSSIER.md': b'private synthetic dossier', 'custom/mine.json': b'{"keep":true}',
                          '.sync_config.json': b'{"athlete":"synthetic"}',
                          '.github/workflows/auto-sync.yml': self.workflow}
        self.remote = Remote(dict(self.protected, **{'sync.py': b'old root source'}))
        self.remote.repo = 'synthetic/data'
        self.pub = DirectPublisher(self.remote)
        self.fetch = mock.Mock(return_value=self.target)
        self.verifier = SimpleNamespace(Distribution=SimpleNamespace(fetch=self.fetch))
        self.event = self.runner / 'event.json'
        self.event.write_text('{}')
        self.env = {'RUNNER_TEMP': str(self.runner), 'GITHUB_WORKSPACE': str(self.checkout),
                    'GITHUB_EVENT_PATH': str(self.event), 'GITHUB_OUTPUT': str(self.runner / 'outputs'),
                    'GITHUB_REPOSITORY': 'synthetic/data', 'SECTION11_DEFAULT_BRANCH': 'main',
                    'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
                    'GITHUB_RUN_ID': '42', 'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_ACTIONS': 'true',
                    'RUNNER_OS': 'Linux', 'GITHUB_REPOSITORY_ID': '123'}
        self.info = {'event': 'workflow_dispatch', 'created_at': '2026-10-30T12:00:00Z',
                     'attempt': 1, 'operation': 'Sync', 'cron': ''}
        for patch in (mock.patch.dict(os.environ, self.env, clear=True),
                      mock.patch.object(hosted, 'publisher', return_value=self.pub),
                      mock.patch.object(hosted, 'trigger', side_effect=lambda *a: dict(self.info)),
                      mock.patch.object(sys, 'argv', ['hosted_bootstrap.py', '--wrapper-api', '2', '--accept-install'])):
            patch.start()
            self.addCleanup(patch.stop)
        write(self.checkout, self.remote.inventory())

    def prepare(self):
        hosted.prepare(self.source, self.target, self.verifier)

    def generated(self):
        files = ['latest.json', 'routes.json', 'route_eta_history.json', 'maps/weather/new.png']
        document = {'data_overview': {'version': 1, 'managed_files': files},
                    'export_freshness': {'generated_at': '2026-10-30T12:01:00Z', 'mode': 'on_demand'},
                    'metadata': {'version': 'synthetic producer version'}}
        write(self.checkout, {'latest.json': H.encoded(document), 'routes.json': b'{"events":[]}',
                              'route_eta_history.json': b'{}', 'maps/weather/new.png': tiny_png(),
                              'state/private.json': b'{"token":"synthetic-do-not-publish"}'})
        return document

    def test_T09_real_legacy_sources_first_install_then_validated_data_and_claim(self):
        # Exercise complete phases with each actual old hosted source, not a
        # fabricated equality-only legacy layout. The old code is never imported.
        for name in ('fdde807', '0ab6e9d', '2d3980e', '2c8a813'):
            old = (ROOT / 'dev/fixtures/hosted' / ('sync-' + name + '.py')).read_bytes()
            self.assertIn(b'class IntervalsSync', old)
        old = (ROOT / 'dev/fixtures/hosted/sync-fdde807.py').read_bytes()
        self.remote.tip = self.remote.commit({'sync.py': old}, [self.remote.tip], 'Legacy input')
        (self.checkout / 'sync.py').write_bytes(old)
        initial = self.remote.tip
        self.prepare()
        installed = self.remote.tip
        self.assertNotEqual(installed, initial)
        self.fetch.assert_not_called()  # bootstrap's verified target was shared
        self.assertFalse((self.checkout / 'sync.py').exists())
        self.assertEqual(D.tree(self.checkout / 'section11'), self.target[:2])
        self.generated()
        hosted.publish_data()
        published = self.remote.tip
        self.assertNotEqual(published, installed)
        self.assertTrue(hosted.context()['published'])
        hosted.maintain()
        actual = self.remote.inventory()
        for name, data in self.protected.items():
            self.assertEqual(actual[name], data)
        self.assertNotIn('state/private.json', actual)
        self.assertIn('maps/weather/new.png', actual)
        self.assertIn('route_eta_history.json', actual)
        self.assertEqual([actual[p] for p in actual if p.startswith('archive/')], [actual['latest.json']])
        self.assertIn(b'synthetic/data', actual['README.md'])
        self.assertEqual(H.control(actual[H.CONTROL])['attempted_day'], '2026.10.30')
        self.assertEqual(json.loads(actual['latest.json'])['metadata']['version'], 'synthetic producer version')
        self.assertEqual(len([c for c in self.remote.calls if c[0] == 'PATCH']), 3)

    def test_T14_declared_cleanup_and_private_public_repository_behavior_equal(self):
        old = H.encoded({'data_overview': {'version': 1, 'managed_files': ['latest.json', 'maps/weather/stale.png']}})
        self.remote.tip = self.remote.commit({'latest.json': old, 'maps/weather/stale.png': tiny_png()},
                                             [self.remote.tip], 'Old data')
        write(self.checkout, {'latest.json': old, 'maps/weather/stale.png': tiny_png()})
        self.prepare()
        self.generated()
        hosted.publish_data()
        self.assertNotIn('maps/weather/stale.png', self.remote.inventory())
        self.assertIn('maps/weather/new.png', self.remote.inventory())
        self.assertFalse(any('visibility' in c[1] or '/pulls' in c[1] for c in self.remote.calls))

    def test_install_replaces_readme_then_later_sync_changes_only_its_timestamp(self):
        old = b'old project notes\n**Last successful sync:** 2026-10-29 12:00:00 UTC\n'
        self.remote.tip = self.remote.commit({'README.md': old}, [self.remote.tip], 'Old README')
        write(self.checkout, {'README.md': old})
        previous = self.pub.snapshot()
        with contextlib.redirect_stdout(io.StringIO()):
            self.prepare()
        installed = self.remote.inventory()['README.md']
        self.assertEqual((self.checkout / 'README.md').read_bytes(), installed)
        self.assertEqual(self.pub.read(previous, 'README.md'), old)
        self.assertNotIn(b'old project notes', installed)
        self.assertEqual(installed, hosted.readme(None, self.source,
            '2026-10-29 12:00:00 UTC', 'synthetic/data', 'main'))
        self.generated()
        with mock.patch.object(hosted, 'datetime') as clock:
            clock.now.return_value = datetime(2026, 10, 30, 13, tzinfo=timezone.utc)
            hosted.publish_data()
        first = self.remote.inventory()['README.md'] + b'\nKeep this later note\n'
        self.remote.tip = self.remote.commit({'README.md': first}, [self.remote.tip], 'Later note')
        write(self.checkout, self.remote.inventory())
        next_runner = self.root / 'next-runner'
        next_runner.mkdir()
        runner_environment = mock.patch.dict(os.environ, {'RUNNER_TEMP': str(next_runner)})
        runner_environment.start()
        self.addCleanup(runner_environment.stop)
        self.prepare()
        document = self.generated()
        document['metadata']['generation'] = 2
        write(self.checkout, {'latest.json': H.encoded(document)})
        with mock.patch.object(hosted, 'datetime') as clock:
            clock.now.return_value = datetime(2026, 10, 30, 14, tzinfo=timezone.utc)
            hosted.publish_data()
        self.assertEqual(self.remote.inventory()['README.md'],
            first.replace(b'2026-10-30 13:00:00 UTC', b'2026-10-30 14:00:00 UTC'))

    def test_T12_unknown_data_publication_blocks_cache_and_maintenance(self):
        self.prepare()
        self.generated()
        self.remote.ref_fault = 'unknown'
        with self.assertRaisesRegex(RuntimeError, 'unknown'):
            hosted.publish_data()
        self.assertFalse(hosted.context().get('published', False))
        with self.assertRaisesRegex(ValueError, 'confirmed data'):
            hosted.cache_promote()
        self.assertEqual(len([c for c in self.remote.calls if c[0] == 'PATCH']), 2)

    def test_missing_template_and_readme_do_not_block_first_sync(self):
        files = dict(self.target[1])
        del files[H.README_TEMPLATE]
        self.target = manifest(files), files, self.target[2]
        (self.source / H.README_TEMPLATE).unlink()
        write(self.source, {'manifest.json': self.target[0],
                            D.RECEIPT: D.receipt(self.target[0], self.target[2])})
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.prepare()
            self.assertNotIn('README.md', self.remote.inventory())
            self.assertFalse((self.checkout / 'README.md').exists())
            self.generated()
            hosted.publish_data()
        self.assertIn(H.README_UNCHANGED, output.getvalue())
        self.assertNotIn('README.md', self.remote.inventory())
        self.assertTrue(hosted.context()['published'])
        self.assertIn('latest.json', self.remote.inventory())
        for name, data in self.protected.items():
            self.assertEqual(self.remote.inventory()[name], data)

    def test_T14_malformed_generated_data_stops_before_publication(self):
        self.prepare()
        before = self.remote.tip
        (self.checkout / 'latest.json').write_bytes(b'{bad json')
        with self.assertRaises(ValueError):
            hosted.publish_data()
        self.assertEqual(self.remote.tip, before)

    def test_T16_fictional_demo_installs_then_uses_real_notice_validation_and_publication(self):
        from datetime import date
        from test_demo_kit import G
        with mock.patch.object(hosted, 'run_sync', side_effect=AssertionError('real producer must not run')):
            self.prepare()
            info = hosted.context()
            info['available_date'] = '2026.10.31'
            hosted.context(info)
            G.produce(self.checkout, date(2026, 10, 30))
            hosted.finalize_export()
            hosted.validate_generated()
            hosted.publish_data()
            hosted.maintain()
        remote = self.remote.inventory()
        self.assertEqual(json.loads(remote['latest.json'])['update_notice'], H.NOTICE)
        for name in G.FILES:
            self.assertIs(json.loads(remote[name])['metadata']['synthetic'], True)
        self.assertEqual(remote['DOSSIER.md'], self.protected['DOSSIER.md'])
        self.assertEqual(remote['custom/mine.json'], self.protected['custom/mine.json'])
        self.assertEqual(remote['.github/workflows/auto-sync.yml'], self.workflow)
        self.assertNotIn('sync.py', remote)
        self.assertNotIn('state/', '\n'.join(remote))
        self.assertTrue(hosted.context()['published'])
        self.assertEqual(H.control(remote[H.CONTROL])['attempted_day'], '2026.10.30')

    def test_T10_local_custom_type_collision_stops_before_remote_install(self):
        (self.checkout / 'custom/mine.json').unlink()
        (self.checkout / 'custom').rmdir()
        (self.checkout / 'custom').write_bytes(b'owner file')
        before = self.remote.tip
        with self.assertRaisesRegex(ValueError, 'custom checkout'):
            self.prepare()
        self.assertEqual(self.remote.tip, before)
        self.assertFalse(any(c[0] != 'GET' for c in self.remote.calls))


    def test_T10_missing_receipt_with_recorded_date_does_not_silently_reinstall(self):
        self.prepare()
        path = 'section11/' + D.RECEIPT
        self.remote.tip = self.remote.commit({path: None}, [self.remote.tip], 'Damaged identity')
        (self.checkout / path).unlink()
        before = self.remote.tip
        self.prepare()
        self.assertEqual(self.remote.tip, before)
        self.assertNotIn(path, self.remote.inventory())

    def test_resolved_custom_guidance_repair_invalidates_pending_notice(self):
        self.prepare()
        self.remote.tip = self.remote.commit({'custom/README.md': None}, [self.remote.tip], 'Missing guidance')
        state = H.control(self.remote.inventory()[H.CONTROL])
        state['available_date'] = self.target[2]['tag']
        state['available_tree'] = H.installation_digest(DirectPublisher(self.remote).snapshot())
        self.remote.tip = self.remote.commit({H.CONTROL: H.encoded(state)}, [self.remote.tip], 'Pending repair')
        self.remote.tip = self.remote.commit(
            {'custom/README.md': self.target[1]['examples/maintenance/CUSTOM_README.md']},
            [self.remote.tip], 'Guidance restored')
        write(self.checkout, self.remote.inventory())
        self.prepare()
        self.assertIsNone(hosted.context()['available_date'])

    def test_T11_next_export_does_not_repeat_a_deliberately_skipped_notice(self):
        self.prepare()
        state = H.control(self.remote.inventory()[H.CONTROL])
        state['available_date'] = '2026.10.31'
        state['available_tree'] = H.installation_digest(DirectPublisher(self.remote).snapshot())
        state['skip_release'] = '2026.10.31'
        self.remote.tip = self.remote.commit({H.CONTROL: H.encoded(state)}, [self.remote.tip], 'Pending notice')
        (self.checkout / H.CONTROL).write_bytes(H.encoded(state))
        self.prepare()
        self.assertIsNone(hosted.context()['available_date'])


class UnsealedWorkflowExecution(Offline):
    def test_actual_first_step_rejects_unsealed_and_accepts_only_synthetic_complete_pins(self):
        for name in ('json-auto-sync', 'json-on-demand'):
            text = (ROOT / 'examples' / name / 'auto-sync.yml').read_text()
            guard = text.split('run: |', 1)[1].split('      - name:', 1)[0]
            script = '\n'.join(line[10:] for line in guard.splitlines() if line.strip())
            for commit, digest, result in (('UNSEALED', 'UNSEALED', 1),
                                           ('a' * 40, 'UNSEALED', 1),
                                           ('a' * 40, 'b' * 64, 0)):
                completed = subprocess.run(['/bin/bash', '-c', script],
                    env={'BOOTSTRAP_BLOB': commit, 'BOOTSTRAP_SHA256': digest},
                    capture_output=True, text=True, check=False)
                self.assertEqual(completed.returncode, result)
                self.assertEqual(completed.stdout.count('\n'), result)
                if result:
                    self.assertIn('bootstrap is unsealed', completed.stdout)
