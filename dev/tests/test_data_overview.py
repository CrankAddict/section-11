"""Offline discovery, local display and exact workflow-rule regression tests."""
import copy
import io
import json
import struct
import tempfile
import textwrap
import unittest
import zlib
from datetime import timedelta
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from _harness import SYNC_PATH, install_verb_guard, restore_verb_guard
from test_route_weather_map import mod, fixture, Map, Weather, NOW


def setUpModule():
    global guard
    guard = install_verb_guard(mod.requests)


def tearDownModule():
    restore_verb_guard(mod.requests, guard)


def workflow_rules():
    """Load the shipped standalone rules; no YAML library or GitHub needed."""
    path = SYNC_PATH.parent / 'maintenance/validate_data.py'
    block = path.read_text()
    namespace = {'__name__': 'offline_publication_rules'}
    exec(compile(block, str(path), 'exec'), namespace)
    return namespace


def tiny_png():
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\0\xff\xff\xff')) + chunk(b'IEND', b''))


class LocalDisplayTests(unittest.TestCase):
    def test_sixteen_compass_sectors_and_boundaries(self):
        self.assertEqual([Map.compass(i * 22.5) for i in range(16)],
                         'N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW'.split())
        self.assertEqual([Map.compass(v) for v in (11.249, 11.25, 348.75, -22.5, 720)], ['N', 'NNE', 'N', 'NNW', 'N'])
        self.assertEqual(Map.compass(None), 'UNKNOWN')
        self.assertEqual(Map.compass(float('nan')), 'UNKNOWN')

    def test_copenhagen_dst_repeated_hour_and_spring_forward(self):
        context = Map.time_context({}, {'timezone': 'Europe/Copenhagen'})
        self.assertEqual(Map.local_time('2026-10-25T00:30:00Z', context), '2026-10-25 02:30 CEST+0200')
        self.assertEqual(Map.local_time('2026-10-25T01:30:00Z', context), '2026-10-25 02:30 CET+0100')
        self.assertIn('03:30 CEST+0200', Map.local_time('2026-03-29T01:30:00Z', context))

    def test_timezone_source_and_labelled_fallback(self):
        self.assertEqual(Map.time_context({'timezone': 'America/New_York'}, {'timezone': 'Europe/Copenhagen'})['source'], 'event_timezone')
        self.assertEqual(Map.time_context({'timezone': 'invalid'}, {'timezone': 'Europe/Copenhagen'})['zone'], 'Europe/Copenhagen')
        context = Map.time_context({}, {'timezone': 'invalid'})
        self.assertTrue(context['fallback'])
        self.assertIn('unknown', context['source'])
        self.assertIn('UTC+0000', Map.local_time(NOW.isoformat(), context))


class OverviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sync = object.__new__(mod.IntervalsSync)
        self.sync.data_dir = self.root
        self.sync.athlete_id = 'synthetic'
        self.sync.debug = False
        self.sync.route_weather_enabled = True
        self.row, self.event = fixture(self.sync, athlete={'timezone': 'Europe/Copenhagen'})
        self.sync._routes_data = {'events': [self.row]}
        self.sync._overview_events = [self.event]
        self.sync._overview_athlete = {'timezone': 'Europe/Copenhagen'}

    def overview(self):
        return mod.DataOverview.build(self.sync, {}, now=NOW)

    def test_all_companions_present_missing_and_relative_paths(self):
        for name, _, _, _ in mod.DataOverview.COMPANIONS:
            (self.root / name).write_text('{}')
        value = self.overview()
        self.assertEqual(len(value['files']), 7)
        self.assertEqual(value['managed_files'], sorted(f['path'] for f in value['files']))
        for entry in value['files']:
            self.assertTrue(entry['present'])
            self.assertIsNotNone(entry['updated_at'])
            self.assertFalse(Path(entry['path']).is_absolute())
            self.assertNotIn(str(self.root), json.dumps(entry))
        (self.root / 'history.json').unlink()
        value = self.overview()
        self.assertNotIn('history.json', value['managed_files'])
        self.assertFalse(next(f for f in value['files'] if f['path'] == 'history.json')['present'])

    def test_no_geometry_and_weather_summary_is_one_line(self):
        value = self.overview()
        ride = value['rides'][0]
        self.assertTrue(ride['has_route'])
        self.assertEqual(ride['route_status'], 'ok')
        self.assertEqual(ride['climb_count'], len(self.row['terrain_summary']['climbs']))
        for word in ('polyline', 'coordinates', 'latitude', 'longitude', 'sampling'):
            self.assertNotIn(word, json.dumps(value))
        for word in ('Wind', 'gust', 'rain', 'temp'):
            self.assertIn(word, ride['weather']['summary'])
        self.assertNotIn('\n', ride['weather']['summary'])

    def test_missing_expired_off_and_partial_status(self):
        original = copy.deepcopy(self.row)
        for status in ('missing', 'expired', 'off', 'partial'):
            self.row.clear()
            self.row.update(copy.deepcopy(original))
            self.sync.route_weather_enabled = status != 'off'
            if status == 'missing':
                self.row.pop('route_weather')
            elif status == 'expired':
                self.row['route_weather']['expires_at'] = NOW.isoformat()
            elif status == 'partial':
                self.row['route_weather']['status'] = status
            ride = self.overview()['rides'][0]
            self.assertEqual(ride['weather']['status'], status)
            self.assertEqual(ride['weather']['summary'] is not None, status == 'partial')
            self.assertFalse(ride['map']['present'])

    def test_no_route_and_deduplication(self):
        self.sync._routes_data = {'events': []}
        self.sync._overview_events = [self.event, self.event]
        ride = self.overview()['rides'][0]
        self.assertFalse(ride['has_route'])
        self.assertEqual(ride['route_status'], 'absent')
        self.assertIsNone(ride['json_path'])
        self.assertEqual(self.overview()['rides_total'], 1)

    def test_rides_are_bounded_with_explicit_omission(self):
        self.sync._overview_events = [{**self.event, 'id': i} for i in range(100)]
        value = self.overview()
        self.assertEqual(len(value['rides']), 64)
        self.assertEqual(value['rides_omitted'], 36)
        self.assertLess(len(json.dumps(value).encode()), 60000)

    def test_maps_share_registry_and_symlinks_not_declared(self):
        with mock.patch.object(Map, 'png', return_value=tiny_png()):
            Map.generate(self.sync, [self.event], self.sync._overview_athlete, NOW)
        value = self.overview()
        path = self.row['route_weather_map']['path']
        self.assertTrue(path.startswith('maps/weather/'))
        self.assertIn(path, value['managed_files'])
        self.assertTrue(value['rides'][0]['map']['present'])
        (self.root / path).unlink()
        (self.root / path).symlink_to(self.root / 'ordinary.png')
        (self.root / 'ordinary.png').write_bytes(tiny_png())
        self.assertNotIn(path, self.overview()['managed_files'])

    def test_nested_parent_symlink_is_not_followed(self):
        target = self.root / 'untouched'
        target.mkdir()
        (self.root / 'maps').symlink_to(target, target_is_directory=True)
        Map.generate(self.sync, [self.event], self.sync._overview_athlete, NOW)
        self.assertEqual(self.row['route_weather_map_status'], 'unsafe_directory')
        self.assertEqual(list(target.iterdir()), [])

    def test_actual_write_precedes_declaration_and_custom_output_directory(self):
        nested = self.root / 'export'
        nested.mkdir()
        self.sync.data_dir = nested
        self.sync._intervals_data = {'activities': []}
        data = {}
        self.sync.save_local_outputs(data, str(nested / 'latest.json'))
        saved = json.loads((nested / 'latest.json').read_text())
        self.assertIn('routes.json', saved['data_overview']['managed_files'])
        self.assertIn('intervals.json', saved['data_overview']['managed_files'])
        self.assertFalse((self.root / 'routes.json').exists())
        self.assertEqual(workflow_rules()['plan'](nested)['mode'], 'declared')

    def test_map_sample_changes_snapshot_id_without_growing_full_snapshots(self):
        producer = Weather(self.sync, NOW)
        brief = self.row['route_weather']
        producer.save_snapshot(brief)
        first = copy.deepcopy(producer.snapshots[0])
        for i in range(30):
            updated = copy.deepcopy(brief)
            updated['sections'][0]['weather']['map_sample']['wind_from_deg'] = i
            updated['brief_id'] = Weather.digest(updated)
            producer.save_snapshot(updated)
        self.assertEqual(len(producer.snapshots), 2)
        self.assertEqual(producer.snapshots[0], first)
        for snapshot in producer.snapshots:
            self.assertEqual(snapshot['snapshot_version'], 1)
            self.assertLessEqual(len(json.dumps(snapshot, separators=(',', ':')).encode()), 16000)
            self.assertNotIn('map_sample', json.dumps(snapshot))
            self.assertNotIn('sections', snapshot['brief'])

    def test_cli_selects_output_parent_before_history_and_collection(self):
        target = self.root / 'chosen' / 'latest.json'
        calls = []
        def history_gate(sync):
            self.assertEqual(sync.data_dir, target.parent)
            calls.append('history')
            return False
        def collect(sync, days_back):
            self.assertEqual(sync.data_dir, target.parent)
            calls.append('collect')
            sync._routes_data = {'events': []}
            sync._intervals_data = {'activities': []}
            return {}
        with mock.patch('sys.argv', ['sync.py', '--athlete-id', 'synthetic', '--intervals-key', 'synthetic', '--output', str(target)]), \
             mock.patch.dict(mod.os.environ, {}, clear=True), \
             mock.patch.object(mod.os.path, 'exists', return_value=False), \
             mock.patch.object(mod, '_rotate_log_if_needed'), \
             mock.patch.object(mod, 'notify_if_updates_available'), \
             mock.patch.object(mod.IntervalsSync, 'should_generate_history', autospec=True, side_effect=history_gate), \
             mock.patch.object(mod.IntervalsSync, 'collect_training_data', autospec=True, side_effect=collect), \
             redirect_stdout(io.StringIO()):
            mod.main()
        self.assertEqual(calls, ['history', 'collect'])
        saved = json.loads(target.read_text())
        self.assertIn('routes.json', saved['data_overview']['managed_files'])
        self.assertIn('intervals.json', saved['data_overview']['managed_files'])
        self.assertFalse((self.root / 'routes.json').exists())


class WorkflowRulesTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.rules = workflow_rules()

    def write_latest(self, paths=None):
        value = {} if paths is None else {'data_overview': {'version': 1, 'managed_files': paths}}
        (self.root / 'latest.json').write_text(json.dumps(value))
        return value

    def test_future_json_and_nested_png_need_no_filename_change(self):
        (self.root / 'future').mkdir()
        (self.root / 'future/other.json').write_text('{"new": true}')
        (self.root / 'future/chart.png').write_bytes(tiny_png())
        paths = ['latest.json', 'future/other.json', 'future/chart.png']
        self.write_latest(paths)
        self.assertEqual(self.rules['plan'](self.root)['saved'], sorted(paths))

    def test_unsafe_paths_types_hidden_and_traversal_fall_back(self):
        for path in ('/outside.json', '../outside.json', 'a/../x.json', 'a/.secrets/x.json', '.secrets.json',
                     'a//x.json', './x.json', 'C:/x.json', 'a\\x.json', 'x.txt', 'x.svg', '-x.json', 'x\ny.json'):
            self.write_latest(['latest.json', path])
            self.assertEqual(self.rules['plan'](self.root)['mode'], 'legacy_fallback', path)

    def test_missing_duplicate_wrong_type_or_version_declarations_fall_back(self):
        for paths in (None, [], ['latest.json'] * 2, [1], ['missing.json'], ['latest.json'] + [f'{i}.json' for i in range(128)]):
            self.write_latest(paths)
            self.assertEqual(self.rules['plan'](self.root)['mode'], 'legacy_fallback')
        (self.root / 'latest.json').write_text('{"data_overview":{"version":2,"managed_files":["latest.json"]}}')
        self.assertEqual(self.rules['plan'](self.root)['mode'], 'legacy_fallback')

    def test_invalid_json_is_fail_closed_even_in_fallback(self):
        self.write_latest()
        (self.root / 'routes.json').write_text('not json')
        with self.assertRaises(ValueError):
            self.rules['plan'](self.root)
        (self.root / 'routes.json').write_text('{"x": NaN}')
        with self.assertRaises(ValueError):
            self.rules['plan'](self.root)

    def test_invalid_png_header_crc_dimensions_and_size(self):
        self.write_latest(['latest.json', 'map.png'])
        for content in (b'not png', tiny_png()[:20], tiny_png()[:29] + b'bad!' + tiny_png()[33:]):
            (self.root / 'map.png').write_bytes(content)
            self.assertEqual(self.rules['plan'](self.root)['mode'], 'legacy_fallback')
        (self.root / 'map.png').write_bytes(tiny_png())
        self.assertEqual(self.rules['plan'](self.root)['mode'], 'declared')
        invalid_dimensions = bytearray(tiny_png())
        invalid_dimensions[16:20] = struct.pack('>I', 0)
        invalid_dimensions[29:33] = struct.pack('>I', zlib.crc32(invalid_dimensions[12:29]) & 0xffffffff)
        (self.root / 'map.png').write_bytes(invalid_dimensions)
        self.assertEqual(self.rules['plan'](self.root)['mode'], 'legacy_fallback')
        (self.root / 'map.png').write_bytes(tiny_png())
        self.rules['MAX_BYTES'] = 1
        with self.assertRaisesRegex(ValueError, '64 MiB'):
            self.rules['read_data'](self.root, 'map.png')

    def test_symlink_file_and_parent_are_never_published(self):
        target = self.root / 'target'
        target.mkdir()
        (target / 'x.json').write_text('{}')
        (self.root / 'linked').symlink_to(target, target_is_directory=True)
        (self.root / 'linked.json').symlink_to(target / 'x.json')
        for path in ('linked/x.json', 'linked.json'):
            self.write_latest(['latest.json', path])
            self.assertEqual(self.rules['plan'](self.root)['mode'], 'legacy_fallback')

    def test_only_previously_declared_dropped_files_are_removed(self):
        self.write_latest(['latest.json'])
        (self.root / 'old.png').write_bytes(tiny_png())
        (self.root / 'personal.json').write_text('{}')
        previous = {'data_overview': {'version': 1, 'managed_files': ['latest.json', 'old.png']}}
        result = self.rules['plan'](self.root, previous)
        self.assertEqual(result['removed'], ['old.png'])
        self.assertNotIn('personal.json', result['touched'])
        self.write_latest()
        self.assertEqual(self.rules['plan'](self.root, previous)['removed'], [])

    def test_invalid_previous_ownership_never_deletes(self):
        self.write_latest(['latest.json'])
        (self.root / 'old.png').write_bytes(tiny_png())
        previous = {'data_overview': {'version': 1, 'managed_files': ['latest.json', 'old.png', '../x.json']}}
        self.assertEqual(self.rules['plan'](self.root, previous)['removed'], [])

    def test_prepare_restore_keeps_nested_files_and_unrelated_bytes(self):
        (self.root / 'maps').mkdir()
        (self.root / 'maps/current.png').write_bytes(tiny_png())
        (self.root / 'old.png').write_bytes(tiny_png())
        (self.root / 'personal.json').write_text('{"keep":1}')
        previous = self.root / 'previous.json'
        previous.write_text(json.dumps({'data_overview': {'version': 1, 'managed_files': ['latest.json', 'old.png']}}))
        self.write_latest(['latest.json', 'maps/current.png'])
        stage = self.root / 'stage'
        self.rules['prepare'](self.root, previous, stage)
        (self.root / 'maps/current.png').unlink()
        (self.root / 'latest.json').write_text('{}')
        self.rules['restore'](self.root, stage)
        self.assertEqual((self.root / 'maps/current.png').read_bytes(), tiny_png())
        self.assertFalse((self.root / 'old.png').exists())
        self.assertEqual((self.root / 'personal.json').read_text(), '{"keep":1}')
        self.rules['restore'](self.root, stage)  # Retry after a clean readback is deterministic.

    def test_restore_refuses_new_symlink_before_mutating_any_file(self):
        (self.root / 'maps').mkdir()
        (self.root / 'maps/current.png').write_bytes(tiny_png())
        previous = self.root / 'previous.json'
        previous.write_text('{}')
        self.write_latest(['latest.json', 'maps/current.png'])
        stage = self.root / 'stage'
        self.rules['prepare'](self.root, previous, stage)
        (self.root / 'maps/current.png').unlink()
        (self.root / 'maps').rmdir()
        (self.root / 'target').mkdir()
        (self.root / 'maps').symlink_to(self.root / 'target', target_is_directory=True)
        (self.root / 'latest.json').write_text('{"unchanged": true}')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.rules['restore'](self.root, stage)
        self.assertEqual((self.root / 'latest.json').read_text(), '{"unchanged": true}')
        self.assertEqual(list((self.root / 'target').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
