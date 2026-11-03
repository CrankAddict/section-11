"""Offline G1-G3 regressions; workflow text and bounded shell argument checks."""
import copy
import json
import os
import re
import subprocess
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from _harness import install_verb_guard, restore_verb_guard
import test_route_weather as fixtures

mod, Weather, NOW = fixtures.mod, fixtures.Weather, fixtures.NOW
ROOT = Path(__file__).resolve().parents[2]


def setUpModule():
    global guard
    guard = install_verb_guard(mod.requests)


def tearDownModule():
    restore_verb_guard(mod.requests, guard)


class DemandTests(unittest.TestCase):
    setUp = fixtures.RouteWeatherTests.setUp
    run_weather = fixtures.RouteWeatherTests.run_weather
    persist = fixtures.RouteWeatherTests.persist
    two_routes = fixtures.RouteWeatherTests.two_routes

    def test_midnight_to_ten_default_change_fetches_next_sync(self):
        self.events[0]['start_date_local'] = '2026-10-20T00:00:00'
        self.s.route_weather_default_start = '00:00'
        first, _ = self.run_weather(fixtures.window_success)
        self.persist()
        self.now += timedelta(seconds=60)
        self.s.route_weather_default_start = '10:00'
        updated, request = self.run_weather(fixtures.window_success)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(updated['status'], 'ok')
        self.assertEqual(Weather.parse_time(updated['departure']['at_utc']) -
                         Weather.parse_time(first['departure']['at_utc']), 36000)
        self.assertIn('10:00 UTC+0000 (ASSUMED)', updated['summary']['display']['departure'])

    def test_departure_edit_fetches_missing_hours_and_retains_refresh_deadline(self):
        first, _ = self.run_weather(fixtures.window_success)
        old_deadline = self.s._routes_data['route_weather_cache']['next_attempt_at']
        first_snapshot = copy.deepcopy(self.s._routes_data['brief_snapshots'][0])
        self.persist()
        self.now += timedelta(seconds=60)
        self.events[0]['start_date_local'] = '2026-10-19T16:00:00+00:00'
        updated, request = self.run_weather(fixtures.window_success)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(updated['status'], 'ok')
        self.assertNotEqual(updated['departure'], first['departure'])
        self.assertEqual(updated['eta']['duration_range_s'], first['eta']['duration_range_s'])
        self.assertEqual(self.s._routes_data['brief_snapshots'][0], first_snapshot)
        self.assertEqual(self.s._routes_data['route_weather_cache']['next_attempt_at'], old_deadline)
        self.persist()
        self.now += timedelta(seconds=60)
        repeated, _ = self.run_weather()  # any unmocked HTTP fails the test
        self.assertEqual(repeated, updated)
        self.assertEqual(self.s._routes_data['route_weather_requests_this_sync'], 0)

    def test_new_ride_fetches_only_its_window_under_closed_gate(self):
        rows = self.two_routes(same_location=True)
        both_events = self.events
        self.events = both_events[:1]
        first, _ = self.run_weather(fixtures.window_success, rows[:1])
        self.persist()
        self.now += timedelta(seconds=60)
        self.events = both_events
        _, request = self.run_weather(fixtures.window_success, rows)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(self.s._routes_data['events'][0]['route_weather'], first)
        self.assertEqual(self.s._routes_data['events'][1]['route_weather']['status'], 'ok')

    def test_covered_departure_edit_and_repeat_cache_hits_make_no_requests(self):
        self.run_weather(fixtures.success)  # broad covering legacy-style response
        self.persist()
        self.now += timedelta(seconds=60)
        self.events[0]['start_date_local'] = '2026-10-19T16:00:00+00:00'
        brief, _ = self.run_weather()
        self.assertEqual(brief['status'], 'ok')
        self.assertEqual(self.s._routes_data['route_weather_requests_this_sync'], 0)

    def test_unchanged_demand_refresh_waits_for_gate_without_new_fallback_calls(self):
        self.run_weather(fixtures.window_success)
        state = self.s._routes_data['route_weather_cache']
        due = state['next_attempt_at']
        for record in state['points'].values():
            record['expires_at'] = NOW.timestamp() + 30
            record['next_attempt_at'] = NOW.timestamp() + 30
        self.persist()
        self.now += timedelta(seconds=60)
        brief, _ = self.run_weather()
        self.assertEqual(brief['status'], 'stale')
        self.assertIn('forecast_backoff', brief['reason_codes'])
        self.assertEqual(self.s._routes_data['route_weather_requests_this_sync'], 0)
        self.now = NOW + timedelta(seconds=due - NOW.timestamp())
        brief, request = self.run_weather(fixtures.window_success)
        self.assertEqual(brief['status'], 'ok')
        self.assertEqual(request.call_count, 1)

    def test_new_demand_respects_failure_backoff_and_legacy_error_migration(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                self.now = NOW
                self.run_weather(lambda *a, **k: fixtures.reply(status=503))
                if legacy:
                    self.s._routes_data['route_weather_cache'].pop('failure_backoff_until')
                self.persist()
                self.now += timedelta(seconds=899)
                self.events[0]['start_date_local'] = '2026-10-19T16:00:00+00:00'
                blocked, _ = self.run_weather()
                self.assertEqual(self.s._routes_data['route_weather_requests_this_sync'], 0)
                self.assertIn('forecast_backoff', blocked['reason_codes'])
                self.now += timedelta(seconds=1)
                brief, request = self.run_weather(fixtures.window_success)
                self.assertEqual(brief['status'], 'ok')
                self.assertEqual(request.call_count, 1)
                # Leave the failure file on disk for the next subtest's same-time
                # constructor, but explicitly remove it between independent runs.
                (self.s.data_dir / self.s.ROUTES_FILE).unlink()

    def test_new_demand_respects_later_retry_after_and_provider_cooldown(self):
        self.run_weather(lambda *a, **k: fixtures.reply(status=429, headers={'Retry-After': '7200'}))
        self.persist()
        self.now += timedelta(seconds=1000)
        self.events[0]['start_date_local'] = '2026-10-20T16:00:00+00:00'
        brief, _ = self.run_weather()
        self.assertIn('forecast_backoff', brief['reason_codes'])
        self.assertEqual(self.s._routes_data['route_weather_requests_this_sync'], 0)

    def test_new_demand_timeout_splits_still_stop_at_eight_calls(self):
        self.run_weather(fixtures.window_success)
        self.persist()
        self.now += timedelta(seconds=60)
        self.events[0]['start_date_local'] = '2026-10-19T16:00:00+00:00'
        def timeout(*args, **kwargs):
            raise mod.requests.exceptions.ReadTimeout('synthetic')
        with mock.patch.object(mod.time, 'monotonic', return_value=0):
            _, request = self.run_weather(timeout)
        self.assertEqual(request.call_count, 8)
        self.assertEqual(self.s._routes_data['route_weather_requests_this_sync'], 8)
        self.persist()
        self.now += timedelta(seconds=1)
        self.events[0]['start_date_local'] = '2026-10-19T17:00:00+00:00'
        self.run_weather()
        self.assertEqual(self.s._routes_data['route_weather_requests_this_sync'], 0)

    def test_mixed_new_and_expired_points_do_not_refresh_old_points_early(self):
        producer = Weather(self.s, NOW)
        producer.can_fetch = False
        producer.request_window = (NOW.timestamp(), NOW.timestamp() + 3600)
        old = {'lat':55, 'lon':12, 'altitude':10}
        new = {'lat':56, 'lon':12, 'altitude':10}
        old_key = producer.point_key('open_meteo', old)
        producer.cache[old_key] = {'forecast': Weather.parse_open_meteo(fixtures.om_point()),
                                   'fetched_at': NOW.timestamp()-7200, 'expires_at': NOW.timestamp()-1,
                                   'next_attempt_at': NOW.timestamp()-1}
        with mock.patch.object(mod.requests, 'get', side_effect=fixtures.window_success) as request:
            producer.fetch_provider('open_meteo', [old,new], [new])
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs['params']['latitude'], '56')
        self.assertEqual(producer.cache[old_key]['fetched_at'], NOW.timestamp()-7200)

    def test_met_legacy_coverage_reuses_key_but_new_hours_get_separate_key(self):
        producer = Weather(self.s, NOW)
        point = {'lat':55, 'lon':12, 'altitude':10}
        key = producer.point_key('met_norway', point)
        producer.cache[key] = {'forecast': {'instants': [{'at':NOW.timestamp()}, {'at':NOW.timestamp()+3600}]},
                               'expires_at': NOW.timestamp()+7200}
        producer.request_window = (NOW.timestamp(), NOW.timestamp()+3600)
        self.assertEqual(producer.point_key('met_norway', point), key)
        self.assertFalse(producer.new_point_demand('met_norway', point))
        producer.request_window = (NOW.timestamp()+3600, NOW.timestamp()+7200)
        self.assertNotEqual(producer.point_key('met_norway', point), key)
        self.assertTrue(producer.new_point_demand('met_norway', point))

    def test_attempted_partial_window_is_not_new_on_every_sync(self):
        def partial(url, params, **kwargs):
            response = fixtures.window_success(url, params, **kwargs)
            for row in response.json.return_value:
                row['hourly'] = {k:v[:1] for k,v in row['hourly'].items()}
            return response
        self.run_weather(partial)
        self.persist()
        self.now += timedelta(seconds=60)
        self.run_weather()
        self.assertEqual(self.s._routes_data['route_weather_requests_this_sync'], 0)


class WorkflowTests(unittest.TestCase):
    def test_optional_repository_variables_are_in_sync_step_environment(self):
        workflow = (ROOT/'examples/json-auto-sync/auto-sync.yml').read_text()
        step = workflow.split('      - name: Run sync\n',1)[1].split('      - name:',1)[0]
        environment = step.split('        run:',1)[0]
        for name in ('SECTION11_ROUTE_WEATHER','SECTION11_ROUTE_WEATHER_DEFAULT_START'):
            self.assertIn(f'          {name}: ${{{{ vars.{name} }}}}', environment)
        self.assertNotIn('${{ vars.', step.split('        run:',1)[1])

    def test_empty_settings_use_defaults_and_nonempty_values_stay_strict(self):
        with mock.patch.dict(mod.os.environ, {'SECTION11_ROUTE_WEATHER':'', 'SECTION11_ROUTE_WEATHER_DEFAULT_START':''}, clear=True):
            self.assertTrue(Weather.enabled({}))
            self.assertEqual(Weather.default_start({}), '10:00')
            self.assertEqual(Weather.default_start({'route_weather_default_start':'09:15'}), '09:15')
            self.assertEqual(Weather.default_start({'route_weather_default_start':''}), '10:00')
            self.assertFalse(Weather.enabled({'route_weather':False}))
        with mock.patch.dict(mod.os.environ, {'SECTION11_ROUTE_WEATHER':'0', 'SECTION11_ROUTE_WEATHER_DEFAULT_START':'24:00'}):
            self.assertFalse(Weather.enabled({}))
            with self.assertRaisesRegex(ValueError, 'invalid_default_start'):
                Weather.departure({'start_date_local':'2026-10-20'}, {'timezone':'UTC'}, Weather.default_start({}))

    def workflow_args(self, time='', command='move', confirm='false'):
        from _harness import load_module_by_path
        push = load_module_by_path('weather_managed_push', ROOT/'examples/agentic/push.py')
        from types import SimpleNamespace
        inputs = {'command': command, 'confirm': confirm, 'event_id':'42','date':'2099-01-01', 'time': time}
        try:
            argv = push.workflow_arguments(inputs, Path('unused'))
            # Compare the preserved CLI contract independent of --key=value spelling.
            flat = [part for arg in argv for part in (arg.split('=', 1) if arg.startswith('--') and '=' in arg else [arg])]
            return SimpleNamespace(returncode=0, stdout=chr(0).join(flat), stderr='')
        except ValueError as exc:
            return SimpleNamespace(returncode=1, stdout=json.dumps({'error': str(exc)}), stderr='')

    def test_dispatch_time_input_is_optional_and_passed_as_literal_data(self):
        workflow = (ROOT/'examples/agentic/push-workout.yml').read_text()
        self.assertTrue(workflow.startswith('# push.py v0.8 workflow:'))
        self.assertRegex(workflow, r'(?s)      time:\n.*?required: false\n        type: string')
        self.assertNotIn('github.event.inputs', workflow)
        self.assertIn('python section11/examples/agentic/push.py --workflow', workflow)

    def test_move_argument_builder_optional_time_and_confirmation(self):
        for time in ('','00:00','00:01','09:30','23:59'):
            for confirm in ('false','true'):
                result = self.workflow_args(time, confirm=confirm)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = ['move','--event-id','42','--date','2099-01-01']
                if time:
                    expected += ['--time',time]
                if confirm == 'true':
                    expected += ['--confirm']
                self.assertEqual(result.stdout.rstrip('\0').split('\0'), expected)

    def test_move_argument_builder_rejects_malformed_time_before_execution(self):
        for time in ('24:00','9:30','09:60','09:30:00','09:30\n','09:30; false','$(false)','0\u0661:30'):
            result = self.workflow_args(time)
            self.assertEqual(result.returncode, 1, time)
            self.assertEqual(json.loads(result.stdout)['error'], 'time must be HH:MM local')
        result = self.workflow_args('09:30', command='push')
        self.assertEqual(result.returncode, 1)
        self.assertIn('only valid for move', json.loads(result.stdout)['error'])
