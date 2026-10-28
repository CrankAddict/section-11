"""Offline v3.151 calendar-span and deferred evidence-boundary regressions."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from _harness import SYNC_PATH, install_verb_guard, load_module_by_path, restore_verb_guard

mod = load_module_by_path("s11_calendar_spans", SYNC_PATH)
originals = None


def setUpModule():
    global originals
    originals = install_verb_guard(mod.requests)


def tearDownModule():
    restore_verb_guard(mod.requests, originals)


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 11, 5, 12, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


def event(eid=42, start="2026-11-03T00:00:00", end="2026-11-07T00:00:00", **changes):
    row = {"id": eid, "start_date_local": start, "end_date_local": end,
           "category": "HOLIDAY", "name": "Holiday - Off Season"}
    row.update(changes)
    return row


def ride(aid="s1", date="2026-11-04", trainer=True, **changes):
    row = {"id": aid, "start_date_local": date + "T10:00:00", "date": date,
           "type": "Ride", "trainer": trainer, "source": "GARMIN_CONNECT", "name": "Synthetic ride",
           "moving_time": 3600, "icu_training_load": 50}
    row.update(changes)
    return row


class CalendarSpans(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sync = mod.IntervalsSync("synthetic", "synthetic")
        self.sync.data_dir = Path(tmp.name)
        self.sync._intervals_data = {}
        clock = mock.patch.object(mod, "datetime", Clock)
        clock.start()
        self.addCleanup(clock.stop)

    def formatted(self, evt):
        return self.sync._format_events([evt], today="2026-11-05")[0]

    def test_midnight_holiday_inclusive_end(self):
        row = self.formatted(event())
        self.assertEqual((row["date"], row["end_date"]), ("2026-11-03", "2026-11-06"))

    def test_same_day_and_next_midnight_do_not_add_end_date(self):
        for end in (None, "", "2026-11-03T18:00:00", "2026-11-04T00:00:00"):
            with self.subTest(end=end):
                self.assertNotIn("end_date", self.formatted(event(end=end)))

    def test_non_midnight_includes_end_day(self):
        self.assertEqual(self.formatted(event(end="2026-11-07T12:30:00"))["end_date"], "2026-11-07")

    def test_end_before_start_is_clamped(self):
        for end in ("2026-11-01T00:00:00", "2026-11-01T12:00:00", "2026-11-03T00:00:00"):
            self.assertNotIn("end_date", self.formatted(event(end=end)))
            self.assertEqual(self.sync._calendar_end_date(event(end=end)), "2026-11-03")

    def test_all_categories_share_the_span_rule(self):
        for category in ("HOLIDAY", "NOTE", "SICK", "INJURED", "WORKOUT", "RACE_A"):
            self.assertEqual(self.formatted(event(category=category))["end_date"], "2026-11-06")

    def test_ordinary_workouts_serialization_unchanged_by_single_day_end(self):
        for start, end in (("2026-11-05T08:00:00", "2026-11-05T09:00:00"),
                           ("2026-11-05T00:00:00", "2026-11-06T00:00:00"),
                           ("2026-11-20T08:00:00", "2026-11-20T09:00:00")):
            workout = event(start=start, end=end, category="WORKOUT", type="Ride", indoor=True,
                            name="Endurance", moving_time=3600, icu_training_load=50,
                            description="NOTE: Easy today\n\n- 60m 60%", workout_doc={"steps": []})
            with_end = json.dumps(self.formatted(workout)).encode()
            workout.pop("end_date_local")
            self.assertEqual(with_end, json.dumps(self.formatted(workout)).encode())

    def test_health_marker_conversion_and_holiday_exclusion(self):
        events = [event(category="SICK"), event(43, category="HOLIDAY"),
                  event(44, end="2026-11-07T12:00:00", category="INJURED")]
        with mock.patch.object(self.sync, "_intervals_get", return_value=events):
            health = self.sync._build_health_context([], {}, "2026-11-05", "2026-10-09")
        self.assertEqual([e["event_id"] for e in health["current"]], [44, 42])
        by_id = {e["event_id"]: e for e in health["current"]}
        for evt in (events[0], events[2]):
            self.assertEqual(by_id[evt["id"]]["end_date"], self.formatted(evt)["end_date"])

    def collect(self, events=(), activities=(), curves=None):
        """Real collector and GET wrapper, with start-indexed synthetic HTTP responses."""
        calls = []
        def get(url, **kwargs):
            prefix = "https://intervals.icu/api/v1/athlete/synthetic"
            self.assertTrue(url.startswith(prefix), url)
            endpoint = url[len(prefix):].lstrip("/")
            params = kwargs.get("params") or {}
            calls.append((endpoint, dict(params)))
            if endpoint == "events":
                self.assertEqual(set(params), {"oldest", "newest", "category"}
                                 if "category" in params else {"oldest", "newest", "resolve"})
                if "category" not in params:
                    self.assertEqual(params["resolve"], "true")
                payload = [copy.deepcopy(e) for e in events
                           if params["oldest"] <= e["start_date_local"][:10] <= params["newest"]
                           and ("category" not in params or e["category"] in params["category"].split(","))]
            elif endpoint == "activities":
                for activity in activities:
                    self.assertNotIn("indoor", activity)
                payload = [copy.deepcopy(a) for a in activities
                           if params["oldest"] <= a["start_date_local"][:10] <= params["newest"]]
            elif endpoint == "wellness":
                payload = [{"id": "2026-11-05", "ctl": 50, "atl": 60}]
            elif endpoint.startswith("wellness/"):
                payload = {"ctl": 50, "atl": 60}
            elif endpoint == "power-curves":
                payload = curves or {}
            elif endpoint in ("", "hr-curves"):
                payload = {}
            else:
                raise AssertionError("Unexpected GET: " + endpoint)
            response = mock.Mock(status_code=200, headers={})
            response.json.return_value = payload
            return response
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(mod.requests, "get", side_effect=get))
            for method, value in (("_generate_saved_workouts", None), ("_generate_terrain", set()),
                    ("_generate_route_weather", {}), ("_generate_intervals", set()),
                    ("_prepare_session_structures", {}), ("_build_terrain_for_activity", {}),
                    ("_build_weather_for_activity", {}), ("_get_activity_messages", ("ok", [])),
                    ("_fetch_activity_power_curve", ("no_data", None)),
                    ("_build_sport_thresholds", {"cycling": {"ftp": 240, "ftp_indoor": 220}})):
                stack.enter_context(mock.patch.object(self.sync, method, return_value=value))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            data = self.sync.collect_training_data()
        return data, calls

    def test_producer_keeps_in_progress_original_dates_and_window_edges(self):
        rows = [event(), event(43, end="2026-11-05T00:00:00"),
                event(44, start="2026-10-09T00:00:00"),
                event(45, start="2026-10-08T00:00:00"),
                event(46, start="2026-12-17T00:00:00", end="2026-12-20T00:00:00"),
                event(47, start="2026-12-18T00:00:00", end="2026-12-20T00:00:00")]
        data, calls = self.collect(rows)
        planned = {e["id"]: e for e in data["planned_workouts"]}
        self.assertEqual(set(planned), {42, 44, 46})
        self.assertEqual(planned[42]["date"], "2026-11-03")
        self.assertEqual(planned[44]["date"], "2026-10-09")
        self.assertEqual(planned[42]["end_date"], "2026-11-06")
        main = [p for endpoint, p in calls if endpoint == "events" and "resolve" in p]
        self.assertEqual(main, [{"oldest": "2026-10-09", "newest": "2027-02-03", "resolve": "true"}])
        self.assertEqual(sum(endpoint == "events" for endpoint, _ in calls), 2)
        self.assertFalse(data["health_context"]["current"])

    def test_producer_42_day_metadata_does_not_expand_report_or_load_slices(self):
        old = ride("old", "2026-09-25", trainer=False)
        recent = ride(type="VirtualRide")
        curve = {"list": [{"id": "r.2026-09-25.2026-11-05", "secs": [300, 1200], "watts": [300, 250]}]}
        mixed, calls = self.collect(activities=[old, recent], curves=curve)
        self.assertEqual([a["id"] for a in mixed["recent_activities"]], ["s1"])
        self.assertEqual(mixed["fun_facts"]["rolling_28d"]["cycling_activity_count"], 1)
        self.assertEqual(mixed["derived_metrics"]["tss_7d_total"], 50)
        anchor = mixed["derived_metrics"]["capability"]["sustainability_profile"]["cycling"]["anchors"]["300s"]
        self.assertEqual(anchor["source"], "observed_unknown")
        self.assertIsNone(anchor["coggan_watts"])
        self.assertEqual([p for endpoint, p in calls if endpoint == "activities"],
                         [{"oldest": "2026-09-11", "newest": "2026-11-05"}])
        old["trainer"] = True
        uniform, uniform_calls = self.collect(activities=[old, recent], curves=curve)
        anchor = uniform["derived_metrics"]["capability"]["sustainability_profile"]["cycling"]["anchors"]["300s"]
        self.assertEqual((anchor["source"], anchor["ftp_used"]), ("observed_indoor", 220))
        self.assertEqual(anchor["coggan_watts"], 233)
        self.assertIsNone(anchor["activity_id"])
        self.assertIsNone(anchor["date"])
        # The second materialization reuses the valid profile and unaffected
        # curves; the core checks still run and changed activity fields apply.
        core = lambda rows: [(e, p) for e, p in rows if e in ("activities", "wellness", "events")]
        self.assertEqual(core(calls), core(uniform_calls))
        self.assertLess(len(uniform_calls), len(calls))
        self.assertEqual(mixed["rolling_7d_chunks"], uniform["rolling_7d_chunks"])

    def test_producer_mixed_raw_window_attributes_each_anchor(self):
        indoor = ride(type="VirtualRide")
        outdoor = ride("s2", trainer=False)
        curve = {"list": [{"id": "r.2026-09-25.2026-11-05", "secs": [300, 1200],
                            "watts": [300, 250], "activity_ids": ["s1", "s2"]}]}
        data, calls = self.collect(activities=[indoor, outdoor], curves=curve)
        block = data["derived_metrics"]["capability"]["sustainability_profile"]["cycling"]
        for duration, source, ftp, identity in (("300s", "observed_indoor", 220, "s1"),
                                                ("1200s", "observed_outdoor", 240, "s2")):
            anchor = block["anchors"][duration]
            self.assertEqual((anchor["source"], anchor["ftp_used"], anchor["activity_id"]),
                             (source, ftp, identity))
            self.assertEqual(anchor["date"], "2026-11-04")
        self.assertIsNone(block["ftp_used"])
        self.assertEqual(sum(endpoint == "activities" for endpoint, _ in calls), 1)


class SustainabilityEvidence(unittest.TestCase):
    setUp = CalendarSpans.setUp

    def profile(self, activities, complete=True, identity=None, settings=None):
        for activity in activities:
            self.assertNotIn("indoor", activity)
        window = ("2026-09-25", "2026-11-05")
        curve = {"id": "r." + ".".join(window), "secs": [300, 1200], "watts": [300, 250]}
        if identity:
            curve["activity_ids"] = [identity, identity]
        return self.sync._calculate_sustainability_profile(
            {"cycling": {"power": {"Ride": {"list": [curve]}}}}, window, {"w_prime": 18000},
            {"cycling": settings or {"ftp": 240, "ftp_indoor": 220}}, [], [], 70,
            activities=activities, activities_window=window if complete else ("2026-10-09", window[1]))["cycling"]

    def test_uniform_indoor_outdoor_use_matching_ftp_without_identity(self):
        for indoor, source, ftp in ((True, "observed_indoor", 220), (False, "observed_outdoor", 240)):
            block = self.profile([ride(trainer=indoor, type="VirtualRide" if indoor else "Ride"),
                                  ride("s2", "2026-09-25", trainer=indoor)])
            self.assertEqual(block["ftp_used"], ftp)
            anchor = block["anchors"]["300s"]
            self.assertEqual((anchor["source"], anchor["ftp_used"]), (source, ftp))
            self.assertEqual(anchor["cp_model_watts"], ftp + 60)
            self.assertIsNone(anchor["activity_id"])
            self.assertIsNone(anchor["date"])
            self.assertIsNone(block["anchors"]["600s"]["source"])
            self.assertIsNone(block["anchors"]["600s"]["coggan_watts"])

    def test_mixed_unknown_empty_and_incomplete_do_not_infer(self):
        cases = [([], True), ([ride(), ride("s2", trainer=False)], True),
                 ([ride(), ride("s2", trainer="false")], True), ([ride(trainer="true")], True),
                 ([ride(trainer=1)], True), ([ride()], False), ([ride(date="")], True)]
        for rows, complete in cases:
            with self.subTest(rows=rows, complete=complete):
                anchor = self.profile(rows, complete)["anchors"]["300s"]
                self.assertEqual(anchor["source"], "observed_unknown")
                self.assertIsNone(anchor["ftp_used"])
                self.assertIsNone(anchor["cp_model_watts"])

    def test_outside_window_and_noncycling_flags_do_not_contaminate(self):
        rows = [ride(), ride("before", "2026-09-24", trainer=False),
                ride("after", "2026-11-06", trainer=False), ride("run", trainer=False, type="Run")]
        self.assertEqual(self.profile(rows)["anchors"]["300s"]["source"], "observed_indoor")

    def test_mixed_window_allows_exact_attribution(self):
        rows = [ride(type="VirtualRide"), ride("s2", trainer=False)]
        for identity, source, ftp in (("s1", "observed_indoor", 220), ("s2", "observed_outdoor", 240)):
            anchor = self.profile(rows, identity=identity)["anchors"]["300s"]
            self.assertEqual((anchor["source"], anchor["ftp_used"], anchor["activity_id"]),
                             (source, ftp, identity))

    def test_missing_trainer_ride_is_outdoor_in_both_attribution_paths(self):
        row = ride()
        row.pop("trainer")
        for identity in (None, "s1"):
            anchor = self.profile([row], identity=identity)["anchors"]["300s"]
            self.assertEqual((anchor["source"], anchor["ftp_used"]), ("observed_outdoor", 240))

    def test_virtual_sub_type_and_nonboolean_flag_use_shared_classifier(self):
        for row, source, ftp in ((ride(trainer=False, sub_type="virtual"), "observed_indoor", 220),
                                  (ride(trainer="false"), "observed_unknown", None)):
            for identity in (None, "s1"):
                anchor = self.profile([row], identity=identity)["anchors"]["300s"]
                self.assertEqual((anchor["source"], anchor["ftp_used"]), (source, ftp))

    def test_missing_matching_ftp_never_uses_other_environment(self):
        anchor = self.profile([ride()], settings={"ftp": 240})["anchors"]["300s"]
        self.assertEqual(anchor["source"], "observed_indoor")
        self.assertIsNone(anchor["ftp_used"])
        self.assertIsNone(anchor["cp_model_watts"])


class LegacyAssessmentEvidence(unittest.TestCase):
    setUp = CalendarSpans.setUp

    def test_legacy_without_identity_stays_historical_even_with_old_event_update(self):
        act = ride(paired_event_id=42)
        plan = event(category="WORKOUT", updated="2020-01-01T00:00:00Z", paired_activity_id="s1",
                     workout_doc={"steps": [{"duration": 3600, "power": {"value": 60, "units": "%ftp"}}]})
        legacy = {"method": "plan_match_v2", "status": "followed", "steps": [[3600, 144, 145, "matched"]]}
        with contextlib.ExitStack() as stack:
            for method, value in (("_build_terrain_for_activity", {}), ("_build_weather_for_activity", {}),
                                  ("_get_activity_messages", ("ok", [])),
                                  ("_fetch_activity_power_curve", ("no_data", None))):
                stack.enter_context(mock.patch.object(self.sync, method, return_value=value))
            first = self.sync._format_activities([act], paired_events=[plan],
                       previous_latest_lookup={"s1": {"structure_summary": legacy}})[0]
            summary = first["interval_data"]["plan_match"]
            self.assertEqual(summary["status"], "not_assessed")
            self.assertEqual(summary["retained_step_assessment"], legacy)
            self.assertNotIn("assessment_retained", summary)
            again = self.sync._format_activities([act], paired_events=[plan],
                                                previous_latest_lookup={"s1": first})[0]
            self.assertEqual(again["interval_data"]["plan_match"], summary)
            # Nearby valid evidence: captured identity and current definition match.
            first["interval_data"]["plan_match"] = dict(legacy, plan=first["plan_pairing"]["plan"])
            retained = self.sync._format_activities([act], paired_events=[plan],
                                                    previous_latest_lookup={"s1": first})[0]
            self.assertEqual(retained["interval_data"]["plan_match"]["status"], "followed")
            self.assertTrue(retained["interval_data"]["plan_match"]["assessment_retained"])


if __name__ == "__main__":
    unittest.main()
