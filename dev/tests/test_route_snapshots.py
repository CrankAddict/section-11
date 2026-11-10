"""Bounded saved forecasts and shared workflow persistence; synthetic and offline."""
import copy
import json
import math
import re
import unittest
from datetime import timedelta
from unittest import mock

import test_route_weather as fixtures
from _harness import REPO_ROOT

Weather = fixtures.Weather
NOW = fixtures.NOW
setUpModule = fixtures.setUpModule
tearDownModule = fixtures.tearDownModule


def hundred_km_row(row):
    """200 half-km legs, rolling elevation and changing bearings, no real route."""
    row = copy.deepcopy(row)
    terrain = row["terrain_summary"]
    terrain.update(total_distance_km=100, climbs=[], descents=[],
                   polyline=[[i / 2, 55 + .1 * math.sin(i / 25), 12 + i * .004,
                              round(80 + 25 * math.sin(i / 8), 1)] for i in range(201)])
    return row


class SnapshotTests(unittest.TestCase):
    setUp = fixtures.RouteWeatherTests.setUp
    run_weather = fixtures.RouteWeatherTests.run_weather
    persist = fixtures.RouteWeatherTests.persist

    def initial(self):
        self.row = hundred_km_row(self.row)
        brief, _ = self.run_weather(fixtures.success)
        self.assertIn(brief["status"], ("ok", "partial"))
        self.assertEqual(len(brief["sections"]), 200)
        return brief

    def test_first_24_hour_boundary_and_late_planning(self):
        self.events[0]["start_date_local"] = Weather.iso(NOW.timestamp() + 86401)
        brief, _ = self.run_weather(fixtures.success)
        self.assertEqual(self.s._routes_data["brief_snapshots"], [])
        self.assertEqual(brief["snapshot_context"], "now")
        self.assertEqual(brief["snapshot_status"], "outside_snapshot_window")
        self.persist()
        self.now += timedelta(seconds=1)
        brief, _ = self.run_weather()
        self.assertEqual(len(self.s._routes_data["brief_snapshots"]), 1)
        self.assertEqual(self.s._routes_data["brief_snapshots"][0]["brief"]["brief_id"], brief["brief_id"])
        self.assertNotIn("snapshot_context", brief)

    def test_first_immutable_latest_replaced_across_route_and_time_edits(self):
        first = self.initial()
        frozen = copy.deepcopy(self.s._routes_data["brief_snapshots"][0])
        for minute in (20, 40, 60, 80):
            self.persist()
            self.now = NOW + timedelta(minutes=minute)
            self.row["route_ref"]["revision"] = str(minute) * 32
            self.events[0]["start_date_local"] = Weather.iso(NOW.timestamp() + 3 * 3600)
            brief, _ = self.run_weather(fixtures.success)
            snapshots = self.s._routes_data["brief_snapshots"]
            self.assertEqual(len(snapshots), 2)
            self.assertEqual(snapshots[0], frozen)
            self.assertEqual(snapshots[1]["brief"]["brief_id"], brief["brief_id"])
            self.assertEqual(snapshots[1]["brief"]["route_ref"], self.row["route_ref"])
        self.assertEqual(frozen["brief"]["brief_id"], first["brief_id"])

    def test_compact_identity_coverage_weather_and_no_raw_series(self):
        brief = self.initial()
        snapshot = self.s._routes_data["brief_snapshots"][0]
        saved = snapshot["brief"]
        for key in ("event_id", "route_ref", "brief_id", "cache_key", "departure", "tier", "fetched_at"):
            self.assertEqual(saved[key], brief[key])
        self.assertEqual(saved["eta"]["duration_range_s"], brief["eta"]["duration_range_s"])
        self.assertEqual(saved["eta"]["method"], brief["eta"]["method"])
        self.assertEqual(len(saved["segments"]), 10)
        self.assertEqual(saved["segments"][0]["start_km"], 0)
        self.assertEqual(saved["segments"][-1]["end_km"], 100)
        for segment in saved["segments"]:
            self.assertEqual(segment["temperature_range_c"], [0, 0])
            self.assertEqual(segment["wind_speed_range_mps"], [5, 5])
            self.assertEqual(segment["gust_max_range_mps"], [9, 9])
            self.assertEqual(segment["precipitation"]["amount_range_mm"], [.5, .5])
            self.assertTrue(segment["precipitation"]["wet_window_utc"])
            self.assertTrue(all(segment["coverage"].values()))
        self.assertFalse({"sections", "sampling", "display"} & saved.keys())
        self.assertNotIn("points", saved["provenance"])
        self.assertLess(len(json.dumps(snapshot, separators=(",", ":")).encode()), 12000)

    def test_return_to_first_binding_updates_latest_without_rewriting_first(self):
        brief = self.initial()
        self.persist()
        producer = Weather(self.s, NOW)
        first = copy.deepcopy(producer.snapshots[0])
        producer.epoch += 60
        producer.save_snapshot({**brief, "brief_id": "edited-route"})
        producer.epoch += 60
        producer.save_snapshot(brief)
        self.assertEqual(producer.snapshots[0], first)
        self.assertEqual(producer.snapshots[1]["brief"]["brief_id"], brief["brief_id"])
        self.assertEqual(producer.snapshots[1]["saved_at"], Weather.iso(producer.epoch))
        restored = producer.restore_snapshots(producer.snapshots)
        self.assertEqual(restored, producer.snapshots)
        producer.epoch += 60
        producer.save_snapshot(brief)
        self.assertEqual(producer.snapshots, restored)

    def test_partial_rain_stays_unknown_and_known_rain_is_not_totalled(self):
        brief = self.initial()
        brief["sections"][0]["weather"]["coverage"]["precipitation"] = False
        brief["sections"][0]["weather"]["precipitation_intervals"] = []
        brief["sections"][1]["weather"]["precipitation_intervals"][0]["amount_mm"] = 2
        compact = Weather.compact_snapshot({"saved_at": NOW.isoformat(), "brief": brief})
        first = compact["brief"]["segments"][0]
        self.assertFalse(first["coverage"]["precipitation"])
        self.assertEqual(first["precipitation"]["amount_range_mm"], [.5, 2])
        for leg in brief["sections"]:
            leg["weather"]["precipitation_intervals"] = []
            leg["weather"]["coverage"]["precipitation"] = False
        compact = Weather.compact_snapshot({"saved_at": NOW.isoformat(), "brief": brief})
        for segment in compact["brief"]["segments"]:
            self.assertIsNone(segment["precipitation"]["amount_range_mm"])
            self.assertIsNone(segment["precipitation"]["wet_window_utc"])
            self.assertFalse(segment["coverage"]["precipitation"])

    def test_expiry_is_departure_based_with_or_without_event(self):
        self.initial()
        self.persist()
        expiry = NOW + timedelta(hours=2, days=14)
        for events in ([], self.events):
            for seconds, count in ((-1, 1), (0, 0), (1, 0)):
                with self.subTest(events=bool(events), seconds=seconds):
                    self.s._routes_data = {"events": []}
                    producer = Weather(self.s, expiry + timedelta(seconds=seconds))
                    producer.generate(events, [], {}, self.athlete)
                    self.assertEqual(len(self.s._routes_data["brief_snapshots"]), count)

    def test_old_full_snapshots_shrink_on_next_generation(self):
        brief = self.initial()
        old = []
        for hour in range(-28, 1):
            b = copy.deepcopy(brief)
            b["brief_id"] = str(hour)
            old.append({"saved_at": (NOW + timedelta(hours=hour)).isoformat(), "brief": b})
        old.extend([None, [], {}, {"brief": []}, {"brief": {"status": "ok"}}])
        self.s._routes_data["brief_snapshots"] = old
        self.persist()
        self.s._routes_data = {"events": []}
        producer = Weather(self.s, NOW)
        producer.generate([], [], {}, self.athlete)
        migrated = self.s._routes_data["brief_snapshots"]
        self.assertEqual([s["brief"]["brief_id"] for s in migrated], ["-22", "0"])
        self.assertLess(len(json.dumps(migrated)), len(json.dumps(old)) / 20)
        self.persist()
        self.assertEqual(Weather(self.s, NOW).snapshots, migrated)

    def test_malformed_old_shapes_and_nonfinite_values_do_not_crash(self):
        brief = self.initial()
        for change in ({"sections": [None]}, {"departure": []}, {"route_ref": None},
                       {"summary": []}, {"event_id": {}}, {"fetched_at": float("nan")}):
            bad = {"saved_at": NOW.isoformat(), "brief": {**brief, **change}}
            self.s._routes_data["brief_snapshots"] = [bad]
            self.persist()
            self.assertEqual(Weather(self.s, NOW).snapshots, [])
        self.s._routes_data["brief_snapshots"] = {"old_shape": []}
        self.persist()
        self.assertEqual(Weather(self.s, NOW).snapshots, [])

    def test_capacity_rejects_new_slot_but_updates_existing_latest(self):
        brief = self.initial()
        self.persist()
        producer = Weather(self.s, NOW)
        with mock.patch.object(Weather, "MAX_SNAPSHOTS", 2):
            second = {**brief, "brief_id": "second"}
            producer.save_snapshot(second)
            third = {**brief, "brief_id": "third"}
            producer.save_snapshot(third)
            self.assertEqual(producer.snapshots[1]["brief"]["brief_id"], "third")
            other = {**brief, "event_id": 8, "brief_id": "other"}
            producer.save_snapshot(other)
            self.assertEqual(other["snapshot_status"], "capacity_reached")
            self.assertEqual(other["snapshot_context"], "now")
            self.assertEqual(len(producer.snapshots), 2)
        self.assertEqual(producer.snapshots[0]["brief"]["brief_id"], brief["brief_id"])

    def test_oversized_snapshot_not_saved_and_labelled_now(self):
        brief = self.initial()
        producer = Weather(self.s, NOW)
        brief["route_ref"]["revision"] = "x" * 20000
        producer.save_snapshot(brief)
        self.assertEqual(producer.snapshots, [])
        self.assertEqual(brief["snapshot_context"], "now")
        self.assertEqual(brief["snapshot_status"], "snapshot_not_saved")

    def test_after_departure_and_unusable_never_save(self):
        brief = self.initial()
        producer = Weather(self.s, NOW + timedelta(hours=2))
        producer.save_snapshot(brief)
        self.assertEqual(producer.snapshots, [])
        for status in ("stale", "unavailable"):
            producer = Weather(self.s, NOW)
            producer.save_snapshot({**brief, "status": status})
            self.assertEqual(producer.snapshots, [])

    def test_six_rides_five_days_many_refreshes_have_fixed_size_bound(self):
        brief = self.initial()
        producer = Weather(self.s, NOW)
        firsts = {}
        peak = 0
        for tick in range(241):  # half-hour refresh attempts over five days
            producer.epoch = NOW.timestamp() + tick * 1800
            for ride in range(6):
                b = copy.deepcopy(brief)
                b.update(event_id=ride, brief_id=f"{ride}:{tick}", fetched_at=Weather.iso(producer.epoch))
                b["departure"]["at_utc"] = Weather.iso(NOW.timestamp() + (108 + ride * 2) * 3600)
                producer.save_snapshot(b)
            producer.snapshots = producer.restore_snapshots(producer.snapshots)
            for s in producer.snapshots:
                key = s["brief"]["event_id"]
                if key not in firsts:
                    firsts[key] = copy.deepcopy(s)
            for key, saved in firsts.items():
                self.assertEqual(next(s for s in producer.snapshots if s["brief"]["event_id"] == key), saved)
            size = len(json.dumps(producer.snapshots, separators=(",", ":")).encode())
            peak = max(peak, size)
            self.assertLessEqual(len(producer.snapshots), 12)
            self.assertLessEqual(size, 192013)  # 12 * 16,000 + 11 commas + 2 brackets
        self.assertEqual(len(producer.snapshots), 12)
        self.assertLess(peak, 144000)

    def test_migration_enforces_overall_cap(self):
        brief = self.initial()
        old = [{"saved_at": NOW.isoformat(), "brief": {**brief, "event_id": i}} for i in range(80)]
        self.s._routes_data["brief_snapshots"] = old
        self.persist()
        self.assertEqual(len(Weather(self.s, NOW).snapshots), 64)


class WorkflowPersistenceTests(unittest.TestCase):
    def test_eta_history_validated_published_and_excluded_from_artifact(self):
        workflow = (REPO_ROOT / "examples/json-auto-sync/auto-sync.yml").read_text()
        publish = workflow.split("- name: Publish data and update README", 1)[1]
        artifact = workflow.split("- name: Upload data files for download", 1)[1].split("- name: Publish", 1)[0]
        expected = {"history.json", "intervals.json", "routes.json", "saved_workouts.json",
                    "ftp_history.json", "route_eta_history.json"}
        from test_data_overview import workflow_rules
        self.assertEqual(set(workflow_rules()['FALLBACK']), expected | {"latest.json"})
        self.assertIn('section11-gate.py" publish --tag "$RUNTIME_TAG" --commit "$RUNTIME_COMMIT" --wrapper-api 2', publish)
        self.assertNotIn("route_eta_history.json", artifact)
        rules = (REPO_ROOT / "examples/maintenance/validate_data.py").read_text()
        self.assertIn('json.loads(content, parse_constant=invalid_constant)', rules)
        hosted = (REPO_ROOT / "examples/maintenance/hosted.py").read_text()
        self.assertIn('validate_data.prepare(root, previous_path, stage)', hosted)
        self.assertIn("plan['removed']", hosted)
        self.assertIn("changes[archive] = latest", hosted)


    def test_on_demand_uses_shared_workflow_without_schedule(self):
        doc = (REPO_ROOT / "examples/json-on-demand/SETUP.md").read_text()
        self.assertIn('[On-demand workflow](auto-sync.yml)', doc)
        self.assertIn('It already has only `workflow_dispatch`', doc)
        self.assertIn('route_eta_history.json', doc)


if __name__ == "__main__":
    unittest.main()
