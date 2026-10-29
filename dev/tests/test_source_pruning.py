"""Offline retention, saturation and ninety-day producer comparisons."""
import contextlib
import io
import json
import os
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from _harness import load_module_by_path
import test_decoupling_detail as decoupling
import test_source_schedule as fixtures


class Producer(unittest.TestCase):
    setUp = fixtures.SourceCase.setUp
    new_sync = fixtures.SourceCase.new_sync
    next_run = fixtures.SourceCase.next_run
    produce = fixtures.SourceCase.produce

    def healthy_reply(self, prepared, path, query):
        end = path.rsplit("/", 1)[-1]
        if end == "activities":
            return fixtures.response(200, [a for a in self.rows
                if query["oldest"][0] <= a["start_date_local"][:10] <= query["newest"][0]])
        if end == "events":
            return fixtures.response(200, [] if "category" in query else [e for e in self.events
                if query["oldest"][0] <= e["start_date_local"][:10] <= query["newest"][0]])
        if end == "power-vs-hr":
            return fixtures.response(200, decoupling.body())
        if end == "power-curve.json" and int(path.split("/")[-2].split("-")[-1]) % 3 == 0:
            return fixtures.response(404)
        if end == "messages":
            return fixtures.response(200, [{"content": "Synthetic activity note"}])
        if "/attachment/" in path:
            result = fixtures.response(200)
            result._content = (b'<gpx><trk><trkseg><trkpt lat="55" lon="12"><ele>5</ele></trkpt>'
                b'<trkpt lat="55.01" lon="12.01"><ele>25</ele></trkpt>'
                b'<trkpt lat="55.02" lon="12.02"><ele>5</ele></trkpt></trkseg></trk></gpx>')
            return result
        if "/activity/" in path and (end == "streams" or end.startswith("ride-")):
            return fixtures.response(404)

    def add_ride(self, number, age=0):
        day = (self.Date.now() - timedelta(days=age)).strftime("%Y-%m-%d")
        self.rows.append(decoupling.raw(id="ride-" + str(number), type="Ride",
            start_date_local=day + "T08:00:00", start_date=day + "T08:00:00Z",
            icu_training_load=50, stream_types=["watts", "heartrate"]))

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.sync._acquisition.root.glob("*.json")}


class Pruning(Producer):
    def setUp(self):
        super().setUp()
        self.reply = self.healthy_reply

    def obsolete(self, group="activity_power", resource="obsolete"):
        store = self.sync._acquisition
        store.adopt(group, resource, True, "http_404")
        key, _ = store.key(group + "/" + resource, {})
        store.consumed.pop(key)
        return store.root / (key + ".json")

    def test_upgrade_prunes_without_sends_or_warnings_and_keeps_provenance(self):
        self.clock.now -= 120  # Both upgrade ticks stay in one date scope at either injected base.
        self.new_sync()
        self.add_ride(0)
        self.produce()
        path = self.obsolete()
        kept = self.snapshot()
        self.next_run()
        data = self.produce()
        self.assertEqual(len(self.sent), 4)
        self.assertFalse(path.exists())
        self.assertEqual(data["source_freshness"]["warnings"], [])
        for key, entry in self.sync._acquisition.entries.items():
            if entry["group"].startswith("activity_"):
                self.assertEqual((self.sync._acquisition.root / (key + ".json")).read_bytes(),
                                 kept[key + ".json"])

    def test_leaves_window_then_edited_back_refetches(self):
        self.add_ride(0, age=27)
        self.produce()
        store = self.sync._acquisition
        key, _ = store.key("activity_power/ride-0", {})
        path = store.root / (key + ".json")
        self.assertTrue(path.exists())
        self.next_run(86400)
        self.produce()
        self.assertFalse(path.exists())
        self.assertFalse(any("/activity/ride-0/" in p for _, p, _ in self.sent))
        self.rows[0]["start_date_local"] = self.Date.now().strftime("%Y-%m-%dT08:00:00")
        self.rows[0]["start_date"] = self.rows[0]["start_date_local"] + "Z"
        self.next_run()
        data = self.produce()
        self.assertTrue(path.exists())
        self.assertTrue(any(p.endswith("/ride-0/power-curve.json") for _, p, _ in self.sent))
        self.assertEqual(data["source_freshness"]["sources"]["activity_power"]["status"], "fresh")

    def test_obsolete_messages_routes_and_curve_descriptors_leave_without_sends(self):
        self.produce()
        store = self.sync._acquisition
        route = self.obsolete("route_attachments", "a" * 64)
        keys = []
        for group, endpoint, params, payload in (
                ("messages", "activity/removed/messages", {}, ["Synthetic note"]),
                ("aggregate_curves", "power-curves", {"type": "obsolete"}, {"list": []})):
            store.acquire(group, endpoint, params, lambda: payload, 21600)
            key, _ = store.key(endpoint, params)
            keys.append(key)
        self.next_run()
        self.produce()
        self.assertEqual(len(self.sent), 4)
        self.assertFalse(route.exists())
        self.assertTrue(all(not (store.root / (key + ".json")).exists() for key in keys))

    def test_coherent_pruning_resumes_pending_persistence_without_raising_cap(self):
        data = self.produce()
        store = self.sync._acquisition
        obsolete = [self.obsolete(resource=str(n)) for n in (1, 2)]
        store.entry_limit = len(self.snapshot())
        self.sync._power_curve_fetches_used = 0
        self.sync._fetch_activity_power_curve("ride-901")
        self.assertEqual(len(store._pending), 1)
        entry = next(iter(store._pending.values()))
        acquired = entry["last_success"]
        store.prune(data)
        self.assertFalse(any(path.exists() for path in obsolete))
        self.assertEqual(store._pending, {})
        persisted = json.loads((store.root / (entry["key"] + ".json")).read_text())
        self.assertEqual(persisted["last_success"], acquired)
        self.assertNotIn("source_store_capacity", [w["code"] for w in data["source_freshness"]["warnings"]])

    def test_consumed_and_retained_interval_ids_are_never_deleted(self):
        data = self.produce()
        store = self.sync._acquisition
        consumed = self.obsolete(resource="consumed")
        store.consumed[consumed.stem] = store.entries[consumed.stem]
        retained = self.obsolete(resource="retained")
        self.sync._intervals_data["fetch_state"]["retained"] = {"date": "synthetic"}
        gone = self.obsolete()
        store.prune(data)
        self.assertTrue(consumed.exists())
        self.assertTrue(retained.exists())
        self.assertFalse(gone.exists())

    def test_failed_deferred_and_incomplete_generation_prune_nothing(self):
        self.produce()
        path = self.obsolete()
        for kind in ("failed", "deferred", "incomplete"):
            with self.subTest(kind=kind):
                self.next_run()
                if kind == "failed":
                    self.reply = lambda prepared, p, q: fixtures.response(503) if p.endswith("/wellness") else self.healthy_reply(prepared, p, q)
                    self.produce()
                elif kind == "deferred":
                    self.reply = lambda prepared, p, q: fixtures.response(429, headers={"Retry-After": "60"}) if p.endswith("/wellness") else self.healthy_reply(prepared, p, q)
                    self.produce()
                else:
                    self.reply = self.healthy_reply
                    with mock.patch.object(self.sync, "_format_activities", side_effect=ValueError("synthetic generation failure")):
                        with self.assertRaises(ValueError):
                            self.produce()
                self.assertTrue(path.exists())

    def test_corrupt_foreign_and_concurrent_replacement_are_untouched(self):
        data = self.produce()
        store = self.sync._acquisition
        replaced = self.obsolete()
        self.next_run()
        self.sync.begin_tick()
        store = self.sync._acquisition
        # A replacement after this reader loaded the file belongs to a newer writer.
        entry = json.loads(replaced.read_text())
        entry["generation"] = 9
        self.sync.request_budget._atomic(replaced, entry)
        corrupt = store.root / ("a" * 64 + ".json")
        corrupt.write_text("{")
        foreign = store.root / "foreign.json"
        foreign.write_text('{"owner":"elsewhere"}')
        outside = store.root.parent / "unrelated.json"
        outside.write_text("unchanged")
        linked = store.root / ("b" * 64 + ".json")
        linked.symlink_to(outside)
        before = {p: p.read_bytes() for p in (replaced, corrupt, foreign, outside)}
        self.produce()
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertTrue(linked.is_symlink())

    def test_prune_does_not_change_budget_files_and_is_oldest_first(self):
        data = self.produce()
        store, budget = self.sync._acquisition, self.sync.request_budget
        paths = []
        for number in (3, 1, 2):
            path = self.obsolete(resource=str(number))
            entry = store.entries[path.stem]
            entry["adopted_at"] = number
            store.save(entry)
            paths.append(path)
        budget_files = {p: p.read_bytes() for p in budget.root.iterdir() if p.is_file()}
        removed = []
        unlink = Path.unlink
        def record(path, *args, **kwargs):
            self.assertIsNotNone(budget._handle)
            removed.append(path)
            return unlink(path, *args, **kwargs)
        with mock.patch.object(Path, "unlink", record):
            store.prune(data)
        self.assertEqual(removed, [paths[1], paths[2], paths[0]])
        self.assertEqual({p: p.read_bytes() for p in budget_files}, budget_files)

    def test_count_and_byte_caps_refuse_growth_keep_true_times_and_resume(self):
        self.clock.now += 3600  # Keep the once-per-day comparison within one UTC day at either base.
        self.new_sync()
        for cap in ("entry_limit", "byte_limit"):
            with self.subTest(cap=cap):
                self.next_run(86400)
                self.produce()
                self.next_run()
                self.assertTrue(self.sync.begin_tick())
                store = self.sync._acquisition
                original = getattr(store, cap)
                setattr(store, cap, 0)
                before = self.snapshot()
                with mock.patch.object(self.sync.request_budget, "private_log") as logged:
                    for number in ((901, 902) if cap == "entry_limit" else (1901, 1903)):
                        self.sync._power_curve_fetches_used = 0
                        result = self.sync._fetch_activity_power_curve("ride-" + str(number))
                        self.assertEqual(result[0], "ok")
                    self.assertEqual(sum("cache is full" in call.args[0] for call in logged.call_args_list), 1)
                self.assertEqual(self.snapshot(), before)
                source = store.source_status("activity_power")
                self.assertEqual(source["status"], "fresh")
                self.assertIsNotNone(source["last_success_at"])
                self.assertEqual([w["code"] for w in store.warnings], ["source_store_capacity"])
                # The same UTC day cannot emit a second log line, even after restart.
                self.next_run()
                self.sync.begin_tick()
                store = self.sync._acquisition
                setattr(store, cap, 0)
                with mock.patch.object(self.sync.request_budget, "private_log") as logged:
                    self.sync._power_curve_fetches_used = 0
                    self.sync._fetch_activity_power_curve("ride-901")
                    self.assertEqual(sum("cache is full" in call.args[0] for call in logged.call_args_list), 0)
                self.assertTrue(any(p.endswith("/ride-901/power-curve.json") for _, p, _ in self.sent))
                setattr(store, cap, original)
                data = self.produce()
                self.assertFalse(any(w["code"] == "source_store_capacity" for w in data["source_freshness"]["warnings"]))
                self.assertEqual(store._pending, {})


class Growth(unittest.TestCase):
    def simulate(self, module, days, capped=False):
        records, outputs = [], []
        with mock.patch.object(fixtures, "sync_mod", module):
            harness = Producer()
            harness.setUp()
            try:
                harness.reply = harness.healthy_reply
                start = harness.clock()
                serial = 0
                for day in range(days):
                    harness.clock.now = start + day * 86400
                    for _ in range(1 + day % 2):
                        harness.add_ride(serial)
                        serial += 1
                    if day % 7 == 0:
                        harness.events.append({"id": day + 1, "category": "WORKOUT", "type": "Ride",
                            "name": "Synthetic route", "start_date_local": harness.Date.now().strftime("%Y-%m-%dT15:00:00"),
                            "attachments": [{"id": day + 1, "filename": "route.gpx",
                                "url": "https://intervals.icu/attachment/" + str(day)}]})
                    daily_calls = []
                    for quiet in (False, True):
                        if quiet:
                            harness.clock.now += 60
                        harness.new_sync()
                        if capped:
                            harness.sync.begin_tick()
                            harness.sync._acquisition.entry_limit = 0
                        data = harness.produce()
                        self.assertIsNotNone(data)
                        self.assertFalse(any(w["code"] == "source_stale" for w in data["source_freshness"]["warnings"]),
                            (day, quiet, data["source_freshness"]["warnings"],
                             {k: v for k, v in data["source_freshness"]["sources"].items() if v["status"] != "fresh"}))
                        daily_calls.append(list(harness.sent))
                        outputs.append(data)
                    store = harness.sync._acquisition
                    files = list(store.root.glob("*.json"))
                    records.append({"day": day + 1, "entries": len(files),
                        "bytes": sum(p.stat().st_size for p in files), "calls": daily_calls})
                    if hasattr(module, "HostedSlowCache"):
                        cache = harness.sync._hosted_cache
                        slow = [dict((name, entry.get(name)) for name in cache.FIELDS)
                                for entry in store.entries.values() if entry["group"] in cache.GROUPS]
                        envelope = {"version": cache.VERSION, "source_version": store.VERSION,
                                    "scope": cache.scope, "entries": slow}
                        cache.validate(envelope)
                        size = len(cache.canonical(envelope))
                        self.assertGreaterEqual(cache.MAX_ENTRIES, 4 * len(slow))
                        self.assertGreaterEqual(cache.MAX_BYTES, 4 * size)
                        records[-1].update(slow_entries=len(slow), slow_bytes=size)
                return records, outputs, (getattr(store, "entry_limit", 0), getattr(store, "byte_limit", 0))
            finally:
                harness.doCleanups()

    def check_ninety_day_plateau_matches_reviewed_unpruned_producer(self):
        path = os.environ.get("S11_PRUNE_BASELINE")
        if not path:
            self.skipTest("reviewed unpruned producer requires S11_PRUNE_BASELINE")
        baseline = load_module_by_path("unpruned_growth_oracle", Path(path))
        old, _, _ = self.simulate(baseline, 90)
        new, _, limits = self.simulate(fixtures.sync_mod, 90)
        for before, after in zip(old, new):
            self.assertEqual(after["calls"], before["calls"], after["day"])
            print("Growth day:", after["day"], "entries:", after["entries"], "bytes:", after["bytes"],
                  "unpruned:", before["entries"], before["bytes"],
                  "sends:", len(after["calls"][0]), len(after["calls"][1]))
        tail = new[35:]
        self.assertLessEqual(max(r["entries"] for r in tail) - min(r["entries"] for r in tail), 24)
        self.assertLess(max(r["bytes"] for r in tail), 2 * min(r["bytes"] for r in tail))
        self.assertLess(new[-1]["entries"], old[-1]["entries"] // 2)
        self.assertGreaterEqual(limits[0], 4 * max(r["entries"] for r in new))
        self.assertGreaterEqual(limits[1], 4 * max(r["bytes"] for r in new))
        print("Ninety-day slow envelope maxima:", max(r["slow_entries"] for r in new),
              "entries;", max(r["slow_bytes"] for r in new), "bytes")

    def test_cap_never_changes_training_outputs_or_current_acquisition_times(self):
        normal, outputs, _ = self.simulate(fixtures.sync_mod, 1)
        capped, limited, _ = self.simulate(fixtures.sync_mod, 1, capped=True)
        first, second = outputs[0], limited[0]
        self.assertEqual(normal[0]["calls"][0], capped[0]["calls"][0])
        for data in (first, second):
            data.pop("data_overview")  # Real filesystem timestamps differ between isolated producers.
        a, b = first.pop("source_freshness"), second.pop("source_freshness")
        self.assertEqual(first, second)
        self.assertEqual(a["sources"], b["sources"])
        self.assertEqual([w["code"] for w in b["warnings"]], ["source_store_capacity"])
        self.assertEqual(capped[0]["entries"], 0)


if __name__ == "__main__":
    unittest.main()
