"""B1 acceptance: real local trees, synthetic data, mocked release and OS commands."""
import contextlib
import io
import importlib
import json
import os
import plistlib
import sys
import subprocess
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import D, SYNC, ROOT, REAL_TIMERS, Offline, install, inventory, write, manifest
from test_update_path_fixes import ReleaseHTTP, Response
from _harness import load_module_by_path


class LocalInstallerTests(Offline):
    def setUp(self):
        super().setUp()
        self.wire = ReleaseHTTP(4)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(SYNC.Path, 'cwd', return_value=self.root))
        self.stack.enter_context(mock.patch.dict(os.environ, {'GITHUB_ACTIONS': ''}))
        self.stack.enter_context(mock.patch.object(SYNC, '_fetch_verified_release',
            return_value=(self.wire.raw[4], self.wire.files[4], self.wire.identity(4))))
        write(self.root, {'DOSSIER.md': b'private', 'latest.json': b'newer data',
                          'state/private.json': b'preserve', '.sync_config.json': b'{"check_interval_minutes":5}'})

    def run_install(self, answer='y', init=False, **kwargs):
        output = io.StringIO()
        with mock.patch('builtins.input', return_value=answer) as prompt, contextlib.redirect_stdout(output):
            result = (SYNC.do_init if init else SYNC.do_update)(**kwargs)
        return result, output.getvalue(), prompt.call_count

    def test_T03_absent_root_copy_only_init_update_identical(self):
        for init in (False, True):
            with self.subTest(init=init):
                root = self.root / ('init' if init else 'update')
                write(root, {'sync.py': b'root legacy', 'push.py': b'push legacy', 'pull.py': b'pull legacy'})
                with mock.patch.object(SYNC.Path, 'cwd', return_value=root):
                    result, output, prompts = self.run_install(init=init)
                self.assertTrue(result, output)
                self.assertEqual(prompts, 1)
                self.assertEqual(D.tree(root / 'section11'), (self.wire.raw[4], self.wire.files[4]))
                self.assertTrue((root / 'custom/README.md').exists())
                self.assertTrue(all(not (root / n).exists() for n in SYNC._ROOT_ENTRIES))
                self.assertIn('Auto sync will be installed (every 1 minute). If you set up your own timer before, remove it.', output)
        self.assertEqual(inventory(self.root / 'init/section11'), inventory(self.root / 'update/section11'))

    def test_standard_refresh_on_matching_init_update_preserves_previous_slot(self):
        self.assertTrue(self.run_install()[0])
        previous = (self.root / '.section11-state/previous.json').read_bytes()
        original = self.timers.command
        writes = []
        def command(adapter, argv, input=None):
            if argv == ['crontab', '-']:
                writes.append(input)
            return original(adapter, argv, input)
        with mock.patch.object(self.timers, 'command', command):
            for init in (False, True):
                result, output, prompts = self.run_install(init=init)
                self.assertTrue(result, output)
                self.assertEqual(prompts, 1)
                self.assertEqual((self.root / '.section11-state/previous.json').read_bytes(), previous)
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[0], writes[1])
        self.assertFalse((self.root / '.section11-state/transaction.json').exists())

    def test_matching_refresh_unknown_preserves_journal_and_previous_slot(self):
        self.assertTrue(self.run_install()[0])
        previous = (self.root / '.section11-state/previous.json').read_bytes()
        original = self.timers.command
        writes = []
        def command(adapter, argv, input=None):
            if argv == ['crontab', '-']:
                writes.append(argv)
                raise TimeoutError('synthetic refresh timeout')
            return original(adapter, argv, input)
        with mock.patch.object(self.timers, 'command', command):
            result, output, _ = self.run_install()
        self.assertFalse(result)
        self.assertIn('timer write outcome unknown', output)
        self.assertEqual(len(writes), 1)
        self.assertEqual((self.root / '.section11-state/previous.json').read_bytes(), previous)
        self.assertTrue((self.root / '.section11-state/transaction.json').exists())
        result, output, prompts = self.run_install()
        self.assertFalse(result)
        self.assertEqual(prompts, 0)
        self.assertIn('interrupted update', output)

    def test_T04_decline_is_exact_and_one_warning_without_file_list(self):
        write(self.root, {'section11/personal-secret-name.txt': b'edit', 'sync.py': b'legacy'})
        before = inventory(self.root)
        result, output, prompts = self.run_install('n', timer_choice=False)
        self.assertFalse(result)
        self.assertEqual(prompts, 1)
        self.assertEqual(output.count(SYNC.CONVERSION_WARNING), 1)
        self.assertNotIn('personal-secret-name', output)
        self.assertEqual(inventory(self.root), before)
        self.assertEqual(self.timers.crontabs, {})

    def test_T05_normal_update_deletes_unknown_and_lists_it(self):
        self.assertTrue(self.run_install()[0])
        write(self.root, {'section11/unknown.txt': b'personal', 'custom/mine.txt': b'keep',
                          'section11/LICENSE': b'edited'})
        result, output, prompts = self.run_install()
        self.assertTrue(result, output)
        self.assertEqual(prompts, 1)
        self.assertIn('[removed] unknown.txt', output)
        self.assertIn('[changed] LICENSE', output)
        self.assertFalse((self.root / 'section11/unknown.txt').exists())
        self.assertEqual((self.root / 'custom/mine.txt').read_bytes(), b'keep')

    def test_T13_root_only_rollback_restores_all_tools_timer_and_keeps_new_data(self):
        originals = {n: ('old ' + n).encode() for n in SYNC._ROOT_ENTRIES}
        write(self.root, originals)
        timer = '*/5 * * * * cd ' + str(self.root) + ' && python3 sync.py --days 14 --output alternate.json\n'
        self.timers.crontabs[str(self.root)] = timer
        result, output, _ = self.run_install()
        self.assertTrue(result, output)
        self.assertIn('If you set up your own timer before, remove it.', output)
        self.assertTrue(self.timers.crontabs[str(self.root)].endswith(timer))
        self.assertIn('--output latest.json --lockfile', self.timers.crontabs[str(self.root)])
        write(self.root, {'latest.json': b'later data', 'custom/note.md': b'later custom'})
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertTrue(SYNC.do_rollback(), out.getvalue())
        self.assertFalse((self.root / 'section11').exists())
        for name, content in originals.items():
            self.assertEqual((self.root / name).read_bytes(), content)
        self.assertEqual(self.timers.crontabs[str(self.root)], timer)
        self.assertEqual((self.root / 'latest.json').read_bytes(), b'later data')
        self.assertEqual((self.root / 'custom/note.md').read_bytes(), b'later custom')

    def test_T06_clone_decline_accept_rollback_and_external_git_stop(self):
        write(self.root, {'section11/.git/config': b'[core]\nrepositoryformatversion=0\n',
                          'section11/edited.txt': b'local work', 'sync.py': b'old'})
        before = inventory(self.root / 'section11')
        self.assertFalse(self.run_install('n')[0])
        result, output, _ = self.run_install()
        self.assertTrue(result, output)
        self.assertIn('its .git folder is retained in the single rollback ZIP', output)
        self.assertIn('section11/ is no longer a clone afterwards', output)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_rollback())
        self.assertEqual(inventory(self.root / 'section11'), before)
        (self.root / 'section11/.git/commondir').write_text('/external/not-followed')
        result, output, prompts = self.run_install()
        self.assertFalse(result)
        self.assertIn('external Git metadata', output)
        self.assertEqual(prompts, 0)

    def test_T01_opt_out_persists_reenable_then_rollback_restores_policy(self):
        result, output, _ = self.run_install(timer_choice=False)
        self.assertTrue(result, output)
        self.assertFalse(json.loads((self.root / '.sync_config').read_bytes())['auto_sync'])
        self.assertNotIn(str(self.root), self.timers.crontabs)
        self.assertTrue(self.run_install()[0])
        self.assertNotIn(str(self.root), self.timers.crontabs)
        self.assertTrue(self.run_install(timer_choice=True)[0])
        self.assertIn('*/5 ', self.timers.crontabs[str(self.root)])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_rollback())
        self.assertFalse(json.loads((self.root / '.sync_config.json').read_bytes())['auto_sync'])
        self.assertNotIn(str(self.root), self.timers.crontabs)




    def test_T13_later_root_edit_and_backup_corruption_refuse_rollback(self):
        write(self.root, {'sync.py': b'old'})
        self.assertTrue(self.run_install()[0])
        write(self.root, {'push.py': b'later tool'})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(SYNC.do_rollback())
        self.assertEqual((self.root / 'push.py').read_bytes(), b'later tool')
        (self.root / 'push.py').unlink()
        record = SYNC._previous_install(self.root)[0]
        path = self.root / '.section11-state' / (record['transaction'] + '.zip')
        path.write_bytes(b'corrupted')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(SYNC.do_rollback())

    def test_T13_scheduler_write_unknown_preserves_journal_and_blocks_new_install(self):
        write(self.root, {'sync.py': b'old'})
        command = self.timers.command
        writes = []
        def unknown(adapter, argv, input=None):
            if argv == ['crontab', '-']:
                writes.append(argv)
                raise TimeoutError('synthetic scheduler timeout')
            return command(adapter, argv, input)
        with mock.patch.object(self.timers, 'command', unknown):
            result, output, _ = self.run_install()
        self.assertFalse(result)
        self.assertIn('timer write outcome unknown', output)
        self.assertEqual(len(writes), 1)
        self.assertTrue((self.root / '.section11-state/transaction.json').exists())
        result, output, prompts = self.run_install()
        self.assertFalse(result)
        self.assertEqual(prompts, 0)
        self.assertIn('interrupted update', output)

    def test_T13_recovery_does_not_retain_unrelated_scheduler_definitions(self):
        write(self.root, {'sync.py': b'old root'})
        config = b'{"intervals_key":"synthetic-config-value-not-for-recovery","check_interval_minutes":5}'
        write(self.root, {'.sync_config.json': config})
        old_cron = ('* * * * * cd ' + str(self.root) + ' && python3 sync.py --output latest.json\n' +
                    '0 0 * * * unrelated-command synthetic-unrelated-private-value')
        self.timers.crontabs[str(self.root)] = old_cron
        self.assertTrue(self.run_install()[0])
        record = SYNC._previous_install(self.root)[0]
        with zipfile.ZipFile(self.root / '.section11-state' / (record['transaction'] + '.zip')) as archive:
            content = archive.read('timers.json').decode()
        self.assertNotIn('UnrelatedTask', content)
        self.assertNotIn('unrelated private definition', content)
        self.assertNotIn('synthetic-unrelated-private-value', content)
        for path in (self.root / '.section11-state').rglob('*'):
            if path.is_file():
                self.assertNotIn(b'synthetic-config-value-not-for-recovery', path.read_bytes())
        saved = json.loads(content)
        self.assertEqual(set(saved['before']['resources']), {'cron'})
        self.assertEqual(set(saved['after']), {'cron'})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_rollback())
        self.assertEqual((self.root / 'sync.py').read_bytes(), b'old root')
        self.assertEqual(self.timers.crontabs[str(self.root)], old_cron)
        self.assertEqual((self.root / '.sync_config.json').read_bytes(), config)

    def test_T04_unadopted_full_mode_does_not_enroll_or_claim_day(self):
        install(self.root / 'section11', self.wire.raw[0], self.wire.files[0])
        before = inventory(self.root)
        with mock.patch.object(SYNC, '_fetch_verified_release') as fetch:
            SYNC.auto_update_local(self.root, True)
            fetch.assert_not_called()
        self.assertEqual(inventory(self.root), before)
        data = {}
        with contextlib.redirect_stdout(io.StringIO()):
            SYNC._installation_notice(data, self.root)
        self.assertEqual(data, {'installation_notice': SYNC.LEGACY_INSTALLATION_NOTICE})

    def test_T05_missing_readme_repaired_create_only(self):
        write(self.root, {'custom/mine.py': b'keep'})
        self.assertTrue(self.run_install()[0])
        readme = self.root / 'custom/README.md'
        readme.write_bytes(b'personal guidance')
        self.assertTrue(self.run_install()[0])
        self.assertEqual(readme.read_bytes(), b'personal guidance')
        self.assertEqual((self.root / 'custom/mine.py').read_bytes(), b'keep')

    def test_T17_readable_receipt_downgrade_guard_survives_manifest_edit(self):
        self.assertTrue(self.run_install()[0])
        (self.root / 'section11/manifest.json').write_bytes(b'broken metadata')
        with mock.patch.object(SYNC, '_fetch_verified_release', return_value=(self.wire.raw[0], self.wire.files[0], self.wire.identity(0))):
            result, output, prompts = self.run_install()
        self.assertFalse(result)
        self.assertEqual(prompts, 0)
        self.assertIn('downgrade refused', output)

    def test_T03_real_legacy_executables_root_guide_copy_and_first_managed_export(self):
        fixtures = ROOT / 'dev/fixtures/b1-legacy'
        payload = dict(self.wire.files[4], **{'examples/sync.py': (ROOT / 'examples/sync.py').read_bytes()})
        raw = manifest(payload)
        targets = []
        for index, filename in enumerate(('sync-fdde807.py', 'sync-0ab6e9d.py', 'sync-2d3980e.py', 'sync-2c8a813.py')):
            for layout in ('root', 'guide'):
                with self.subTest(executable=filename, layout=layout):
                    root = self.root / (str(index) + '-' + layout)
                    old = fixtures / filename
                    entry = 'sync.py' if layout == 'root' else 'section11/examples/sync.py'
                    config = b'{"athlete_id":"synthetic","intervals_key":"synthetic","week_start":"sun","zone_preference":"run:hr","auto_sync":false}'
                    write(root, {entry: old.read_bytes(), '.sync_config.json': config, 'DOSSIER.md': b'private', 'latest.json': b'old data'})
                    legacy = load_module_by_path('b1_legacy_' + str(index) + layout, root / entry)
                    producer = mock.Mock()
                    producer.collect_training_data.return_value = {}
                    producer.should_generate_history.return_value = False
                    producer.request_budget.degraded = True
                    producer.request_budget.root = None
                    producer.data_dir = root
                    producer._intervals_data = producer._routes_data = producer._saved_workouts_data = None
                    with mock.patch.object(SYNC.Path, 'cwd', return_value=root), \
                            mock.patch.object(sys, 'argv', [str(root / entry), '--athlete-id', 'synthetic', '--intervals-key', 'synthetic', '--days', '14', '--output', str(root / 'alternate.json')]), \
                            mock.patch.object(legacy, 'IntervalsSync', return_value=producer), \
                            mock.patch.object(legacy, 'notify_if_updates_available', create=True), \
                            contextlib.redirect_stdout(io.StringIO()):
                        legacy.main()
                    self.assertEqual(producer.collect_training_data.call_args.kwargs['days_back'], 14)
                    self.timers.crontabs[str(root)] = None
                    with mock.patch.object(SYNC.Path, 'cwd', return_value=root), \
                            mock.patch.object(SYNC, '_fetch_verified_release', return_value=(raw, payload, self.wire.identity(4))):
                        result, output, prompts = self.run_install()
                    self.assertTrue(result, output)
                    self.assertEqual(prompts, 1)
                    self.assertEqual((root / '.sync_config.json').read_bytes(), config)
                    self.assertEqual((root / 'DOSSIER.md').read_bytes(), b'private')
                    targets.append(inventory(root / 'section11'))
                    managed = load_module_by_path('b1_managed_' + str(index) + layout, root / 'section11/examples/sync.py')
                    new_producer = mock.Mock()
                    new_producer.collect_training_data.return_value = {'metric': 42}
                    new_producer.should_generate_history.return_value = False
                    new_producer.request_budget.degraded = True
                    new_producer.request_budget.root = None
                    new_producer.data_dir = root
                    def save(data, output):
                        Path(output).write_text(json.dumps(data))
                        return output
                    new_producer.save_local_outputs.side_effect = save
                    with mock.patch.object(SYNC.Path, 'cwd', return_value=root), \
                            mock.patch.object(sys, 'argv', [str(root / 'section11/examples/sync.py'), '--athlete-id', 'synthetic', '--intervals-key', 'synthetic', '--days', '14', '--output', str(root / 'alternate.json'), '--no-auto-update']), \
                            mock.patch.object(managed, 'IntervalsSync', return_value=new_producer), \
                            contextlib.redirect_stdout(io.StringIO()):
                        managed._main(installation_root=root)
                    self.assertEqual(new_producer.collect_training_data.call_args.kwargs['days_back'], 14)
                    self.assertEqual(json.loads((root / 'alternate.json').read_text()), {'metric': 42})
        self.assertTrue(all(tree == targets[0] for tree in targets))

    def test_T02_actual_3165_first_hop_then_latest_release_advanced(self):
        legacy_path = ROOT / 'dev/fixtures/b1-legacy/sync-7db221d8.py'
        legacy = load_module_by_path('b1_actual_3165', legacy_path)
        next_files = dict(self.wire.files[0], **{'examples/sync.py': (ROOT / 'examples/sync.py').read_bytes()})
        raw = manifest(next_files)
        write(self.root, {'section11/examples/sync.py': legacy_path.read_bytes(),
                          'history.json': b'old history', 'intervals.json': b'old intervals', 'routes.json': b'old routes'})
        calls = []
        def get(url, **kwargs):
            self.assertTrue(url.startswith(legacy.SECTION11_REPO_RAW + '/'))
            name = url[len(legacy.SECTION11_REPO_RAW) + 1:]
            calls.append(name)
            return Response(json.loads(raw)) if name == 'manifest.json' else Response(content=next_files[name])
        with mock.patch.object(legacy.requests, 'get', get), mock.patch('builtins.input', return_value='y'), \
                contextlib.redirect_stdout(io.StringIO()):
            legacy.do_update()
        self.assertEqual((self.root / 'section11/examples/sync.py').read_bytes(), next_files['examples/sync.py'])
        self.assertFalse((self.root / 'section11' / D.RECEIPT).exists())
        self.assertTrue(all(not (self.root / name).exists() for name in ('history.json', 'intervals.json', 'routes.json')))
        before = inventory(self.root)
        with mock.patch.object(SYNC, '_fetch_verified_release') as fetch:
            SYNC.auto_update_local(self.root, True)
            fetch.assert_not_called()
        self.assertEqual(inventory(self.root), before)
        result, output, prompts = self.run_install()
        self.assertTrue(result, output)
        self.assertEqual(prompts, 1)
        self.assertEqual(D.tree(self.root / 'section11'), (self.wire.raw[4], self.wire.files[4]))
        self.assertEqual(calls.count('manifest.json'), 1)

    def test_T08_API_and_file_success_hooks_no_duplicate_or_unknown_maintenance(self):
        for route, outcome, suppress in (('api', True, False), ('api', False, False), ('api', 'unknown', False),
                                         ('file', True, False), ('api', True, True)):
            with self.subTest(route=route, outcome=outcome, suppress=suppress):
                producer = mock.Mock()
                producer.request_budget.degraded = True
                producer.request_budget.root = None
                producer.should_generate_history.return_value = False
                producer.collect_training_data.return_value = {}
                producer.data_dir = self.root
                producer._intervals_data = producer._routes_data = producer._saved_workouts_data = None
                producer.publish_to_github.return_value = 'https://example.invalid/latest.json'
                if outcome is False:
                    producer.publish_to_github.side_effect = RuntimeError('definitive synthetic refusal')
                elif outcome == 'unknown':
                    producer.publish_to_github.side_effect = SYNC.PublishOutcomeUnknown('synthetic unknown')
                argv = ['sync.py', '--athlete-id', 'synthetic', '--intervals-key', 'synthetic', '--github-token', 'synthetic', '--github-repo', 'example/data']
                if route == 'file':
                    argv += ['--output', str(self.root / 'latest.json')]
                if suppress:
                    argv += ['--no-auto-update']
                with mock.patch.object(sys, 'argv', argv), mock.patch.object(SYNC, 'IntervalsSync', return_value=producer), \
                        mock.patch.object(SYNC, '_rotate_log_if_needed'), mock.patch.object(SYNC, 'auto_update_local') as maintenance, \
                        contextlib.redirect_stdout(io.StringIO()):
                    if outcome is True:
                        SYNC._main(installation_root=self.root)
                        if suppress:
                            maintenance.assert_not_called()
                        else:
                            maintenance.assert_called_once()
                    else:
                        with self.assertRaises((RuntimeError, SYNC.PublishOutcomeUnknown)):
                            SYNC._main(installation_root=self.root)
                        if outcome == 'unknown':
                            maintenance.assert_not_called()
                        else:
                            maintenance.assert_called_once()
                self.assertEqual(producer.publish_to_github.call_count, 1 if route == 'api' else 0)

    def test_T08_hosted_API_has_no_parallel_changelog_issue_check(self):
        producer = mock.Mock()
        producer.should_generate_history.return_value = False
        producer.collect_training_data.return_value = {}
        producer.data_dir = self.root
        producer._intervals_data = producer._routes_data = producer._saved_workouts_data = None
        args = SimpleNamespace(generate_history=False, output=None, days=7, debug=False)
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC._run_sync(producer, args, 'synthetic', 'example/data'))

    def test_T08_uncertain_companion_holds_maintenance_after_latest_success(self):
        producer = mock.Mock()
        producer.should_generate_history.return_value = False
        producer.collect_training_data.return_value = {}
        producer.data_dir = self.root
        producer.INTERVALS_FILE = 'intervals.json'
        producer._intervals_data = {'activities': []}
        producer._routes_data = producer._saved_workouts_data = None
        producer.publish_to_github.side_effect = ['https://example.invalid/latest.json', SYNC.PublishOutcomeUnknown('synthetic unknown')]
        args = SimpleNamespace(generate_history=False, output=None, days=7, debug=False)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(SYNC._run_sync(producer, args, 'synthetic', 'example/data'))
        self.assertIs(producer._publication_uncertain, True)
        self.assertEqual(producer.publish_to_github.call_count, 2)

    def test_T07_managed_tool_imports_and_literal_CLI_preserve_confirmation(self):
        payload = dict(self.wire.files[4])
        for name in ('push', 'pull'):
            payload['examples/agentic/' + name + '.py'] = (ROOT / 'examples/agentic' / (name + '.py')).read_bytes()
        write(self.root, {'push.py': b'old root push', 'pull.py': b'old root pull'})
        with mock.patch.object(SYNC, '_fetch_verified_release', return_value=(manifest(payload), payload, self.wire.identity(4))):
            self.assertTrue(self.run_install()[0])
        self.assertFalse((self.root / 'push.py').exists())
        self.assertFalse((self.root / 'pull.py').exists())
        with mock.patch.object(sys, 'path', [str(self.root), *sys.path]), mock.patch.dict(sys.modules):
            for name in list(sys.modules):
                if name == 'section11' or name.startswith('section11.'):
                    sys.modules.pop(name)
            push = importlib.import_module('section11.examples.agentic.push')
            pull = importlib.import_module('section11.examples.agentic.pull')
            self.assertTrue(callable(pull.main))
            literal = 'Synthetic $(must-stay-literal); workout'
            argv = ['section11/examples/agentic/push.py', '--athlete-id', 'i123456', '--api-key', 'synthetic',
                    'push', '--name', literal, '--date', '2099-01-01', '--duration', '90', '--tss', '70']
            cwd = os.getcwd()
            os.chdir(self.root)
            try:
                for confirmed in (False, True):
                    with self.subTest(confirmed=confirmed), \
                            mock.patch.object(sys, 'argv', argv + (['--confirm'] if confirmed else [])), \
                            mock.patch.object(push.IntervalsPush, 'preview_push', return_value={'success': True}) as preview, \
                            mock.patch.object(push.IntervalsPush, 'push_workouts', return_value={'success': True}) as mutate, \
                            mock.patch.object(push, '_ensure_requests', side_effect=AssertionError('no real transport')), \
                            contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                        push.main()
                    self.assertEqual(stopped.exception.code, 0)
                    chosen, other = (mutate, preview) if confirmed else (preview, mutate)
                    chosen.assert_called_once()
                    other.assert_not_called()
                    self.assertEqual(chosen.call_args.args[0][0]['name'], literal)
                pusher = push.IntervalsPush('i123456', 'synthetic', data_dir=self.root)
                self.assertTrue(callable(pusher.push_workout))
            finally:
                os.chdir(cwd)

    def test_T13_abrupt_stop_retains_checked_recovery_bytes_and_blocks_retry(self):
        write(self.root, {'section11/old.txt': b'old managed', 'sync.py': b'old root', 'push.py': b'old push'})
        before = inventory(self.root / 'section11')
        state_write = SYNC._write_install_state
        def stop_after_journal(state, name, value):
            state_write(state, name, value)
            if name == 'transaction.json' and value.get('phase') == 'timer-activation':
                raise SystemExit('synthetic abrupt process termination')
        with mock.patch.object(SYNC, '_write_install_state', stop_after_journal):
            with self.assertRaisesRegex(SystemExit, 'synthetic abrupt'):
                self.run_install()
        state = self.root / '.section11-state'
        record = json.loads((state / 'transaction.json').read_text())
        transaction = state / record['transaction']
        self.assertEqual(inventory(transaction / 'old'), before)
        self.assertEqual((transaction / 'entries/sync.py').read_bytes(), b'old root')
        self.assertEqual((transaction / 'entries/push.py').read_bytes(), b'old push')
        self.assertEqual(SYNC._ordinary_tree_digest(transaction / 'old'), record['previous_tree'])
        self.assertEqual(D.digest((transaction / 'timers.json').read_bytes()), record['timers_digest'])
        self.assertEqual(self.timers.crontabs, {})
        result, output, prompts = self.run_install()
        self.assertFalse(result)
        self.assertEqual(prompts, 0)
        self.assertIn('interrupted update', output)

    def test_T05_ordinary_type_collisions_refuse_without_prompt_or_mutation(self):
        for name in ('sync.py', 'custom/README.md', '.section11-state'):
            with self.subTest(name=name):
                root = self.root / name.replace('/', '-')
                root.mkdir()
                if name == '.section11-state':
                    write(root, {name: b'not a directory'})
                else:
                    (root / name).mkdir(parents=True)
                before = inventory(root)
                with mock.patch.object(SYNC.Path, 'cwd', return_value=root):
                    result, output, prompts = self.run_install()
                self.assertFalse(result, output)
                self.assertEqual(prompts, 0)
                self.assertEqual(inventory(root), before)

    def test_T16_local_docs_use_managed_entries_and_explicit_timer_policy(self):
        for name in ('examples/json-local-sync/SETUP.md', 'examples/json-manual/SETUP.md', 'examples/maintenance/UPDATING.md'):
            text = (ROOT / name).read_text()
            self.assertIn('--no-timer', text)
            self.assertIn('auto_sync', text)
            self.assertIn('section11/examples/sync.py', text)
            self.assertNotRegex(text, r'(?:curl|wget).*raw\.githubusercontent\.com.*sync\.py')
        text = (ROOT / 'examples/agentic/README.md').read_text()
        self.assertIn('from section11.examples.agentic.push import IntervalsPush', text)
        self.assertNotRegex(text, r'python3? (?:push|pull)\.py')
        self.assertIn('preview/confirmation gate', text)
        self.assertIn('athlete approves', text)




if __name__ == '__main__':
    unittest.main()
