"""Upgrade adoption is local provenance, never a new acquisition timestamp."""
import json
import unittest
from datetime import timedelta

import test_source_schedule as fixtures
import test_decoupling_detail as decoupling


class LegacyAdoption(unittest.TestCase):
    setUp = fixtures.SourceCase.setUp
    new_sync = fixtures.SourceCase.new_sync
    next_run = fixtures.SourceCase.next_run
    produce = fixtures.SourceCase.produce

    def legacy_folder(self):
        # Leave room for the cold seed and two warm reads before the selected
        # base, so date-window refreshes are not mistaken for adoption sends.
        self.clock.now -= 120
        day = (self.Date.now() - timedelta(days=4)).strftime("%Y-%m-%d")
        self.rows = [decoupling.raw(id="legacy", start_date_local=day + "T08:00:00",
            start_date=day + "T08:00:00Z", icu_training_load=50, stream_types=["watts", "heartrate"])]
        self.reply = lambda prepared, path, query: fixtures.response(200, decoupling.body()) if path.endswith("/power-vs-hr") else None
        self.produce()
        # Native v3.163-shaped output has no acquisition-store provenance. Keep
        # its validated payloads and settled native state, as on an upgrade.
        path = self.data / "intervals.json"
        native = json.loads(path.read_text())
        for state in native["fetch_state"].values():
            for endpoint in ("intervals", "streams"):
                state[endpoint]["status"] = "ok"
        path.write_text(json.dumps(native))
        store = self.sync._acquisition
        for key, entry in store.entries.items():
            if entry["group"].startswith("activity_"):
                (store.root / (key + ".json")).unlink()
        return store.root

    def test_upgrade_producer_adopts_without_extra_sends_or_stale_warning(self):
        private = self.legacy_folder()
        self.next_run()
        data = self.produce()
        self.assertEqual(len(self.sent), 4)
        self.assertFalse(any(w["code"] == "source_stale" for w in data["source_freshness"]["warnings"]))
        for group in ("activity_power", "activity_decoupling"):
            source = data["source_freshness"]["sources"][group]
            self.assertEqual((source["status"], source["coverage"], source["reason"]),
                             ("fresh", "complete", "legacy_cache_adopted"))
            self.assertEqual(source["provenance"], "adopted")
            self.assertIsNotNone(source["adopted_at"])
            for field in ("last_success_at", "source_acquired_at", "age_seconds", "last_attempt_at"):
                self.assertIsNone(source[field], field)
        snapshots = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in private.glob("*.json")
                     if json.loads(p.read_text()).get("provenance") == "adopted"}
        self.assertGreaterEqual(len(snapshots), 2)
        self.next_run()
        self.produce()
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshots}, snapshots)
        self.assertFalse(any(p.name in ("sources", "ledger.json", "ledger.lock") for p in self.data.rglob("*")))

    def test_invalid_legacy_power_warns_and_invalidated_decoupling_refetches(self):
        self.legacy_folder()
        path = self.data / "latest.json"
        data = json.loads(path.read_text())
        data["recent_activities"][0]["power_curve"] = {"5": -1}
        data["recent_activities"][0]["decoupling_cache"]["activity_key"] = "old-key"
        path.write_text(json.dumps(data))
        self.next_run()
        data = self.produce()
        source = data["source_freshness"]["sources"]["activity_power"]
        self.assertNotEqual(source["status"], "fresh")
        self.assertNotEqual(source["reason"], "legacy_cache_adopted")
        self.assertTrue(any(w["code"] == "source_stale" for w in data["source_freshness"]["warnings"]))
        self.assertEqual(sum(p.endswith("/power-vs-hr") for _, p, _ in self.sent), 1)
        acquired = data["source_freshness"]["sources"]["activity_decoupling"]
        self.assertIsNotNone(acquired["last_success_at"])
        self.assertNotEqual(acquired["reason"], "legacy_cache_adopted")

    def test_terrain_adoption_and_real_failure_are_not_confused(self):
        self.assertTrue(self.sync.begin_tick())
        terrain = {"total_distance_km": 20, "total_elevation_m": 100,
                   "elevation_per_km": 5, "climbs": [], "descents": []}
        self.sync._build_terrain_for_activity({"id": "valid", "type": "Ride"}, {"valid": {"terrain_summary": terrain}})
        source = self.sync._acquisition.source_status("activity_terrain")
        self.assertEqual(source["reason"], "legacy_cache_adopted")
        self.assertEqual(self.sent, [])
        self.sync._fetch_activity_power_curve("failed")
        store = self.sync._acquisition
        key, _ = store.key("activity_power/failed", {})
        entry = store.entries[key]
        entry.update(status="deferred", reason="request_budget")
        store.save(entry)
        before = (store.root / (key + ".json")).read_bytes()
        self.sync._build_power_curve_for_activity({"id": "failed", "moving_time": 300}, {"failed": {"power_curve": {"5": 200}}}, True)
        self.assertEqual((store.root / (key + ".json")).read_bytes(), before)
        self.assertEqual(store.source_status("activity_power")["status"], "deferred")

    def test_settled_interval_and_dfa_payloads_are_adopted_without_fetch(self):
        self.assertTrue(self.sync.begin_tick())
        day = (self.Date.now() - timedelta(days=4)).strftime("%Y-%m-%d")
        entry = {"activity_id": "legacy", "date": day,
                 "intervals": [{"type": "WORK", "duration_secs": 1800}],
                 "dfa": {"quality": {"sufficient": False}}}
        native = {"script_hash": self.sync.script_hash, "schema_version": 2, "activities": [entry],
                  "fetch_state": {"legacy": {"date": day, "intervals": {"status": "ok"}, "streams": {"status": "ok"}}}}
        path = self.data / "intervals.json"
        path.write_text(json.dumps(native))
        activity = {"id": "legacy", "type": "VirtualRide", "start_date_local": day + "T08:00:00"}
        self.sync._generate_intervals([activity], {"legacy"})
        self.assertEqual(self.sent, [])
        for group in ("activity_details", "activity_streams"):
            source = self.sync._acquisition.source_status(group)
            self.assertEqual((source["status"], source["reason"]), ("fresh", "legacy_cache_adopted"))
            self.assertIsNone(source["last_success_at"])

    def test_pending_native_refresh_is_not_adopted(self):
        self.assertTrue(self.sync.begin_tick())
        day = (self.Date.now() - timedelta(days=4)).strftime("%Y-%m-%d")
        native = {"script_hash": self.sync.script_hash, "schema_version": 2,
            "activities": [{"activity_id": "pending", "date": day, "intervals": [{"type": "WORK"}]}],
            "fetch_state": {"pending": {"date": day, "intervals": {"status": "pending",
                "next_retry_at": (self.Date.now() + timedelta(hours=1)).isoformat()}}}}
        (self.data / "intervals.json").write_text(json.dumps(native))
        self.sync._generate_intervals([{"id": "pending", "type": "VirtualRide", "start_date_local": day}], {"pending"})
        self.assertEqual(self.sent, [])
        self.assertIsNone(self.sync._acquisition.source_status("activity_details"))

    def test_invalid_native_cache_stays_stale_but_mixed_valid_old_cache_is_fresh(self):
        self.assertTrue(self.sync.begin_tick())
        store = self.sync._acquisition
        store.adopt("activity_power", "legacy", True)
        store.adopt("activity_power", "legacy", False)
        self.assertEqual(store.source_status("activity_power")["status"], "stale")
        store.adopt("activity_terrain", "old", True)
        key, descriptor = store.key("activity_terrain/known", {})
        store.entries[key] = dict(store.entries[next(k for k, e in store.entries.items() if e["group"] == "activity_terrain")],
            key=key, descriptor=descriptor, provenance="acquired", last_success=self.clock() - 86401, reason=None)
        store.consumed[key] = store.entries[key]
        source = store.source_status("activity_terrain")
        self.assertEqual((source["status"], source["coverage"], source["reason"]),
                         ("fresh", "complete", "legacy_cache_adopted"))
        self.assertIsNone(source["last_success_at"])
        store.adopt("activity_terrain", "known", False)
        self.assertEqual(store.source_status("activity_terrain")["status"], "stale")

    def test_acquired_ride_stays_fresh_over_three_days_without_extra_native_sends(self):
        start = self.clock()
        day = (self.Date.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        self.rows = [decoupling.raw(id="steady", start_date_local=day + "T08:00:00",
            start_date=day + "T08:00:00Z", icu_training_load=50, stream_types=["watts", "heartrate"])]
        self.reply = lambda prepared, path, query: fixtures.response(200, decoupling.body()) if path.endswith("/power-vs-hr") else None
        cold = self.produce()["source_freshness"]
        self.assertEqual(len(self.sent), 25)
        self.assertFalse(any(w["code"] == "source_stale" for w in cold["warnings"]))
        for elapsed, expected in ((60, 4), (25 * 3600, 18), (25 * 3600 + 60, 4), (3 * 86400, 17)):
            with self.subTest(elapsed=elapsed):
                self.clock.now = start + elapsed
                self.new_sync()
                data = self.produce()
                fresh = data["source_freshness"]
                print("Native cache steady state:", elapsed, "seconds;", len(self.sent), "sends;",
                      [p.rsplit("/", 1)[-1] for _, p, _ in self.sent])
                self.assertEqual(len(self.sent), expected)
                self.assertFalse(any(w["code"] == "source_stale" for w in fresh["warnings"]))
                for group, source in fresh["sources"].items():
                    if not group.startswith("activity_"):
                        continue
                    self.assertEqual(source["status"], "fresh", group)
                    self.assertIsNone(source["max_age_seconds"])
                    self.assertIsNone(source["next_due_at"])
                    acquired = cold["sources"][group]["last_success_at"]
                    if acquired is not None:
                        self.assertIsNotNone(source["last_success_at"], group)
                        # Sparse detail/stream fixtures retain their native retry
                        # ladder. Successful sends, never cache reuse, may renew it.
                        if group in ("activity_power", "activity_decoupling"):
                            self.assertEqual(source["last_success_at"], acquired, group)
                            self.assertGreater(source["age_seconds"], cold["sources"][group]["age_seconds"], group)
                        else:
                            entries = [e for e in self.sync._acquisition.entries.values() if e["group"] == group]
                            self.assertEqual(source["last_success_at"], self.sync._acquisition.stamp(
                                min(e["last_success"] for e in entries)), group)
                self.assertFalse(any(p.endswith(("/power-curve.json", "/power-vs-hr")) for _, p, _ in self.sent))

    def test_scheduled_sources_expire_and_deferred_refresh_keeps_real_age(self):
        self.assertTrue(self.sync.begin_tick())
        store = self.sync._acquisition
        store.acquire("profile", "", {}, lambda: self.profile, 3600)
        acquired = store.source_status("profile")["last_success_at"]
        self.clock.now += 3601
        # Current-invocation success stays fresh; a retained/status-only
        # evaluation still applies the existing scheduled expiry.
        self.assertEqual(store.source_status("profile")["status"], "fresh")
        source = store.source_status("profile", retained=True)
        self.assertEqual((source["status"], source["reason"]), ("stale", "validity_expired"))
        self.assertEqual(source["last_success_at"], acquired)
        def refused():
            raise fixtures.sync_mod.RequestBudgetRefused("synthetic refusal")
        store.acquire("profile", "", {}, refused, 3600)
        source = store.source_status("profile")
        self.assertEqual((source["status"], source["reason"]), ("deferred", "request_budget"))
        self.assertEqual(source["last_success_at"], acquired)
        self.assertEqual(source["age_seconds"], 3601)

    def test_all_native_groups_keep_old_acquisition_in_retained_exports(self):
        self.assertTrue(self.sync.begin_tick())
        store = self.sync._acquisition
        store.adopt("activity_power", "seed", True)
        seed = next(iter(store.entries.values()))
        store.consumed.clear()
        previous = {}
        for group in ("activity_details", "activity_streams", "activity_power",
                      "activity_decoupling", "activity_terrain", "route_attachments"):
            key, descriptor = store.key(group + "/old", {})
            entry = dict(seed, group=group, key=key, descriptor=descriptor, provenance="acquired",
                         last_success=self.clock() - 3 * 86400, reason=None)
            entry.pop("adopted_at", None)
            store.consumed[key] = entry
            source = store.source_status(group)
            self.assertEqual(source["status"], "fresh", group)
            self.assertEqual(source["age_seconds"], 3 * 86400, group)
            self.assertIsNone(source["max_age_seconds"])
            self.assertIsNone(source["next_due_at"])
            previous[group] = source
        store.consumed.clear()
        self.clock.now += 60
        retained = self.sync._source_freshness({"source_freshness": {"sources": previous}}, retained=True)
        for group, old in previous.items():
            source = retained["sources"][group]
            self.assertEqual(source["status"], "fresh", group)
            self.assertEqual(source["last_success_at"], old["last_success_at"])
            self.assertEqual(source["age_seconds"], 3 * 86400 + 60)
        self.assertEqual(self.sent, [])

    def test_acquired_invalid_power_warns_and_changed_decoupling_refetches(self):
        self.legacy_folder()
        self.next_run()
        self.produce()
        store = self.sync._acquisition
        for entry in store.entries.values():
            if entry.get("provenance") == "adopted":
                entry.update(provenance="acquired", last_success=self.clock() - 90000, reason=None)
                entry.pop("adopted_at", None)
                store.save(entry)
        path = self.data / "latest.json"
        data = json.loads(path.read_text())
        data["recent_activities"][0]["power_curve"] = {"5": -1}
        data["recent_activities"][0]["decoupling_cache"]["activity_key"] = "changed"
        path.write_text(json.dumps(data))
        self.next_run()
        data = self.produce()
        sources = data["source_freshness"]["sources"]
        self.assertEqual((sources["activity_power"]["status"], sources["activity_power"]["reason"]),
                         ("stale", "invalid_native_cache"))
        self.assertEqual(sum(p.endswith("/power-vs-hr") for _, p, _ in self.sent), 1)
        self.assertEqual(sources["activity_decoupling"]["status"], "fresh")
        self.assertLess(sources["activity_decoupling"]["age_seconds"], 60)


if __name__ == "__main__":
    unittest.main()
