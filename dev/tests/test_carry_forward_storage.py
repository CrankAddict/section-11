"""Separate recovery storage and real managed phases over synthetic Git objects."""
import base64
import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import test_carry_forward as carry
import test_decoupling_detail as decoupling
import test_b2_integration as integration
import test_b2_hosted as remote_fixture
import test_update_prototype as update_fixture
from _harness import install_verb_guard, restore_verb_guard

mod = carry.mod
Store = mod.CarryForwardBackup
hosted = integration.hosted


def setUpModule():
    global originals
    originals = install_verb_guard(mod.requests)


def tearDownModule():
    restore_verb_guard(mod.requests, originals)


def clock(day):
    value = type("StorageClock", (carry.sleep.Clock,), {
        "instant": datetime(2026, 1, day, 12, tzinfo=timezone.utc)})
    return mock.patch.object(mod, "datetime", value)


class BackupStorage(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.scenario = carry.Scenario(self.root)
        self.path = self.root / Store.PATH

    def seed(self):
        self.scenario.run(14)
        return self.scenario.run(16)

    def test_quiet_runs_keep_content_timestamp_bytes_mtime_and_revision(self):
        data, *_ = self.seed()
        before = self.path.read_bytes()
        modified = self.path.stat().st_mtime_ns
        document = Store.decode(before)
        for day in (17, 18, 20, 28):
            data, *_ = self.scenario.run(day)
            self.assertEqual(self.path.read_bytes(), before)
            self.assertEqual(self.path.stat().st_mtime_ns, modified)
            self.assertEqual(data['carry_forward']['backup_revision'], document['revision'])
            self.assertNotEqual(data['metadata']['last_updated'], document['generated_at'])
            self.assertNotIn('carry_forward', json.loads((self.root / 'intervals.json').read_bytes()))

    def test_reordered_inputs_are_stable_but_real_change_and_expiry_advance_revision(self):
        data, sync, *_ = self.seed()
        before = self.path.read_bytes()
        row = data['recent_activities'][0]
        # Dictionary order is not content; order within an ordered list still is.
        row['plan_pairing'] = dict(reversed(list(row['plan_pairing'].items())))
        with clock(17):
            sync._load_previous_latest([self.scenario.act])
            data['metadata']['last_updated'] = '2026-01-17T12:00:00Z'
            sync._prepare_carry_forward(data)
            sync.save_local_outputs(data, str(self.root / 'latest.json'))
        self.assertEqual(self.path.read_bytes(), before)
        self.scenario.event['workout_doc']['steps'][0]['power']['value'] = 130
        changed = self.scenario.run(18)[0]
        changed_backup = Store.decode(self.path.read_bytes())
        self.assertNotEqual(changed_backup['revision'], Store.decode(before)['revision'])
        self.assertEqual(changed_backup['generated_at'], changed['metadata']['last_updated'])
        self.assertEqual(changed['recent_activities'][0]['interval_data']['plan_match']['status'], 'not_assessed')
        expired = self.scenario.run(29)[0]
        final = Store.decode(self.path.read_bytes())
        self.assertEqual(final['activities'], [])
        self.assertNotEqual(final['revision'], changed_backup['revision'])
        self.assertEqual(final['generated_at'], expired['metadata']['last_updated'])

    def enriched(self):
        data, sync, *_ = self.seed()
        act = dict(self.scenario.act, type='Ride')
        row = data['recent_activities'][0]
        row.update(terrain_summary={'total_distance_km': 5, 'total_elevation_m': 10,
                                    'elevation_per_km': 2, 'climbs': [], 'descents': []},
                   weather_summary={'avg_temp': 10}, power_curve={'5': 400},
                   dfa_rollup={'date': row['date'], 'dfa': {'quality': {'sufficient': False}}},
                   chat_notes=[{'text': 'Synthetic note'}])
        with mock.patch.object(sync, '_fetch_activity_power_vs_hr',
                               return_value=('ok', sync._decoupling_detail(decoupling.body()))):
            row.update(sync._build_decoupling_for_activity(
                act, {}, True, True, row['interval_data']['plan_match']))
        with clock(16):
            sync._prepare_carry_forward(data)
            sync.save_local_outputs(data, str(self.root / 'latest.json'))
        return data, act

    def test_missing_or_later_partial_export_restores_all_groups_without_enrichment_reads(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                data, act = self.enriched()
                expected = copy.deepcopy(data['recent_activities'][0])
                data['metadata']['last_updated'] = '2026-01-17T12:00:00Z'
                row = data['recent_activities'][0]
                for key in ('terrain_summary', 'weather_summary', 'power_curve',
                            'dfa_rollup', 'chat_notes', 'decoupling_detail'):
                    row.pop(key)
                # Keep the decoupling fingerprint, exercising a partly missing group.
                latest = self.root / 'latest.json'
                latest.write_text(json.dumps(data))
                if missing:
                    latest.unlink()
                sync = carry.base.Sync('synthetic', 'synthetic')
                sync.data_dir = self.root
                with clock(18), contextlib.redirect_stdout(io.StringIO()), contextlib.ExitStack() as stack:
                    reads = [stack.enter_context(mock.patch.object(sync, name,
                        side_effect=AssertionError('recovery must not fetch ' + name))) for name in
                        ('_fetch_terrain_streams', '_fetch_activity_power_curve',
                         '_fetch_activity_power_vs_hr', '_fetch_activity_streams')]
                    previous = sync._load_previous_latest([act])
                    recovered = previous[act['id']]
                    for key in ('terrain_summary', 'weather_summary', 'power_curve',
                                'dfa_rollup', 'chat_notes', 'decoupling_detail', 'decoupling_cache'):
                        self.assertEqual(recovered[key], expected[key], key)
                    self.assertTrue(sync._build_terrain_for_activity(act, previous))
                    self.assertTrue(sync._build_weather_for_activity(act, previous, {}))
                    self.assertTrue(sync._build_power_curve_for_activity(act, previous, True))
                    self.assertTrue(sync._build_decoupling_for_activity(
                        act, previous, True, True, recovered['structure_summary']))
                    for read in reads:
                        read.assert_not_called()
                self.assertEqual(sync._carry_forward_status['restored_activity_ids'], [act['id']])

    def test_fresh_empty_evidence_is_not_revived_and_legacy_newer_absence_remains_authoritative(self):
        data, act = self.enriched()
        sync = carry.base.Sync('synthetic', 'synthetic')
        sync.data_dir = self.root
        with clock(18), contextlib.redirect_stdout(io.StringIO()):
            sync._load_previous_latest([act])
            old_revision = data['carry_forward']['backup_revision']
            data['recent_activities'][0].pop('dfa_rollup')
            data['metadata']['last_updated'] = '2026-01-18T12:00:00Z'
            sync._prepare_carry_forward(data)
            sync.save_to_file(data, str(self.root / 'latest.json'))
            self.assertNotEqual(data['carry_forward']['backup_revision'], old_revision)
            (self.root / 'latest.json').unlink()
            recovered = sync._load_previous_latest([act])[act['id']]
            self.assertNotIn('dfa_rollup', recovered)
            # A later producer without the revision protocol may intentionally omit a field.
            data.pop('carry_forward')
            data['metadata']['last_updated'] = '2026-01-19T12:00:00Z'
            data['recent_activities'][0].pop('weather_summary')
            (self.root / 'latest.json').write_text(json.dumps(data))
            recovered = sync._load_previous_latest([act])[act['id']]
            self.assertNotIn('weather_summary', recovered)

    def test_backup_failure_stops_latest_and_interruption_preserves_newer_demotion(self):
        self.seed()
        previous = {name: (self.root / name).read_bytes() for name in ('latest.json', Store.PATH)}
        self.scenario.event['workout_doc']['steps'][0]['power']['value'] = 130
        real_replace = mod.os.replace
        def fail_backup(src, dst):
            if Path(dst) == self.path:
                raise OSError('synthetic backup replace failure')
            return real_replace(src, dst)
        with mock.patch.object(mod.os, 'replace', side_effect=fail_backup), self.assertRaisesRegex(OSError, 'synthetic'):
            self.scenario.run(17)
        for name, raw in previous.items():
            self.assertEqual((self.root / name).read_bytes(), raw)
        self.assertEqual(list(self.path.parent.glob('.carry-*.tmp')), [])
        def fail_latest(src, dst):
            if Path(dst) == self.root / 'latest.json':
                raise OSError('synthetic latest replace failure')
            return real_replace(src, dst)
        with mock.patch.object(mod.os, 'replace', side_effect=fail_latest), self.assertRaisesRegex(OSError, 'synthetic'):
            self.scenario.run(18)
        self.assertEqual((self.root / 'latest.json').read_bytes(), previous['latest.json'])
        self.assertNotEqual(self.path.read_bytes(), previous[Store.PATH])
        self.scenario.event['workout_doc']['steps'][0]['power']['value'] = 100
        data = self.scenario.run(19)[0]
        self.assertEqual(data['recent_activities'][0]['interval_data']['plan_match']['status'], 'not_assessed')
        self.assertIn('previous_latest_older_than_backup', data['carry_forward']['issues'])

    def test_unreleased_embedded_backup_is_not_a_migration_source(self):
        self.seed()
        embedded = Store.decode(self.path.read_bytes())
        intervals = json.loads((self.root / 'intervals.json').read_bytes())
        intervals['carry_forward'] = embedded
        (self.root / 'intervals.json').write_text(json.dumps(intervals))
        self.path.unlink()
        (self.root / 'latest.json').unlink()
        data, sync, _, streams, _ = self.scenario.run(17)
        self.assertEqual(data['recent_activities'][0]['interval_data']['plan_match']['status'], 'not_assessed')
        self.assertEqual(streams, 0)
        self.assertNotIn('carry_forward', sync._intervals_data)

    def test_old_producer_write_then_reupgrade_keeps_backup_and_current_demotion(self):
        data, *_ = self.seed()
        backup = self.path.read_bytes()
        # Simulate the legacy file contract after code rollback: latest only, no backup revision.
        data.pop('carry_forward')
        data['metadata']['last_updated'] = '2026-01-18T12:00:00Z'
        summary = data['recent_activities'][0]['interval_data']['plan_match']
        summary.update(status='not_assessed')
        summary.pop('steps', None)
        (self.root / 'latest.json').write_text(json.dumps(data))
        self.assertEqual(self.path.read_bytes(), backup)
        data = self.scenario.run(19, script_hash='re-upgraded')[0]
        self.assertEqual(data['recent_activities'][0]['interval_data']['plan_match']['status'], 'not_assessed')
        self.assertNotEqual(self.path.read_bytes(), backup)

    def test_custom_output_folder_stores_backup_beside_the_output(self):
        self.root = self.root / 'selected-output'
        self.root.mkdir()
        self.scenario = carry.Scenario(self.root)
        data, sync, *_ = self.seed()
        sync.save_local_outputs(data, str(self.root / 'custom.json'))
        self.assertTrue((self.root / Store.PATH).is_file())
        self.assertFalse((self.root.parent / Store.PATH).exists())
        self.assertNotIn(Store.PATH, data['data_overview']['managed_files'])


class HostedBackup(unittest.TestCase):
    def fixture(self):
        fixture = integration.ControllerIntegration('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def next_runner(self, f, name):
        f.checkout = f.root / (name + '-checkout')
        f.runner = f.root / (name + '-runner')
        f.runner.mkdir()
        update_fixture.write(f.checkout, f.remote.inventory())
        patch = mock.patch.dict(os.environ, {'GITHUB_WORKSPACE': str(f.checkout),
                                            'RUNNER_TEMP': str(f.runner)})
        patch.start()
        self.addCleanup(patch.stop)

    def test_both_wrappers_publish_backup_and_restore_from_a_fresh_checkout(self):
        for wrapper, event in (('json-auto-sync', 'schedule'), ('json-on-demand', 'workflow_dispatch')):
            with self.subTest(wrapper=wrapper):
                f = self.fixture()
                workflow = (update_fixture.ROOT / 'examples' / wrapper / 'auto-sync.yml').read_bytes()
                path = '.github/workflows/auto-sync.yml'
                f.remote.tip = f.remote.commit({path: workflow}, [f.remote.tip], 'Owner workflow')
                update_fixture.write(f.checkout, {path: workflow})
                f.info['event'] = event
                f.prepare()
                first = carry.Scenario(f.checkout).run(14)[0]
                before = f.remote.tip
                hosted.validate_generated()
                hosted.publish_data()
                saved = f.remote.inventory()
                self.assertEqual(f.pub.snapshot()['parents'], [before])
                self.assertEqual(saved[Store.PATH], (f.checkout / Store.PATH).read_bytes())
                self.assertEqual(json.loads(saved['latest.json'])['carry_forward']['backup_revision'],
                                 Store.decode(saved[Store.PATH])['revision'])
                self.assertEqual(saved[path], workflow)
                self.assertNotIn(Store.PATH, first['data_overview']['managed_files'])
                artifact = workflow.decode().split('name: training-data', 1)[1]
                self.assertNotIn('archive/', artifact)
                # Damage is in the remote preimage, not an unverified checkout edit.
                f.remote.tip = f.remote.commit({'latest.json': b'{truncated'}, [f.remote.tip], 'Synthetic damaged export')
                self.next_runner(f, wrapper)
                f.prepare()
                result, _, calls, streams, log = carry.Scenario(f.checkout).run(16)
                self.assertTrue(result['recent_activities'][0]['interval_data']['plan_match']['assessment_retained'])
                self.assertEqual(streams, 0)
                self.assertIn('previous_latest_invalid', log)
                self.assertFalse(any(endpoint.startswith('activities/') for endpoint, _ in calls))
                hosted.validate_generated()
                hosted.publish_data()
                self.assertEqual(f.remote.inventory()[path], workflow)

    def test_quiet_next_run_reuses_the_same_git_blob(self):
        f = self.fixture()
        f.prepare()
        scenario = carry.Scenario(f.checkout)
        scenario.run(14)
        scenario.run(16)
        hosted.publish_data()
        before = f.pub.snapshot()['entries'][Store.PATH]
        raw = f.remote.inventory()[Store.PATH]
        self.next_runner(f, 'quiet')
        f.prepare()
        carry.Scenario(f.checkout).run(17)
        with mock.patch.object(f.remote, 'write', wraps=f.remote.write) as writes:
            hosted.publish_data()
        self.assertEqual(f.pub.snapshot()['entries'][Store.PATH], before)
        self.assertEqual(f.remote.inventory()[Store.PATH], raw)
        for call in writes.call_args_list:
            if call.args[1] == '/git/blobs':
                self.assertNotEqual(call.args[2]['content'], base64.b64encode(raw).decode())

    def test_old_export_preserves_tracked_backup_without_publishing_runner_copies(self):
        f = self.fixture()
        f.prepare()
        carry.Scenario(f.checkout).run(14)
        hosted.publish_data()
        saved = f.remote.inventory()[Store.PATH]
        self.next_runner(f, 'older')
        f.prepare()
        (f.checkout / Store.PATH).unlink()
        f.generated()  # Old producer has no revision declaration.
        update_fixture.write(f.checkout, {'archive/other.state': b'not authorized'})
        hosted.validate_generated()
        hosted.publish_data()
        self.assertEqual(f.remote.inventory()[Store.PATH], saved)
        self.assertNotIn('archive/other.state', f.remote.inventory())

    def test_checkout_preimage_binds_backup_before_producer_runs(self):
        f = self.fixture()
        f.prepare()
        carry.Scenario(f.checkout).run(14)
        hosted.publish_data()
        self.next_runner(f, 'bound')
        before = f.pub.snapshot()
        hosted.check_checkout(f.pub, before, f.checkout)
        path = f.checkout / Store.PATH
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'checkout differs'):
            hosted.check_checkout(f.pub, before, f.checkout)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'checkout differs'):
            hosted.check_checkout(f.pub, before, f.checkout)
        wrong_mode = copy.deepcopy(before)
        wrong_mode['entries'][Store.PATH]['mode'] = '100755'
        with self.assertRaisesRegex(ValueError, 'non-ordinary'):
            hosted.check_checkout(f.pub, wrong_mode, f.checkout)

    def test_claimed_backup_is_required_and_wrong_revision_stops_without_publication(self):
        for failure in ('missing', 'revision', 'export_revision', 'timestamp', 'version',
                        'signal_version', 'metadata', 'extra_path'):
            with self.subTest(failure=failure):
                f = self.fixture()
                f.prepare()
                data = carry.Scenario(f.checkout).run(14)[0]
                path = f.checkout / Store.PATH
                document = json.loads(path.read_bytes())
                if failure == 'missing':
                    path.unlink()
                elif failure == 'extra_path':
                    path.rename(path.with_name('other.state'))
                elif failure in ('export_revision', 'signal_version', 'metadata'):
                    if failure == 'export_revision':
                        data['carry_forward']['backup_revision'] = '0' * 64
                    elif failure == 'signal_version':
                        data['carry_forward']['version'] = 2
                    else:
                        data['metadata'] = None
                    (f.checkout / 'latest.json').write_text(json.dumps(data))
                else:
                    if failure == 'revision':
                        document['activities'][0]['weather_summary'] = {'avg_temp': 99}
                    elif failure == 'timestamp':
                        document['generated_at'] = '2026-01-15T12:00:00Z'
                    else:
                        document['version'] = 2
                    path.write_text(json.dumps(document))
                tip = f.remote.tip
                for action in (hosted.validate_generated, hosted.publish_data):
                    with self.assertRaises(ValueError):
                        action()
                    self.assertEqual(f.remote.tip, tip)

    def test_exact_reader_rejects_nonordinary_paths_and_malformed_or_oversized_json(self):
        f = self.fixture()
        data = carry.Scenario(f.checkout).run(14)[0]
        path = f.checkout / Store.PATH
        good = path.read_bytes()
        for raw in (b'{', b'null', good.replace(b'"version":1', b'"version":1,"version":1'),
                    good.replace(b'"version":1', b'"version":NaN')):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                hosted.read_carry_forward(f.checkout, data)
        path.write_bytes(good)
        with mock.patch.object(hosted.BACKUP, 'MAX_BYTES', len(good) - 1), self.assertRaises(ValueError):
            hosted.read_carry_forward(f.checkout, data)
        other = f.checkout / 'ordinary-copy'
        other.write_bytes(good)
        path.unlink()
        path.symlink_to(other)
        with self.assertRaisesRegex(ValueError, 'non-ordinary'):
            hosted.read_carry_forward(f.checkout, data)
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(ValueError, 'non-ordinary'):
            hosted.read_carry_forward(f.checkout, data)
        path.rmdir()
        path.parent.rmdir()
        path.parent.symlink_to(f.checkout)
        with self.assertRaisesRegex(ValueError, 'non-ordinary'):
            hosted.read_carry_forward(f.checkout, data)
        path.parent.unlink()
        for relative in (Store.PATH, 'archive/other.json', 'archive/other.state', 'other.state'):
            with self.assertRaises(ValueError):
                hosted.validate_data.checked_path(f.checkout, relative)

    def test_managed_controller_handshake_and_mixed_source_provenance(self):
        f = self.fixture()
        f.prepare()
        f.generated()
        with mock.patch.dict(os.environ, {'ATHLETE_ID': 'synthetic', 'INTERVALS_KEY': 'synthetic'}), \
             mock.patch.object(hosted.subprocess, 'run') as run:
            hosted.run_sync()
        env = run.call_args.kwargs['env']
        self.assertEqual(env['SECTION11_SYNC_WRAPPER_API'], '2')
        Store.require_controller(env)
        env.pop('SECTION11_CARRY_FORWARD_VERSION')
        with self.assertRaisesRegex(ValueError, 'matching managed controller'):
            Store.require_controller(env)
        Store.require_controller({'GITHUB_ACTIONS': ''})
        self.next_runner(f, 'mixed')
        altered = (*f.target[:2], dict(f.target[2], commit='a' * 40))
        with self.assertRaisesRegex(ValueError, 'authenticated producer differ'):
            hosted.prepare(f.source, altered, f.verifier)

    def test_hosted_update_and_rollback_preserve_later_backup_data(self):
        remote = remote_fixture.Remote({Store.PATH: b'old recovery bytes'})
        publisher = remote_fixture.DirectPublisher(remote)
        updater = remote_fixture.H.HostedUpdater(publisher, mock.Mock(return_value=remote_fixture.release()), {})
        with contextlib.redirect_stdout(io.StringIO()):
            updater.install(publisher.snapshot(), accepted=True)
            remote.tip = remote.commit({'SKILL.md': b'old removable copy'}, [remote.tip], 'Old copy')
            updater.install(publisher.snapshot(), accepted=True)
            remote.tip = remote.commit({Store.PATH: b'later recovery bytes'}, [remote.tip], 'Data change')
            updater.rollback(publisher.snapshot())
        self.assertEqual(remote.inventory()[Store.PATH], b'later recovery bytes')


class BackupDocumentation(unittest.TestCase):
    def test_ai_exclusion_manual_upload_and_both_artifact_lists(self):
        root = update_fixture.ROOT
        for name in ('PROJECT_INSTRUCTIONS_AGENTIC.md', 'PROJECT_INSTRUCTIONS_WEB.md', 'SKILL.md'):
            text = (root / name).read_text()
            self.assertIn(Store.PATH, text)
            self.assertIn('Read recovery status only from', text)
            self.assertIn('latest.json.carry_forward', text)
        manual = (root / 'examples/json-manual/SETUP.md').read_text()
        self.assertIn('- all `.json` files\n', manual)
        self.assertIn('- a ZIP of only the `section11/` folder\n', manual)
        self.assertFalse(Path(Store.PATH).match('*.json'))
        self.assertFalse(Store.PATH.startswith('section11/'))
        for name in ('json-auto-sync', 'json-on-demand'):
            text = (root / 'examples' / name / 'auto-sync.yml').read_text()
            self.assertNotIn('archive/', text.split('name: training-data', 1)[1])
