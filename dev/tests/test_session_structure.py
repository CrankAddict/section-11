"""Offline synthetic guards for plan windows, fallback and derived-cache freshness.

No FIT, private captures, credentials, current FTP or network are used.
"""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from _harness import (NetworkBlocked, SYNC_PATH, install_verb_guard,
                      load_module_by_path, restore_verb_guard)

mod = load_module_by_path("s11_session_structure", SYNC_PATH)
Sync = mod.IntervalsSync
originals = None
NOW = datetime(2026, 1, 2, tzinfo=timezone.utc)


def setUpModule():
    global originals
    originals = install_verb_guard(mod.requests)


def tearDownModule():
    restore_verb_guard(mod.requests, originals)


def inputs(powers=(100, 200, 300), duration=100, tail=0):
    total = duration * len(powers)
    act = {"id": "synthetic-ride", "paired_event_id": 42, "type": "VirtualRide",
           "start_date": "2026-01-01T10:00:00Z", "start_date_local": "2026-01-01T10:00:00",
           "elapsed_time": total + tail, "moving_time": total + tail,
           "workout_shift_secs": None, "icu_intervals": [], "compliance": 108}
    event = {"id": 42, "updated": "2026-01-01T09:00:00Z", "category": "WORKOUT",
             "workout_doc": {"duration": total, "steps": [
                 {"duration": duration, "power": {"units": "w", "value": p}} for p in powers]}}
    watts = [p for p in powers for _ in range(duration)] + [50] * tail + [0]
    streams = {"time": list(range(len(watts))), "watts": watts,
               "heartrate": [120] * len(watts), "cadence": [90] * len(watts)}
    return act, event, streams


class Structure(unittest.TestCase):
    def setUp(self):
        self.sync = Sync("i123", "synthetic")
        self.sync._intervals_data = {}
        self.act, self.event, self.streams = inputs()

    def build(self):
        return self.sync._build_session_structure(self.act, self.event, self.streams,
                                                 self.act.get("icu_intervals"))

    def test_positive_erg_and_independent_dfa(self):
        block = self.build()
        self.assertEqual(block["status"], "followed")
        self.assertEqual(block["method"], "paired_plan_windows")
        self.assertEqual([s["actual"][2] for s in block["steps"]], [100, 200, 300])
        self.assertEqual([s["actual"][3] for s in block["steps"]], [9.9, 19.8, 29.7])
        self.assertNotIn("execution", block)
        self.assertNotIn("thirds", block)
        self.assertNotIn("efforts", block)
        self.assertNotIn("normalized_power", json.dumps(block))

    def test_name_and_environment_do_not_choose_branch(self):
        first = self.build()
        for kind in ("Ride", "VirtualRide", "Run"):
            self.act.update(type=kind, name="Free ride, no workout")
            self.assertEqual(self.build(), first)

    def test_ignores_plan_and_same_aggregate_wrong_order(self):
        self.streams["watts"] = [300] * 100 + [200] * 100 + [100] * 100 + [0]
        block = self.build()
        self.assertEqual(sum(r[2] for r in block["thirds"]) / 3, 200)
        self.assertEqual(block["status"], "not_followed")
        self.assertEqual(block["method"], "fixed_elapsed_thirds")
        self.assertTrue(all("actual" not in s for s in block["steps"]))

    def test_some_steps_disagree(self):
        self.streams["watts"][100:200] = [160] * 100
        block = self.build()
        self.assertEqual(block["status"], "partly_followed")
        self.assertEqual([s["match"] for s in block["steps"]], [True, False, True])

    def test_target_edges_use_unrounded_mean(self):
        for power, status in ((105, "followed"), (105.001, "partly_followed"),
                              (95, "followed"), (94.999, "partly_followed")):
            with self.subTest(power=power):
                self.streams["watts"][:100] = [power] * 100
                self.assertEqual(self.build()["status"], status)

    def test_range_is_range_not_ramp(self):
        self.event["workout_doc"]["steps"][0]["power"] = {"units": "w", "min": 90, "max": 110}
        self.streams["watts"][:100] = [110] * 100
        self.assertEqual(self.build()["status"], "followed")
        self.streams["watts"][:100] = [110.001] * 100
        self.assertEqual(self.build()["status"], "partly_followed")

    def test_half_disagree_is_partial_and_majority_is_not_followed(self):
        for count, expected in ((2, "partly_followed"), (3, "not_followed")):
            self.act, self.event, self.streams = inputs(powers=(100, 200, 300, 400))
            self.streams["watts"][:count * 100] = [0] * (count * 100)
            block = self.build()
            self.assertEqual(block["status"], expected)
            self.assertEqual("thirds" in block, count == 3)
            self.assertEqual("actual" in block["steps"][0], count == 2)

    def test_neighbouring_six_percent_target_is_outside_match_band(self):
        self.act, self.event, self.streams = inputs(powers=(100,))
        for actual, status in ((105, "followed"), (106, "not_followed")):
            self.streams["watts"][:100] = [actual] * 100
            self.assertEqual(self.build()["status"], status)

    def test_short_tail_and_extension_edges(self):
        for tail, status in ((30, "followed"), (31, "followed"),
                             (300, "followed"), (301, "not_followed")):
            self.act, self.event, self.streams = inputs(tail=tail)
            with self.subTest(tail=tail):
                b = self.build()
                self.assertEqual(b["status"], status)
                if "unassigned" in b:
                    self.assertEqual(b["unassigned"][0][:2], [300, 300 + tail])

    def test_shortened_preserves_full_plan_and_clipped_actuals(self):
        for end, status in ((299, "followed"), (250, "followed"),
                            (150, "partly_followed"), (149, "partly_followed")):
            self.act, self.event, self.streams = inputs()
            self.act["elapsed_time"] = end
            self.streams = {k: v[:end + 1] for k, v in self.streams.items()}
            b = self.build()
            self.assertEqual(b["status"], status)
            self.assertEqual(sum(s.get("duration_s", s["actual"][1] - s["actual"][0] + 1)
                                 if "actual" in s else s["duration_s"] for s in b["steps"]), 300)
            if end == 250:
                self.assertEqual(b["steps"][-1]["actual"][:2], [201, 250])
                self.assertEqual(b["steps"][-1]["observed_window_fraction"], round(49 / 99, 4))
                self.assertEqual(self.sync._structure_summary(b)["steps"][-1], [49, 300, 300, True])

    def test_shifted_lead_in_and_wrong_offset(self):
        self.act["elapsed_time"] = 400
        self.act["workout_shift_secs"] = 100
        self.streams = {"time": list(range(401)), "watts": [50] * 100 + self.streams["watts"]}
        b = self.build()
        self.assertEqual(b["status"], "followed")
        self.assertEqual(b["steps"][0]["actual"][:2], [101, 200])
        self.assertEqual(b["unassigned"][0][:2], [0, 100])
        self.act["workout_shift_secs"] = 0
        self.assertEqual(self.build()["status"], "not_followed")

    def test_negative_shift_does_not_stretch_plan(self):
        self.act["workout_shift_secs"] = -50
        b = self.build()
        self.assertNotEqual(b["status"], "followed")

    def test_no_plan_empty_plan_and_timestamp_only_update(self):
        self.event = None
        self.assertEqual(self.build()["status"], "unknown")
        self.act, self.event, self.streams = inputs()
        self.event["workout_doc"]["steps"] = []
        self.assertEqual(self.build()["status"], "no_steps")
        self.act, self.event, self.streams = inputs()
        self.event["updated"] = "2026-01-02T10:00:00Z"
        self.assertEqual(self.build()["status"], "followed")
        self.assertIn("actual", self.build()["steps"][0])

    def test_exact_pairing_only(self):
        for change in ({"id": 43}, {"paired_activity_id": "other"}, {"athlete_id": "other"}):
            self.act, self.event, self.streams = inputs()
            self.act["athlete_id"] = "owner"
            self.event.update(change)
            self.assertIn("pairing_conflict", self.build()["issues"])

    def test_unsupported_steps_and_missing_total(self):
        cases = [{"distance": 1000}, {"ramp": True}, {"steps": [], "reps": 3},
                 {"power": {"units": "%FTP", "value": 90}}, {"duration": False},
                 {"power": {"units": "w", "start": 100, "end": 200}}]
        for change in cases:
            self.act, self.event, self.streams = inputs()
            self.event["workout_doc"]["steps"][0].update(change)
            self.assertEqual(self.build()["status"], "unknown")
        self.act, self.event, self.streams = inputs()
        self.event["workout_doc"].pop("duration")
        self.assertIn("plan_total_mismatch", self.build()["issues"])

    def test_missing_time_or_power_fails_closed(self):
        for key in ("time", "watts"):
            self.act, self.event, self.streams = inputs()
            self.streams.pop(key)
            self.assertEqual(self.build()["status"], "unknown")

    def test_malformed_time(self):
        for value in (0, -1, float("nan"), "1", True):
            self.act, self.event, self.streams = inputs()
            self.streams["time"][1] = value
            self.assertEqual(self.build()["status"], "unknown")

    def test_coverage_edges_and_interior_gap(self):
        for missing, status in ((5, "followed"), (6, "partly_followed")):
            # 101 prescribed seconds leave exactly 100 measured seconds.
            self.act, self.event, self.streams = inputs(duration=101)
            self.streams["watts"][20:20 + missing] = [None] * missing
            self.assertEqual(self.build()["status"], status)
        self.act, self.event, self.streams = inputs()
        self.streams = {k: v[:20] + v[40:] for k, v in self.streams.items()}
        b = self.build()
        # Removing recorded data changes the power sequence on the recording
        # timeline; the first two windows now disagree, so fallback is correct.
        self.assertEqual(b["status"], "not_followed")
        self.assertEqual(b["thirds"][0][6], 80)

    def test_zeros_gaps_and_independent_denominators(self):
        self.event = None
        self.act["elapsed_time"] = 6
        self.streams = {"time": [0, 1, 4, 5, 6], "watts": [0, 100, 200, None, 999],
                        "heartrate": [0, 100, 120, 140, 999], "cadence": [0, None, 80, 90, 999]}
        b = self.build()
        _, times, values, _ = self.sync._structure_streams(self.act, self.streams)
        self.assertEqual(self.sync._structure_window(0, 6, times, values),
                         [0, 6, 100, .3, 120, 56.7, 50, 50, 50, 33.33])
        self.assertNotIn("whole_observed", b)
        self.assertEqual([r[:2] for r in b["thirds"]], [[0, 2], [2, 4], [4, 6]])
        self.assertIsNone(b["thirds"][1][2])

    def test_detected_efforts_not_steps_and_capped(self):
        self.event = None
        self.act["icu_intervals"] = [{"type": "RECOVERY", "start_time": 0, "end_time": 300}] + [
            {"type": "WORK", "start_time": i, "end_time": i + 1, "average_watts": 0,
             "weighted_average_watts": 999} for i in range(10)]
        b = self.build()
        self.assertEqual(len(b["efforts"]), 8)
        self.assertEqual(b["omitted_efforts"], 2)
        self.assertEqual(b["efforts"][0][2], 0)

    def test_size_and_plan_truncation_revoke_verdict(self):
        self.event["workout_doc"]["steps"] *= 100
        b = self.build()
        self.assertLessEqual(len(b["steps"]), 20)
        self.assertIn("truncated", b["issues"])
        self.assertEqual(b["status"], "unknown")
        for step in self.event["workout_doc"]["steps"]:
            step["text"] = {str(i): ["ø" * 500] * 20 for i in range(20)}
        b = self.build()
        self.assertLessEqual(len(json.dumps(b, ensure_ascii=False, separators=(",", ":")).encode()), 12288)
        self.assertGreater(b["omitted_steps"], 0)


class Cache(unittest.TestCase):
    setUp = Structure.setUp
    build = Structure.build

    def prepare(self, previous=None, now=NOW, events=None):
        return self.sync._prepare_session_structures([self.act], [self.event] if events is None else events,
                                                     previous or {}, now=now)[self.act["id"]]

    def previous(self, block):
        self.sync._intervals_data = {"activities": [
            {"activity_id": self.act["id"], "date": "2026-01-01", "session_structure": block}]}
        return {}

    def test_cache_hit_expiry_revision_and_persisted_reload(self):
        with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("ok", self.streams)) as fetch:
            b = self.prepare()
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(self.prepare(self.previous(b), NOW + timedelta(hours=23)), b)
            self.assertEqual(fetch.call_count, 1)
            self.prepare(self.previous(b), NOW + timedelta(hours=24))
            self.assertEqual(fetch.call_count, 2)
            self.act["icu_sync_date"] = "changed"
            self.prepare(self.previous(b))
            self.assertEqual(fetch.call_count, 3)
            with tempfile.TemporaryDirectory() as folder:
                self.sync.data_dir, self.sync.debug = Path(folder), False
                (Path(folder) / "latest.json").write_text(json.dumps({"recent_activities": [
                    {"id": self.act["id"], "structure_summary": self.sync._structure_summary(b)}]}))
                self.assertEqual(self.sync._load_previous_latest(),
                                 {self.act["id"]: {"structure_summary": self.sync._structure_summary(b)}})

    def test_late_plan_changes_are_compared_against_current_plan(self):
        with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("ok", self.streams)):
            initial = copy.deepcopy(self.event)
            self.event["workout_doc"]["steps"] = []
            b = self.prepare()
            self.event = initial
            revised = self.prepare(self.previous(b))
            self.assertEqual(len(revised["steps"]), 3)
            self.assertEqual(revised["status"], "followed")
            later = self.prepare(self.previous(revised), NOW + timedelta(days=2))
            self.assertEqual(later["status"], "followed")
            self.assertIn("actual", later["steps"][0])

    def test_failed_refresh_is_stale_revokes_actuals_and_retries(self):
        with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("ok", self.streams)):
            b = self.prepare()
        with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("transient", "secret URL")) as fetch:
            t = NOW + timedelta(days=1)
            stale = self.prepare(self.previous(b), t)
            self.assertEqual(stale["cache"]["status"], "stale")
            self.assertTrue(all(r[2] is None for r in stale["thirds"]))
            self.assertEqual(stale["status"], "unknown")
            self.assertNotIn("secret", json.dumps(stale))
            self.assertNotIn("actual", stale["steps"][0])
            self.prepare(self.previous(stale), t + timedelta(minutes=59))
            self.assertEqual(fetch.call_count, 1)
            next_try = self.prepare(self.previous(stale), t + timedelta(hours=1))
            self.assertEqual(next_try["cache"]["next_refresh_at"], (t + timedelta(hours=7)).isoformat())

    def test_ambiguous_pair_and_deleted_plan(self):
        with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("ok", self.streams)):
            self.assertIn("ambiguous_pairing", self.prepare(events=[self.event, self.event])["issues"])
            b = self.prepare()
            self.event["workout_doc"] = None
            revised = self.prepare(self.previous(b))
            self.assertNotIn("steps", revised)
            self.assertEqual(revised["status"], "unknown")

    def test_max_three_logical_fetches_and_cache_hit(self):
        self.act.pop("icu_intervals")
        self.event["workout_doc"]["steps"] = []
        with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("ok", self.streams)) as stream, \
                mock.patch.object(self.sync, "_fetch_activity_intervals", return_value=("no_data", [])) as detail, \
                mock.patch.object(self.sync, "_intervals_get", return_value=self.event) as event:
            b = self.prepare(events=[])
            self.assertEqual((stream.call_count, detail.call_count, event.call_count), (1, 1, 1))
            self.prepare(self.previous(b), events=[])
            self.assertEqual((stream.call_count, detail.call_count, event.call_count), (1, 1, 1))
            event.assert_called_with("events/42", {"resolve": "true"})

    def test_retry_after_and_algorithm_version(self):
        def fail(*args):
            self.sync._last_retry_after_secs = 7200
            return "transient", "http_429"
        with mock.patch.object(self.sync, "_fetch_activity_streams", side_effect=fail) as fetch:
            b = self.prepare()
            self.assertEqual(b["cache"]["next_refresh_at"], (NOW + timedelta(hours=2)).isoformat())
            b["version"] = 0
            self.prepare(self.previous(b))
            self.assertEqual(fetch.call_count, 2)

    def test_network_guard_fires(self):
        self.sync.intervals_auth = "synthetic"
        with self.assertRaises(NetworkBlocked):
            self.prepare()

    def test_format_integration_preserves_aggregate_and_ascent(self):
        self.sync = Sync("athlete_test", "key_test")
        self.sync._intervals_data = {}
        self.act.update(icu_average_watts=200, icu_weighted_avg_watts=220, decoupling=0,
                        total_elevation_gain=0, distance=10000)
        with mock.patch.object(self.sync, "_build_terrain_for_activity", return_value={}), \
                mock.patch.object(self.sync, "_build_weather_for_activity", return_value={}), \
                mock.patch.object(self.sync, "_build_power_curve_for_activity", return_value={}), \
                mock.patch.object(self.sync, "_get_activity_messages", return_value=("ok", [])):
            b = self.build()
            self.sync._intervals_data = {"activities": [{"activity_id": self.act["id"], "session_structure": b}]}
            row = self.sync._format_activities([self.act])[0]
            self.assertEqual((row["avg_power"], row["normalized_power"], row["decoupling"]), (200, 220, 0))
            self.assertEqual(row["display"]["elevation"], {"value": 0, "unit": "m"})
            self.assertFalse(row["has_dfa"])
            self.assertEqual(row["interval_data"]["plan_match"], self.sync._structure_summary(b))
            self.assertTrue(row["has_structure"])
            self.assertNotIn("session_structure", row)
            for kind in ("Walk", "Run", "VirtualRide", "Ride"):
                self.act.update(type=kind, total_elevation_gain=100)
                row = self.sync._format_activities([self.act], athlete_units={"distance": "imperial"})[0]
                self.assertEqual(row["elevation_m"], 100)
                self.assertEqual(row["display"]["elevation"], {"value": 328, "unit": "ft"})
                self.assertEqual(row["display"]["distance"], {"value": 6.21, "unit": "mi"})
            self.act["total_elevation_gain"] = None
            self.assertIsNone(self.sync._format_activities([self.act])[0]["display"]["elevation"])


class Placement(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.act, self.event, self.streams = inputs()
        self.sync = self.fresh_sync()
        for method in ("_build_terrain_for_activity", "_build_weather_for_activity"):
            patcher = mock.patch.object(Sync, method, return_value={})
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(Sync, "_get_activity_messages", return_value=("ok", []))
        patcher.start()
        self.addCleanup(patcher.stop)

    def fresh_sync(self):
        sync = Sync("athlete_test", "key_test")
        sync.data_dir = Path(self.folder.name)
        sync._cached_script_hash = "synthetic-hash"
        sync._intervals_data = {"activities": [], "fetch_state": {}, "script_hash": sync.script_hash}
        return sync

    def capture(self):
        with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("ok", self.streams)):
            self.sync._prepare_session_structures([self.act], [self.event], {}, now=NOW)
        self.sync._intervals_data["fetch_state"] = {self.act["id"]: {
            "date": "2026-01-01", "intervals": {"status": "ok"}, "streams": {"status": "tombstone"}}}
        row = self.sync._format_activities([self.act])[0]
        self.persist(row)
        return row

    def persist(self, row):
        (self.sync.data_dir / "intervals.json").write_text(json.dumps(self.sync._intervals_data))
        (self.sync.data_dir / "latest.json").write_text(json.dumps({"recent_activities": [row]}))

    def cycle(self, at):
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return at.astimezone(tz) if tz else at.astimezone().replace(tzinfo=None)
        previous = self.sync._load_previous_latest()
        with mock.patch.object(mod, "datetime", Clock):
            ids = self.sync._generate_intervals([self.act], {self.act["id"]}, [self.event])
            self.sync._prepare_session_structures([self.act], [self.event], previous, now=at)
            row = self.sync._format_activities([self.act], ids, previous_latest_lookup=previous)[0]
        self.persist(row)
        return row

    def test_committed_summary_survives_detail_expiry_through_day_28(self):
        first = self.capture()
        with mock.patch.object(Sync, "_fetch_activity_streams", side_effect=AssertionError("expired refetch")), \
                mock.patch.object(Sync, "_fetch_activity_intervals", side_effect=AssertionError("expired detail")), \
                mock.patch.object(Sync, "_intervals_get", side_effect=AssertionError("expired event")):
            for day in range(15, 29):
                self.sync = self.fresh_sync()  # Only committed JSON survives each run.
                row = self.cycle(datetime(2026, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=day))
                self.assertEqual(row["interval_data"]["plan_match"]["status"], first["interval_data"]["plan_match"]["status"])
                self.assertEqual(row["interval_data"]["plan_match"]["steps"], first["interval_data"]["plan_match"]["steps"])
                self.assertTrue(row["interval_data"]["plan_match"]["assessment_retained"])
                self.assertFalse(row["has_structure"])
                self.assertFalse(row["has_intervals"])
                self.assertFalse(row["has_dfa"])
                self.assertEqual(self.sync._intervals_data["activities"], [])
                self.assertEqual(self.sync._intervals_data["fetch_state"], {})
            self.assertEqual(self.sync._format_activities([]), [])

    def test_structure_only_entry_survives_generation_and_cache_hit(self):
        first = self.capture()
        self.sync = self.fresh_sync()
        with mock.patch.object(Sync, "_fetch_activity_streams", side_effect=AssertionError("cache refetch")):
            row = self.cycle(NOW + timedelta(hours=1))
        self.assertEqual(row["interval_data"]["plan_match"], first["interval_data"]["plan_match"])
        self.assertTrue(row["has_structure"])
        self.assertFalse(row["has_intervals"])
        self.assertFalse(row["has_dfa"])
        self.assertNotIn("session_structure", row)

    def test_retention_boundary_refreshes_then_expires_without_refetch(self):
        self.capture()
        with mock.patch.object(Sync, "_fetch_activity_streams", return_value=("ok", self.streams)) as fetch:
            self.assertTrue(self.cycle(datetime(2026, 1, 15, 12, tzinfo=timezone.utc))["has_structure"])
            self.assertEqual(fetch.call_count, 1)
            self.assertFalse(self.cycle(datetime(2026, 1, 16, 12, tzinfo=timezone.utc))["has_structure"])
            self.assertEqual(fetch.call_count, 1)

    def test_structure_only_entry_does_not_suppress_interval_first_fetch(self):
        row = self.capture()
        self.sync._intervals_data["fetch_state"] = {}
        self.persist(row)
        with mock.patch.object(Sync, "_fetch_activity_streams", return_value=("no_data", {})) as streams, \
                mock.patch.object(Sync, "_fetch_activity_intervals", return_value=("no_data", [])) as intervals:
            result = self.cycle(NOW + timedelta(hours=1))
        self.assertEqual((streams.call_count, intervals.call_count), (1, 1))
        self.assertTrue(result["has_structure"])

    def test_existing_interval_dfa_and_fetch_state_remain_independent(self):
        first = self.capture()
        entry = self.sync._intervals_data["activities"][0]
        entry["intervals"] = [{"type": "WORK", "avg_power": 350, "start_secs": 1, "end_secs": 5}]
        entry["dfa"] = {"quality": {"sufficient": False}}
        entry["zone_basis"] = "power"
        before = copy.deepcopy(self.sync._intervals_data)
        self.persist(first)
        row = self.cycle(NOW + timedelta(hours=1))
        after = self.sync._intervals_data
        self.assertEqual(after["activities"], before["activities"])
        self.assertEqual(after["fetch_state"], before["fetch_state"])
        self.assertTrue(all(row[k] for k in ("has_structure", "has_intervals", "has_dfa")))
        self.assertNotIn("dfa_summary", row)

    def test_cold_start_old_paired_activity_is_not_assessed_without_fetch(self):
        with mock.patch.object(Sync, "_fetch_activity_streams", side_effect=AssertionError("old fetch")):
            row = self.cycle(NOW + timedelta(days=20))
        self.assertFalse(row["has_structure"])
        self.assertEqual(row["interval_data"]["plan_match"], {
            "method": "plan_match_v2", "status": "not_assessed",
            "plan": {"event_id": "42", "name": None}, "issues": ["detail_unavailable"]})

    def test_no_plan_is_distinct_and_fallback_only_when_needed(self):
        self.act.pop("paired_event_id")
        self.event = None
        row = self.capture()
        block = self.sync._intervals_data["activities"][0]["session_structure"]
        self.assertEqual(row["interval_data"]["plan_match"], {"method": "plan_match_v2", "status": "no_plan"})
        self.assertTrue(row["has_structure"])
        self.assertEqual(len(block["thirds"]), 3)
        self.assertNotIn("plan", block)
        self.assertNotIn("steps", block)

    def test_dropped_fields_and_default_flags_are_absent(self):
        row = self.capture()
        block = self.sync._intervals_data["activities"][0]["session_structure"]
        self.assertEqual(set(block), {"version", "method", "status", "plan", "steps", "cache", "bout_metrics_version"})
        self.assertEqual(block["bout_metrics_version"], 4)
        self.assertEqual(set(block["plan"]), {"event_id", "updated", "duration_s", "duration_source"})
        for step in block["steps"]:
            self.assertEqual(set(step), {"target_w", "duration_s", "actual", "match"})
            self.assertEqual(step["duration_s"], 100)
        self.assertEqual(set(block["cache"]), {"activity_key", "event_key", "plan_key", "plan_key_version",
                                             "sampled_at", "next_refresh_at"})
        self.assertEqual(row["interval_data"]["plan_match"], {"method": "plan_match_v2", "status": "followed",
            "plan": {"event_id": "42", "updated": "2026-01-01T09:00:00Z", "duration_s": 300,
                     "duration_source": "workout_doc.duration"},
            "steps": [[99, 100, 100, True], [99, 200, 200, True], [99, 300, 300, True]]})
        self.assertLess(len(json.dumps(row["interval_data"]["plan_match"], separators=(",", ":"))), 350)

    def test_missing_event_retains_intent_without_actuals_or_obsolete_issue(self):
        self.capture()
        old = self.sync._intervals_data["activities"][0]["session_structure"]
        old["issues"] = ["plan_changed_since_capture"]
        with mock.patch.object(Sync, "_intervals_get", return_value=None), \
                mock.patch.object(Sync, "_fetch_activity_streams", return_value=("ok", self.streams)):
            block = self.sync._prepare_session_structures([self.act], [], {}, NOW + timedelta(days=1))[self.act["id"]]
        self.assertEqual(block["plan"], old["plan"])
        self.assertEqual(block["status"], "unknown")
        self.assertNotIn("plan_changed_since_capture", block["issues"])
        self.assertEqual([s["duration_s"] for s in block["steps"]], [100, 100, 100])
        self.assertTrue(all("actual" not in s for s in block["steps"]))

    def test_walk_hike_format_drops_current_and_carried_structure(self):
        row = self.capture()
        for kind in ("Walk", "Hike"):
            self.act["type"] = kind
            formatted = self.sync._format_activities([self.act], previous_latest_lookup={self.act["id"]: row})[0]
            self.assertFalse(formatted["has_structure"])
            self.assertEqual(formatted["interval_data"]["plan_match"], {
                "method": "plan_match_v2", "status": "unknown", "issues": ["sport_out_of_scope"]})


class LiveShape(unittest.TestCase):
    setUp = Structure.setUp
    build = Structure.build

    def resolve(self):
        for step in self.event["workout_doc"]["steps"]:
            target = step["power"]["value"]
            step["_power"] = {"value": target + 1, "start": target - 4, "end": target + 4}

    def repeated(self, count=12, lag=3, rest=10):
        sequence = [(60, 120)] + [(30, 280), (rest, 90)] * count + [(60, 110)]
        self.act, self.event, _ = inputs()
        self.event["workout_doc"] = {"duration": sum(d for d, _ in sequence), "steps": [
            {"duration": d, "power": {"value": w, "units": "w"}} for d, w in sequence]}
        values = [0] * lag + [w for d, w in sequence for _ in range(d)] + [0]
        self.streams = {"time": list(range(len(values))), "watts": values}
        self.act["elapsed_time"] = len(values) - 1
        self.resolve()

    def test_resolved_band_uses_prescribed_absolute_target(self):
        self.resolve()
        block = self.build()
        self.assertEqual(block["status"], "followed")
        self.assertEqual([s["target_w"] for s in block["steps"]], [100, 200, 300])

    def test_relative_target_uses_resolved_value_not_band(self):
        self.resolve()
        step = self.event["workout_doc"]["steps"][0]
        step["power"] = {"units": "%ftp", "value": 50}
        step["_power"]["value"] = 100
        self.assertEqual(self.build()["status"], "followed")
        self.assertEqual(self.build()["steps"][0]["target_w"], 100)
        step.pop("_power")
        self.assertEqual(self.build()["status"], "unknown")

    def test_prescribed_ramps_stay_unsupported_with_resolved_band(self):
        for ramp in ({"ramp": True}, {"power": {"units": "w", "value": 100, "start": 80, "end": 120}},
                     {"power": {"units": "%ftp", "start": 40, "end": 70}}):
            self.act, self.event, self.streams = inputs()
            self.resolve()
            self.event["workout_doc"]["steps"][0].update(ramp)
            self.assertEqual(self.build()["status"], "unknown")

    def test_lagged_short_sets_reuse_detector_and_cap_counts_sets(self):
        self.repeated(count=24)
        with mock.patch.object(self.sync, "_try_alternating_block", wraps=self.sync._try_alternating_block) as detector:
            block = self.build()
        self.assertTrue(detector.called)
        self.assertEqual(block["status"], "followed")
        self.assertEqual(block["offset_s"], 3)
        self.assertEqual(len(block["steps"]), 3)
        work = block["steps"][1]
        self.assertEqual(work["repeat"], [24, 30, 10])
        self.assertEqual(work["work_s"], 24 * 29)
        self.assertEqual(work["actual"][2:4], [280, 194.9])
        self.assertEqual(self.sync._structure_summary(block)["steps"][1],
                         [696, 280, 280, True, [24, 30, 10]])

    def test_short_recoveries_not_judged_or_averaged_with_work(self):
        self.repeated(lag=0)
        for n in range(12):
            self.streams["watts"][90 + n * 40:100 + n * 40] = [0] * 10
        block = self.build()
        self.assertEqual(block["status"], "followed")
        self.assertEqual(block["steps"][1]["actual"][2], 280)
        self.assertEqual(len(block["steps"]), 3)

    def test_long_recoveries_still_judged(self):
        self.repeated(count=3, lag=0, rest=60)
        self.streams["watts"][90:150] = [0] * 60
        block = self.build()
        self.assertEqual(block["status"], "partly_followed")
        self.assertEqual(len(block["steps"]), 8)
        self.assertFalse(block["steps"][2]["match"])

    def test_identical_sets_stop_before_long_recovery(self):
        sequence = ([(60, 120)] + [(30, 280), (10, 90)] * 3 + [(30, 280), (60, 90)]
                    + [(30, 280), (10, 90)] * 3 + [(30, 280), (60, 110)])
        self.event["workout_doc"] = {"duration": sum(d for d, _ in sequence), "steps": [
            {"duration": d, "power": {"units": "w", "value": w}} for d, w in sequence]}
        watts = [w for d, w in sequence for _ in range(d)] + [0]
        self.act["elapsed_time"] = len(watts) - 1
        self.streams = {"time": list(range(len(watts))), "watts": watts}
        block = self.build()
        self.assertEqual(block["status"], "followed")
        self.assertEqual(len(block["steps"]), 5)
        self.assertEqual([s.get("repeat") for s in block["steps"]],
                         [None, [4, 30, 10], None, [4, 30, 10], None])
        self.assertEqual([s["actual"][:2] for s in block["steps"]],
                         [[1, 60], [61, 210], [211, 270], [271, 420], [421, 480]])

    def test_nonidentical_or_unsupported_atoms_cannot_disappear_in_set(self):
        self.repeated(count=3, lag=0)
        self.event["workout_doc"]["steps"][3]["power"]["value"] = 281
        self.assertEqual(len(self.build()["steps"]), 8)
        self.event["workout_doc"]["steps"][3]["distance"] = 50
        block = self.build()
        self.assertEqual(block["status"], "unknown")
        self.assertTrue(any(s.get("supported") is False for s in block["steps"]))

    def test_recording_pause_removed_but_nulls_and_coasting_remain(self):
        self.streams["time"] = [t if t <= 40 else t + 70 for t in self.streams["time"]]
        self.act.update(elapsed_time=370, recording_stops=[40])
        block = self.build()
        self.assertEqual(block["status"], "followed")
        self.assertEqual([s["actual"][2] for s in block["steps"]], [100, 200, 300])
        self.streams["watts"][120:130] = [None] * 10
        block = self.build()
        self.assertEqual(block["status"], "partly_followed")
        self.assertIsNone(block["steps"][1]["actual"][2])
        self.assertEqual(block["steps"][0]["actual"][2], 100)
        self.assertEqual(block["steps"][2]["actual"][2], 300)
        self.streams["watts"][120:130] = [0] * 10
        block = self.build()
        self.assertEqual(block["steps"][1]["actual"][6], 100)
        self.assertGreater(block["steps"][1]["actual"][9], 0)

    def test_no_observed_power_is_partial_without_invented_step_numbers(self):
        self.streams["watts"] = [None] * len(self.streams["watts"])
        block = self.build()
        self.assertEqual(block["status"], "partly_followed")
        self.assertTrue(all(s["actual"][2:6] == [None] * 4 and s["match"] is None for s in block["steps"]))

    def test_timestamp_is_reference_and_changed_targets_are_actually_compared(self):
        for updated in (None, "invalid", "2026-02-01T12:00:00Z"):
            self.event["updated"] = updated
            self.assertEqual(self.build()["status"], "followed")
        for step in self.event["workout_doc"]["steps"]:
            step["power"]["value"] *= 2
        self.assertEqual(self.build()["status"], "not_followed")

    def test_offset_tie_smallest_bound_and_explicit_shift_additive(self):
        self.act, self.event, self.streams = inputs(powers=(100,), tail=10)
        self.streams["watts"] = [100] * len(self.streams["watts"])
        self.assertNotIn("offset_s", self.build())
        for lag in (0, 3, 8, 12):
            self.repeated(lag=lag)
            self.assertEqual(self.build().get("offset_s", 0), min(lag, 8))
        self.repeated(lag=8)
        self.act["workout_shift_secs"] = 5
        self.assertEqual(self.build()["offset_s"], 3)

    def test_exclusion_is_exactly_one_second_and_forward_samples_stay(self):
        self.act, self.event, self.streams = inputs(powers=(100,), duration=30)
        self.streams["watts"][0] = 0
        self.streams["watts"][1] = 71
        with mock.patch.object(self.sync, "_structure_offset", return_value=0):
            block = self.build()
        self.assertEqual(block["steps"][0]["actual"][:4], [1, 30, 99, 2.9])
        self.assertEqual(self.sync._structure_summary(block)["steps"][0][0], 29)

    def test_lag_at_recording_end_is_not_extra_prescribed_duration(self):
        self.repeated(lag=3)
        self.streams = {k: v[:-3] for k, v in self.streams.items()}
        self.act["elapsed_time"] -= 3
        block = self.build()
        self.assertEqual(block["status"], "followed")
        self.assertLess(block["steps"][-1]["observed_window_fraction"], 1)
        self.act["elapsed_time"] -= 1
        self.streams = {k: v[:-1] for k, v in self.streams.items()}
        self.assertEqual(self.build()["status"], "followed")

    def test_walk_and_hike_no_fetch_or_stale_fallback_other_sports_keep_it(self):
        for kind in ("Walk", "Hike"):
            for paired in (None, 42):
                self.act.update(type=kind, paired_event_id=paired)
                self.sync._intervals_data = {"activities": [{"activity_id": self.act["id"],
                    "intervals": [{"type": "WORK"}], "dfa": {"quality": {}},
                    "session_structure": {"thirds": [1, 2, 3]}}]}
                with mock.patch.object(self.sync, "_fetch_activity_streams", side_effect=AssertionError("fetch")):
                    self.assertEqual(self.sync._prepare_session_structures([self.act], [self.event], {}, NOW), {})
                self.assertIsNone(self.build())
                entry = self.sync._intervals_data["activities"][0]
                self.assertNotIn("session_structure", entry)
                self.assertIn("intervals", entry)
                self.assertIn("dfa", entry)
        for kind in ("Ride", "VirtualRide", "Run", "NordicSki", "Rowing"):
            self.act.update(type=kind, paired_event_id=None)
            self.event = None
            block = self.build()
            self.assertEqual(block["status"], "no_plan")
            self.assertEqual(len(block["thirds"]), 3)


if __name__ == "__main__":
    unittest.main()
