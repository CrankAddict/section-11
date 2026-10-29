"""189 delivery deadlines, using the producer's pinned noon/night clock harness."""
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import requests
import test_source_schedule as fixtures


Contract = fixtures.sync_mod.ExportFreshness


class DeadlineContract(unittest.TestCase):
    def setUp(self):
        self.clock = fixtures.BudgetClock()
        self.g = datetime.fromtimestamp(self.clock(), timezone.utc)
        self.local = {"mode": "local_scheduled", "interval": None}

    def build(self, interval=60, hold=None, pause=None, requested=60, previous=None):
        fresh = {"schedule": {"state": "paused" if pause else "running",
                              "requested_interval_seconds": requested,
                              "effective_interval_seconds": None if pause else interval},
                 "budget": {"hold_until": hold}, "warnings": []}
        if pause:
            fresh["warnings"] = [{"code": "budget_paused", "next_eligible_at": pause}]
        return Contract.build(Contract.stamp(self.g), self.local, fresh, self.g, previous)

    def test_local_choices_and_effective_ladder(self):
        for requested in (60, 120, 300, 600):
            for effective in (v for v in (60, 120, 300, 600) if v >= requested):
                with self.subTest(requested=requested, effective=effective):
                    row = self.build(effective, requested=requested)
                    self.assertEqual(row["expected_update_by"], Contract.stamp(
                        self.g + timedelta(seconds=max(600, effective * 2))))
                    self.assertEqual(row["reason"], "cadence")

    def test_absolute_hold_pause_and_later_boundary_across_midnight(self):
        self.g = self.g.replace(hour=23, minute=59, second=50)
        midnight = self.g.replace(hour=0, minute=0, second=0) + timedelta(days=1)
        hold = midnight + timedelta(minutes=2)
        original = self.build(600)
        cases = [(Contract.stamp(hold), None, "provider_hold", hold),
                 (None, Contract.stamp(midnight), "budget_pause", midnight),
                 (Contract.stamp(hold), Contract.stamp(midnight), "provider_hold", hold),
                 (Contract.stamp(self.g + timedelta(seconds=5)), Contract.stamp(midnight),
                  "budget_pause", midnight)]
        for h, m, reason, resume in cases:
            row = self.build(600, h, m, requested=120, previous=original)
            grace = 600 if m else 1200
            expected = max(Contract.parse(original["expected_update_by"]), resume + timedelta(seconds=grace))
            self.assertEqual(row["expected_update_by"], Contract.stamp(expected))
            self.assertEqual(row["reason"], reason)
            self.assertEqual(row["generated_at"], Contract.stamp(self.g))
        # Without a prior deadline, the requested interval supplies the baseline.
        row = self.build(pause=Contract.stamp(midnight), requested=600)
        self.assertEqual(row["expected_update_by"], Contract.stamp(midnight + timedelta(seconds=1200)))

    def test_missing_invalid_and_expired_controller_times_fail_closed(self):
        for hold in ("bad", "2026-10-28T12:00:00", Contract.stamp(self.g - timedelta(seconds=1))):
            self.assertIsNone(self.build(hold=hold)["expected_update_by"])
        for pause in ("bad", Contract.stamp(self.g - timedelta(seconds=1))):
            self.assertEqual(self.build(pause=pause)["reason"], "unknown_schedule")
        for interval in (None, True, "60", 0, 900):
            self.assertIsNone(self.build(interval)["expected_update_by"])
        missing = {"schedule": {"state": "paused", "requested_interval_seconds": 60}, "warnings": []}
        self.assertIsNone(Contract.build(Contract.stamp(self.g), self.local, missing, self.g)["expected_update_by"])

    def test_modes_and_hosted_cron_forms(self):
        for mode in (None, "", "local", "hosted_scheduled", "on_demand", "LOCAL_SCHEDULED"):
            self.assertEqual(Contract.context({} if mode is None else {"SECTION11_EXPORT_MODE": mode})["mode"], "unknown")
        for mode in ("manual", "local_scheduled"):
            self.assertEqual(Contract.context({"SECTION11_EXPORT_MODE": mode})["mode"], mode)
        env = {"GITHUB_ACTIONS": "true", "SECTION11_EXPORT_EVENT": "schedule", "SECTION11_EXPORT_MODE": "manual"}
        for cron, seconds in (("*/15 * * * *", 900), ("*/30 * * * *", 1800),
                              ("7,37 * * * *", 1800), ("37,7 * * * *", 1800),
                              ("7,22,37,52 * * * *", 900), ("0,15,30,45 * * * *", 900)):
            context = Contract.context(dict(env, SECTION11_EXPORT_CRON=cron))
            self.assertEqual(context, {"mode": "hosted_scheduled", "interval": seconds})
            row = Contract.build(Contract.stamp(self.g), context, {}, self.g)
            self.assertEqual(row["expected_update_by"], Contract.stamp(self.g + timedelta(seconds=2 * seconds + 3600)))
        for cron in ("", "7,37 8-20 * * *", "*/15 * * * 1-5", "7,37 * * * *; */15 8 * * *",
                     "7,22,37 * * * *", "7,7 * * * *", "0,60 * * * *", "*/5 * * * *", "@hourly"):
            self.assertEqual(Contract.context(dict(env, SECTION11_EXPORT_CRON=cron))["mode"], "unknown")
        env.update(SECTION11_EXPORT_EVENT="workflow_dispatch", SECTION11_EXPORT_CRON="7,37 * * * *")
        self.assertEqual(Contract.context(env)["mode"], "on_demand")
        for mode in ("manual", "on_demand", "unknown"):
            row = Contract.build(Contract.stamp(self.g), {"mode": mode, "interval": None}, {}, self.g)
            self.assertIsNone(row["expected_update_by"])
            self.assertEqual(row["reason"], "unknown_schedule" if mode == "unknown" else mode)

    def test_hosted_hold_extends_without_a_local_budget_pause(self):
        hold = self.g + timedelta(hours=3)
        fresh = {"budget": {"hold_until": Contract.stamp(hold)},
                 "schedule": {"state": "paused"}, "warnings": [{"code": "budget_paused"}]}
        row = Contract.build(Contract.stamp(self.g), {"mode": "hosted_scheduled", "interval": 1800}, fresh, self.g)
        self.assertEqual(row["reason"], "provider_hold")
        self.assertEqual(row["expected_update_by"], Contract.stamp(hold + timedelta(hours=2)))

    def test_utc_dst_naive_and_clock_rollback(self):
        for stamp in ("2026-10-25T02:30:00+02:00", "2026-10-25T02:30:00+01:00"):
            parsed = Contract.parse(stamp)
            row = Contract.build(stamp, self.local, {"schedule": {"effective_interval_seconds": 60}}, parsed)
            self.assertTrue(row["generated_at"].endswith("Z"))
            self.assertEqual(Contract.parse(row["expected_update_by"]) - parsed, timedelta(minutes=10))
        for stamp in (None, "bad", "2026-10-25T02:30:00"):
            self.assertIsNone(Contract.build(stamp, self.local, {}, self.g))
        row = Contract.build(Contract.stamp(self.g), self.local, {}, self.g - timedelta(seconds=1))
        self.assertEqual(row["generated_at"], Contract.stamp(self.g))
        self.assertIsNone(row["expected_update_by"])


class DeadlineProducer(unittest.TestCase):
    setUp = fixtures.SourceCase.setUp
    new_sync = fixtures.SourceCase.new_sync
    next_run = fixtures.SourceCase.next_run
    produce = fixtures.SourceCase.produce

    def local(self):
        patch = mock.patch.dict(os.environ, {"SECTION11_EXPORT_MODE": "local_scheduled", "GITHUB_ACTIONS": "false"})
        patch.start()
        self.addCleanup(patch.stop)

    def latest(self):
        return json.loads((self.data / "latest.json").read_text())

    def test_cold_slow_success_captures_once_at_end_and_save_does_not_renew(self):
        self.local()
        start = self.clock.now
        self.after_send = lambda path: setattr(self.clock, "now", self.clock.now + 12)
        data = self.produce()
        # Crossing UTC midnight can add the producer's existing daily read.
        self.assertGreaterEqual(self.clock.now - start, 156)
        self.assertEqual(self.clock.now - start, 12 * len(self.sent))
        export = data["export_freshness"]
        self.assertEqual(export["generated_at"], Contract.stamp(self.Date.now(timezone.utc)))
        self.assertEqual(export["generated_at"], data["metadata"]["last_updated"])
        self.assertEqual(set(export), {"version", "generated_at", "mode", "expected_update_by", "reason"})
        self.clock.now += 600
        self.sync.save_to_file(data, str(self.data / "latest.json"))
        self.assertEqual(self.latest()["export_freshness"], export)

    def test_status_ladder_preserves_training_and_not_due_does_not_slide(self):
        self.local()
        first = self.produce()
        self.next_run()
        self.sync.check_interval_seconds = 600
        self.assertIsNone(self.produce())
        after = self.latest()
        self.assertEqual(after["export_freshness"]["generated_at"], first["metadata"]["last_updated"])
        self.assertEqual(Contract.parse(after["export_freshness"]["expected_update_by"]) -
                         Contract.parse(first["metadata"]["last_updated"]), timedelta(minutes=20))
        for key in first:
            if key not in ("export_freshness", "source_freshness"):
                self.assertEqual(first[key], after[key], key)
        before = (self.data / "latest.json").read_bytes()
        for _ in range(3):
            self.next_run()
            self.sync.check_interval_seconds = 600
            self.assertIsNone(self.produce())
            self.assertEqual((self.data / "latest.json").read_bytes(), before)

    def test_real_hold_then_failed_generation_retains_last_coherent_deadline(self):
        self.local()
        self.clock.now = datetime.fromtimestamp(self.clock.now, timezone.utc).replace(hour=23, minute=58).timestamp()
        first = self.produce()
        self.next_run()
        budget = self.sync.request_budget
        with budget._lock():
            budget._load()
            budget.state["hold_until"] = self.clock.now + 300
            budget._save()
        self.assertIsNone(self.produce())
        held = self.latest()
        self.assertEqual(held["export_freshness"]["reason"], "provider_hold")
        self.assertEqual(held["metadata"], first["metadata"])
        frozen = (self.data / "latest.json").read_bytes()
        self.next_run()
        self.assertIsNone(self.produce())
        self.assertEqual((self.data / "latest.json").read_bytes(), frozen)
        # A genuine failure after hold expiry cannot hide lateness.
        self.next_run(400)
        with mock.patch.object(self.sync, "_intervals_get", side_effect=requests.exceptions.Timeout("offline failure")):
            with self.assertRaises(requests.exceptions.Timeout):
                self.produce()
        self.assertEqual((self.data / "latest.json").read_bytes(), frozen)
        self.next_run()
        retried = self.produce()
        self.assertGreater(retried["export_freshness"]["generated_at"], held["export_freshness"]["generated_at"])
        self.assertEqual(retried["export_freshness"]["reason"], "cadence")

    def test_absent_declaration_keeps_existing_upgrade_behavior_and_file_inventory(self):
        # --update still installs the same standalone script; no new config,
        # required CLI argument, environment variable or timer is introduced.
        with mock.patch.dict(os.environ, {"SECTION11_EXPORT_MODE": "", "GITHUB_ACTIONS": "false"}):
            first = self.produce()
            initial = {p.relative_to(self.data) for p in self.data.rglob("*") if p.is_file()}
            length = len(json.dumps(first["export_freshness"]))
            for _ in range(5):
                previous_day = self.Date.now().date()
                self.next_run()
                data = self.produce()
                self.assertEqual(len(self.sent), 6 if self.Date.now().date() != previous_day else 4)
                self.assertEqual([p.rsplit("/", 1)[-1] for _, p, _ in self.sent[:4]],
                                 ["activities", "wellness", "events", "events"])
                if len(self.sent) == 6:
                    self.assertEqual({p.rsplit("/", 1)[-1] for _, p, _ in self.sent[4:]},
                                     {"power-curves", "hr-curves"})
                self.assertEqual(data["export_freshness"]["mode"], "unknown")
                self.assertIsNone(data["export_freshness"]["expected_update_by"])
                # RFC3339 optionally includes up to six fractional digits.
                self.assertLessEqual(len(json.dumps(data["export_freshness"])), length + 7)
                self.assertEqual({p.relative_to(self.data) for p in self.data.rglob("*") if p.is_file()}, initial)

    def test_legacy_naive_status_only_transition_does_not_invent_generation(self):
        self.local()
        data = self.produce()
        data.pop("export_freshness")
        data["metadata"]["last_updated"] = "2026-10-28T12:00:00"
        (self.data / "latest.json").write_text(json.dumps(data))
        self.next_run()
        self.sync.check_interval_seconds = 300
        self.assertIsNone(self.produce())
        self.assertNotIn("export_freshness", self.latest())
        self.assertEqual(self.latest()["metadata"], data["metadata"])

    def test_authoritative_daily_pause_preserves_g_and_uses_reset_boundary(self):
        self.local()
        self.clock.now = datetime.fromtimestamp(self.clock.now, timezone.utc).replace(hour=0, minute=0, second=0).timestamp()
        first = self.produce()
        self.next_run()
        budget = self.sync.request_budget
        with budget._lock():
            budget._load()
            budget.state["days"][budget.day]["sync"] = {"seed": 6999}
            budget._save()
        self.assertIsNone(self.produce())
        paused = self.latest()
        row = paused["export_freshness"]
        boundary = next(w["next_eligible_at"] for w in paused["source_freshness"]["warnings"] if w["code"] == "budget_paused")
        self.assertEqual(row["reason"], "budget_pause")
        self.assertEqual(row["generated_at"], first["metadata"]["last_updated"])
        self.assertEqual(Contract.parse(row["expected_update_by"]), Contract.parse(boundary) + timedelta(minutes=10))
        self.next_run()
        self.assertIsNone(self.produce())
        self.assertEqual(self.latest()["export_freshness"], row)

    def test_update_without_mode_keeps_config_and_normal_export(self):
        import test_init_update_distribution as update
        before = update.legacy_install(github=False, dev=False)
        script = Path(fixtures.sync_mod.__file__).read_bytes()
        managed = dict(update.MANAGED, **{"examples/sync.py": script})
        reply = requests.Response()
        reply.status_code = 200
        reply._content = script
        with mock.patch.dict(os.environ, {"SECTION11_EXPORT_MODE": "", "GITHUB_ACTIONS": "false"}):
            with mock.patch.object(update.sync_mod.requests, "get", return_value=reply) as download:
                result = update.run_update(before, ["y"], manifest=update.manifest_for(managed))
            self.assertEqual(download.call_count, 1)
            self.assertEqual(result.files["section11/examples/sync.py"], script)
            for path, content in before.items():
                if path not in ("section11/examples/sync.py", "section11/manifest.json"):
                    self.assertEqual(result.files[path], content, path)
            self.assertEqual(self.produce()["export_freshness"]["mode"], "unknown")

    def test_every_setup_writes_fixed_shape_without_extra_files(self):
        cases = [("local_scheduled", "", "", "false"), ("manual", "", "", "false"),
                 ("hosted_scheduled", "schedule", "7,37 * * * *", "true"),
                 ("on_demand", "workflow_dispatch", "7,37 * * * *", "true")]
        inventories = []
        for mode, event, cron, hosted in cases:
            self.data = self.root / mode
            self.data.mkdir()
            with mock.patch.dict(os.environ, {"SECTION11_EXPORT_MODE": mode, "GITHUB_ACTIONS": hosted,
                    "SECTION11_EXPORT_EVENT": event, "SECTION11_EXPORT_CRON": cron}):
                self.new_sync()
                first = self.produce()
                row = first["export_freshness"]
                self.assertEqual(row["mode"], mode)
                self.assertEqual(row["reason"], mode if mode in ("manual", "on_demand") else "cadence")
                inventories.append({p.name for p in self.data.iterdir()})
                self.next_run(1800 if hosted == "true" else 60)
                self.assertEqual(set(self.produce()["export_freshness"]), set(row))
                self.assertEqual({p.name for p in self.data.iterdir()}, inventories[-1])
        self.assertTrue(all(paths == inventories[0] for paths in inventories))


class DeadlineConsumerContract(unittest.TestCase):
    def test_deadline_age_utc_and_warning_rules_remain_separate(self):
        root = Path(__file__).resolve().parents[2]
        for path in ("SECTION_11.md", "SKILL.md", "PROJECT_INSTRUCTIONS_AGENTIC.md", "PROJECT_INSTRUCTIONS_WEB.md"):
            text = (root / path).read_text()
            self.assertIn("Use export_freshness.generated_at for snapshot age (legacy fallback: metadata.last_updated)", text)
            self.assertIn("Mention source_stale once only when its named sources affect the answer", text)
            self.assertIn("operational notices, not data-quality warnings", text)
            self.assertIn("Metric dates, native availability, coverage, health/readiness and forecast-expiry rules still apply", text)
        protocol = (root / "SECTION_11.md").read_text()
        self.assertIn("With no known deadline, expect under 12 hours", protocol)
        self.assertIn("Beyond 24 hours, request refresh", protocol)
        self.assertIn("even during a permitted pause", protocol)
        self.assertIn("If time or timezone is unknown, say age cannot be verified", protocol)
        self.assertIn("treat a future generation timestamp as fresh", protocol)
        self.assertIn("metadata.last_updated is also UTC (Z) from sync 3.164", protocol)
        workflow = (root / "examples/json-auto-sync/auto-sync.yml").read_text()
        self.assertIn("SECTION11_EXPORT_EVENT: ${{ github.event_name }}", workflow)
        self.assertIn("SECTION11_EXPORT_CRON: ${{ github.event.schedule }}", workflow)


if __name__ == "__main__":
    unittest.main()
