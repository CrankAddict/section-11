"""Single-main-sport report sources and activity zone provenance, offline."""
import contextlib
import copy
import io
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from unittest import mock

from _harness import (REPO_ROOT, SYNC_PATH, install_verb_guard,
                      load_module_by_path, restore_verb_guard)
from test_sleep_context import Clock, D, wellness_rows

mod = load_module_by_path("s11_report_intensity", SYNC_PATH)
originals = None


def setUpModule():
    global originals
    originals = install_verb_guard(mod.requests)


def tearDownModule():
    restore_verb_guard(mod.requests, originals)


def activity(aid, sport="Ride", date=D, tss=80, **changes):
    row = {"id": aid, "name": "Synthetic session", "type": sport,
           "start_date_local": date + "T10:00:00", "moving_time": 3600,
           "icu_training_load": tss, "trainer": False, "icu_ftp": 250,
           "icu_zone_times": [{"id": "Z2", "secs": 2880},
                              {"id": "Z3", "secs": 360}, {"id": "Z4", "secs": 360}]}
    row.update(changes)
    return row


def collect(module, directory, activities, preference=None):
    """Real collector/calculators with bounded synthetic transport and no network."""
    sync = module.IntervalsSync("synthetic", "synthetic", week_start_day=0)
    sync.data_dir = Path(directory)
    sync._intervals_data = {}
    sync.zone_preference = preference or {}
    calls = []
    wellness = wellness_rows()

    def get(endpoint, params=None):
        calls.append((endpoint, copy.deepcopy(params)))
        if endpoint == "":
            return {"timezone": "Europe/Copenhagen", "icu_weight": 70,
                    "sportSettings": [{"types": ["Ride"], "ftp": 290,
                                       "indoor_ftp": 270, "lthr": 165}]}
        if endpoint == "activities":
            return copy.deepcopy([a for a in activities
                if params["oldest"] <= a["start_date_local"][:10] <= params["newest"]])
        if endpoint == "wellness":
            return copy.deepcopy([w for w in wellness if params["oldest"] <= w["id"] <= params["newest"]])
        if endpoint.startswith("wellness/"):
            return copy.deepcopy(wellness[-1])
        if endpoint == "events":
            return []
        if endpoint in ("power-curves", "hr-curves"):
            return {}
        raise AssertionError("unexpected endpoint: " + endpoint)

    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(module, "datetime", Clock))
        stack.enter_context(mock.patch.object(sync, "_intervals_get", side_effect=get))
        for method, value in (("_generate_saved_workouts", None), ("_generate_terrain", set()),
                ("_generate_route_weather", {}), ("_generate_intervals", set()),
                ("_prepare_session_structures", {}), ("_build_terrain_for_activity", {}),
                ("_build_weather_for_activity", {}), ("_get_activity_messages", ("ok", [])),
                ("_fetch_activity_power_curve", ("ok", {"1": 600, "5": 550})),
                ("_build_decoupling_for_activity", {})):
            stack.enter_context(mock.patch.object(sync, method, return_value=value))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        output = sync.collect_training_data()
    return output, calls, sync


class ReportIntensity(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.sync = mod.IntervalsSync("synthetic", "synthetic")
        self.clock = mock.patch.object(mod, "datetime", Clock)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_cyclist_cross_training_excluded_and_own_activity_ftp_retained(self):
        acts = [activity("indoor", trainer=True, icu_ftp=260),
                activity("outdoor", date="2026-06-14", icu_ftp=280),
                activity("walk", "Walk", tss=15, trainer=None, icu_zone_times=[],
                         icu_hr_zone_times=[3600, 0, 0, 0, 0]),
                activity("ski", "VirtualSki", tss=25, trainer=True,
                         icu_zone_times=[], icu_hr_zone_times=[3600, 0, 0, 0, 0])]
        output, _, _ = collect(mod, self.folder, acts)
        dm = output["derived_metrics"]
        self.assertEqual(dm["primary_sport"], "cycling")
        primary = dm["seiler_tid_7d_primary"]
        self.assertEqual((primary["sport"], primary["zone_basis"], primary["z1_pct"]),
                         ("cycling", "power", 80))
        self.assertEqual(dm["seiler_tid_7d"]["z1_pct"], 90)
        self.assertEqual(dm["seiler_tid_7d"]["zone_basis"], "mixed")
        self.assertEqual(output["rolling_7d_chunks"][0]["seiler_tid_primary"], primary)
        rows = {a["id"]: a for a in output["recent_activities"]}
        self.assertEqual(rows["indoor"]["zone_reference"],
                         {"basis": "power", "ftp_w": 260, "environment": "indoor"})
        self.assertEqual(rows["outdoor"]["zone_reference"],
                         {"basis": "power", "ftp_w": 280, "environment": "outdoor"})
        self.assertEqual(rows["walk"]["zone_reference"]["basis"], "hr")
        self.assertEqual(rows["walk"]["zone_reference"]["environment"], "outdoor")
        self.assertEqual(rows["ski"]["zone_reference"]["environment"], "indoor")
        self.assertIsNone(rows["walk"]["indoor"])
        self.assertIsNone(rows["ski"]["indoor"])
        self.assertEqual(dm["capability"]["tid_comparison_primary"]["sport"], "cycling")

    def test_runner_with_cycling_cross_training_uses_running_hr(self):
        acts = [activity("run", "Run", tss=120, icu_hr_zone_times=[0, 2700, 540, 360, 0]),
                activity("bike", "Ride", tss=40)]
        output, _, _ = collect(mod, self.folder, acts, {"run": "hr"})
        dm = output["derived_metrics"]
        self.assertEqual(dm["primary_sport"], "run")
        primary = dm["seiler_tid_7d_primary"]
        self.assertEqual((primary["sport"], primary["zone_basis"], primary["z1_pct"]),
                         ("run", "hr", 75))
        row = next(a for a in output["recent_activities"] if a["id"] == "run")
        self.assertIsNone(row["zone_reference"]["ftp_w"])
        self.assertEqual(row["zone_reference"]["basis"], "hr")
        self.assertEqual(dm["seiler_tid_28d_primary"], primary)

    def test_current_primary_anchors_older_chunks_weekly_and_monthly_periods(self):
        acts = [activity("current", "Run", tss=120, icu_zone_times=[],
                         icu_hr_zone_times=[2700, 0, 540, 360, 0]),
                activity("old-bike", date="2026-06-07", tss=300),
                activity("old-run", "Run", date="2026-06-07", tss=40,
                         icu_zone_times=[], icu_hr_zone_times=[2700, 0, 540, 360, 0]),
                activity("prior-month", "Run", date="2026-05-31", tss=30,
                         icu_zone_times=[], icu_hr_zone_times=[2700, 0, 540, 360, 0])]
        primary = self.sync._report_primary_sport(acts)
        self.assertEqual(primary, "run")
        chunks = self.sync._rolling_7d_chunks(acts, [], [], D, 50, primary)
        self.assertTrue(all(c["seiler_tid_primary"]["sport"] == primary for c in chunks))
        self.assertEqual(chunks[1]["seiler_tid_primary"]["z1_pct"], 75)
        by_date = defaultdict(list)
        for act in acts:
            by_date[act["start_date_local"][:10]].append(act)
        weeks = self.sync._build_weekly_tier(by_date, {}, days=28)
        old = next(w for w in weeks if w["week_start"] == "2026-06-01")
        self.assertEqual(old["primary_sport"], "cycling")
        self.assertEqual(old["seiler_tid_primary"]["sport"], "run")
        self.assertEqual(old["seiler_tid_primary"]["z1_pct"], 75)
        months = self.sync._build_monthly_tier(by_date, {}, days=60)
        may = next(m for m in months if m["month"] == "2026-05")
        self.assertEqual(may["seiler_tid_primary"]["sport"], "run")
        self.assertEqual(may["seiler_tid_primary"]["z1_seconds"], 2700)

    def test_highest_tss_rule_can_flip_and_ties_keep_existing_order(self):
        bike, run = activity("bike"), activity("run", "Run", tss=79)
        self.assertEqual(self.sync._report_primary_sport([bike, run]), "cycling")
        run["icu_training_load"] = 81
        self.assertEqual(self.sync._report_primary_sport([bike, run]), "run")
        run["icu_training_load"] = 80
        self.assertEqual(self.sync._report_primary_sport([bike, run]), "cycling")
        self.assertEqual(self.sync._report_primary_sport([run, bike]), "run")

    def test_no_current_primary_or_no_matching_zone_data_stays_unavailable(self):
        self.assertIsNone(self.sync._report_primary_sport([activity("old", date="2026-05-01")]))
        self.assertIsNone(self.sync._report_seiler_tid([activity("bike")], None))
        empty = self.sync._report_seiler_tid([activity("bike")], "run")
        self.assertEqual(empty["sport"], "run")
        self.assertIsNone(empty["z1_pct"])
        self.assertIsNone(empty["classification"])
        self.assertIsNone(empty["zone_basis"])
        output, _, _ = collect(mod, self.folder, [])
        self.assertTrue(all(c["seiler_tid_primary"] is None for c in output["rolling_7d_chunks"]))
        self.assertIsNone(output["derived_metrics"]["capability"]["tid_comparison_primary"]["drift"])

    def test_reference_missing_invalid_and_name_never_supplies_environment(self):
        for ftp in (None, 0, -1, True, "260", float("nan"), float("inf")):
            row = self.sync._zone_reference(activity("a", icu_ftp=ftp))
            self.assertIsNone(row["ftp_w"])
        for changes, env in (({"trainer": None, "name": "Indoor trainer"}, "outdoor"),
                             ({"trainer": "false"}, "unknown"),
                             ({"indoor": True, "trainer": False}, "indoor"),
                             ({"indoor": False, "trainer": None}, "outdoor")):
            self.assertEqual(self.sync._zone_reference(activity("a", **changes))["environment"], env)
        row = self.sync._zone_reference(activity("a", "VirtualRun", trainer=None,
                                       icu_zone_times=[], icu_pace_zone_times=[3600]))
        self.assertEqual(row, {"basis": None, "ftp_w": None, "environment": "indoor"})

    def test_environment_uses_indoor_markings_and_defaults_unmarked_outdoor(self):
        cases = [("Walk", {"trainer": None}, "outdoor"),
                 ("VirtualSki", {"trainer": True}, "indoor"),
                 ("VirtualRide", {"trainer": None}, "indoor"),
                 ("VirtualRun", {"trainer": False}, "indoor"),
                 ("VirtualRow", {"trainer": "malformed"}, "indoor"),
                 ("Ride", {"trainer": False}, "outdoor"),
                 ("Ride", {"trainer": "false"}, "unknown"),
                 ("Walk", {"trainer": 0}, "unknown"),
                 ("Walk", {"trainer": 1}, "unknown"),
                 ("Walk", {"trainer": None, "indoor": "false"}, "unknown"),
                 ("Walk", {"trainer": "malformed", "indoor": True}, "indoor"),
                 ("Walk", {"trainer": True, "indoor": "malformed"}, "indoor"),
                 ("Ride", {"trainer": None, "name": "Virtual indoor ride"}, "outdoor"),
                 ("VirtualRide", {"trainer": False, "name": "Outdoor ride"}, "indoor")]
        for sport, changes, expected in cases:
            with self.subTest(sport=sport, changes=changes):
                act = activity("synthetic", sport, **changes)
                before = copy.deepcopy(act)
                self.assertEqual(self.sync._zone_reference(act),
                                 {"basis": "power", "ftp_w": 250, "environment": expected})
                self.assertEqual(act, before)
        for sport, expected in (("Walk", "outdoor"), ("Ride", "outdoor"),
                                ("VirtualSki", "indoor")):
            with self.subTest(absent_flags=sport):
                act = activity("synthetic", sport)
                act.pop("trainer")
                self.assertEqual(self.sync._zone_reference(act)["environment"], expected)

    def test_reference_uses_preference_and_fallback_without_changing_zones(self):
        act = activity("a", "Run", icu_hr_zone_times=[3600, 0, 0, 0, 0])
        before = copy.deepcopy(act)
        self.sync.zone_preference = {"run": "hr"}
        self.assertEqual(self.sync._zone_reference(act)["basis"], "hr")
        self.assertEqual(act, before)
        act["icu_hr_zone_times"] = []
        self.assertEqual(self.sync._zone_reference(act)["basis"], "power")
        act["icu_zone_times"] = []
        self.assertIsNone(self.sync._zone_reference(act)["basis"])

    def test_guidance_routes_reports_to_additive_sources_and_preserves_provenance(self):
        reports = REPO_ROOT / "examples/reports"
        for name in ("PRE_WORKOUT", "POST_WORKOUT", "7_DAY", "28_DAY", "SEASON"):
            text = (reports / (name + "_REPORT_TEMPLATE.md")).read_text()
            self.assertIn("#report-intensity-source", text)
            self.assertIn("report_intensity", text)
            self.assertIn("covered", text)
            self.assertIn("unavailable", text)
            self.assertNotIn("seiler_tid_7d.z1_pct", text)
        weekly = (reports / "7_DAY_REPORT_TEMPLATE.md").read_text()
        self.assertIn("zone_reference", weekly)
        self.assertIn("whether or not provenance is present", weekly)
        self.assertNotIn("only when basis provenance is unavailable", weekly)
        output, _, sync = collect(mod, self.folder, [activity("a")])
        for guidance in (output["READ_THIS_FIRST"], mod.DataOverview.build(sync, output)):
            note = guidance["report_intensity_note"]
            for phrase in ("report_intensity_7d", "report_intensity_28d", "zone_reference",
                           "sport", "zone_basis", "aggregate context only"):
                self.assertIn(phrase, note)


if __name__ == "__main__":
    unittest.main()
