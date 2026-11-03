"""Local entry, consent, replacement and rollback; all upstream traffic mocked."""
import contextlib
import io
import json
import os
import re
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from test_update_prototype import D, SYNC, ROOT, Offline, install, inventory, manifest, write, validate_data
from test_update_path_fixes import ReleaseHTTP, Response
from test_alignment_recovery import recovery_bytes


class LocalEntryTests(Offline):
    def setUp(self):
        super().setUp()
        self.wire = ReleaseHTTP(4)
        self.target = self.root / 'section11'
        install(self.target, self.wire.raw[0], self.wire.files[0])
        (self.target / D.RECEIPT).write_bytes(D.receipt(self.wire.raw[0], self.wire.identity(0)))
        write(self.root, {'DOSSIER.md': b'private dossier', 'latest.json': b'current data',
                          '.sync_config.json': b'{"auto_update":false}',
                          'custom/mine.py': b'personal', 'custom/README.md': b'personal guidance',
                          'state/private.json': b'private accounting'})
        self.protected = inventory(self.root / 'custom')
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(SYNC, '__file__', str(self.target / 'examples/sync.py')))
        self.stack.enter_context(mock.patch.object(SYNC.Path, 'cwd', return_value=self.root))
        self.stack.enter_context(mock.patch.dict(os.environ, {'GITHUB_ACTIONS': '', 'SECTION11_SYNC_WRAPPER_API': ''}))

    def update(self, answer='y', index=4, **kwargs):
        output = io.StringIO()
        with mock.patch.object(SYNC, '_fetch_verified_release', return_value=(self.wire.raw[index], self.wire.files[index], self.wire.identity(index))), \
                mock.patch('builtins.input', return_value=answer) as prompt, contextlib.redirect_stdout(output):
            result = SYNC.do_update(**kwargs)
        self.assertEqual(inventory(self.root / 'custom'), self.protected)
        self.assertEqual((self.root / 'DOSSIER.md').read_bytes(), b'private dossier')
        self.assertEqual((self.root / 'latest.json').read_bytes(), b'current data')
        self.assertEqual((self.root / 'state/private.json').read_bytes(), b'private accounting')
        return result, output.getvalue(), prompt.call_count

    def automatic(self, enabled=False, index=4):
        output = io.StringIO()
        with self.wire.intercepted(), mock.patch('builtins.input', side_effect=AssertionError('unexpected prompt')), \
                contextlib.redirect_stdout(output):
            SYNC.auto_update_local(self.root, enabled, advisory_only=not enabled)
        return output.getvalue()

    def test_L2_old_unidentified_install_updates_without_age_window(self):
        self.wire = ReleaseHTTP(40)
        (self.target / D.RECEIPT).unlink()
        result, text, prompts = self.update(index=40)
        self.assertTrue(result, text)
        self.assertEqual(prompts, 1)
        self.assertIn(SYNC.CONVERSION_WARNING, text)
        self.assertEqual(D.tree(self.target), (self.wire.raw[40], self.wire.files[40]))

    def test_L4_managed_edit_is_listed_and_exactly_restored(self):
        (self.target / 'LICENSE').write_bytes(b'my edited managed bytes')
        before = inventory(self.target)
        result, text, _ = self.update()
        self.assertTrue(result, text)
        self.assertIn('[changed] LICENSE', text)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_rollback())
        self.assertEqual(inventory(self.target), before)

    def test_edited_manifest_is_repaired_without_conversion_warning(self):
        (self.target / 'manifest.json').write_bytes(b'{malformed')
        self.assertTrue(SYNC._converted_installation(self.root))
        result, text, _ = self.update()
        self.assertTrue(result, text)
        self.assertNotIn(SYNC.CONVERSION_WARNING, text)

    def test_L5_ahead_content_is_not_automatically_downgraded(self):
        (self.target / 'examples/sync.py').write_bytes(b'class IntervalsSync:\n    VERSION = "99.1"\n')
        before = inventory(self.target)
        self.assertIn('newer than the latest official release', self.automatic(True))
        self.assertEqual(inventory(self.target), before)
        result, text, _ = self.update('n')
        self.assertFalse(result)
        self.assertIn('Accepting replaces it with that release', text)
        self.assertEqual(inventory(self.target), before)

    def test_L7_receiptless_half_mode_never_enrolls_or_searches_history(self):
        (self.target / D.RECEIPT).unlink()
        local_raw = json.dumps(json.loads(self.wire.raw[0]), indent=4).encode()
        (self.target / 'manifest.json').write_bytes(local_raw)
        before = inventory(self.target)
        text = self.automatic(False)
        self.assertEqual(text, '')
        self.assertIsNone(D.read_receipt(self.target, local_raw))
        after = inventory(self.target)
        self.assertEqual(after, before)
        self.assertFalse((self.root / '.section11-state/previous.json').exists())
        self.assertEqual(self.wire.calls, [])

    def test_enrollment_never_claims_edited_or_extra_content(self):
        (self.target / D.RECEIPT).unlink()
        write(self.target, {'personal.txt': b'not official'})
        self.automatic(False)
        self.assertFalse((self.target / D.RECEIPT).exists())
        self.assertEqual((self.target / 'personal.txt').read_bytes(), b'not official')

    def test_S2_latest_release_ignores_raw_main(self):
        (self.root / '.sync_config.json').write_text('{"auto_sync":false}')
        install(self.target, self.wire.raw[4], self.wire.files[4])
        (self.target / D.RECEIPT).write_bytes(D.receipt(self.wire.raw[4], self.wire.identity(4)))
        text = self.automatic(False)
        self.assertFalse(any('/main/' in url for url in self.wire.calls))
        self.assertNotIn('available', text)
        self.assertIn('already current', text)

    def test_C1_C2_conversion_has_one_warning_no_list_and_one_rollback(self):
        (self.target / D.RECEIPT).unlink()
        write(self.target, {'personal.txt': b'keep only in rollback', 'LICENSE': b'edited'})
        write(self.root, {'sync.py': b'root bootstrap'})
        before = inventory(self.target)
        with mock.patch.object(SYNC, '__file__', str(self.root / 'sync.py')):
            result, text, prompts = self.update()
        self.assertTrue(result, text)
        self.assertEqual(text.count(SYNC.CONVERSION_WARNING), 1)
        self.assertEqual(prompts, 1)
        self.assertNotIn('personal.txt', text)
        self.assertNotIn('[changed]', text)
        self.assertFalse((self.target / 'personal.txt').exists())
        self.assertFalse((self.root / 'sync.py').exists())
        self.assertEqual(len(list((self.root / '.section11-state').glob('transaction-*'))), 1)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_rollback())
        self.assertEqual(inventory(self.target), before)

    def test_C1_absent_custom_created_but_existing_custom_is_untouched(self):
        (self.root / 'custom/mine.py').unlink()
        (self.root / 'custom/README.md').unlink()
        (self.root / 'custom').rmdir()
        with mock.patch.object(SYNC, '__file__', str(self.root / 'sync.py')), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(self.wire.raw[4], self.wire.files[4], self.wire.identity(4))), \
                mock.patch('builtins.input', return_value='y'), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_update())
        self.assertEqual((self.root / 'custom/README.md').read_bytes(), self.wire.files[4]['examples/maintenance/CUSTOM_README.md'])

    def test_S3_declined_clone_conversion_changes_nothing_then_accept_restores_git_on_rollback(self):
        write(self.target, {'.git/config': b'synthetic ordinary git metadata'})
        before = inventory(self.root)
        result, text, prompts = self.update('n')
        self.assertFalse(result)
        self.assertEqual(prompts, 1)
        self.assertIn(SYNC.CONVERSION_WARNING, text)
        self.assertEqual(inventory(self.root), before)
        self.assertTrue(self.update()[0])
        self.assertFalse((self.target / '.git').exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_rollback())
        self.assertEqual((self.target / '.git/config').read_bytes(), b'synthetic ordinary git metadata')

    def test_C3_later_edit_does_not_block_next_update_and_only_last_tree_is_kept(self):
        self.assertTrue(self.update(index=1)[0])
        write(self.target, {'LICENSE': b'edited between updates'})
        before = inventory(self.target)
        self.assertTrue(self.update(index=4)[0])
        self.assertEqual(len(list((self.root / '.section11-state').glob('transaction-*'))), 1)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_rollback())
        self.assertEqual(inventory(self.target), before)

    def test_status_and_manual_decline_do_not_enroll(self):
        install(self.target, self.wire.raw[4], self.wire.files[4])
        (self.target / D.RECEIPT).unlink()
        before = inventory(self.root)
        self.assertTrue(self.update(status_only=True)[0])
        self.assertFalse(self.update('n')[0])
        self.assertEqual(inventory(self.root), before)

    def test_L6_notice_is_fixed_and_repeated_until_accepted_installation(self):
        (self.target / D.RECEIPT).unlink()
        with mock.patch.object(SYNC, '__file__', str(self.root / 'sync.py')):
            for _ in range(2):
                data = {'metric': 123}
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    SYNC._installation_notice(data, self.root)
                self.assertEqual(data, {'metric': 123, 'installation_notice': SYNC.LEGACY_INSTALLATION_NOTICE})
                self.assertIn(SYNC.LEGACY_INSTALLATION_NOTICE, out.getvalue())
                self.assertNotIn(str(self.root), out.getvalue())
        (self.target / D.RECEIPT).write_bytes(D.receipt(self.wire.raw[0], self.wire.identity(0)))
        data = {'metric': 123}
        SYNC._installation_notice(data, self.root)
        self.assertEqual(data, {'metric': 123})

    def test_structure_is_independent_of_receipt_and_wrapper_marker(self):
        self.assertTrue(SYNC._converted_installation(self.root))
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}):
            data = {}
            with contextlib.redirect_stdout(io.StringIO()) as out:
                SYNC._installation_notice(data, self.root)
            self.assertNotIn('::warning::', out.getvalue())
            self.assertNotIn('installation_notice', data)
            with mock.patch.dict(os.environ, {'SECTION11_SYNC_WRAPPER_API': '1'}):
                self.assertTrue(SYNC._converted_installation(self.root))
                (self.root / 'section11' / D.RECEIPT).unlink()
                self.assertTrue(SYNC._converted_installation(self.root))
                self.assertIsNone(SYNC._known_local_identity(self.target))

    def test_detector_failure_never_blocks_export(self):
        data = {'metric': 123}
        with mock.patch.object(SYNC, '_converted_installation', side_effect=OSError('synthetic failure')):
            SYNC._installation_notice(data, self.root)
        self.assertEqual(data, {'metric': 123})

    def test_L6_successful_sync_serializes_notice_and_publisher_accepts_it(self):
        (self.target / D.RECEIPT).unlink()
        producer = object.__new__(SYNC.IntervalsSync)
        producer.data_dir = self.root
        producer.athlete_id = 'synthetic'
        producer.debug = False
        producer.route_weather_enabled = False
        producer.begin_tick = lambda: True
        producer.should_generate_history = lambda: False
        producer.collect_training_data = lambda **kw: {'READ_THIS_FIRST': {}, 'metric': 123}
        args = SimpleNamespace(generate_history=False, days=7, output=str(self.root / 'latest.json'), debug=False)
        with mock.patch.object(SYNC, '__file__', str(self.root / 'sync.py')), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC._run_sync(producer, args, '', ''))
        saved = json.loads((self.root / 'latest.json').read_bytes())
        self.assertEqual(saved['installation_notice'], SYNC.LEGACY_INSTALLATION_NOTICE)
        self.assertEqual(saved['metric'], 123)
        self.assertEqual(list(saved)[:2], ['READ_THIS_FIRST', 'data_overview'])
        self.assertEqual(validate_data.plan(self.root)['mode'], 'declared')
        # The legacy API publisher receives the same field before serialization.
        args.output = None
        producer.publish_to_github = mock.Mock(return_value='https://example.invalid/latest.json')
        with mock.patch.object(SYNC, '__file__', str(self.root / 'sync.py')), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC._run_sync(producer, args, 'synthetic', 'example/data'))
        self.assertEqual(producer.publish_to_github.call_args.args[0]['installation_notice'], SYNC.LEGACY_INSTALLATION_NOTICE)

    def test_automatic_managed_edits_are_replaced_and_listed(self):
        write(self.target, {'LICENSE': b'edited local file'})
        text = self.automatic(True)
        self.assertIn('replaced/removed: LICENSE', text)
        self.assertEqual((self.target / 'LICENSE').read_bytes(), self.wire.files[4]['LICENSE'])

    def test_legacy_auto_preference_does_not_convert_or_claim_a_check(self):
        (self.target / D.RECEIPT).unlink()
        before = inventory(self.root)
        with mock.patch.object(SYNC, '__file__', str(self.root / 'sync.py')):
            self.assertEqual(self.automatic(True), '')
        self.assertEqual(self.wire.calls, [])
        self.assertEqual(inventory(self.root), before)

    def test_missing_receipt_does_not_enroll_or_consume_existing_rollback(self):
        self.assertTrue(self.update(index=4)[0])
        saved = (self.root / '.section11-state/previous.json').read_bytes()
        record = json.loads(saved)
        backup = recovery_bytes(self.root, record)
        (self.target / D.RECEIPT).unlink()
        self.automatic(False)
        self.assertFalse((self.target / D.RECEIPT).exists())
        self.assertEqual((self.root / '.section11-state/previous.json').read_bytes(), saved)
        self.assertEqual(recovery_bytes(self.root, record), backup)

    def test_source_manifest_mutation_during_confirmation_refuses_write(self):
        before = (self.target / 'LICENSE').read_bytes()
        def answer(prompt):
            write(self.target, {'personal-after-review.txt': b'concurrent edit'})
            return 'y'
        with mock.patch.object(SYNC, '_fetch_verified_release', return_value=(self.wire.raw[4], self.wire.files[4], self.wire.identity(4))), \
                mock.patch('builtins.input', side_effect=answer), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(SYNC.do_update())
        self.assertIn('changed after review', output.getvalue())
        self.assertEqual((self.target / 'LICENSE').read_bytes(), before)
        self.assertEqual((self.target / 'personal-after-review.txt').read_bytes(), b'concurrent edit')

    def test_conversion_preserves_bootstrap_changed_during_confirmation(self):
        write(self.root, {'sync.py': b'bootstrap before review'})
        before = inventory(self.target)
        def answer(prompt):
            (self.root / 'sync.py').write_bytes(b'concurrent bootstrap edit')
            return 'y'
        with mock.patch.object(SYNC, '__file__', str(self.root / 'sync.py')), \
                mock.patch.object(SYNC, '_fetch_verified_release', return_value=(self.wire.raw[4], self.wire.files[4], self.wire.identity(4))), \
                mock.patch('builtins.input', side_effect=answer), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(SYNC.do_update())
        self.assertIn('root bootstrap changed', output.getvalue())
        self.assertEqual((self.root / 'sync.py').read_bytes(), b'concurrent bootstrap edit')
        self.assertEqual(inventory(self.target), before)

    def test_safe_asset_redirect_is_counted_and_deadline_prevents_new_request(self):
        redirect = mock.Mock(status_code=302, headers={'Location': 'https://release-assets.githubusercontent.com/example/blob'})
        with SYNC._release_request_budget(), mock.patch.object(SYNC.requests, 'get', side_effect=[redirect, Response(content=b'zip')]) as get:
            result = D.request('https://github.com/' + D.UPSTREAM + '/releases/download/2026.10.31/section11-2026.10.31.zip', timeout=60)
            self.assertEqual(result.content, b'zip')
            self.assertEqual(get.call_count, 2)
            self.assertTrue(all(c.kwargs['allow_redirects'] is False and 0 < c.kwargs['timeout'] <= 10 for c in get.call_args_list))
            SYNC._RELEASE_REQUEST_BUDGET.get()['deadline'] = 0
            with self.assertRaisesRegex(ValueError, 'bound reached'):
                D.api_read('/synthetic')
            self.assertEqual(get.call_count, 2)

    def test_request_budget_refuses_41st_call_and_unsafe_redirect(self):
        with SYNC._release_request_budget(), mock.patch.object(SYNC.requests, 'get', return_value=Response({})) as get:
            for _ in range(40):
                D.api_read('/synthetic')
            with self.assertRaisesRegex(ValueError, 'bound reached'):
                D.api_read('/synthetic')
            self.assertEqual(get.call_count, 40)
        response = mock.Mock(status_code=302, headers={'Location': 'https://example.invalid/private'})
        with SYNC._release_request_budget(), mock.patch.object(SYNC.requests, 'get', return_value=response) as get:
            with self.assertRaisesRegex(ValueError, 'redirect refused'):
                D.api_read('/synthetic')
            self.assertEqual(get.call_count, 1)


def check_entry_contract(root, raw):
    """The installed legacy reader expects files -> path -> hash, at fixed paths."""
    assert (root / 'manifest.json').is_file(), 'permanent manifest entry missing'
    value = json.loads(raw)
    assert isinstance(value.get('files'), dict), 'legacy files map required'
    assert 'examples/sync.py' in value['files'], 'permanent sync entry missing'
    for path, entry in value['files'].items():
        assert SYNC._safe_manifest_path(path), 'unsafe legacy path'
        assert isinstance(entry, dict) and re.fullmatch('[0-9a-f]{64}', entry.get('hash', '')), 'legacy hash required'
        assert (root / path).is_file(), 'listed entry no longer fetchable'


class EntryContractTests(Offline):
    def test_C4_permanent_paths_and_legacy_shape(self):
        check_entry_contract(ROOT, (ROOT / 'manifest.json').read_bytes())
        write(self.root, {'manifest.json': b'{}', 'examples/sync.py': b'script'})
        raw = manifest({'examples/sync.py': b'script'})
        check_entry_contract(self.root, raw)
        for broken in (b'{}', b'{"files":[]}', b'{"files":{"examples/sync.py":{"sha":"x"}}}', manifest({'moved/sync.py': b'script'})):
            with self.assertRaises(AssertionError):
                check_entry_contract(self.root, broken)
        (self.root / 'examples/sync.py').unlink()
        with self.assertRaises(AssertionError):
            check_entry_contract(self.root, raw)
        (self.root / 'manifest.json').unlink()
        with self.assertRaises(AssertionError):
            check_entry_contract(self.root, raw)
