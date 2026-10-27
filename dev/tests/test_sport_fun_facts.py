"""Synthetic observed facts, period selection and report display contracts."""
import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from _harness import (REPO_ROOT, SYNC_PATH, install_verb_guard,
                      load_module_by_path, restore_verb_guard)

mod = load_module_by_path("s11_sport_fun_facts", SYNC_PATH)
originals = None


def setUpModule():
    global originals
    originals = install_verb_guard(mod.requests)


def tearDownModule():
    restore_verb_guard(mod.requests, originals)


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 10, 21, 12, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


def activity(aid="s1", kind="VirtualSki", day="2026-10-17", **changes):
    # Listed generic fields retain null keys; aliases/extra flags are absent.
    # Values and sample sizes are invented, not taken from athlete payloads.
    row = {"id": aid, "type": kind, "start_date_local": day + "T10:00:00",
           "name": "Synthetic session", "moving_time": 3600, "elapsed_time": 3700,
           "distance": 12000.0, "total_elevation_gain": None, "max_heartrate": 160,
           "average_heartrate": 130, "trainer": None, "sub_type": None,
           "icu_joules": None, "carbs_used": None, "icu_training_load": 50,
           "average_speed": 3.0, "max_speed": None, "pool_length": None,
           "lengths": None, "icu_zone_times": None,
           "icu_hr_zone_times": [1000, 2000, 500, 100, 0], "pace": None,
           "icu_average_watts": None, "stream_types": ["heartrate"]}
    row.update(changes)
    return row


class SportFacts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sync = mod.IntervalsSync("synthetic", "synthetic", week_start_day=0)
        self.sync.data_dir = Path(tmp.name)
        self.sync._intervals_data = {}
        patch = mock.patch.object(mod, "datetime", Clock)
        patch.start()
        self.addCleanup(patch.stop)

    def selection(self, rows, start="2026-10-15", end="2026-10-21", rescue=False):
        return self.sync._report_pack(self.sync._report_intensity(
            rows, start, end, week_mode="rolling", weekly_rescue=rescue, as_of=end), ready=True)

    def facts(self, rows, **kw):
        return self.sync._sport_period_facts(rows, self.selection(rows, **kw))

    def test_real_shape_nulls_virtual_type_wins_false_flag_and_no_snow_ascent(self):
        rows = [activity("v1", trainer=False), activity("v2", trainer=True, max_heartrate=None),
                activity("n1", "NordicSki"), activity("w1", "Walk")]
        self.assertTrue(all(set(a) == set(rows[0]) for a in rows))
        facts = self.facts(rows)["sports"]["nordic_skiing"]
        self.assertEqual(facts["activity_count"], 3)
        self.assertEqual(facts["coverage"]["max_hr"], 2)
        self.assertEqual(facts["max_hr"]["bpm"], 160)
        indoor = facts["distance_elevation"]["indoor"]
        self.assertEqual((indoor["distance_m"], indoor["distance_activities"]), (24000, 2))
        self.assertNotIn("elevation_m", indoor)
        snow = facts["distance_elevation"]["snow"]
        self.assertIsNone(snow["elevation_m"])
        self.assertEqual(snow["elevation_activities"], 0)

    def test_partial_hr_distance_and_duration_keep_observed_values(self):
        swims = [activity("s1", "Swim", max_heartrate=None), activity("s2", "OpenWaterSwim")]
        swim = self.facts(swims)["sports"]["swimming"]
        self.assertEqual((swim["max_hr"]["bpm"], swim["coverage"]["max_hr"], swim["activity_count"]), (160, 1, 2))
        rows = [activity("r1", "VirtualRow", distance=None, moving_time=None),
                activity("r2", "VirtualRow", distance=24000, moving_time=7200)]
        row = self.facts(rows)["sports"]["rowing"]
        self.assertEqual((row["moving_time_s"], row["coverage"]["moving_time_s"]), (7200, 1))
        self.assertEqual(row["longest_session"]["activity_id"], "r2")
        self.assertEqual(row["distance_elevation"]["indoor"],
                         {"activity_count": 2, "distance_m": 24000, "distance_activities": 1})

    def test_zero_coverage_is_null_but_recorded_zero_is_retained(self):
        facts = self.facts([activity(distance=None, max_heartrate=None, moving_time=None)])["sports"]["nordic_skiing"]
        self.assertIsNone(facts["max_hr"])
        self.assertIsNone(facts["longest_session"])
        self.assertIsNone(facts["moving_time_s"])
        self.assertIsNone(facts["distance_elevation"]["indoor"]["distance_m"])
        zero = self.facts([activity(distance=0, moving_time=0, max_heartrate=0)])["sports"]["nordic_skiing"]
        self.assertEqual(zero["moving_time_s"], 0)
        self.assertEqual(zero["coverage"], {"moving_time_s": 1, "max_hr": 0})

    def test_invalid_metric_values_and_absent_keys_do_not_become_zero(self):
        for value in (None, True, "12", -1, float("nan"), float("inf"), 1e13):
            with self.subTest(value=value):
                row = self.facts([activity(distance=value, max_heartrate=value)])["sports"]["nordic_skiing"]
                self.assertIsNone(row["distance_elevation"]["indoor"]["distance_m"])
                self.assertIsNone(row["max_hr"])
        raw = activity()
        for key in ("distance", "max_heartrate", "trainer"):
            raw.pop(key)
        row = self.facts([raw])["sports"]["nordic_skiing"]
        self.assertIsNone(row["max_hr"])
        self.assertIn("indoor", row["distance_elevation"])

    def test_swim_settings_ignore_pool_fields_and_names(self):
        rows = [activity("s1", "Swim", pool_length=25, lengths=80, name="Open water"),
                activity("s2", "OpenWaterSwim", name="Pool"),
                activity("s3", "OpenWaterSwim", trainer=True)]
        buckets = self.facts(rows)["sports"]["swimming"]["distance_elevation"]
        self.assertEqual(set(buckets), {"pool_other", "open_water", "unknown"})
        self.assertTrue(all(b["activity_count"] == 1 for b in buckets.values()))
        self.assertTrue(all("elevation_m" not in b for b in buckets.values()))

    def test_all_nordic_modes_and_running_ascent_stay_separate(self):
        kinds = ("NordicSki", "VirtualSki", "RollerSki", "BackcountrySki")
        rows = [activity(str(i), k, total_elevation_gain=100) for i, k in enumerate(kinds)]
        buckets = self.facts(rows)["sports"]["nordic_skiing"]["distance_elevation"]
        self.assertEqual(set(buckets), {"indoor", "snow", "roller"})
        self.assertEqual(buckets["snow"]["distance_m"], 24000)
        self.assertEqual(buckets["snow"]["elevation_m"], 200)
        self.assertEqual(buckets["roller"]["elevation_m"], 100)
        self.assertNotIn("elevation_m", buckets["indoor"])
        runs = [activity(str(i), k, total_elevation_gain=50) for i,k in enumerate(("Run", "VirtualRun", "TrailRun"))]
        buckets = self.facts(runs)["sports"]["running"]["distance_elevation"]
        self.assertEqual(buckets["outdoor"]["elevation_m"], 100)
        self.assertNotIn("elevation_m", buckets["indoor"])

    def test_flags_and_names_cannot_borrow_settings(self):
        for kind in ("Run", "Rowing", "NordicSki"):
            for flag, expected in ((False, "outdoor"), (None, "outdoor"), (True, "indoor"), ("false", "unknown")):
                sport = self.sync._report_sport(kind)
                if sport == "nordic_skiing" and expected == "outdoor":
                    expected = "snow"
                with self.subTest(kind=kind, flag=flag):
                    raw = activity(kind=kind, trainer=flag, name="Indoor erg pool")
                    self.assertEqual(self.sync._sport_fact_environment(raw, sport), expected)
        rows = [activity("a", "Rowing"), activity("b", "VirtualRow"), activity("c", "Rowing", trainer="bad")]
        self.assertEqual(set(self.facts(rows)["sports"]["rowing"]["distance_elevation"]), {"indoor", "outdoor", "unknown"})

    def test_cycling_and_everyday_activities_never_add_a_sibling(self):
        rows = [activity("c", "Ride")]
        baseline = self.selection(rows)
        for i, kind in enumerate(("Walk", "Hike", "Snowshoe", "EBikeRide", "EMountainBikeRide")):
            rows.append(activity(str(i), kind, icu_training_load=99999))
        self.assertEqual(self.selection(rows)["selected"], baseline["selected"])
        self.assertIsNone(self.sync._build_sport_fun_facts(rows, {"rolling_7d":self.selection(rows)}))
        for kind in ("TrackRide", "Cyclocross", "Velomobile"):
            self.assertEqual(self.sync._build_fun_facts([activity(kind=kind)], "2026-10-15", "2026-10-21")["cycling_activity_count"], 1)

    def test_other_selected_endurance_sports_get_no_facts(self):
        for kind in ("AlpineSki", "Canoeing", "Handcycle", "Elliptical", "Workout", "WeightTraining"):
            rows = [activity(kind=kind, name="Running cycling ski")]
            self.assertIsNone(self.sync._build_sport_fun_facts(rows, {"rolling_7d": self.selection(rows)}))

    def test_period_local_selection_not_chunk_union(self):
        rows = [activity("c0", "Ride", icu_training_load=450, moving_time=7200), activity("r", "Run", icu_training_load=50)]
        rows += [activity("c"+str(i), "Ride", day=day, icu_training_load=500)
                 for i,day in enumerate(("2026-10-01", "2026-10-08", "2026-10-14"),1)]
        short = self.selection(rows)
        long = self.selection(rows, "2026-09-24", rescue=True)
        block = self.sync._build_sport_fun_facts(rows, {"rolling_7d":short, "rolling_28d":long})
        self.assertEqual(set(block["rolling_7d"]["sports"]), {"running"})
        self.assertEqual(block["rolling_28d"]["sports"], {})
        self.assertNotIn("cycling", json.dumps(block))
        rows[1]["icu_training_load"] = 49
        self.assertNotIn("running", self.selection(rows)["selected"])
        rows[1]["icu_training_load"] = 51
        self.assertIn("running", self.selection(rows)["selected"])

    def test_season_uses_all_selected_sport_weeks_and_excludes_current(self):
        self.sync.week_start_day = 6
        rows = [activity("c", "Ride", "2026-10-05", icu_training_load=400, moving_time=14400),
                activity("s1", "VirtualSki", "2026-10-06", icu_training_load=10),
                activity("s2", "VirtualSki", "2026-10-13", icu_training_load=100),
                activity("s3", "VirtualSki", "2026-10-20", moving_time=99999)]
        weeks = [{"week_start":d} for d in ("2026-10-04", "2026-10-11", "2026-10-18")]
        selection = self.sync._report_pack(self.sync._report_season_intensity(rows,weeks,"2026-10-21"), ready=True)
        self.assertNotIn("nordic_skiing", self.selection(rows,"2026-10-04","2026-10-10")["selected"])
        facts = self.sync._sport_period_facts(rows,selection,season=True)
        self.assertEqual((facts["start"],facts["end"],facts["completed_weeks"]), ("2026-10-04","2026-10-17",2))
        ski = facts["sports"]["nordic_skiing"]
        self.assertEqual(ski["moving_time_s"],7200)
        self.assertEqual(ski["activity_count"],2)
        self.assertNotIn("longest_session",ski)
        self.assertIsNone(self.sync._build_sport_fun_facts(rows,{"season":None}))

    def test_duplicate_metric_conflicts_are_local_and_names_use_id_fallback(self):
        raw = activity()
        other = dict(raw,distance=999,name="Other name",max_heartrate=180)
        a = self.facts([raw,other])["sports"]["nordic_skiing"]
        b = self.facts([other,raw])["sports"]["nordic_skiing"]
        self.assertEqual(a,b)
        self.assertEqual(a["activity_count"],1)
        self.assertEqual(a["moving_time_s"],3600)
        self.assertIsNone(a["max_hr"])
        self.assertIsNone(a["distance_elevation"]["indoor"]["distance_m"])
        self.assertIsNone(a["longest_session"]["activity_name"])
        self.assertIsNone(a["longest_session"]["distance_m"])
        self.assertEqual(self.facts([raw,copy.deepcopy(raw)]),self.facts([raw]))

    def test_identity_conflicts_missing_ids_and_invalid_dates_are_not_winners(self):
        self.sync.report_main_sports = ["nordic_skiing"]
        for change in ({"start_date_local":"2026-10-14T10:00:00"}, {"type":"Run"},
                       {"moving_time":999}, {"start_date_local":"invalid"}):
            rows = [activity(),dict(activity(),**change)]
            facts = self.facts(rows)["sports"]["nordic_skiing"]
            self.assertEqual(facts["activity_count"],1)
            self.assertIsNone(facts["longest_session"])
            self.assertIsNone(facts["max_hr"])
        rows = [activity(aid=None),activity("good"),activity("bad",day="bad-date")]
        facts = self.facts(rows)["sports"]["nordic_skiing"]
        self.assertEqual(facts["activity_count"],2)
        self.assertEqual(facts["coverage"]["moving_time_s"],1)
        self.assertEqual(facts["longest_session"]["activity_id"],"good")

    def test_hr_alias_disagreement_and_deterministic_ties(self):
        raw = activity(max_hr=170)
        self.assertIsNone(self.facts([raw])["sports"]["nordic_skiing"]["max_hr"])
        rows = [activity("b"),activity("a"),activity("z",day="2026-10-16")]
        facts = self.facts(rows)["sports"]["nordic_skiing"]
        self.assertEqual(facts["max_hr"]["activity_id"],"z")
        self.assertEqual(self.facts(rows),self.facts(list(reversed(rows))))
        self.assertEqual(self.facts(rows[:2])["sports"]["nordic_skiing"]["longest_session"]["activity_id"],"a")

    def test_empty_missing_selection_and_exact_local_boundaries(self):
        rows = [activity("a",day="2026-10-14"),activity("b",day="2026-10-15"),
                activity("c",day="2026-10-21"),activity("d",day="2026-10-22")]
        result = self.facts(rows)
        self.assertEqual(result["sports"]["nordic_skiing"]["activity_count"],2)
        selection = self.selection(rows)
        selection["selected"] = {}
        self.assertEqual(self.sync._sport_period_facts(rows,selection)["sports"],{})
        self.assertIsNone(self.sync._sport_period_facts(rows,None))
        self.assertIsNone(self.sync._sport_period_facts(rows,{}))

    def test_zero_completed_weeks_and_selected_without_zone_evidence(self):
        rows = [activity(icu_hr_zone_times=None, icu_zone_times=None)]
        selected = self.selection(rows)
        self.assertIn("nordic_skiing", selected["selected"])
        self.assertEqual(self.sync._sport_period_facts(rows, selected)["sports"]
                         ["nordic_skiing"]["max_hr"]["bpm"], 160)
        empty = self.sync._report_pack(self.sync._report_season_intensity(
            rows, [{"week_start": "2026-10-19"}], "2026-10-21"), ready=True)
        self.assertIsNone(self.sync._build_sport_fun_facts(rows, {"season": empty}))
        ready = self.sync._report_pack(self.sync._report_season_intensity(
            rows, [{"week_start": "2026-10-12"}, {"week_start": "2026-10-19"}],
            "2026-10-21"), ready=True)
        self.assertIn("nordic_skiing", self.sync._build_sport_fun_facts(
            rows, {"season": ready})["season"]["sports"])

    def test_reducer_makes_no_requests_and_keeps_selection_input_unchanged(self):
        rows = [activity(str(i),kind) for i,kind in enumerate(("Ride","Run","Swim","OpenWaterSwim"))]
        selection = self.selection(rows)
        before = copy.deepcopy((rows,selection))
        with mock.patch.object(self.sync,"_intervals_get",side_effect=AssertionError("extra request")):
            result = self.sync._build_sport_fun_facts(rows,{"rolling_7d":selection,"rolling_28d":selection})
        self.assertEqual((rows,selection),before)
        self.assertEqual(set(result["rolling_7d"]["sports"]),{"running","swimming"})


def producer_activities(three_sport=True, extended=False):
    """Invented repeatable history with current and completed-week sessions."""
    rows = []
    kinds = [("Ride", "VirtualRide"), ("Run", "VirtualRun", "TrailRun"),
             ("Swim", "OpenWaterSwim")]
    if not three_sport:
        kinds = kinds[:1]
    if extended:
        kinds += [("NordicSki", "VirtualSki", "RollerSki", "BackcountrySki"),
                  ("Rowing", "VirtualRow")]
    for number, offset in enumerate((1, 4, 8, 11, 15, 18, 22, 25, 29, 32, 36, 39)):
        date = (Clock.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
        for sport, types in enumerate(kinds):
            kind = types[number % len(types)]
            row = activity("sample-%s-%s" % (sport, number), kind, date,
                           name="Synthetic %s %s" % (kind, number),
                           icu_training_load=(60 if sport == 0 else 30),
                           distance=(30000 if sport == 0 else 1500 if sport == 2 else 9000),
                           total_elevation_gain=(120 if kind in ("Ride", "Run", "TrailRun", "RollerSki") else None))
            if sport == 0:
                row.update(icu_average_watts=180, icu_joules=650000, carbs_used=90,
                           stream_types=["watts", "heartrate"])
            rows.append(row)
    return rows


def producer_run(module, directory, activities, *, days=7, refresh="auto",
                 curve_mode="ok", output_name="latest.json", selection=None):
    """Run actual collectors/writers; mock HTTP and unrelated companion builders."""
    sync = module.IntervalsSync("synthetic", "synthetic", week_start_day=6,
                               report_main_sports=selection)
    sync.data_dir = Path(directory)
    sync._intervals_data = {"generated_at": Clock.now(timezone.utc).isoformat(), "activities": {}}
    sends = []
    secs = [1, 5, 60, 300, 1200, 3600]
    watts = [710, 620, 380, 280, 230, 210]
    file_state = module.DataOverview.file_state

    def frozen_file_state(root, relative):
        present, _ = file_state(root, relative)
        return present, Clock.now(timezone.utc).isoformat() if present else None

    def get(url, **kwargs):
        endpoint = url.split("/api/v1/")[-1]
        params = copy.deepcopy(kwargs.get("params"))
        sends.append(("GET", endpoint, params, kwargs.get("allow_redirects", True)))
        response = mock.Mock(status_code=200, headers={})
        response.raise_for_status.return_value = None
        if endpoint == "athlete/synthetic/activities":
            if refresh == "fail" and params["oldest"] < "2026-01-01":
                raise module.requests.exceptions.RequestException("synthetic history read failure")
            value = [a for a in activities if params["oldest"] <=
                     a["start_date_local"][:10] <= params["newest"]]
        elif endpoint == "athlete/synthetic/wellness":
            value = [{"id": (Clock.now() - timedelta(days=n)).strftime("%Y-%m-%d"),
                      "ctl": 50, "atl": 55} for n in range(84)]
        elif "/wellness/" in endpoint:
            value = {"ctl": 50, "atl": 55}
        elif endpoint == "athlete/synthetic/events" or endpoint.endswith("/messages"):
            value = []
        elif endpoint == "athlete/synthetic/activity-power-curves":
            if curve_mode == "fail":
                response.status_code = 503
            cycling = {a["id"]: a for a in activities if sync._report_sport(a["type"]) == "cycling"}
            value = {"after_kj": 0, "secs": secs, "curves": [
                {"id": a["id"], "start_date_local": a["start_date_local"],
                 "watts": watts[:3] if curve_mode == "partial" else watts}
                for a in cycling.values()]}
        elif endpoint.endswith("/power-curve.json"):
            value = {"secs": secs, "watts": watts}
        else:
            value = {}
        response.json.return_value = copy.deepcopy(value)
        return response

    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(module, "datetime", Clock))
        stack.enter_context(mock.patch.object(module.DataOverview, "file_state", side_effect=frozen_file_state))
        stack.enter_context(mock.patch.object(module.requests, "get", side_effect=get))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        for method, value in (("_generate_saved_workouts", None), ("_generate_terrain", set()),
                ("_generate_route_weather", {}), ("_generate_intervals", set()),
                ("_prepare_session_structures", {}), ("_build_terrain_for_activity", {}),
                ("_build_weather_for_activity", {}), ("_update_route_eta_history", None)):
            stack.enter_context(mock.patch.object(sync, method, return_value=value))
        if refresh in ("force", "fail") or refresh == "auto" and sync.should_generate_history():
            if refresh == "fail":
                try:
                    sync.generate_history()
                except module.requests.exceptions.RequestException:
                    pass
                else:
                    raise AssertionError("expected synthetic history failure")
            else:
                sync.generate_history()
        data = sync.collect_training_data(days_back=days)
        sync.save_local_outputs(data, sync.data_dir / output_name)
    history_path = sync.data_dir / sync.HISTORY_FILE
    history = json.loads(history_path.read_text()) if history_path.exists() else None
    return data, history, sends


class ProducerFacts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)

    def test_actual_producers_bind_all_sports_and_only_add_summary_siblings(self):
        latest, history, _ = producer_run(mod, self.directory, producer_activities(extended=True))
        for period, selection in (("rolling_7d", "report_intensity_7d"),
                                  ("rolling_28d", "report_intensity_28d")):
            facts = latest["sport_fun_facts"][period]
            chosen = latest["derived_metrics"][selection]
            self.assertEqual(set(facts["sports"]), set(chosen["selected"]) - {"cycling"})
            self.assertEqual((facts["start"], facts["end"]), (chosen["start"], chosen["end"]))
        facts = history["sport_fun_facts"]["season"]
        chosen = history["report_intensity_season"]
        self.assertEqual(set(facts["sports"]), set(chosen["selected"]) - {"cycling"})
        self.assertEqual(facts["completed_weeks"], chosen["weeks"])
        self.assertTrue(all("longest_session" not in f for f in facts["sports"].values()))
        for key in ("daily_90d", "weekly_180d", "monthly_1y", "monthly_2y", "monthly_3y"):
            self.assertTrue(all("sport_fun_facts" not in row for row in history[key]))
        self.assertTrue(all("sport_fun_facts" not in row for row in latest["rolling_7d_chunks"]))
        self.assertEqual(json.loads((self.directory / "latest.json").read_text()), latest)
        self.assertEqual({p.name for p in self.directory.iterdir()},
                         {"latest.json", "history.json", "intervals.json", "ftp_history.json"})

    def test_days_and_output_name_do_not_change_period_facts(self):
        rows = producer_activities()
        first = None
        for days in (1, 7, 28):
            with tempfile.TemporaryDirectory() as directory:
                latest, history, _ = producer_run(mod, directory, rows, days=days,
                                                 output_name="manual.json")
                facts = (latest["sport_fun_facts"], history["sport_fun_facts"])
                if first is None:
                    first = facts
                self.assertEqual(facts, first)
                self.assertEqual(json.loads((Path(directory) / "manual.json").read_text()), latest)

    def test_four_delivery_contexts_share_nested_facts_and_companions(self):
        first = None
        rows = producer_activities()
        contexts = (("local", None, 7, "latest.json"),
                    ("scheduled", "schedule", 7, "latest.json"),
                    ("on_demand", "workflow_dispatch", 7, "latest.json"),
                    ("manual", None, 28, "manual.json"))
        for label, event, days, filename in contexts:
            with self.subTest(path=label), tempfile.TemporaryDirectory() as directory, \
                    mock.patch.dict(os.environ):
                for key in ("GITHUB_ACTIONS", "GITHUB_EVENT_NAME",
                            "GITHUB_RUN_NUMBER", "GITHUB_RUN_ATTEMPT"):
                    os.environ.pop(key, None)
                if event:
                    os.environ.update(GITHUB_ACTIONS="true", GITHUB_EVENT_NAME=event,
                                      GITHUB_RUN_NUMBER="100", GITHUB_RUN_ATTEMPT="1")
                latest, history, _ = producer_run(mod, directory, rows, days=days,
                                                 output_name=filename)
                nested = latest["sport_fun_facts"], history["sport_fun_facts"]
                if first is None:
                    first = nested
                self.assertEqual(nested, first)
                self.assertEqual({p.name for p in Path(directory).iterdir()},
                                 {filename, "history.json", "intervals.json", "ftp_history.json"})

    def test_refresh_retention_failure_replacement_and_deselection(self):
        rows = producer_activities()
        _, first, cold = producer_run(mod, self.directory, rows)
        old_bytes = (self.directory / "history.json").read_bytes()
        cycling = [a for a in rows if a["type"] in ("Ride", "VirtualRide")]
        latest, retained, warm = producer_run(mod, self.directory, cycling, refresh="keep")
        self.assertNotIn("sport_fun_facts", latest)
        self.assertEqual(retained, first)
        self.assertEqual((self.directory / "history.json").read_bytes(), old_bytes)
        latest, failed, _ = producer_run(mod, self.directory, cycling, refresh="fail")
        self.assertNotIn("sport_fun_facts", latest)
        self.assertEqual(failed, first)
        self.assertEqual((self.directory / "history.json").read_bytes(), old_bytes)
        _, replaced, _ = producer_run(mod, self.directory, cycling, refresh="force")
        self.assertNotIn("sport_fun_facts", replaced)
        self.assertTrue(any(c[1].endswith("activity-power-curves") for c in cold))
        self.assertFalse(any(c[1].endswith("activity-power-curves") for c in warm))

class FactTemplates(unittest.TestCase):
    def test_period_sources_coverage_settings_and_all_five_distance_labels(self):
        for period,selector in (("7_DAY","derived_metrics.report_intensity_7d.selected"),
                                ("28_DAY","derived_metrics.report_intensity_28d.selected"),
                                ("SEASON","history.report_intensity_season.selected")):
            text = (REPO_ROOT/"examples/reports"/(period+"_REPORT_TEMPLATE.md")).read_text()
            with self.subTest(period=period):
                self.assertIn(selector,text)
                self.assertIn("sport_fun_facts.",text)
                self.assertIn("Zero coverage omits the metric",text)
                self.assertIn("Duplicate-conflicting metrics remain unavailable",text)
                self.assertIn("pool/other",text)
                self.assertIn("Longest sessions belong here only in 7-day/28-day",text)
                for verb in ("ridden","run","swum","skied","rowed"):
                    self.assertIn("Distance "+verb,text)
                self.assertIn("Climbed: 600 m (outdoor)",text)
                self.assertNotIn("Format split facts as `Distance:",text)

    def test_typical_distance_and_climbing_examples_fit_phone_width(self):
        for line in ("Distance ridden: 80 km (outdoor)", "Distance run: 18 km (outdoor)",
                     "Distance swum: 2 km (pool/other)", "Distance skied: 18 km (indoor)",
                     "Distance rowed: 24 km (indoor)", "Climbed: 600 m (outdoor)"):
            self.assertLessEqual(len(line),40)

    def test_fragment_partial_coverage_and_season_longest_omission(self):
        for stem in ("7_DAY", "28_DAY", "SEASON"):
            text = (REPO_ROOT / "examples/reports" / (stem + "_REPORT_EXAMPLES.md")).read_text()
            fragment = text.split("## Selected-sport fact fragments")[1]
            for sport in ("running", "swimming", "Nordic skiing", "rowing"):
                self.assertIn("**Fun facts (" + sport + ", descriptive)**", fragment)
            for value in ("158 bpm, 10 Jul, Lake swim\nHR coverage: 2 of 3 sessions",
                          "Distance rowed: 24 km (indoor)\nIndoor distance: 2 of 3 sessions",
                          "Rowing time: 2h30m\nTime coverage: 3 of 4 sessions",
                          "Distance swum: 2 km (pool/other)"):
                self.assertIn(value, fragment)
            self.assertNotIn("Climbed: 0", fragment)
            if stem == "SEASON":
                self.assertNotIn("Longest ", fragment)
            else:
                self.assertIn("12 km (indoor)\nLongest coverage: 3 of 4 sessions", fragment)


if __name__ == "__main__":
    unittest.main()
