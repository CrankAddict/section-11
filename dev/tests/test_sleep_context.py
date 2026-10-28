"""Raw wellness shapes and offline sleep-context/old-consumer boundaries."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from _harness import (SYNC_PATH, install_verb_guard, load_module_by_path,
                      restore_verb_guard)

mod = load_module_by_path("s11_sleep_context", SYNC_PATH)
originals = None
D = "2026-06-15"


def setUpModule():
    global originals
    originals = install_verb_guard(mod.requests)


def tearDownModule():
    restore_verb_guard(mod.requests, originals)


class Clock(datetime):
    instant = datetime(2026, 6, 15, 12, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)


def wellness_rows(day=D, reference=28800, recent=None):
    end = datetime.strptime(day, "%Y-%m-%d")
    values = [reference] * 28 + (recent if recent is not None else [28800] * 4 + [27600] * 3)
    return [{"id": (end - timedelta(days=34-i)).strftime("%Y-%m-%d"),
             "sleepSecs": seconds, "hrv": 60 + i % 5, "restingHR": 48 + i % 3,
             "weight": 70 + i % 4 / 10, "ctl": 50, "atl": 55,
             "sleepQuality": 2, "sleepScore": 85, "rampRate": 1}
            for i, seconds in enumerate(values)]


def collect(module, directory, rows=None, day=D, fail=False, days_back=7, timezone_name="Europe/Copenhagen"):
    """Run real collection/calculators, replacing only remote/ancillary I/O.

    Reused by the job-local frozen-baseline comparison. The read fake honors
    exact date bounds, so widening without slicing cannot accidentally pass.
    """
    rows = wellness_rows(day) if rows is None else rows
    end = datetime.strptime(day, "%Y-%m-%d")
    clock = type("ScenarioClock", (Clock,), {
        "instant": end.replace(hour=12, tzinfo=timezone.utc)})
    sync = module.IntervalsSync("synthetic", "synthetic", week_start_day=0)
    sync.data_dir = Path(directory)
    sync._intervals_data = {}
    calls = []
    acts = [{"id": "i" + str(i), "start_date_local": row["id"] + "T10:00:00",
             "name": "Synthetic endurance", "type": "Ride", "trainer": False,
             "moving_time": 5400, "elapsed_time": 5500, "distance": 45000,
             "icu_training_load": 50 + i, "icu_average_watts": 180,
             "icu_weighted_avg_watts": 185, "average_heartrate": 130,
             "icu_variability_index": 1.03, "decoupling": 2, "icu_joules": 972000,
             "icu_ftp": 250, "icu_weight": 70, "total_elevation_gain": 400}
            for i, row in enumerate(rows) if i % 3 == 0]

    def get(endpoint, params=None):
        calls.append((endpoint, copy.deepcopy(params)))
        if endpoint == "":
            return {"timezone": timezone_name, "icu_weight": 70,
                    "sportSettings": [{"types": ["Ride"], "ftp": 250, "lthr": 165}]}
        if endpoint == "wellness":
            if fail and params["oldest"] <= (end - timedelta(days=27)).strftime("%Y-%m-%d"):
                raise module.requests.exceptions.HTTPError("synthetic extended wellness failure")
            return copy.deepcopy([r for r in rows if params["oldest"] <= r["id"] <= params["newest"]])
        if endpoint.startswith("wellness/"):
            return copy.deepcopy(next((r for r in rows if r["id"] == day), {}))
        if endpoint == "activities":
            return copy.deepcopy([a for a in acts if params["oldest"] <= a["start_date_local"][:10] <= params["newest"]])
        if endpoint == "events":
            return []
        if endpoint in ("power-curves", "hr-curves"):
            return {}
        raise AssertionError("unexpected endpoint: " + endpoint)

    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(module, "datetime", clock))
        stack.enter_context(mock.patch.object(sync, "_intervals_get", side_effect=get))
        for method, value in (("_generate_saved_workouts", None), ("_generate_terrain", set()),
                ("_generate_route_weather", {}), ("_generate_intervals", set()),
                ("_prepare_session_structures", {}), ("_build_terrain_for_activity", {}),
                ("_build_weather_for_activity", {}), ("_get_activity_messages", ("ok", [])),
                ("_fetch_activity_power_curve", ("ok", {"1": 600, "5": 550})),
                ("_build_decoupling_for_activity", {})):
            stack.enter_context(mock.patch.object(sync, method, return_value=value))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        output = sync.collect_training_data(days_back=days_back)
    return output, calls, sync


class SleepContext(unittest.TestCase):
    def setUp(self):
        self.sync = mod.IntervalsSync("synthetic", "synthetic")

    def build(self, rows=None, day=D, zone="Europe/Copenhagen", stamp=None):
        return self.sync._build_sleep_context(wellness_rows(day) if rows is None else rows,
            day, zone, stamp or datetime.fromisoformat(day + "T12:00:00+00:00"))

    def test_exact_hour_threshold_and_one_second_below(self):
        result = self.build()
        self.assertTrue(result["repeat_context"])
        self.assertEqual(result["recent"]["latest_three_difference_sum_seconds"], 3600)
        rows = wellness_rows()
        rows[-1]["sleepSecs"] += 1
        self.assertFalse(self.build(rows)["repeat_context"])

    def test_each_night_must_be_strictly_below_even_with_large_total(self):
        for last in (28800, 28801):
            rows = wellness_rows(recent=[28800] * 4 + [20000, 20000, last])
            result = self.build(rows)
            self.assertFalse(result["repeat_context"])
            self.assertEqual(result["recent"]["consecutive_observed_below_reference"], 0)

    def test_two_nights_and_nonadjacent_lows_do_not_fire(self):
        for recent in ([28800] * 5 + [20000, 20000], [20000] * 5 + [28800, 20000]):
            self.assertFalse(self.build(wellness_rows(recent=recent))["repeat_context"])

    def test_no_seven_hour_floor_or_per_night_percentage(self):
        self.assertTrue(self.build(wellness_rows(reference=32400, recent=[32400]*4 + [31200]*3))["repeat_context"])
        self.assertFalse(self.build(wellness_rows(reference=21600, recent=[23400]*7))["repeat_context"])
        rows = wellness_rows(recent=[28800]*4 + [28799, 28799, 25202])
        self.assertTrue(self.build(rows)["repeat_context"])

    def test_raw_seconds_not_rounded_hours(self):
        rows = wellness_rows(recent=[28800]*4 + [28799, 27000, 27000])
        result = self.build(rows)
        self.assertTrue(result["repeat_context"])
        self.assertEqual(result["recent"]["nights"][-3]["sleep_hours"], 8)
        self.assertTrue(result["recent"]["nights"][-3]["below_reference"])
        self.assertEqual(result["recent"]["nights"][-3]["sleep_formatted"], "7h59m")

    def test_disjoint_reference_and_median(self):
        rows = wellness_rows(recent=[1000]*7)
        rows[0]["sleepSecs"] = 86400
        result = self.build(rows)
        self.assertEqual(result["reference"]["median_seconds"], 28800)
        self.assertEqual(result["reference"]["end"], "2026-06-08")
        self.assertEqual(result["recent"]["start"], "2026-06-09")

    def test_even_reference_median_retains_half_second(self):
        rows = wellness_rows()
        for row in rows[:14]:
            row["sleepSecs"] = 28801
        self.assertEqual(self.build(rows)["reference"]["median_seconds"], 28800.5)

    def test_missing_reference_withholds_comparison(self):
        rows = wellness_rows()
        result = self.build(rows[1:])
        self.assertIsNone(result["repeat_context"])
        self.assertEqual(result["reason"], "incomplete_reference")
        self.assertEqual(result["reference"]["missing_dates"], [rows[0]["id"]])
        self.assertIsNone(result["reference"]["median_seconds"])
        self.assertTrue(all(n["below_reference"] is None for n in result["recent"]["nights"]))

    def test_each_missing_latest_three_is_unassessed_not_false(self):
        for index in (-1, -2, -3):
            rows = wellness_rows()
            del rows[index]
            result = self.build(rows)
            self.assertEqual(result["reason"], "incomplete_latest_three")
            self.assertIsNone(result["repeat_context"])
            self.assertIsNone(result["recent"]["consecutive_observed_below_reference"])
            self.assertEqual(result["recent"]["run_dates"], [])

    def test_older_missing_recent_breaks_run_but_preserves_latest_three(self):
        rows = wellness_rows(recent=[27600]*7)
        missing = rows.pop(-4)["id"]
        result = self.build(rows)
        self.assertTrue(result["repeat_context"])
        self.assertEqual(result["status"], "partial_recent")
        self.assertEqual(result["recent"]["run_boundary"], "missing")
        self.assertEqual(result["recent"]["consecutive_observed_below_reference"], 3)
        self.assertIsNone(result["recent"]["mean_seconds"])
        self.assertEqual(result["recent"]["missing_dates"], [missing])
        self.assertEqual(len(result["recent"]["nights"]), 7)

    def test_partial_recent_can_be_assessably_false(self):
        rows = wellness_rows(recent=[28800]*7)
        del rows[-5]
        result = self.build(rows)
        self.assertEqual(result["status"], "partial_recent")
        self.assertIs(result["repeat_context"], False)

    def test_run_is_capped_at_seven(self):
        result = self.build(wellness_rows(recent=[27000]*7))
        self.assertEqual(result["recent"]["consecutive_observed_below_reference"], 7)
        self.assertEqual(result["recent"]["run_formatted"], "at least 7")
        self.assertEqual(result["recent"]["run_boundary"], "window_start")
        self.assertEqual(result["recent"]["run_dates"], [n["date"] for n in result["recent"]["nights"]])

    def test_invalid_values_and_upper_valid_boundary(self):
        for value in (None, 0, -1, 86401, True, "25000", float("nan"), float("inf"), -float("inf"), 10**400):
            rows = wellness_rows()
            rows[-1]["sleepSecs"] = value
            with self.subTest(value=repr(value)):
                result = self.build(rows)
                self.assertIsNone(result["repeat_context"])
                self.assertEqual(result["recent"]["nights"][-1]["status"], "invalid")
                self.assertIsNone(result["recent"]["nights"][-1]["sleep_seconds"])
                json.dumps(result, allow_nan=False)
        rows[-1]["sleepSecs"] = 86400
        self.assertEqual(self.build(rows)["recent"]["nights"][-1]["status"], "observed")

    def test_duplicate_dates_rejected_in_all_windows(self):
        for index in (0, -1, -4):
            rows = wellness_rows()
            rows.append(copy.deepcopy(rows[index]))
            result = self.build(rows)
            part = result["reference"] if index == 0 else result["recent"]
            self.assertEqual(part["invalid_dates"][0]["reason"], "ambiguous_duplicate")
            if index != -4:
                self.assertIsNone(result["repeat_context"])
            else:
                self.assertTrue(result["repeat_context"])
                self.assertEqual(result["status"], "partial_recent")

    def test_invalid_older_recent_boundary(self):
        rows = wellness_rows(recent=[27000]*7)
        rows[-4]["sleepSecs"] = 0
        result = self.build(rows)
        self.assertTrue(result["repeat_context"])
        self.assertEqual(result["recent"]["run_boundary"], "invalid")

    def test_source_order_does_not_change_context(self):
        rows = wellness_rows()
        self.assertEqual(self.build(rows), self.build(list(reversed(rows))))

    def test_future_and_outside_dates_never_enter_windows(self):
        rows = wellness_rows()
        expected = self.build(rows)
        rows += [{"id": "2026-06-16", "sleepSecs": 1}, {"id": "2020-01-01", "sleepSecs": 86400}]
        self.assertEqual(self.build(rows), expected)

    def test_malformed_rows_or_date_keys_withhold_assessment(self):
        for extra in (None, {}, {"id": "2026-6-15"}, {"id": "2026-06-15T00:00:00"}, {"id": "2026-02-30"}):
            result = self.build(wellness_rows() + [extra])
            self.assertIsNone(result["repeat_context"])
            self.assertEqual(result["reason"], "invalid_input")

    def test_empty_and_unavailable_source_are_not_normal(self):
        self.assertIsNone(self.build([])["repeat_context"])
        for raw, reason in ((None, "source_unavailable"), ({}, "invalid_input")):
            result = self.sync._build_sleep_context(raw, D, "UTC", Clock.instant)
            self.assertIsNone(result["repeat_context"])
            self.assertEqual(result["reason"], reason)

    def test_timezone_missing_invalid_and_date_mismatch(self):
        for zone in (None, "", "Not/AZone", False):
            result = self.build(zone=zone)
            self.assertEqual(result["reason"], "unknown_timezone")
            self.assertIsNone(result["repeat_context"])
        result = self.build(stamp=datetime(2026, 6, 15, 23, tzinfo=timezone.utc))
        self.assertEqual(result["reason"], "current_date_mismatch")
        self.assertIsNone(result["repeat_context"])

    def test_stale_and_naive_source_timestamps_withhold_current_comparison(self):
        for stamp, reason in ((datetime(2026, 6, 14, 12, tzinfo=timezone.utc), "current_date_mismatch"),
                              (datetime(2026, 6, 15, 12), "unknown_date_alignment")):
            result = self.build(stamp=stamp)
            self.assertEqual(result["reason"], reason)
            self.assertIsNone(result["repeat_context"])

    def test_year_leap_and_dst_calendar_boundaries(self):
        for day in ("2027-01-01", "2028-03-01", "2026-03-29", "2026-10-25"):
            result = self.build(day=day)
            self.assertTrue(result["repeat_context"])
            self.assertEqual(result["reference"]["observed_nights"], 28)
            self.assertEqual(result["recent"]["observed_nights"], 7)
            self.assertEqual(result["recent"]["end"], day)

    def test_quality_score_and_fragmentation_fields_are_ignored(self):
        rows = wellness_rows()
        expected = self.build(rows)
        for row in rows:
            row.update(sleepQuality=4, sleepScore=1, avgSleepingHR=99,
                       sleep_fragmentation_reports=[{"fragmented": True}], awakeTime=9999)
        self.assertEqual(self.build(rows), expected)
        self.assertNotIn("fragmentation", json.dumps(expected))
        self.assertIs(expected["readiness_eligible"], False)
        self.assertEqual(expected["confidence"], "low")


class Producer(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)

    def test_one_widened_read_and_exact_28_date_baselines(self):
        rows = wellness_rows()
        for row in rows[:7]:
            row.update(hrv=9999, restingHR=9999, weight=199)
        output, calls, _ = collect(mod, self.directory, rows)
        wellness = [p for e, p in calls if e == "wellness"]
        self.assertEqual(wellness, [{"oldest": "2026-05-12", "newest": D}])
        self.assertEqual(output["wellness_28d"]["sleep_hours"]["days"], 28)
        self.assertLess(output["wellness_28d"]["weight_kg"]["avg"], 71)
        self.assertIs(output["sleep_context"]["repeat_context"], True)
        self.assertIn("sleep_context_note", output["READ_THIS_FIRST"])
        self.assertNotIn("sleep_context", output["readiness_decision"]["signals"])

    def test_only_new_context_changes_when_exclusive_reference_dates_change(self):
        rows = wellness_rows()
        a, _, _ = collect(mod, self.directory, rows)
        for row in rows[:7]:
            row.update(hrv=9999, restingHR=9999, weight=199, sleepSecs=86400)
        b, _, _ = collect(mod, self.directory, rows)
        a.pop("sleep_context")
        b.pop("sleep_context")
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_failed_extended_fetch_retains_files_and_original_timestamp(self):
        out, _, sync = collect(mod, self.directory)
        with contextlib.redirect_stdout(io.StringIO()):
            sync.save_to_file(out, str(self.directory / "latest.json"))
        before = {p.name: p.read_bytes() for p in self.directory.iterdir() if p.is_file()}
        with self.assertRaisesRegex(mod.requests.exceptions.HTTPError, "synthetic extended wellness failure"):
            collect(mod, self.directory, fail=True)
        after = {p.name: p.read_bytes() for p in self.directory.iterdir() if p.is_file()}
        self.assertEqual(before, after)

    def test_late_correction_recomputed_without_history_or_prior_context(self):
        rows = wellness_rows()
        first, _, sync = collect(mod, self.directory, rows)
        with contextlib.redirect_stdout(io.StringIO()):
            sync.save_to_file(first, str(self.directory / "latest.json"))
        rows[-2]["sleepSecs"] = 28800
        corrected, _, _ = collect(mod, self.directory, rows)
        self.assertTrue(first["sleep_context"]["repeat_context"])
        self.assertFalse(corrected["sleep_context"]["repeat_context"])
        self.assertFalse((self.directory / "history.json").exists())

    def test_old_missing_timezone_does_not_change_readiness(self):
        known, _, _ = collect(mod, self.directory)
        unknown, _, _ = collect(mod, self.directory, timezone_name=None)
        self.assertEqual(known["readiness_decision"], unknown["readiness_decision"])
        self.assertIsNone(unknown["sleep_context"]["repeat_context"])

    def test_repeat_toggle_does_not_change_go_p0_or_p1(self):
        for change, priority in (({}, 3), ({"hrv": 25}, 0),
                                 ({"ctl": 30, "atl": 70, "hrv": 50}, 1)):
            rows = wellness_rows()
            rows[-1].update(change)
            firing, _, _ = collect(mod, self.directory, rows)
            rows[-3]["sleepSecs"] = 28800
            quiet, _, _ = collect(mod, self.directory, rows)
            with self.subTest(priority=priority):
                self.assertTrue(firing["sleep_context"]["repeat_context"])
                self.assertFalse(quiet["sleep_context"]["repeat_context"])
                self.assertEqual(firing["readiness_decision"]["priority"], priority)
                self.assertEqual(firing["readiness_decision"], quiet["readiness_decision"])
                self.assertEqual(firing["alerts"], quiet["alerts"])

    def test_public_example_matches_synthetic_producer_block(self):
        example = json.loads((SYNC_PATH.parent / "json-examples/latest.example.json").read_text())
        actual, _, _ = collect(mod, self.directory)
        self.assertEqual(example["sleep_context"], actual["sleep_context"])
        self.assertEqual(example["READ_THIS_FIRST"]["sleep_context_note"],
                         actual["READ_THIS_FIRST"]["sleep_context_note"])


if __name__ == "__main__":
    unittest.main()
