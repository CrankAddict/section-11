"""Hosted producer activation must not depend on delivery-deadline support."""
import copy
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import test_hosted_cache as hosted

mod = hosted.mod


class HostedSchedules(unittest.TestCase):
    produce = hosted.HostedCase.produce
    publish = hosted.HostedCase.publish

    def setUp(self):
        hosted.HostedCase.setUp(self)
        self.clock.now = datetime(2026, 11, 4, 12, tzinfo=timezone.utc).timestamp()
        # Use production selection, not the fixture's injected hosted controller.
        for patch in (mock.patch.object(mod.IntervalsSync, "_budget_factory", mod.RequestBudget),
                      mock.patch.object(mod.time, "time", self.clock),
                      mock.patch.object(mod.time, "sleep", self.clock.sleep),
                      mock.patch.object(mod.RequestBudget, "SEND_INTERVAL", 0)):
            patch.start()
            self.addCleanup(patch.stop)

    def new_sync(self):
        sync = hosted.source.SourceCase.new_sync(self)
        del sync._request_budget
        return sync

    def new_runner(self, seconds=0, restore=True):
        hosted.HostedCase.new_runner(self, seconds, restore)
        del self.sync._request_budget

    def assert_freshness(self, data, mode, interval=None):
        # Frozen baseline contract, serialized with the same field order.
        expected = {"version": 1, "generated_at": "2026-11-04T12:00:00Z",
                    "mode": mode, "expected_update_by": None,
                    "reason": "unknown_schedule" if mode == "unknown" else mode}
        generated = datetime.fromtimestamp(self.clock(), timezone.utc)
        expected["generated_at"] = generated.isoformat().replace("+00:00", "Z")
        if interval is not None:
            grace = max(600, 2 * interval) if mode == "local_scheduled" else 2 * interval + 3600
            expected.update(expected_update_by=(generated + timedelta(seconds=grace)).isoformat().replace("+00:00", "Z"),
                            reason="cadence")
        self.assertEqual(json.dumps(data["export_freshness"]).encode(), json.dumps(expected).encode())

    def slow_sends(self):
        return [path for _, path, _ in self.sent if path.endswith(
            ("/i123", "/power-curves", "/hr-curves", "/messages"))]

    def test_cold_and_restored_runs_for_all_schedule_shapes_and_dispatch(self):
        cases = [("schedule", cron, "unknown", None) for cron in (
            "7 */3 * * *", "7 * * * *",
            "7,27,47 6-21 * * *", "7 0-5,22-23 * * *",
            "7,27,47 6-23 * * *", "7 0-5 * * *",
            "7,22,37,52 7-18 * * *", "7 0-6,19-23 * * *",
            "7 6 * * 1-5")]
        cases += [("schedule", "7,37 * * * *", "hosted_scheduled", 1800),
                  ("schedule", "*/15 * * * *", "hosted_scheduled", 900),
                  ("workflow_dispatch", "", "on_demand", None),
                  ("Sync timer", "", "hosted_scheduled", 1800),
                  ("Sync timer", "7 */3 * * *", "hosted_scheduled", 1800)]
        with mock.patch.object(hosted.runs.FrozenDate, "fixed", self.Date.now(timezone.utc), create=True):
            self.rows = hosted.runs.activities()[:1]
        for event, cron, mode, interval in cases:
            with self.subTest(event=event, cron=cron), mock.patch.dict(os.environ, {
                    "GITHUB_EVENT_NAME": "workflow_dispatch" if event == "Sync timer" else event,
                    "SECTION11_EXPORT_EVENT": event,
                    "SECTION11_EXPORT_CRON": cron}):
                self.remote, self.published = None, {}
                self.new_runner()
                cold = self.produce()
                self.assert_freshness(cold, mode, interval)
                self.assertTrue(self.publish(cold))
                self.assertIs(type(self.sync.request_budget), mod.HostedRequestBudget)
                self.assertEqual(cold["source_freshness"]["budget"]["scope"], "hosted_invocation")
                self.assertTrue(self.slow_sends())
                envelope = json.loads(self.remote)
                self.assertEqual({row["group"] for row in envelope["entries"]},
                                 set(mod.HostedSlowCache.GROUPS))
                self.new_runner(60)
                restored = self.produce()
                self.assertIs(type(self.sync.request_budget), mod.HostedRequestBudget)
                budget = restored["source_freshness"]["budget"]
                self.assertEqual(budget["scope"], "hosted_invocation")
                self.assertIsNone(budget["sync_daily_limit"])
                self.assertIsNone(budget["sync_remaining"])
                self.assertEqual(self.slow_sends(), [])
                self.assertEqual(self.sync._hosted_cache.original, self.remote)
                self.assertFalse(self.publish(restored))
                for group in mod.HostedSlowCache.GROUPS:
                    self.assertEqual(restored["source_freshness"]["sources"][group]["last_success_at"],
                                     cold["source_freshness"]["sources"][group]["last_success_at"])
                self.assert_freshness(restored, mode, interval)
                print("Hosted cold/restore verified:", event, cron or "(no cron)",
                      "restored sends", len(self.sent), "slow sends", len(self.slow_sends()))

    def test_local_and_manual_keep_daily_controller_and_private_cache(self):
        for mode in ("local_scheduled", "manual"):
            with self.subTest(mode=mode), mock.patch.dict(os.environ, {
                    "GITHUB_ACTIONS": "", "SECTION11_EXPORT_MODE": mode}):
                self.new_runner(60, restore=False)
                cold = self.produce()
                self.assertIs(type(self.sync.request_budget), mod.RequestBudget)
                self.assertIsNone(self.sync._hosted_cache.stage)
                self.assertFalse((self.stage / "next.json").exists())
                self.assertEqual(cold["source_freshness"]["budget"]["scope"], "local_data_folder_key_athlete")
                self.assert_freshness(cold, mode, 60 if mode == "local_scheduled" else None)
                self.clock.now += 60
                self.new_sync()  # Local private state stays in the same data folder.
                warm = self.produce()
                self.assertIs(type(self.sync.request_budget), mod.RequestBudget)
                self.assertEqual(len(self.sent), 4)
                self.assertEqual(self.slow_sends(), [])
                self.assertEqual(warm["source_freshness"]["sources"]["profile"]["last_success_at"],
                                 cold["source_freshness"]["sources"]["profile"]["last_success_at"])
                self.assert_freshness(warm, mode, 60 if mode == "local_scheduled" else None)

    def test_missing_or_invalid_hosted_identity_disables_cache(self):
        base = dict(os.environ, SECTION11_EXPORT_EVENT="schedule", SECTION11_EXPORT_CRON="7 */3 * * *")
        for field, value in (("GITHUB_ACTIONS", None), ("GITHUB_ACTIONS", "TRUE"),
                             ("SECTION11_EXPORT_EVENT", None), ("SECTION11_EXPORT_EVENT", "push"),
                             ("GITHUB_REPOSITORY_ID", None), ("GITHUB_REPOSITORY_ID", "invalid"),
                             ("GITHUB_REF_NAME", ""), ("RUNNER_TEMP", ""), ("GITHUB_WORKSPACE", "")):
            env = dict(base)
            if value is None:
                env.pop(field, None)
            else:
                env[field] = value
            with self.subTest(field=field, value=value), mock.patch.dict(os.environ, env, clear=True):
                self.new_sync()
                self.sync._acquisition = None
                self.assertIsNone(mod.HostedSlowCache(self.sync).stage)
                if field in ("GITHUB_ACTIONS", "SECTION11_EXPORT_EVENT"):
                    self.assertIs(type(self.sync.request_budget), mod.RequestBudget)

    def test_slower_schedule_rejects_wrong_scope_and_corrupt_cache(self):
        with mock.patch.dict(os.environ, {"SECTION11_EXPORT_EVENT": "schedule",
                                          "SECTION11_EXPORT_CRON": "7 */3 * * *"}):
            self.new_runner()
            self.assertTrue(self.publish(self.produce()))
            good = json.loads(self.remote)
            bad = [b"{"]
            for field, value in (("repository", "54321"), ("branch", "other"),
                                 ("producer", "other"), ("athlete", "0" * 64)):
                envelope = copy.deepcopy(good)
                envelope["scope"][field] = value
                bad.append(json.dumps(envelope).encode())
            for payload in bad:
                with self.subTest(payload=payload[:1]):
                    self.remote = payload
                    self.new_runner(60)
                    data = self.produce()
                    self.assertIsNone(self.sync._hosted_cache.original)
                    self.assertTrue(self.slow_sends())
                    self.assertTrue(self.publish(data))

    def test_missing_or_published_staging_uses_normal_reads(self):
        with mock.patch.dict(os.environ, {"SECTION11_EXPORT_EVENT": "schedule",
                                          "SECTION11_EXPORT_CRON": "7 */3 * * *"}):
            for nested in (False, True):
                with self.subTest(nested=nested):
                    self.new_runner(60, restore=False)
                    runner_temp = self.data if nested else self.root / "unprepared"
                    if nested:
                        (runner_temp / "section11-slow-cache").mkdir()
                    with mock.patch.dict(os.environ, {"RUNNER_TEMP": str(runner_temp)}):
                        data = self.produce()
                    self.assertIs(type(self.sync.request_budget), mod.HostedRequestBudget)
                    self.assertIsNone(self.sync._hosted_cache.stage)
                    self.assertTrue(self.slow_sends())
                    self.assertFalse(self.publish(data))
