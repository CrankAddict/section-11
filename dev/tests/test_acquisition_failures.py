"""Invalidation, incomplete acquisition, and private-state failure boundaries."""
import contextlib
import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import requests
import test_source_schedule as fixtures


class AcquisitionFailures(unittest.TestCase):
    setUp = fixtures.SourceCase.setUp
    new_sync = fixtures.SourceCase.new_sync
    next_run = fixtures.SourceCase.next_run
    produce = fixtures.SourceCase.produce

    def assert_clean_wait(self, before, interval):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertFalse(self.sync.begin_tick())
            self.sync._save_schedule_transition()
        self.assertEqual(self.sent, [])
        after = json.loads((self.data / "latest.json").read_text())
        fresh = after["source_freshness"]
        self.assertNotIn("source_stale", [w["code"] for w in fresh["warnings"]])
        self.assertNotIn("source_stale", [w["code"] for w in self.sync._acquisition.warnings])
        self.assertNotIn("Sources need refresh", output.getvalue())
        budget = self.sync.request_budget
        log = budget.root / "budget.log"
        self.assertNotIn("Sources need refresh", log.read_text() if log.exists() else "")
        ledger = json.loads((budget.root / "ledger.json").read_text())
        self.assertEqual(ledger.get("source_warning", []), [])
        self.assertNotIn("source_stale", ledger.get("warning_since", {}))
        self.assertEqual({k: v for k, v in after.items() if k != "source_freshness"},
                         {k: v for k, v in before.items() if k != "source_freshness"})
        for group in fixtures.sync_mod.AcquisitionStore.CORE:
            row = fresh["sources"][group]
            self.assertEqual(row["status"], "fresh", row)
            self.assertEqual(row["max_age_seconds"], interval)
            for key in ("source_acquired_at", "last_success_at", "last_attempt_at"):
                self.assertEqual(row[key], before["source_freshness"]["sources"][group][key])
            acquired = datetime.fromisoformat(row["source_acquired_at"].replace("Z", "+00:00"))
            due = datetime.fromisoformat(row["next_due_at"].replace("Z", "+00:00"))
            self.assertEqual((due - acquired).total_seconds(), interval)
            if fresh["as_of"] != before["source_freshness"]["as_of"]:
                self.assertEqual(row["next_eligible_at"], fresh["budget"]["next_eligible_at"])
        return after

    def test_freshness_waits_ladder_and_changed_choices_preserve_success(self):
        for ladder in (True, False):
            for interval, spent in ((120, 3500), (300, 5500), (600, 6200)):
                with self.subTest(ladder=ladder, interval=interval):
                    self.data = self.root / ("wait-" + str(ladder) + "-" + str(interval))
                    self.data.mkdir()
                    start = datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp()
                    self.clock.now = start
                    self.new_sync()
                    first = self.produce()
                    if ladder:
                        budget = self.sync.request_budget
                        with budget._lock():
                            budget._load()
                            budget.state["days"][budget.day]["sync"] = {"seed": spent}
                            budget._save()
                    self.clock.now = start + 60
                    self.new_sync()
                    if not ladder:
                        self.sync.check_interval_seconds = interval
                    after = self.assert_clean_wait(first, interval)
                    if ladder:
                        self.assertIn("budget_step_down", [w["code"] for w in after["source_freshness"]["warnings"]])
                    self.clock.now = start + interval
                    self.new_sync()
                    if not ladder:
                        self.sync.check_interval_seconds = interval
                    current = self.produce()
                    self.assertEqual(len(self.sent), 4)
                    self.assertTrue(all(current["source_freshness"]["sources"][g]["status"] == "fresh"
                                        for g in fixtures.sync_mod.AcquisitionStore.CORE))
                    before_bytes = (self.data / "latest.json").read_bytes()
                    self.next_run()
                    if not ladder:
                        self.sync.check_interval_seconds = interval
                    self.assert_clean_wait(current, interval)
                    self.assertEqual((self.data / "latest.json").read_bytes(), before_bytes)

    def test_freshness_waits_explicit_initial_choices(self):
        for interval in (120, 300, 600):
            with self.subTest(interval=interval):
                self.data = self.root / ("chosen-" + str(interval))
                self.data.mkdir()
                self.new_sync()
                self.sync.check_interval_seconds = interval
                first = self.produce()
                before = (self.data / "latest.json").read_bytes()
                self.next_run()
                self.sync.check_interval_seconds = interval
                self.assert_clean_wait(first, interval)
                self.assertEqual((self.data / "latest.json").read_bytes(), before)

    def test_freshness_choice_change_keeps_a_real_failure(self):
        self.produce()
        self.next_run()
        self.reply = lambda prepared, path, query: fixtures.response(200, {"invalid": []}) if path.endswith("/wellness") else None
        failed = self.produce()
        self.assertEqual(failed["source_freshness"]["sources"]["wellness"]["status"], "stale")
        self.next_run()
        self.sync.check_interval_seconds = 300
        self.assertIsNone(self.produce())
        row = json.loads((self.data / "latest.json").read_text())["source_freshness"]["sources"]["wellness"]
        self.assertEqual(row["status"], "stale")
        self.assertEqual(row["reason"], "refresh_failed")
        self.assertEqual(row["last_success_at"], failed["source_freshness"]["sources"]["wellness"]["last_success_at"])
        self.assertEqual(self.sent, [])

    def test_freshness_retained_problems_are_never_promoted_by_slower_cadence(self):
        first = self.produce()
        for status, reason in (("stale", "refresh_failed"), ("deferred", "request_budget"),
                               ("unavailable", "no_snapshot"), ("stale", "acquisition_age_unknown"),
                               ("fresh", None)):
            with self.subTest(status=status, reason=reason):
                prior = json.loads(json.dumps(first))
                row = prior["source_freshness"]["sources"]["wellness"]
                row.update(status=status, reason=reason)
                if status == "fresh":
                    row["source_acquired_at"] = fixtures.sync_mod.AcquisitionStore.stamp(self.clock.now - 601)
                elif reason in ("no_snapshot", "acquisition_age_unknown"):
                    row.update(source_acquired_at=None, last_success_at=None)
                (self.data / "latest.json").write_text(json.dumps(prior))
                self.new_sync()
                self.sync.check_interval_seconds = 600
                self.assertFalse(self.sync.begin_tick())
                self.sync._save_schedule_transition()
                after = json.loads((self.data / "latest.json").read_text())["source_freshness"]["sources"]["wellness"]
                self.assertEqual(after["status"], "stale" if status == "fresh" else status)
                self.assertEqual(after["reason"], "validity_expired" if status == "fresh" else reason)
                self.assertEqual(after["last_success_at"], row["last_success_at"])
                self.assertEqual(self.sent, [])

    def test_freshness_slow_successful_run_does_not_expire_its_acquisitions(self):
        start = self.clock.now
        self.after_send = lambda path: setattr(self.clock, "now", self.clock.now + 12)
        data = self.produce()
        self.assertEqual(len(self.sent), 13)
        self.assertEqual(self.clock.now - start, 156)
        fresh = data["source_freshness"]
        self.assertNotIn("source_stale", [w["code"] for w in fresh["warnings"]])
        self.assertGreater(fresh["sources"]["activities"]["age_seconds"], 60)
        for group in fixtures.sync_mod.AcquisitionStore.CORE:
            self.assertEqual(fresh["sources"][group]["status"], "fresh")
            self.assertEqual(fresh["sources"][group]["max_age_seconds"], 60)
        # The exemption is per invocation, not a renewed timestamp or TTL.
        self.after_send = None
        self.next_run(61)
        self.assertTrue(self.sync.begin_tick())
        retained = self.sync._source_freshness(data, retained=True)
        for group in fixtures.sync_mod.AcquisitionStore.CORE:
            self.assertEqual(retained["sources"][group]["status"], "stale")
            self.assertEqual(retained["sources"][group]["reason"], "validity_expired")
            self.assertEqual(retained["sources"][group]["last_success_at"],
                             fresh["sources"][group]["last_success_at"])

    def test_freshness_slow_run_does_not_hide_a_failed_source(self):
        self.produce()
        self.next_run(21601)
        start = self.clock.now
        self.after_send = lambda path: setattr(self.clock, "now", self.clock.now + 12)
        self.reply = lambda prepared, path, query: fixtures.response(200, {"invalid": []}) if path.endswith("/wellness") else None
        data = self.produce()
        self.assertGreater(self.clock.now - start, 60)
        fresh = data["source_freshness"]
        self.assertEqual(fresh["sources"]["wellness"]["status"], "stale")
        self.assertEqual(fresh["sources"]["wellness"]["reason"], "refresh_failed")
        self.assertEqual(fresh["sources"]["activities"]["status"], "fresh")
        self.assertIn("source_stale", [w["code"] for w in fresh["warnings"]])

    def test_freshness_current_success_does_not_mask_an_expired_reused_group_member(self):
        self.produce()
        self.next_run()
        self.assertTrue(self.sync.begin_tick())
        self.sync._intervals_get("power-curves", {"type": "Ride", "curves": "all"})
        store = self.sync._acquisition
        self.clock.now += 21601
        self.sync._intervals_get("hr-curves", {"type": "Ride", "curves": "all"})
        # The first row really succeeded this run and remains fresh, but a
        # consumed row loaded from an earlier invocation still expires.
        prior = next(e for k, e in store.entries.items()
                     if e["group"] == "aggregate_curves" and k not in store.acquired)
        store.consumed[prior["key"]] = prior
        row = store.source_status("aggregate_curves")
        self.assertEqual(row["status"], "stale")
        self.assertEqual(row["reason"], "validity_expired")

    def test_export_times_are_utc_even_with_a_different_local_clock(self):
        instant = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
        class LocalDate(datetime):
            @classmethod
            def now(cls, tz=None):
                return instant.astimezone(tz) if tz else (instant + timedelta(hours=2)).replace(tzinfo=None)
        with mock.patch.object(fixtures.sync_mod, "datetime", LocalDate):
            data = self.produce()
        for value in (data["metadata"]["last_updated"], data["derived_metrics"]["calculation_timestamp"]):
            self.assertTrue(value.endswith("Z"), value)
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            self.assertEqual(parsed.utcoffset(), timedelta(0))
            self.assertEqual(parsed, instant)
        prior = json.loads((self.data / "latest.json").read_text())
        prior["metadata"]["last_updated"] = "2026-10-28T14:00:00"
        prior["derived_metrics"]["calculation_timestamp"] = "2026-10-28T14:00:00"
        (self.data / "latest.json").write_text(json.dumps(prior))
        self.next_run()
        self.sync.check_interval_seconds = 300
        self.assertIsNone(self.produce())
        kept = json.loads((self.data / "latest.json").read_text())
        self.assertEqual(kept["metadata"], prior["metadata"])
        self.assertEqual(kept["current_status"], prior["current_status"])
        self.assertEqual(kept["derived_metrics"], prior["derived_metrics"])
        self.next_run(300)
        self.assertTrue(self.produce()["metadata"]["last_updated"].endswith("Z"))

    def test_native_library_and_history_freshness(self):
        data = self.produce()
        for group in ("saved_workouts", "history"):
            row = data["source_freshness"]["sources"][group]
            self.assertEqual(row["status"], "fresh", row)
            self.assertIsNotNone(row["source_acquired_at"])

    def test_mixed_native_acquisition_coverage_never_claims_fresh_completeness(self):
        self.assertTrue(self.sync.begin_tick())
        self.sync._fetch_activity_intervals("known")
        data = {"recent_activities": [{"id": "known", "has_intervals": True},
                                      {"id": "legacy", "has_intervals": True}]}
        source = self.sync._source_freshness(data)["sources"]["activity_details"]
        self.assertEqual(source["status"], "stale")
        self.assertEqual(source["coverage"], "partial")
        self.assertIsNone(source["source_acquired_at"])
        self.assertEqual(source["scope"]["untracked_resources"], ["legacy"])

    def test_warning_since_tracks_its_own_transition(self):
        self.produce()
        self.next_run(21600)
        self.refuse = lambda path, query: path.endswith("power-curves")
        data = self.produce()
        warning = next(w for w in data["source_freshness"]["warnings"] if w["code"] == "source_stale")
        self.assertGreater(warning["since"], data["source_freshness"]["schedule"]["changed_at"])
        self.assertEqual(set(warning), {"code", "message", "since", "next_eligible_at"})

    def test_wellness_failed_refresh_keeps_values_and_true_acquisition_time(self):
        first = self.produce()
        acquired = first["source_freshness"]["sources"]["wellness"]["last_success_at"]
        for failure in (401, 403, "timeout", "shape"):
            with self.subTest(failure=failure):
                self.next_run()
                def reply(prepared, path, query):
                    if path.endswith("/wellness"):
                        if failure == "timeout":
                            raise requests.exceptions.Timeout("synthetic timeout")
                        return fixtures.response(200, {"partial": []}) if failure == "shape" else fixtures.response(failure)
                self.reply = reply
                data = self.produce()
                row = data["source_freshness"]["sources"]["wellness"]
                self.assertEqual(row["status"], "stale")
                self.assertEqual(row["last_success_at"], acquired)
                self.assertGreater(row["last_attempt_at"], acquired)
                self.assertTrue(data["wellness_data"])
                self.assertTrue(all(row in first["wellness_data"] for row in data["wellness_data"]))
                self.assertEqual(data["source_freshness"]["sources"]["activities"]["status"], "fresh")
        self.reply = None
        self.next_run()
        refreshed = self.produce()["source_freshness"]["sources"]["wellness"]
        self.assertEqual(refreshed["status"], "fresh")
        self.assertGreater(refreshed["last_success_at"], acquired)

    def test_cold_required_source_rolls_back_all_exports(self):
        self.produce()
        store = self.sync._acquisition
        for key, entry in store.entries.items():
            if entry["group"] == "activities":
                (store.root / (key + ".json")).unlink()
        prior = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.data.rglob("*") if p.is_file()}
        self.next_run()
        self.refuse = lambda path, query: path.endswith("/activities")
        with self.assertRaises(requests.exceptions.RequestException):
            self.sync.collect_training_data()
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in prior}, prior)

    def test_private_source_creation_failure_never_falls_back(self):
        original = Path.mkdir
        def mkdir(path, *args, **kwargs):
            if "sources" in path.parts:
                raise OSError("synthetic private source failure")
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, "mkdir", mkdir):
            self.assertTrue(self.sync.begin_tick())
        self.assertTrue(self.sync.request_budget.degraded)
        with self.assertRaises(fixtures.sync_mod.RequestBudgetRefused):
            self.sync._intervals_get("")
        fresh = self.sync._source_freshness({})
        self.assertEqual(fresh["budget"]["capacity_status"], "unknown")
        self.assertIsNone(fresh["budget"]["sync_remaining"])
        self.assertIn("private_state_unavailable", [w["code"] for w in fresh["warnings"]])
        self.assertFalse(list(self.data.rglob("*.json")))

    def test_incompatible_entry_is_individually_rejected(self):
        self.produce()
        store = self.sync._acquisition
        key, _ = store.key("", {})
        path = store.root / (key + ".json")
        entry = json.loads(path.read_text())
        entry["ttl"] = "invalid"
        path.write_text(json.dumps(entry))
        self.next_run()
        self.produce()
        self.assertEqual(len(self.sent), 5)

    def test_changed_deleted_added_rows_invalidate_only_affected_curve_and_message_keys(self):
        today = self.Date.now().date()
        self.rows = [{"id": "a", "type": "Ride", "start_date_local": today.isoformat(), "load": 1, "updated": "same"},
                     {"id": "b", "type": "VirtualRide", "start_date_local": today.isoformat(), "load": 2, "updated": "same"}]
        def acquire():
            self.assertTrue(self.sync.begin_tick())
            self.sync._intervals_get("activities", {"oldest": (self.Date.now().date() - timedelta(days=6)).isoformat(),
                                                    "newest": self.Date.now().date().isoformat()})
            for typ in ("Ride", "VirtualRide"):
                self.sync._intervals_get("power-curves", {"type": typ, "curves": "r." +
                    (self.Date.now().date() - timedelta(days=6)).isoformat() + "." + self.Date.now().date().isoformat()})
            for aid in ("a", "b"):
                self.sync._get_activity_messages(aid)
        acquire()
        self.next_run()
        acquire()
        self.assertEqual(len(self.sent), 1)
        for kind in ("changed", "deleted", "added"):
            prior_day = self.Date.now().date()
            self.next_run()
            if kind == "changed":
                self.rows[0]["load"] = 3
            elif kind == "deleted":
                self.rows.pop()
            else:
                self.rows.append({"id": "c", "type": "Ride", "start_date_local": today.isoformat(), "load": 4})
            acquire()
            curves = [q["type"][0] for _, p, q in self.sent if p.endswith("/power-curves")]
            self.assertEqual(curves, ["Ride", "VirtualRide"] if self.Date.now().date() != prior_day else
                             ["VirtualRide" if kind == "deleted" else "Ride"])
            messages = [p.split("/")[-2] for _, p, q in self.sent if p.endswith("/messages")]
            self.assertEqual(messages, ["a"] if kind == "changed" else ["b"] if kind == "deleted" else [])
        self.clock.now = datetime.fromtimestamp(self.clock.now, timezone.utc).replace(hour=0, minute=0, second=0).timestamp() + 86400
        self.new_sync()
        acquire()
        self.assertEqual(sum(p.endswith("/power-curves") for _, p, q in self.sent), 2)


if __name__ == "__main__":
    unittest.main()
