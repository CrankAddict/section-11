"""Private acquisition and actual-send scheduler checks with explicit UTC clocks."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import requests
from _harness import BudgetClock, NetworkBlocked
from test_request_budget import sync_mod, push_mod, response


class SourceCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.clock = BudgetClock()
        self.clock.now -= 60  # Warm-up precedes either injected base time.
        clock = self.clock
        class Date(datetime):
            @classmethod
            def now(cls, tz=None):
                value = cls.fromtimestamp(clock(), timezone.utc)
                return value.astimezone(tz) if tz else value.replace(tzinfo=None)
        self.Date = Date
        env = mock.patch.dict(os.environ, {"SECTION11_STATE_DIR": str(self.root / "private/request-budget")})
        env.start()
        self.addCleanup(env.stop)
        dates = mock.patch.object(sync_mod, "datetime", Date)
        dates.start()
        self.addCleanup(dates.stop)
        self.calls, self.sent = [], []
        self.rows, self.events, self.health = [], [], []
        self.refuse = None
        self.reply = None
        self.after_send = None
        self.profile = {"id": "i123", "timezone": "UTC", "icu_weight": 70,
                        "sportSettings": [{"types": ["Ride", "VirtualRide"], "ftp": 250}]}
        self.new_sync()

        def send(session, prepared, **kwargs):
            budget = self.sync.request_budget
            if budget._handle is None or budget.count != len(self.sent) + 1:
                raise NetworkBlocked("source request escaped admission")
            ledger = json.loads((budget.root / "ledger.json").read_text())
            if ledger["last_run"]["count"] != budget.count:
                raise NetworkBlocked("source request escaped durable accounting")
            path = urlsplit(prepared.url).path
            query = parse_qs(urlsplit(prepared.url).query)
            self.sent.append((prepared.method, path, query))
            self.calls.append(self.sent[-1])
            if self.after_send:
                self.after_send(path)
            if self.reply:
                reply = self.reply(prepared, path, query)
                if reply is not None:
                    return reply
            if self.refuse and self.refuse(path, query):
                return response(429, headers={"Retry-After": "60"})
            end = path.rsplit("/", 1)[-1]
            today = self.Date.now().date()
            if end == "activities":
                value = self.rows
            elif end == "wellness":
                oldest, newest = query["oldest"][0], query["newest"][0]
                days = max(35, (today - datetime.fromisoformat(oldest).date()).days + 1)
                value = [{"id": (today - timedelta(days=i)).isoformat(), "ctl": 50, "atl": 60,
                          "weight": 70, "sleepSecs": 28800} for i in reversed(range(days))]
                value = [v for v in value if oldest <= v["id"] <= newest]
            elif "/wellness/" in path:
                value = {"id": end, "ctl": 50, "atl": 60, "weight": 70}
            elif end == "events":
                value = self.health if "category" in query else self.events
            elif end in ("folders", "workouts", "messages"):
                value = []
            elif end in ("power-curves", "hr-curves"):
                value = {"list": [], "activities": []}
            elif end == "activity-power-curves":
                value = {"after_kj": 0, "secs": [1, 5, 60, 300, 1200, 3600], "curves": []}
            elif end == "streams":
                value = [{"type": "time", "data": [0, 1, 2]}, {"type": "watts", "data": [150, 150, 150]}]
            elif end == "power-curve.json":
                value = {"secs": [5, 60, 300, 1200], "watts": [300, 250, 200, 180]}
            elif end == "streams.json":
                value = []
            elif "/activity/" in path:
                value = {"icu_intervals": []}
            else:
                value = self.profile
            return response(200, value)
        guard = mock.patch.object(requests.sessions.Session, "send", send)
        guard.start()
        self.addCleanup(guard.stop)

    def new_sync(self):
        self.sent = []
        self.sync = sync_mod.IntervalsSync("i123", "synthetic", report_main_sports=["cycling"])
        self.sync.data_dir = self.data
        self.sync.route_weather_enabled = False
        self.sync._cached_script_hash = "frozen-input"
        self.sync._request_budget = sync_mod.RequestBudget(self.data, "sync", sync_mod.RequestBudgetRefused,
            sync_mod.RequestBudget.fingerprint("i123", "synthetic"), clock=self.clock,
            sleep=self.clock.sleep, jitter=lambda: 0)
        return self.sync

    def produce(self):
        with contextlib.redirect_stdout(io.StringIO()):
            if not self.sync.begin_tick():
                self.sync._save_schedule_transition()
                return None
            if self.sync.should_generate_history():
                self.sync.generate_history()
            data = self.sync.collect_training_data()
            self.sync.save_local_outputs(data, str(self.data / "latest.json"))
        return data

    def next_run(self, seconds=60):
        self.clock.now += seconds
        return self.new_sync()

    def test_quiet_warm_tick_is_exactly_four_sends_and_private(self):
        self.produce()
        self.next_run()
        data = self.produce()
        self.assertEqual([p.rsplit("/", 1)[-1] for _, p, _ in self.sent],
                         ["activities", "wellness", "events", "events"])
        self.assertEqual(data["source_freshness"]["budget"]["requests_this_run"], 4)
        self.assertEqual(set(data["source_freshness"]["sources"]), set(sync_mod.AcquisitionStore.SOURCES))
        for group in sync_mod.AcquisitionStore.CORE:
            self.assertEqual(data["source_freshness"]["sources"][group]["status"], "fresh")
        for path in self.data.rglob("*"):
            self.assertNotIn(path.name, ("ledger.json", "ledger.lock", "ledger.anchor", "sources", "budget.log"))
        self.assertTrue(self.sync._acquisition.root.is_dir())
        if os.name == "posix":
            self.assertEqual(self.sync._acquisition.root.stat().st_mode & 0o777, 0o700)
            self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.sync._acquisition.root.glob("*.json")))

    def test_profile_projection_cache_age_and_independent_copies(self):
        self.profile.update(icu_api_key="synthetic-secret", icu_friend_invite_token="synthetic-invite")
        self.profile["sportSettings"][0]["access_token"] = "synthetic-nested"
        first = self.produce()["source_freshness"]["sources"]["profile"]
        private = "".join(p.read_text() for p in self.sync._acquisition.root.glob("*.json"))
        for secret in ("synthetic-secret", "synthetic-invite", "synthetic-nested"):
            self.assertNotIn(secret, private)
        self.next_run()
        second = self.produce()["source_freshness"]["sources"]["profile"]
        self.assertEqual(first["source_acquired_at"], second["source_acquired_at"])
        self.assertGreater(second["age_seconds"], first["age_seconds"])
        value = self.sync._intervals_get("")
        value["sportSettings"][0]["ftp"] = 999
        self.assertEqual(self.sync._intervals_get("")["sportSettings"][0]["ftp"], 250)

    def test_individual_corrupt_entry_refetches_without_purging_siblings(self):
        self.produce()
        store = self.sync._acquisition
        key, _ = store.key("", {})
        (store.root / (key + ".json")).write_text("{")
        self.next_run()
        self.produce()
        self.assertEqual(len(self.sent), 5)
        self.assertEqual(sum(path.endswith("/i123") for _, path, _ in self.sent), 1)

    def test_refused_curve_refresh_keeps_last_good_and_fresh_core(self):
        self.produce()
        self.next_run(21601)
        self.refuse = lambda path, query: path.endswith("power-curves")
        data = self.produce()
        sources = data["source_freshness"]["sources"]
        self.assertEqual(sources["aggregate_curves"]["status"], "deferred")
        self.assertTrue(sources["aggregate_curves"]["snapshot_present"])
        for group in ("activities", "wellness", "calendar", "health_events"):
            self.assertEqual(sources[group]["status"], "fresh")
        self.assertIn("rate_hold", [w["code"] for w in data["source_freshness"]["warnings"]])

    def test_refused_health_read_never_establishes_no_marker(self):
        self.health = [{"id": 1, "category": "SICK", "start_date_local": self.Date.now().date().isoformat(),
                        "end_date_local": (self.Date.now().date() + timedelta(days=2)).isoformat()}]
        self.produce()
        self.next_run()
        self.refuse = lambda path, query: path.endswith("events") and "category" in query
        data = self.produce()
        self.assertEqual(data["source_freshness"]["sources"]["health_events"]["status"], "deferred")
        health = data["health_context"]
        self.assertEqual(health["source_status"], "partial")
        self.assertNotIn("marker_active", health)
        self.assertNotIn("recent_marker", health)
        self.assertTrue(health["clarification_required"])

    def test_step_down_not_due_zero_sends_and_utc_reset(self):
        self.clock.now = datetime(2026, 10, 28, 0, tzinfo=timezone.utc).timestamp()
        self.produce()
        previous = 60
        for spent, expected in ((3500, 120), (5500, 300), (6200, 600), (6500, None)):
            self.next_run()
            budget = self.sync.request_budget
            with budget._lock():
                budget._load()
                budget.state["days"][budget.day]["sync"] = {"seed": spent}
                budget._save()
            self.assertFalse(self.sync.begin_tick())
            self.sync._save_schedule_transition()
            self.assertEqual(self.sent, [])
            updated = json.loads((self.data / "latest.json").read_text())["source_freshness"]
            self.assertEqual(updated["schedule"]["effective_interval_seconds"], expected)
            code = "budget_paused" if expected is None else "budget_step_down"
            self.assertIn(code, [w["code"] for w in updated["warnings"]])
            if expected is None:
                self.assertIn(sync_mod.AcquisitionStore.PAUSE_MESSAGE, [w["message"] for w in updated["warnings"]])
            prior = (self.data / "latest.json").read_bytes()
            self.next_run(1)
            self.assertFalse(self.sync.begin_tick())
            self.sync._save_schedule_transition()
            self.assertEqual((self.data / "latest.json").read_bytes(), prior)
            previous = expected
        self.clock.now = datetime(2026, 10, 29, 0, tzinfo=timezone.utc).timestamp()
        self.new_sync()
        self.assertTrue(self.sync.begin_tick())
        self.assertEqual(self.sync._acquisition.schedule["state"], "running")

    def test_dirty_generation_refresh_and_concurrent_write_remains_pending(self):
        self.produce()
        self.next_run()
        self.assertTrue(self.sync.begin_tick())
        budget = self.sync.request_budget
        with budget._lock():
            budget._load()
            budget._dirty_write("https://intervals.icu/api/v1/athlete/i123/events/1")
            first = budget.state["dirty"]["calendar"]
        def during_fetch(path):
            if path.endswith("/events"):
                budget._dirty_write("https://intervals.icu/api/v1/athlete/i123/events/1")
                self.after_send = None
        self.after_send = during_fetch
        self.produce()
        entry = next(e for e in self.sync._acquisition.entries.values() if e["group"] == "calendar")
        self.assertEqual(entry["generation"], first)
        with budget._lock():
            budget._load()
            self.assertGreater(budget.state["dirty"]["calendar"], entry["generation"])
        self.assertEqual(sum(p.endswith("/events") and "category" not in q for _, p, q in self.sent), 1)
        self.next_run()
        self.produce()
        entry = next(e for e in self.sync._acquisition.entries.values() if e["group"] == "calendar")
        self.assertEqual(entry["generation"], self.sync.request_budget.state["dirty"]["calendar"])

    def test_settings_dirty_refreshes_profile_without_new_credentials_in_store(self):
        self.produce()
        self.next_run()
        budget = self.sync.request_budget
        with budget._lock():
            budget._load()
            budget._dirty_write("https://intervals.icu/api/v1/athlete/i123/sport-settings/1")
        self.profile["sportSettings"][0]["ftp"] = 275
        data = self.produce()
        self.assertEqual(sum(p.endswith("/i123") for _, p, _ in self.sent), 1)
        self.assertEqual(data["current_status"]["thresholds"]["sports"]["cycling"]["ftp"], 275)

    def test_full_quiet_days_chosen_intervals_with_one_minute_timer(self):
        for interval in (60, 120, 300, 600):
            with self.subTest(interval=interval):
                base = self.root / ("day-" + str(interval))
                self.data = base / "data"
                self.data.mkdir(parents=True)
                start = datetime(2026, 10, 28, 0, tzinfo=timezone.utc).timestamp()
                self.calls = []
                with mock.patch.dict(os.environ, {"SECTION11_STATE_DIR": str(base / "private/request-budget")}):
                    admitted = 0
                    for elapsed in range(0, 86400, 60):
                        self.clock.now = start + elapsed
                        self.new_sync()
                        self.sync.check_interval_seconds = sync_mod.IntervalsSync._check_interval(
                            {"check_interval_minutes": interval // 60}, {})
                        data = self.produce()
                        if elapsed % interval:
                            self.assertIsNone(data)
                            self.assertEqual(self.sent, [])
                            continue
                        admitted += 1
                        self.assertIsNotNone(data)
                        self.assertEqual(data["source_freshness"]["schedule"]["state"], "running")
                    self.assertEqual(admitted, 86400 // interval)
                total = len(self.calls)
                population = {}
                for _, path, query in self.calls:
                    kind = path.rsplit("/", 1)[-1]
                    if kind == "i123":
                        kind = "profile"
                    population[kind] = population.get(kind, 0) + 1
                print("Quiet full-producer day, one-minute OS timer:", interval, "seconds;", total, "sends;", population)
                self.assertEqual(total, {60: 5804, 120: 2924, 300: 1196, 600: 620}[interval])
                self.assertEqual(sum(p.endswith("/events") for _, p, _ in self.calls), 2 * (86400 // interval))

    def test_full_day_with_two_new_rides(self):
        self.two_ride_day(1)

    def test_full_two_ride_days_chosen_intervals_with_one_minute_timer(self):
        for minutes in (2, 5, 10):
            with self.subTest(minutes=minutes):
                self.data = self.root / ("rides-" + str(minutes))
                self.data.mkdir()
                self.rows = []
                self.two_ride_day(minutes)

    def two_ride_day(self, minutes):
        start = datetime(2026, 10, 28, 0, tzinfo=timezone.utc).timestamp()
        self.calls = []
        for elapsed in range(0, 86400, 60):
            self.clock.now = start + elapsed
            if elapsed in (21600, 64800):
                indoor = elapsed == 21600
                self.rows.append({"id": "indoor" if indoor else "outdoor", "type": "VirtualRide" if indoor else "Ride",
                    "name": "Synthetic ride", "start_date_local": self.Date.now().isoformat(),
                    "start_date": self.Date.now(timezone.utc).isoformat(), "moving_time": 1800, "elapsed_time": 1800,
                    "icu_training_load": 50, "icu_average_watts": 150, "icu_weighted_avg_watts": 150,
                    "icu_ftp": 250, "icu_atl": 60, "icu_ctl": 50, "icu_intervals": [],
                    "stream_types": ["watts"], "trainer": indoor})
            self.new_sync()
            self.sync.check_interval_seconds = sync_mod.IntervalsSync._check_interval(
                {"check_interval_minutes": minutes}, {})
            data = self.produce()
            if elapsed % (minutes * 60):
                self.assertIsNone(data)
                self.assertEqual(self.sent, [])
            else:
                self.assertIsNotNone(data)
                self.assertEqual(data["source_freshness"]["schedule"]["state"], "running")
        population = {}
        for _, path, query in self.calls:
            kind = path.rsplit("/", 1)[-1]
            kind = "profile" if kind == "i123" else "detail" if kind in ("indoor", "outdoor") else kind
            population[kind] = population.get(kind, 0) + 1
        print("Two-new-ride full-producer day, one-minute OS timer:", minutes,
              "minutes;", len(self.calls), "sends;", population)
        self.assertEqual(len(self.calls), {1: 5887, 2: 3007, 5: 1279, 10: 703}[minutes])
        if minutes == 1:
            self.assertEqual(len(self.calls), 5887)
            self.assertEqual(population, {"activities": 1441, "wellness": 1441, "profile": 25,
                "activity-power-curves": 1, "events": 2880, "folders": 4, "workouts": 4,
                "power-curves": 14, "hr-curves": 14, "detail": 28, "streams": 28,
                "messages": 4, "power-curve.json": 2, "streams.json": 1})
        self.assertEqual(population["activities"], 86400 // (minutes * 60) + 1)
        self.assertEqual(population["events"], 2 * (86400 // (minutes * 60)))

    def test_actual_push_write_and_preview_dirty_generations(self):
        self.produce()
        self.next_run()
        push = push_mod.IntervalsPush("i123", "synthetic")
        push.data_dir = self.data
        push._request_budget = push_mod.RequestBudget(self.data, "push", push_mod.RequestBudgetRefused,
            push_mod.RequestBudget.fingerprint("i123", "synthetic"), clock=self.clock,
            sleep=self.clock.sleep, jitter=lambda: 0)
        self.sync = push
        event = {"id": 1, "start_date_local": "2026-10-29T08:00:00", "category": "WORKOUT", "name": "Synthetic"}
        self.reply = lambda prepared, path, query: response(200, event)
        push.preview_move(1, "2026-10-30")
        self.assertFalse(push.request_budget.state.get("dirty"))
        result = push.update_event(1, {"name": "Updated"})
        self.assertTrue(result["success"])
        generation = push.request_budget.state["dirty"]["calendar"]
        self.assertGreater(generation, 0)
        self.reply = None
        self.new_sync()
        self.produce()
        entries = [e for e in self.sync._acquisition.entries.values() if e["group"] == "calendar"]
        self.assertEqual(entries[0]["generation"], generation)
        self.assertEqual(sum(p.endswith("/events") and "category" not in q for _, p, q in self.sent), 1)
        self.assertFalse(any(p.name in ("ledger.json", "ledger.lock", "ledger.anchor", "sources") for p in self.data.rglob("*")))


if __name__ == "__main__":
    unittest.main()
