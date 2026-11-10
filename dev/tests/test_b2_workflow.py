"""Offline hosted boundaries with real staged legacy workflow/source fixtures."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import D, ROOT, Offline, write, manifest, inventory
from test_b2_hosted import Remote, release
from direct_commit import DirectPublisher
import hosted
import hosted_bootstrap as bootstrap
import hosted_update as H
from _harness import load_module_by_path


class BootstrapTests(Offline):
    def test_unsealed_stops_before_network_directory_import_or_commit(self):
        fetch = mock.Mock(side_effect=AssertionError('must not fetch'))
        path = self.root / 'unsealed'
        with self.assertRaisesRegex(ValueError, 'bootstrap is unsealed'):
            bootstrap.pinned_verifier(path, 'UNSEALED', 'UNSEALED', fetch=fetch)
        self.assertFalse(path.exists())
        fetch.assert_not_called()
        with mock.patch.object(bootstrap, 'pinned_verifier') as verifier, \
                mock.patch.object(bootstrap, 'VERIFIER_BLOB', 'UNSEALED'):
            with self.assertRaisesRegex(ValueError, 'bootstrap is unsealed'):
                bootstrap.main()
            verifier.assert_not_called()

    def test_synthetic_sealed_pins_verify_exact_bytes_before_execution(self):
        data = b'SYNTHETIC_VERIFIER = True\n'
        fetch = mock.Mock(return_value=data)
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        module = bootstrap.pinned_verifier(self.root / 'sealed', blob, hashlib.sha256(data).hexdigest(), fetch)
        self.assertTrue(module.SYNTHETIC_VERIFIER)
        self.assertEqual(fetch.call_args.args[0],
                         'https://api.github.com/repos/CrankAddict/section-11/git/blobs/' + blob)
        self.assertEqual((self.root / 'sealed/trusted_sync.py').read_bytes(), data)

    def test_wrong_digest_executes_no_candidate_and_has_no_main_fallback(self):
        malicious = b'raise AssertionError("unverified code executed")\n'
        fetch = mock.Mock(return_value=malicious)
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            bootstrap.pinned_verifier(self.root / 'bad', 'a' * 40, 'b' * 64, fetch)
        self.assertFalse((self.root / 'bad').exists())
        self.assertEqual(fetch.call_count, 1)
        self.assertNotIn('/main/', fetch.call_args.args[0])

    def test_both_workflows_stop_unsealed_before_checkout_or_dependency_install(self):
        for name in ('json-auto-sync', 'json-on-demand'):
            text = (ROOT / 'dev/fixtures/hosted' / (name + '-v11.105.yml')).read_text()
            self.assertEqual(len(re.findall(r'^      BOOTSTRAP_BLOB: (?:UNSEALED|[0-9a-f]{40})$', text, re.M)), 1)
            self.assertEqual(len(re.findall(r'^      BOOTSTRAP_SHA256: (?:UNSEALED|[0-9a-f]{64})$', text, re.M)), 1)
            self.assertLess(text.index('Require sealed release pins'), text.index('uses: actions/checkout'))
            self.assertLess(text.index('digest mismatch; no code executed'), text.index('subprocess.run'))
            self.assertIn('persist-credentials: false', text)
            self.assertNotIn('pull-requests:', text)
            self.assertNotIn('issues:', text)
            self.assertNotIn('actions: write', text)
            self.assertNotIn('/main/', text)


class WorkflowTests(Offline):
    def setUp(self):
        super().setUp()
        self.auto = (ROOT / 'examples/json-auto-sync/auto-sync.yml').read_bytes()
        self.demand = (ROOT / 'examples/json-on-demand/auto-sync.yml').read_bytes()

    def test_T09_T11_same_adapter_and_inputs_only_triggers_differ(self):
        self.assertEqual(self.auto.split(b'  workflow_dispatch:', 1)[1],
                         self.demand.split(b'  workflow_dispatch:', 1)[1])
        self.assertNotIn(b'  schedule:', self.demand)
        self.assertEqual(hosted.data_crons(self.demand), [])
        self.assertEqual(hosted.data_crons(self.auto), ['7,37 * * * *'])

    def test_timer_job_gate_run_name_and_artifact_boundary(self):
        text = self.auto.decode()
        self.assertIn("jobs:\n  sync:\n    if: ${{ github.event_name != 'schedule' || vars.SECTION11_SYNC_TIMER != 'on' }}\n    runs-on:", text)
        self.assertIn("run-name: ${{ github.event_name == 'workflow_dispatch' && inputs.operation == 'Sync timer' && 'Sync timer run' || 'Auto-Sync Intervals.icu Data' }}", text)
        artifact = text.split('      - name: Upload data files for download\n', 1)[1]
        self.assertTrue(artifact.startswith("        if: always() && github.event_name == 'workflow_dispatch' && steps.prepare.outputs.operation != 'Sync timer' && steps.validate.outcome == 'success'\n"))
        self.assertEqual([line for line in self.auto.splitlines() if line.startswith(b'run-name:')],
                         [line for line in self.demand.splitlines() if line.startswith(b'run-name:')])
        self.assertIn(b"options: [Sync, Update, Status, Rollback, 'Sync timer', Other]", self.demand)

    def test_timer_trigger_identity_operation_and_maintenance_timing(self):
        env = {'SECTION11_DEFAULT_BRANCH': 'main', 'GITHUB_REF': 'refs/heads/main',
               'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_RUN_ID': '42',
               'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_REPOSITORY': 'synthetic/data'}
        run = {'id': 42, 'event': 'workflow_dispatch', 'head_branch': 'main', 'run_attempt': 1,
               'head_repository': {'full_name': 'synthetic/data'}, 'created_at': '2026-11-07T04:00:00Z'}
        api = mock.Mock()
        api.get.return_value = run
        info = hosted.trigger(api, {'inputs': {'operation': 'Sync timer'}}, env)
        self.assertEqual(info['event'], 'workflow_dispatch')
        self.assertEqual(info['operation'], 'Sync timer')
        self.assertEqual(info['cron'], '')
        for operation in ('Sync', 'Update', 'Status', 'Rollback'):
            self.assertEqual(hosted.trigger(api, {'inputs': {'operation': operation}}, env)['operation'], operation)
        for operation in ('sync timer', 'Timer', 'not-an-operation'):
            with self.assertRaisesRegex(ValueError, 'unknown workflow operation'):
                hosted.trigger(api, {'inputs': {'operation': operation}}, env)
        for stamp, expected in (('2026-11-07T03:59:59Z', None),
                                ('2026-11-07T04:00:00Z', '2026.11.07'),
                                ('2026-11-07T23:59:59Z', '2026.11.07')):
            for success in (False, True):
                for attempt in (1, 2):
                    self.assertEqual(H.eligible_day(stamp, info['event'], success, attempt, True), expected)
                    self.assertEqual(H.eligible_day(stamp, 'schedule', success, attempt, True), expected)
        # An external timer remains eligible even without native crons.
        self.assertEqual(H.eligible_day(info['created_at'], info['event'], True, scheduled=False), '2026.11.07')

    def test_timer_export_identity_crosses_token_free_producer_boundary(self):
        (self.root / 'latest.json').write_text('{}')
        for operation, event in (('Sync timer', 'Sync timer'), ('Sync', 'workflow_dispatch')):
            state = {'run_sync': True, 'source': str(ROOT), 'event': 'workflow_dispatch',
                     'operation': operation, 'cron': '', 'available_date': None}
            env = {'ATHLETE_ID': 'synthetic', 'INTERVALS_KEY': 'synthetic-key',
                   'GITHUB_TOKEN': 'never-child', 'GITHUB_WORKSPACE': str(self.root)}
            with mock.patch.dict(os.environ, env), mock.patch.object(hosted, 'context', return_value=state), \
                    mock.patch.object(hosted.subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
                hosted.run_sync()
            child = run.call_args.kwargs['env']
            self.assertEqual(child['SECTION11_EXPORT_EVENT'], event)
            self.assertNotIn('GITHUB_TOKEN', child)
            self.assertEqual(state['event'], 'workflow_dispatch')

    def test_T09_real_legacy_cron_and_secret_names_survive_editor_replacement(self):
        for name in ('fdde807', '0ab6e9d', '2d3980e', '2c8a813'):
            with self.subTest(commit=name):
                text = (ROOT / 'dev/fixtures/hosted' / ('auto-sync-' + name + '.yml')).read_text()
                crons = re.findall(r"- cron: '([^']+)'", text)
                self.assertTrue(crons)
                replacement = self.auto.decode().replace("    - cron: '7,37 * * * *'",
                    '\n'.join("    - cron: '" + cron + "'" for cron in crons))
                self.assertEqual(hosted.data_crons(replacement.encode()), crons)
                names = set(re.findall(r'secrets\.([A-Z_]+)', text)) - {'GITHUB_TOKEN'}
                self.assertTrue(names <= set(re.findall(r'secrets\.([A-Z_]+)', replacement)))
                self.assertIn('sync.py', text)
                self.assertNotIn('--accept-install', text)
                # Old data staging is not an installer, irrespective of code copied in.
                self.assertNotIn('hosted_bootstrap.py', text)

    def test_T11_multiple_custom_crons_are_data(self):
        for crons in (['*/15 * * * *'], ['7 6-18 * * *', '7 0-5,19-23 * * *'], ['19 4 * * *']):
            replacement = self.auto.decode().replace("    - cron: '7,37 * * * *'",
                '\n'.join("    - cron: '" + cron + "'" for cron in crons))
            self.assertEqual(hosted.data_crons(replacement.encode()), crons)

    def test_T15_trigger_requires_actual_default_branch_same_repo_and_attempt(self):
        env = {'SECTION11_DEFAULT_BRANCH': 'main', 'GITHUB_REF': 'refs/heads/main',
               'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_RUN_ID': '42',
               'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_REPOSITORY': 'synthetic/data'}
        run = {'id': 42, 'event': 'workflow_dispatch', 'head_branch': 'main', 'run_attempt': 1,
               'head_repository': {'full_name': 'synthetic/data'}, 'created_at': '2026-10-30T04:00:00Z'}
        api = mock.Mock()
        api.get.return_value = run
        self.assertEqual(hosted.trigger(api, {}, env)['operation'], 'Sync')
        for changed in ({'head_branch': 'feature'}, {'head_repository': {'full_name': 'foreign/data'}},
                        {'run_attempt': 2}, {'event': 'pull_request'}):
            api.get.return_value = dict(run, **changed)
            with self.assertRaises(ValueError):
                hosted.trigger(api, {}, env)

    def test_T14_six_artifact_files_only_and_save_after_confirmed_publication(self):
        text = self.auto.decode()
        path = text.split('name: training-data', 1)[1].split('path: |', 1)[1].split('retention-days:', 1)[0]
        self.assertEqual(path.split(), ['latest.json', 'history.json', 'intervals.json', 'routes.json',
                                       'saved_workouts.json', 'ftp_history.json'])
        self.assertIn("steps.publish.outputs.published == 'true'", text)
        self.assertIn("steps.sync.outputs.cache_changed == 'true'", text)
        self.assertIn("steps.validate.outcome == 'success'", text)
        self.assertNotIn('state/', path)

    def test_T09_T14_literal_producer_argv_and_publisher_token_isolation(self):
        (self.root / 'latest.json').write_text('{}')
        state = {'run_sync': True, 'source': str(ROOT), 'event': 'schedule', 'cron': '*/15 * * * *',
                 'available_date': None, 'source_identity': {'tag': '2026.10.30'}}
        env = {'ATHLETE_ID': 'synthetic;echo not-code', 'INTERVALS_KEY': 'synthetic key',
               'GITHUB_TOKEN': 'never-child', 'GH_TOKEN': 'never-child', 'GIT_CONFIG_COUNT': '1',
               'GITHUB_WORKSPACE': str(self.root), 'SECTION11_DAYS': '14'}
        with mock.patch.dict(os.environ, env), mock.patch.object(hosted, 'context', return_value=state), \
                mock.patch.object(hosted.subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
            hosted.run_sync()
        argv = run.call_args.args[0]
        self.assertEqual(argv[3], env['ATHLETE_ID'])
        self.assertIn('synthetic key', argv)
        self.assertEqual(argv[-4:], ['--days', '14', '--output', 'latest.json'])
        child = run.call_args.kwargs['env']
        for name in ('GITHUB_TOKEN', 'GH_TOKEN', 'GIT_CONFIG_COUNT'):
            self.assertNotIn(name, child)
        self.assertEqual(child['SECTION11_EXPORT_CRON'], '*/15 * * * *')
        self.assertEqual(child['SECTION11_EXPORT_EVENT'], 'schedule')

    def test_T14_readme_initializes_actual_identity_and_preserves_existing_text(self):
        created = hosted.readme(None, ROOT, 'synthetic UTC', 'fictional/fitness', 'trunk').decode()
        self.assertIn('fictional/fitness', created)
        self.assertNotIn('YOUR_', created)
        self.assertIn('section11/examples/json-examples/README.md', created)
        self.assertIn('**Last successful sync:** synthetic UTC', created)
        existing = b'# Owner text\nPrivate note\n**Last successful sync:** yesterday\n'
        self.assertEqual(hosted.readme(existing, ROOT, 'today', 'fictional/fitness', 'main'),
                         b'# Owner text\nPrivate note\n**Last successful sync:** today\n')

    def test_T14_cache_promote_requires_confirmed_publication(self):
        with mock.patch.object(hosted, 'context', return_value={'published': False}):
            with self.assertRaisesRegex(ValueError, 'confirmed data publication'):
                hosted.cache_promote()

    def test_T17_data_control_transport_is_same_repo_bounded_and_never_retries(self):
        api = hosted.HostedGitHub('synthetic/data', 'synthetic-token')
        with mock.patch.object(hosted.requests, 'request') as request:
            with self.assertRaisesRegex(ValueError, 'cross-repository'):
                api.request('GET', '/repos/CrankAddict/section-11/releases/latest')
            request.assert_not_called()
            response = mock.Mock(status_code=403, content=b'{}')
            request.return_value = response
            with self.assertRaises(hosted.APIError):
                api.get('/git/ref/heads/main')
            self.assertEqual(request.call_count, 1)
            self.assertFalse(request.call_args.kwargs['allow_redirects'])
            self.assertLessEqual(request.call_args.kwargs['timeout'], 10)
            api.count = 1200
            with self.assertRaisesRegex(ValueError, 'admission bound'):
                api.get('/git/ref/heads/main')
            self.assertEqual(request.call_count, 1)
            api.count = 0
            api.deadline = 0
            with self.assertRaisesRegex(ValueError, 'admission bound'):
                api.get('/git/ref/heads/main')
            self.assertEqual(request.call_count, 1)


class PushDispatchTests(Offline):
    def setUp(self):
        super().setUp()
        self.push = load_module_by_path('b2_dispatch_push', ROOT / 'examples/agentic/push.py')

    def test_T09_old_dispatch_fields_preserved_and_stub_calls_managed_tool(self):
        stub = (ROOT / 'examples/agentic/push-workout.yml').read_text()
        inputs = set(re.findall(r'^      ([a-z_]+):$', stub, re.M))
        for name in ('fdde807', '0ab6e9d', '2d3980e', '2c8a813'):
            old = (ROOT / 'dev/fixtures/hosted' / ('push-workout-' + name + '.yml')).read_text()
            self.assertTrue(set(re.findall(r'^      ([a-z_]+):$', old, re.M)) <= inputs)
        self.assertIn('python section11/examples/agentic/push.py --workflow', stub)
        self.assertNotIn('eval ', stub)
        self.assertNotIn('github.event.inputs', stub)

    def test_T09_preview_confirm_and_literal_injection_like_inputs(self):
        values = {'command': 'annotate', 'activity_id': '42', 'message': '"; echo not-code; $(not-code)',
                  'confirm': 'false', 'chat': 'true'}
        argv = self.push.workflow_arguments(values, self.root / 'unused.json')
        self.assertIn('--message=' + values['message'], argv)
        self.assertNotIn('--confirm', argv)
        self.assertIn('--chat', argv)
        self.assertIn('--confirm', self.push.workflow_arguments(dict(values, confirm='true'), self.root / 'unused.json'))
        for values in ({'command': 'move', 'time': '25:00'}, {'command': 'delete', 'time': '09:00'},
                       {'command': 'push', 'confirm': 'yes'}, {'command': 'sh'}):
            with self.assertRaises(ValueError):
                self.push.workflow_arguments(values, self.root / 'bad.json')

    def test_T09_workout_json_is_data_only_and_list_never_confirms(self):
        value = '[{"name":"$(not-code)","description":"literal"}]'
        path = self.root / 'workouts.json'
        argv = self.push.workflow_arguments({'workouts': value}, path)
        self.assertEqual(argv, ['push', '--json', str(path)])
        self.assertEqual(path.read_text(), value)
        self.assertNotIn('--confirm', self.push.workflow_arguments({'command': 'list', 'confirm': 'true'}, path))
