"""Settled native absence is valid cache truth, not a refresh failure."""
import json
import unittest
from datetime import timedelta

import requests
import test_source_schedule as fixtures
import test_decoupling_detail as decoupling


class NativeTerminal(unittest.TestCase):
    setUp = fixtures.SourceCase.setUp
    new_sync = fixtures.SourceCase.new_sync
    next_run = fixtures.SourceCase.next_run
    produce = fixtures.SourceCase.produce

    def ride(self):
        day = (self.Date.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        self.rows = [decoupling.raw(id="terminal", start_date_local=day + "T08:00:00",
            start_date=day + "T08:00:00Z", icu_training_load=50, stream_types=["watts", "heartrate"])]

    def sequence(self, code, legacy):
        self.ride()
        def reply(prepared, path, query):
            if path.endswith("/power-curve.json"):
                return fixtures.response(code)
            if path.endswith("/power-vs-hr"):
                return fixtures.response(200, decoupling.body())
        self.reply = reply
        start = self.clock()
        data = self.produce()
        self.assertEqual(len(self.sent), 25)
        acquired = data["source_freshness"]["sources"]["activity_power"]["last_success_at"]
        if legacy:
            store = self.sync._acquisition
            for key, entry in store.entries.items():
                if entry["group"].startswith("activity_"):
                    (store.root / (key + ".json")).unlink()
        else:
            self.assertIsNotNone(acquired)
            self.assert_terminal(data, code, False)
        for elapsed, expected in ((60, 4), (90000, 18), (90060, 4), (259200, 17), (259260, 4)):
            with self.subTest(elapsed=elapsed):
                self.clock.now = start + elapsed
                self.new_sync()
                data = self.produce()
                self.assertEqual(len(self.sent), expected)
                source = self.assert_terminal(data, code, legacy)
                self.assertEqual(source["last_success_at"], None if legacy else acquired)
                if legacy:
                    self.assertIsNone(source["age_seconds"])
                else:
                    self.assertGreaterEqual(source["age_seconds"], elapsed - 30)
                self.assertFalse(any(p.endswith("/power-curve.json") for _, p, _ in self.sent))

    def assert_terminal(self, data, code, legacy):
        fresh = data["source_freshness"]
        source = fresh["sources"]["activity_power"]
        self.assertEqual((source["status"], source["coverage"]), ("fresh", "complete"))
        self.assertEqual(source["reason"], "legacy_cache_adopted" if legacy else "native_terminal_result")
        self.assertEqual(source["native_outcomes"][0]["outcome"], "http_" + str(code))
        self.assertFalse(any(w["code"] == "source_stale" for w in fresh["warnings"]))
        self.assertIsNone(source["max_age_seconds"])
        self.assertIsNone(source["next_due_at"])
        return source

    def test_cold_404_stays_settled_for_three_days(self):
        self.sequence(404, False)

    def test_cold_410_stays_settled_for_three_days(self):
        self.sequence(410, False)

    def test_legacy_404_stays_settled_for_three_days(self):
        self.sequence(404, True)

    def test_legacy_410_stays_settled_for_three_days(self):
        self.sequence(410, True)

    def recovery(self, failure):
        self.ride()
        def reply(prepared, path, query):
            if path.endswith("/power-curve.json"):
                if isinstance(failure, Exception):
                    raise failure
                return failure
            if path.endswith("/power-vs-hr"):
                return fixtures.response(200, decoupling.body())
        self.reply = reply
        data = self.produce()
        source = data["source_freshness"]["sources"]["activity_power"]
        self.assertIn(source["status"], ("unavailable", "stale", "deferred"))
        self.assertNotIn("native_outcomes", source)
        self.assertTrue(any(w["code"] == "source_stale" for w in data["source_freshness"]["warnings"]))
        self.next_run()
        self.reply = lambda prepared, path, query: fixtures.response(200, decoupling.body()) if path.endswith("/power-vs-hr") else None
        data = self.produce()
        source = data["source_freshness"]["sources"]["activity_power"]
        self.assertEqual(source["status"], "fresh")
        self.assertIsNotNone(source["last_success_at"])
        self.assertFalse(any(w["code"] == "source_stale" for w in data["source_freshness"]["warnings"]))
        self.assertEqual(sum(p.endswith("/power-curve.json") for _, p, _ in self.sent), 1)

    def test_server_failure_warns_then_success_clears(self):
        self.recovery(fixtures.response(503))

    def test_timeout_warns_then_success_clears(self):
        self.recovery(requests.exceptions.Timeout("synthetic timeout"))

    def test_network_failure_warns_then_success_clears(self):
        self.recovery(requests.exceptions.ConnectionError("synthetic connection failure"))

    def test_unexpected_shape_warns_then_success_clears(self):
        self.recovery(fixtures.response(200, {"secs": [], "watts": "invalid"}))

    def test_rate_hold_warns_then_success_clears(self):
        self.recovery(fixtures.response(429, headers={"Retry-After": "60"}))

    def test_detail_stream_decoupling_and_terrain_terminal_acquisitions(self):
        self.assertTrue(self.sync.begin_tick())
        for code in (404, 410):
            self.reply = lambda prepared, path, query: fixtures.response(code)
            for group, fetch in (("activity_details", self.sync._fetch_activity_intervals),
                ("activity_streams", lambda aid: self.sync._fetch_activity_streams(aid, ["watts"])),
                ("activity_decoupling", self.sync._fetch_activity_power_vs_hr),
                ("activity_terrain", self.sync._fetch_terrain_streams)):
                with self.subTest(group=group, code=code):
                    before = len(self.sent)
                    self.assertEqual(fetch(str(code))[0], "terminal_error")
                    self.assertEqual(len(self.sent), before + 1)
                    source = self.sync._acquisition.source_status(group)
                    self.assertEqual((source["status"], source["reason"]), ("fresh", "native_terminal_result"))
                    self.assertIsNotNone(source["last_success_at"])
        self.clock.now += 3 * 86400
        for group in ("activity_details", "activity_streams", "activity_decoupling", "activity_terrain"):
            self.assertEqual(self.sync._acquisition.source_status(group)["status"], "fresh")

    def test_legacy_detail_stream_tombstones_are_adopted_without_sends(self):
        self.assertTrue(self.sync.begin_tick())
        day = (self.Date.now() - timedelta(days=4)).strftime("%Y-%m-%d")
        native = {"script_hash": self.sync.script_hash, "schema_version": 2, "activities": [],
            "fetch_state": {"gone": {"date": day, "intervals": {"status": "tombstone", "reason": "terminal_error"},
                                     "streams": {"status": "tombstone", "reason": "terminal_error"}}}}
        (self.data / "intervals.json").write_text(json.dumps(native))
        for elapsed in (60, 3 * 86400):
            self.next_run(elapsed)
            self.assertTrue(self.sync.begin_tick())
            self.sync._generate_intervals([{"id": "gone", "type": "VirtualRide", "start_date_local": day}], {"gone"})
            self.assertEqual(self.sent, [])
            for group in ("activity_details", "activity_streams"):
                source = self.sync._acquisition.source_status(group)
                self.assertEqual((source["status"], source["reason"]), ("fresh", "legacy_cache_adopted"))
                self.assertEqual(source["native_outcomes"][0]["outcome"], "resource_gone")
                self.assertIsNone(source["last_success_at"])

    def test_legacy_decoupling_and_terrain_terminal_results_are_adopted(self):
        self.assertTrue(self.sync.begin_tick())
        self.reply = lambda prepared, path, query: fixtures.response(410)
        act = decoupling.raw(id="gone")
        cached = self.sync._build_decoupling_for_activity(act, {}, True, True, {})
        cached.update(self.sync._build_terrain_for_activity({"id": "gone", "type": "Ride"}, {}))
        store = self.sync._acquisition
        for key, entry in store.entries.items():
            if entry["group"].startswith("activity_"):
                (store.root / (key + ".json")).unlink()
        for elapsed in (60, 3 * 86400):
            self.next_run(elapsed)
            self.assertTrue(self.sync.begin_tick())
            self.sync._build_decoupling_for_activity(act, {"gone": cached}, True, True, {})
            self.sync._build_terrain_for_activity({"id": "gone", "type": "Ride"}, {"gone": cached})
            for status in ("no_gps", "no_elevation"):
                self.sync._build_terrain_for_activity({"id": status, "type": "Ride"},
                    {status: {"terrain_status": status}})
            self.assertEqual(self.sent, [])
            for group in ("activity_decoupling", "activity_terrain"):
                source = self.sync._acquisition.source_status(group)
                self.assertEqual((source["status"], source["reason"]), ("fresh", "legacy_cache_adopted"))
                self.assertIsNone(source["last_success_at"])
                self.assertIsNone(source["next_eligible_at"])
                self.assertIn("http_410", [o["outcome"] for o in source["native_outcomes"]])

    def test_failed_cache_without_terminal_evidence_stays_unavailable(self):
        self.assertTrue(self.sync.begin_tick())
        self.sync._build_power_curve_for_activity({"id": "bad", "moving_time": 300},
            {"bad": {"power_curve_status": "failed", "power_curve_error": "http_500"}}, True)
        self.sync._build_terrain_for_activity({"id": "bad", "type": "Ride"},
            {"bad": {"terrain_status": "failed", "terrain_error": "unexpected_shape"}})
        for group in ("activity_power", "activity_terrain"):
            source = self.sync._acquisition.source_status(group)
            self.assertEqual((source["status"], source["reason"]), ("unavailable", "invalid_native_cache"))
            self.assertNotIn("native_outcomes", source)
        self.assertEqual(self.sent, [])

    def test_legacy_unsupported_route_cache_is_adopted_without_download(self):
        self.assertTrue(self.sync.begin_tick())
        event = {"id": 1, "start_date_local": self.Date.now().isoformat(),
                 "attachments": [{"id": 2, "filename": "route.fit", "url": "https://intervals.icu/synthetic"}]}
        self.sync._generate_terrain([event])
        (self.data / "routes.json").write_text(json.dumps(self.sync._routes_data))
        store = self.sync._acquisition
        for key, entry in store.entries.items():
            if entry["group"] == "route_attachments":
                (store.root / (key + ".json")).unlink()
        self.next_run(3 * 86400)
        self.assertTrue(self.sync.begin_tick())
        self.sync._generate_terrain([event])
        source = self.sync._acquisition.source_status("route_attachments")
        self.assertEqual((source["status"], source["reason"]), ("fresh", "legacy_cache_adopted"))
        self.assertIsNone(source["last_success_at"])
        self.assertEqual(source["native_outcomes"][0]["outcome"], "unsupported_format")
        self.assertEqual(self.sent, [])

    def test_unsupported_route_is_settled_but_download_errors_are_not(self):
        self.assertTrue(self.sync.begin_tick())
        url = "https://intervals.icu/route/synthetic"
        self.sync._download_and_parse_route(url, "route.fit")
        source = self.sync._acquisition.source_status("route_attachments")
        self.assertEqual(source["status"], "fresh")
        self.assertEqual(source["native_outcomes"][0]["outcome"], "unsupported_format")
        self.assertIsNone(source["last_success_at"])
        self.assertEqual(self.sent, [])
        self.reply = lambda prepared, path, query: fixtures.response(404)
        self.sync._download_and_parse_route(url + "/missing", "route.gpx")
        self.assertNotEqual(self.sync._acquisition.source_status("route_attachments")["status"], "fresh")


if __name__ == "__main__":
    unittest.main()
