"""Consecutive offline producer runs; synthetic rides, mocked remote/OS I/O."""
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

import test_session_structure as base
import test_sleep_context as sleep
from _harness import install_verb_guard, restore_verb_guard
from test_update_prototype import Offline, SYNC, write, validate_data
from test_update_path_fixes import ReleaseHTTP

mod = base.mod
BACKUP = mod.CarryForwardBackup.PATH


def setUpModule():
    global originals
    originals = install_verb_guard(mod.requests)


def tearDownModule():
    restore_verb_guard(mod.requests, originals)


class Scenario:
    def __init__(self, root):
        self.root = root
        self.act, self.event, self.streams = base.inputs()
        self.event.update(start_date_local="2026-01-01T10:00:00", type="VirtualRide")
        self.present = True

    def run(self, day, script_hash="candidate", save=True):
        clock = type("CarryClock", (sleep.Clock,), {
            "instant": datetime(2026, 1, day, 12, tzinfo=timezone.utc)})
        sync = base.Sync("synthetic", "synthetic")
        sync.data_dir = self.root
        sync._cached_script_hash = script_hash
        calls = []
        def get(endpoint, params=None):
            calls.append((endpoint, copy.deepcopy(params)))
            if endpoint == "":
                return {"timezone": "UTC", "icu_weight": 70,
                        "sportSettings": [{"types": ["Ride", "VirtualRide"], "ftp": 250}]}
            if endpoint == "activities":
                return [copy.deepcopy(self.act)] if self.present else []
            if endpoint == "wellness":
                return [r for r in sleep.wellness_rows(f"2026-01-{day:02d}")
                        if params["oldest"] <= r["id"] <= params["newest"]]
            if endpoint.startswith("wellness/"):
                return {"id": endpoint.split("/")[-1], "ctl": 50, "atl": 55, "weight": 70}
            if endpoint == "events":
                return [copy.deepcopy(self.event)]
            if endpoint in ("power-curves", "hr-curves"):
                return {}
            raise AssertionError("unexpected endpoint: " + endpoint)

        log = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(mod, "datetime", clock))
            stack.enter_context(mock.patch.object(sync, "_intervals_get", side_effect=get))
            for method, value in (("_generate_saved_workouts", None), ("_generate_terrain", set()),
                    ("_generate_route_weather", {}), ("_build_terrain_for_activity", {}),
                    ("_build_weather_for_activity", {}), ("_get_activity_messages", ("ok", [])),
                    ("_build_power_curve_for_activity", {}), ("_build_decoupling_for_activity", {}),
                    ("_fetch_activity_intervals", ("no_data", []))):
                stack.enter_context(mock.patch.object(sync, method, return_value=value))
            streams = stack.enter_context(mock.patch.object(sync, "_fetch_activity_streams",
                                                            return_value=("ok", self.streams)))
            stack.enter_context(contextlib.redirect_stdout(log))
            data = sync.collect_training_data()
            if save:
                sync.save_local_outputs(data, str(self.root / "latest.json"))
        return data, sync, calls, streams.call_count, log.getvalue()


class CarryForward(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scenario = Scenario(self.root)

    def plan(self, data):
        return data["recent_activities"][0]["interval_data"]["plan_match"]

    def seed(self):
        first = self.scenario.run(14)[0]
        self.assertEqual(self.plan(first)["status"], "followed")
        self.assertTrue(first["recent_activities"][0]["has_structure"])
        return first

    def test_consecutive_runs_cross_detail_boundary_without_refetch(self):
        first = self.seed()
        for day in (15, 16, 17, 20, 28):
            data, sync, calls, streams, log = self.scenario.run(day)
            self.assertEqual(self.plan(data)["steps"], self.plan(first)["steps"])
            self.assertEqual(self.plan(data)["status"], "followed")
            if day > 15:
                self.assertTrue(self.plan(data)["assessment_retained"])
                self.assertFalse(data["recent_activities"][0]["has_structure"])
                self.assertEqual(streams, 0)
                self.assertEqual(sync._intervals_data["activities"], [])
                self.assertIsNone(data["recent_activities"][0]["interval_data"]["compliance"]["on_target"])
            self.assertEqual(data["carry_forward"]["issues"], [])

    def test_one_bad_previous_export_then_normal_runs(self):
        for failure, issue in (("missing", "previous_latest_missing"),
                               ("unreadable", "previous_latest_unreadable"),
                               ("truncated", "previous_latest_invalid"),
                               ("wrong_shape", "previous_latest_invalid"),
                               ("missing_activity", "previous_latest_incomplete"),
                               ("missing_summary", "previous_latest_incomplete"),
                               ("missing_summary_status", "previous_latest_incomplete"),
                               ("missing_steps", "previous_latest_incomplete")):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                scenario = Scenario(Path(folder))
                first = scenario.run(14)[0]
                latest = scenario.root / "latest.json"
                if failure == "missing":
                    latest.unlink()
                elif failure == "truncated":
                    latest.write_text('{"recent_activities": [')
                elif failure == "wrong_shape":
                    latest.write_text('{"recent_activities": {}}')
                elif failure.startswith("missing_"):
                    bad = copy.deepcopy(first)
                    if failure == "missing_activity":
                        bad["recent_activities"] = []
                    elif failure == "missing_summary":
                        bad["recent_activities"][0].pop("interval_data")
                    elif failure == "missing_summary_status":
                        bad["recent_activities"][0]["interval_data"]["plan_match"] = {}
                    else:
                        bad["recent_activities"][0]["interval_data"]["plan_match"].pop("steps")
                    latest.write_text(json.dumps(bad))
                real_open = open
                def read(path, mode="r", *args, **kwargs):
                    if failure == "unreadable" and Path(path) == latest and mode == "r":
                        raise OSError("synthetic unreadable previous export")
                    return real_open(path, mode, *args, **kwargs)
                with mock.patch("builtins.open", side_effect=read):
                    data, _, calls, streams, log = scenario.run(16)
                self.assertIn(issue, log)
                self.assertIn(issue, data["carry_forward"]["issues"])
                self.assertEqual(data["carry_forward"]["restored_activity_ids"], [scenario.act["id"]])
                self.assertEqual(self.plan(data)["steps"], self.plan(first)["steps"])
                self.assertTrue(self.plan(data)["assessment_retained"])
                self.assertEqual(streams, 0)
                with tempfile.TemporaryDirectory() as normal_folder:
                    normal = Scenario(Path(normal_folder))
                    normal.run(14)
                    healthy = normal.run(16)
                self.assertEqual(calls, healthy[2])
                self.assertEqual(streams, healthy[3])
                for day in (17, 18):
                    healthy = scenario.run(day)[0]
                    self.assertEqual(self.plan(healthy)["status"], "followed")
                    self.assertTrue(self.plan(healthy)["assessment_retained"])
                    self.assertEqual(healthy["carry_forward"]["issues"], [])

    def test_missing_upstream_activity_for_one_run_does_not_prune_backup(self):
        self.seed()
        self.scenario.present = False
        data = self.scenario.run(16)[0]
        self.assertEqual(data["recent_activities"], [])
        self.scenario.present = True
        data = self.scenario.run(17)[0]
        self.assertTrue(self.plan(data)["assessment_retained"])
        self.assertIn("previous_latest_incomplete", data["carry_forward"]["issues"])
        # Normal window expiry removes the compact backup, not just detail.
        data, sync, *_ = self.scenario.run(29)
        self.assertEqual(data["recent_activities"], [])
        self.assertEqual(json.loads((self.root / BACKUP).read_bytes())["activities"], [])
        self.assertNotIn("carry_forward", sync._intervals_data)

    def test_pairing_edit_after_recovery_still_demotes_and_never_repromotes(self):
        first = self.seed()
        (self.root / "latest.json").unlink()
        self.scenario.event["workout_doc"]["steps"][0]["power"]["value"] = 130
        changed = self.scenario.run(16)[0]
        self.assertEqual(self.plan(changed)["status"], "not_assessed")
        self.assertEqual(self.plan(changed)["retained_step_assessment"]["steps"], self.plan(first)["steps"])
        self.assertNotIn("assessment_retained", self.plan(changed))
        (self.root / "latest.json").unlink()
        self.scenario.event["workout_doc"]["steps"][0]["power"]["value"] = 100
        restored = self.scenario.run(17)[0]
        self.assertEqual(self.plan(restored)["status"], "not_assessed")
        self.assertNotIn("assessment_retained", self.plan(restored))

    def test_new_pair_identity_and_unpaired_results_keep_existing_semantics(self):
        self.seed()
        (self.root / "latest.json").unlink()
        self.scenario.act["paired_event_id"] = 43
        self.scenario.event["id"] = 43
        data = self.scenario.run(16)[0]
        self.assertEqual(self.plan(data)["status"], "not_assessed")
        self.assertIn("retained_step_assessment", self.plan(data))
        self.scenario.act.pop("paired_event_id")
        data = self.scenario.run(17)[0]
        self.assertEqual(self.plan(data)["status"], "no_plan")

    def test_newer_companion_demotion_beats_older_latest_after_interruption(self):
        self.seed()
        old_latest = (self.root / "latest.json").read_bytes()
        self.scenario.event["workout_doc"]["steps"][0]["power"]["value"] = 130
        self.scenario.run(16)
        (self.root / "latest.json").write_bytes(old_latest)
        self.scenario.event["workout_doc"]["steps"][0]["power"]["value"] = 100
        data = self.scenario.run(17)[0]
        self.assertEqual(self.plan(data)["status"], "not_assessed")
        self.assertIn("previous_latest_older_than_backup", data["carry_forward"]["issues"])

    def test_newer_incomplete_assessment_group_still_uses_captured_identity(self):
        for missing in ("summary", "pairing", "definition_key", "plan"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as folder:
                scenario = Scenario(Path(folder))
                prior = scenario.run(14)[0]
                prior["metadata"]["last_updated"] = "2026-01-15T12:00:00Z"
                row = prior["recent_activities"][0]
                expected_key = row["plan_pairing"]["definition_key"]
                if missing == "summary":
                    row.pop("interval_data")
                elif missing == "pairing":
                    row["plan_pairing"] = None
                elif missing == "definition_key":
                    row["plan_pairing"].pop("definition_key")
                else:
                    row["interval_data"]["plan_match"].pop("plan")
                (scenario.root / "latest.json").write_text(json.dumps(prior))
                data = scenario.run(16)[0]
                self.assertTrue(self.plan(data)["assessment_retained"])
                self.assertIn("previous_latest_incomplete", data["carry_forward"]["issues"])
                self.assertEqual(data["recent_activities"][0]["plan_pairing"]["definition_key"],
                                 expected_key)

    def test_newer_explicit_demotion_is_authoritative(self):
        prior = self.seed()
        old_companion = (self.root / BACKUP).read_bytes()
        prior["metadata"]["last_updated"] = "2026-01-15T12:00:00Z"
        summary = self.plan(prior)
        summary["status"] = "not_assessed"
        summary.pop("steps", None)
        (self.root / "latest.json").write_text(json.dumps(prior))
        data = self.scenario.run(16)[0]
        self.assertEqual(self.plan(data)["status"], "not_assessed")
        self.assertNotIn("assessment_retained", self.plan(data))
        self.assertEqual(data["carry_forward"]["issues"], [])
        # Even a partly missing pairing must not promote an explicit demotion.
        prior["recent_activities"][0]["plan_pairing"] = None
        (self.root / BACKUP).write_bytes(old_companion)
        (self.root / "latest.json").write_text(json.dumps(prior))
        data = self.scenario.run(17)[0]
        self.assertEqual(self.plan(data)["status"], "not_assessed")
        self.assertNotIn("assessment_retained", self.plan(data))

    def test_legacy_latest_bootstraps_backup_after_detail_expiry(self):
        first = self.seed()
        first.pop("carry_forward")
        (self.root / "latest.json").write_text(json.dumps(first))
        (self.root / BACKUP).unlink()
        data = self.scenario.run(16)[0]
        self.assertTrue(self.plan(data)["assessment_retained"])
        self.assertEqual(data["carry_forward"]["backup"], "missing")
        (self.root / "latest.json").unlink()
        self.assertTrue(self.plan(self.scenario.run(17)[0])["assessment_retained"])

    def test_script_hash_change_does_not_invalidate_compact_backup(self):
        self.seed()
        (self.root / "latest.json").unlink()
        data, sync, _, streams, _ = self.scenario.run(16, script_hash="updated")
        self.assertTrue(self.plan(data)["assessment_retained"])
        self.assertEqual(streams, 0)
        self.assertEqual(sync._intervals_data["script_hash"], "updated")
        (self.root / "latest.json").unlink()
        self.assertTrue(self.plan(self.scenario.run(17, script_hash="rollback")[0])["assessment_retained"])

    def test_fresh_folder_and_double_loss_are_visible_without_backfill(self):
        for seed in (False, True):
            with self.subTest(seed=seed):
                if seed:
                    self.seed()
                for name in ("latest.json", "intervals.json", BACKUP):
                    (self.root / name).unlink(missing_ok=True)
                data, _, _, streams, log = self.scenario.run(16)
                self.assertEqual(self.plan(data)["status"], "not_assessed")
                self.assertNotIn("retained_step_assessment", self.plan(data))
                self.assertIn("carry_forward_backup_unavailable", log)
                self.assertEqual(data["carry_forward"]["unavailable_activity_ids"], [self.scenario.act["id"]])
                self.assertEqual(streams, 0)

    def test_bad_backup_is_visible_and_rebuilt_from_healthy_latest(self):
        self.seed()
        (self.root / BACKUP).write_text("{")
        data = self.scenario.run(16)[0]
        self.assertTrue(self.plan(data)["assessment_retained"])
        self.assertIn("carry_forward_backup_invalid", data["carry_forward"]["issues"])
        (self.root / "latest.json").unlink()
        self.assertTrue(self.plan(self.scenario.run(17)[0])["assessment_retained"])

    def test_other_carry_fields_are_projected_and_restored_together(self):
        first = self.seed()
        row = first["recent_activities"][0]
        fields = {"terrain_summary": {"distance_km": 5}, "terrain_status": "available",
                  "weather_summary": {"temp_c": 10}, "power_curve": {"5": 400},
                  "power_curve_status": "available", "dfa_rollup": {"date": row["date"]},
                  "chat_notes": [{"text": "Synthetic note"}],
                  "decoupling_detail": {"status": "available"}, "decoupling_cache": {"version": 1}}
        row.update(fields)
        row["unexpected_private_field"] = "must not be copied"
        sync = base.Sync("synthetic", "synthetic")
        sync.data_dir = self.root
        clock = type("ProjectionClock", (sleep.Clock,), {"instant": datetime(2026, 1, 16, 12, tzinfo=timezone.utc)})
        with mock.patch.object(mod, "datetime", clock):
            sync._load_previous_latest([self.scenario.act])
            sync._intervals_data = {"activities": []}
            sync._prepare_carry_forward(first)
            sync.save_local_outputs(first, str(self.root / "latest.json"))
            (self.root / "latest.json").unlink()
            prior = sync._load_previous_latest([self.scenario.act])[row["id"]]
        for key, value in fields.items():
            self.assertEqual(prior[key], value, key)
        self.assertNotIn("unexpected_private_field", prior)
        self.assertNotIn("compliance", prior)
        self.assertNotIn("session_structure", prior)

    def test_atomic_write_failure_preserves_both_complete_preimages(self):
        self.seed()
        before = {n: (self.root / n).read_bytes() for n in ("latest.json", "intervals.json")}
        for failing in ("latest.json", "intervals.json"):
            real_replace = mod.os.replace
            def replace(src, dst):
                if Path(dst).name == failing:
                    raise OSError("synthetic replace failure")
                return real_replace(src, dst)
            with mock.patch.object(mod.os, "replace", side_effect=replace), self.assertRaisesRegex(OSError, "synthetic"):
                mod.IntervalsSync._write_carry_json(self.root / failing, {"new": "value"})
            self.assertEqual((self.root / failing).read_bytes(), before[failing])
        self.assertEqual(list(self.root.glob(".carry-*.tmp")), [])

    def test_backup_is_not_an_ai_companion_or_generic_publication_path(self):
        self.seed()
        plan = validate_data.plan(self.root)
        self.assertEqual(plan["mode"], "declared")
        self.assertIn("intervals.json", plan["saved"])
        self.assertNotIn(BACKUP, plan["saved"])
        self.assertNotIn(BACKUP, (self.root / "latest.json").read_text())
        with self.assertRaises(ValueError):
            validate_data.checked_path(self.root, BACKUP)


class UpdateCarryForward(Offline):
    def test_real_update_and_rollback_preserve_latest_and_compact_backup(self):
        scenario = Scenario(self.root)
        scenario.run(14)
        before = {n: (self.root / n).read_bytes() for n in ("latest.json", "intervals.json", BACKUP)}
        wire = ReleaseHTTP(4)
        write(self.root, {"sync.py": b"synthetic old producer", ".sync_config.json": b"{}"})
        with mock.patch.object(SYNC.Path, "cwd", return_value=self.root), \
             mock.patch.dict(os.environ, {"GITHUB_ACTIONS": ""}), \
             mock.patch.object(SYNC, "_fetch_verified_release", return_value=(wire.raw[4], wire.files[4], wire.identity(4))), \
             mock.patch("builtins.input", return_value="y"), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(SYNC.do_update(timer_choice=False))
            for name, content in before.items():
                self.assertEqual((self.root / name).read_bytes(), content)
            (self.root / "latest.json").unlink()
            data = scenario.run(16, script_hash="update")[0]
            self.assertTrue(data["recent_activities"][0]["interval_data"]["plan_match"]["assessment_retained"])
            later = {n: (self.root / n).read_bytes() for n in before}
            self.assertTrue(SYNC.do_rollback())
            for name, content in later.items():
                self.assertEqual((self.root / name).read_bytes(), content)
            (self.root / "latest.json").unlink()
            data = scenario.run(17, script_hash="rollback")[0]
            self.assertTrue(data["recent_activities"][0]["interval_data"]["plan_match"]["assessment_retained"])
