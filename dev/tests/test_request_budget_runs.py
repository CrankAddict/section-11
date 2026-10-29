"""Synthetic full producers, recorded request signatures and frozen-byte oracle."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from unittest import mock

import requests
from _harness import load_module_by_path, SYNC_PATH, NetworkBlocked
from test_request_budget import Clock, response

module = load_module_by_path("budget_runs", SYNC_PATH)


class FrozenDate(datetime):
    @classmethod
    def now(cls, tz=None):
        value = getattr(cls, "fixed", cls(2026, 10, 28, 12, tzinfo=timezone.utc))
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


class StableSet(set):
    """Freeze the baseline's unordered sport-family iteration for trace parity."""
    def __iter__(self):
        values = list(super().__iter__())
        if all(v in ("ski", "cycling", "rowing") for v in values):
            return iter(sorted(values, key=("ski", "cycling", "rowing").index))
        return iter(values)


def activities():
    rows = []
    for index in range(19):
        age = index // 2 if index < 14 else index - 6
        day = (FrozenDate.now() - timedelta(days=age)).strftime("%Y-%m-%d")
        rows.append({"id": "i" + str(index), "type": "VirtualRide" if index < 18 else "VirtualSki",
                     "name": "Synthetic session", "start_date_local": day + "T08:00:00",
                     "start_date": day + "T08:00:00Z", "moving_time": 1800, "elapsed_time": 1800,
                     "icu_training_load": 50, "icu_average_watts": 150, "icu_weighted_avg_watts": 150,
                     "icu_ftp": 250, "icu_atl": 60, "icu_ctl": 50,
                     "icu_intervals": [], "stream_types": ["watts"], "trainer": True})
    return rows


class FullRuns(unittest.TestCase):
    def run_producer(self, mod, directory, cold=False, guarded=True):
        if getattr(self, "rollover_after_wellness", False):
            FrozenDate.fixed = self.rollover_start
        sync = mod.IntervalsSync("i123", "synthetic", report_main_sports=["cycling"])
        # Compare training bytes across releases, excluding only the release label.
        sync.VERSION = "parity"
        sync.data_dir = directory
        sync._cached_script_hash = "frozen-input"
        sync.route_weather_enabled = False
        clock = Clock()
        if hasattr(mod, "RequestBudget"):
            with mock.patch.dict(os.environ):
                if hasattr(mod.DataOverview, "STATE_NOTE"):
                    os.environ.pop("SECTION11_STATE_DIR", None)
                else:
                    os.environ["SECTION11_STATE_DIR"] = str(directory.parent / (directory.name + "-state") / "request-budget")
                sync._request_budget = mod.RequestBudget(directory, "sync", mod.RequestBudgetRefused,
                    mod.RequestBudget.fingerprint("i123", "synthetic"),
                    clock=clock, sleep=clock.sleep, jitter=lambda: 0)
        calls = []
        rolled = False
        source = activities()
        def send(session, prepared, **kwargs):
            nonlocal rolled
            if guarded and hasattr(mod, "RequestBudget"):
                budget = sync.request_budget
                if budget._handle is None or budget.count != len(calls) + 1:
                    raise NetworkBlocked("full producer bypassed ledger")
                ledger = json.loads((budget.root / "ledger.json").read_text())
                if ledger["last_run"]["count"] != budget.count:
                    raise NetworkBlocked("full producer was not durably charged")
            url = urlsplit(prepared.url)
            if url.hostname != "intervals.icu":
                raise NetworkBlocked("unexpected non-provider send")
            query = parse_qs(url.query)
            path = url.path
            calls.append((path, query))
            end = path.rsplit("/", 1)[-1]
            if end == "activities":
                payload = source
            elif end == "wellness":
                oldest, newest = query["oldest"][0], query["newest"][0]
                payload = [{"id": (FrozenDate.now() - timedelta(days=i)).strftime("%Y-%m-%d"),
                            "ctl": 50, "atl": 60, "weight": 70, "sleepSecs": 28800}
                           for i in range(35)]
                payload = [r for r in reversed(payload) if oldest <= r["id"] <= newest]
                if hasattr(self, "wellness_range"):
                    payload = self.wellness_range(oldest, newest)
                if getattr(self, "rollover_after_wellness", False) and not rolled:
                    FrozenDate.fixed += timedelta(days=1)
                    clock.now += 86400
                    rolled = True
            elif "/wellness/" in path:
                payload = {"id": end, "ctl": 50, "atl": 60, "weight": 70}
                if hasattr(self, "wellness_day"):
                    payload = self.wellness_day(end)
                    if payload is None:
                        return response(404)
            elif end in ("events", "folders", "workouts", "messages"):
                payload = []
                if end == "events":
                    payload = getattr(self, "calendar_rows", [])
            elif end in ("power-curves", "hr-curves"):
                payload = {"list": [], "activities": []}
            elif end == "activity-power-curves":
                payload = {"after_kj": 0, "secs": [1, 5, 60, 300, 1200, 3600], "curves": []}
            elif end == "streams":
                payload = [{"type": "time", "data": [0, 1, 2]},
                           {"type": "watts", "data": [150, 150, 150]}]
            elif "/activity/" in path:
                payload = {"icu_intervals": []}
            else:
                payload = {"id": "i123", "timezone": "UTC", "icu_weight": 70,
                           "sportSettings": [{"types": ["Ride", "VirtualRide"], "ftp": 250}]}
                payload.update(getattr(self, "profile_fields", {}))
            return response(200, payload)

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(mod, "datetime", FrozenDate))
            stack.enter_context(mock.patch.object(mod, "set", StableSet, create=True))
            stack.enter_context(mock.patch.object(requests.sessions.Session, "send", send))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            if cold:
                sync.generate_history()
            data = sync.collect_training_data(days_back=getattr(self, "days_back", 7))
            # Freeze filesystem clock evidence, not any serialized consumer value.
            original_state = mod.DataOverview.file_state
            def state(root, relative):
                present, stamp = original_state(root, relative)
                return present, "2026-10-28T12:00:00+00:00" if present else stamp
            with mock.patch.object(mod.DataOverview, "file_state", side_effect=state):
                sync.save_local_outputs(data, str(directory / "latest.json"))
        if hasattr(mod.DataOverview, "STATE_NOTE"):
            self.assertEqual(sync.request_budget.root.parent, directory / "state/request-budget")
            self.assertTrue((directory / "state/README.md").is_file())
            for path in (directory / "state").rglob("*"):
                if path.is_file():
                    self.assertNotIn("synthetic", path.read_text())
                    self.assertNotIn("Authorization", path.read_text())
                    if os.name != "nt":
                        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                elif os.name != "nt":
                    self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        else:
            self.assertFalse(any(p.name in ("ledger.json", "ledger.lock", "ledger.anchor", "budget.log")
                                 for p in directory.rglob("*")))
        return calls, {p.name: p.read_bytes() for p in directory.glob("*.json")}

    def normalize_state_notes(self, old, new):
        if "export_freshness" not in old:
            export = new.pop("export_freshness")
            self.assertEqual(export["version"], 1)
            self.assertEqual(export["generated_at"], new["metadata"]["last_updated"])
            self.assertEqual(export["mode"], "unknown")
            self.assertIsNone(export["expected_update_by"])
        for section in ("READ_THIS_FIRST", "data_overview"):
            if "state_note" not in old[section]:
                self.assertEqual(new[section].pop("state_note"), module.DataOverview.STATE_NOTE)
        # This fixture's naive baseline clock is explicitly UTC. Only the
        # two approved export stamps change representation, never their instant.
        for section, key in (("metadata", "last_updated"), ("derived_metrics", "calculation_timestamp")):
            prior = datetime.fromisoformat(old[section][key].replace("Z", "+00:00"))
            if prior.tzinfo is None:
                prior = prior.replace(tzinfo=timezone.utc)
            self.assertEqual(new[section][key], prior.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))
            new[section][key] = old[section][key]

    def seed(self, mod, root):
        root.mkdir()
        (root / "latest.json").write_text(json.dumps({"recent_activities": [
            {"id": row["id"], "power_curve": {}} for row in activities()]}))
        self.run_producer(mod, root, cold=True, guarded=False)
        # Only private accounting is reset between independent fixture scenarios.
        private = root.parent / (root.name + "-state")
        if private.exists():
            shutil.rmtree(private)

    @staticmethod
    def signature(cold=False):
        base = "/api/v1/athlete/i123"
        a = lambda endpoint, keys=(): (base + ("/" + endpoint if endpoint else ""), tuple(keys))
        top = [a(""), a("activities", ("newest", "oldest")),
               a("wellness", ("newest", "oldest")), a("wellness", ("newest", "oldest")),
               a("wellness/2026-10-28"), a("wellness", ("newest", "oldest")),
               a("events", ("newest", "oldest", "resolve")),
               a("events", ("category", "newest", "oldest"))]
        curves = [a("power-curves", ("curves", "type")), a("hr-curves", ("curves",))]
        curves += [a(metric + "-curves", ("curves", "type"))
                   for family in ("ski", "cycling") for metric in ("power", "hr") for typ in range(2)]
        selected = [a(metric + "-curves", ("curves", "subMaxEfforts", "type")) for metric in ("power", "hr")]
        messages = [("/api/v1/activity/{activity}/messages", ())] * 14
        if not cold:
            return top + curves + selected + messages
        history = [a("activities", ("newest", "oldest")), a("wellness", ("newest", "oldest")), a("")]
        detail = [item for i in range(19) for item in
                  [("/api/v1/activity/{activity}", ("intervals",)),
                   ("/api/v1/activity/{activity}/streams", ())]]
        return history + top + [a("folders"), a("workouts")] + curves + detail + selected + messages

    def assert_signature(self, calls, cold):
        normalized = []
        for path, query in calls:
            if "/activity/" in path:
                parts = path.split("/")
                parts[4] = "{activity}"
                path = "/".join(parts)
            normalized.append((path, tuple(sorted(query))))
        expected = self.signature(cold)
        offset = 3 if cold else 0
        expected = expected[:offset + 3] + expected[offset + 6:]
        self.assertEqual(normalized, expected)
        curve_calls = [(p, q) for p, q in calls if p.endswith(("/power-curves", "/hr-curves"))]
        self.assertEqual([q.get("type") for p, q in curve_calls],
                         [["Ride"], None, ["NordicSki"], ["VirtualSki"], ["NordicSki"], ["VirtualSki"],
                          ["Ride"], ["VirtualRide"], ["Ride"], ["VirtualRide"], ["VirtualRide"], ["VirtualRide"]])
        for path, query in calls:
            if path.endswith("/events") and "resolve" in query:
                self.assertEqual(query["resolve"], ["true"])
            if "subMaxEfforts" in query:
                self.assertEqual(query["subMaxEfforts"], ["3"])

    def test_full_warm_and_cold_and_baseline_bytes(self):
        baseline_path = os.environ.get("S11_PARITY_BASELINE")
        baseline = load_module_by_path("budget_baseline", Path(baseline_path)) if baseline_path else module
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            seed = parent / "seed"
            self.seed(baseline, seed)
            for cold in (False, True):
                with self.subTest(cold=cold):
                    before, after = parent / ("baseline" + str(cold)), parent / ("candidate" + str(cold))
                    shutil.copytree(seed, before)
                    shutil.copytree(seed, after)
                    if cold:
                        for root in (before, after):
                            for name in ("intervals.json", "saved_workouts.json"):
                                (root / name).unlink()
                    original_calls, original_bytes = self.run_producer(baseline, before, cold, guarded=False)
                    candidate_calls, candidate_bytes = self.run_producer(module, after, cold)
                    self.assert_signature(candidate_calls, cold)
                    offset = 3 if cold else 0
                    # Keep the old 35-date read; omit display, day object and yesterday.
                    merged_calls = (original_calls if hasattr(baseline, "AcquisitionStore") else
                                    original_calls[:offset + 2] + original_calls[offset + 3:offset + 4] + original_calls[offset + 6:])
                    self.assertEqual(candidate_calls, merged_calls)
                    self.assertEqual(set(candidate_bytes), set(original_bytes))
                    for name, content in original_bytes.items():
                        if name != "latest.json":
                            self.assertEqual(candidate_bytes[name], content, name)
                            continue
                        old, new = json.loads(content), json.loads(candidate_bytes[name])
                        if not hasattr(baseline, "AcquisitionStore"):
                            self.assertEqual(new.pop("source_freshness")["version"], 1)
                        self.normalize_state_notes(old, new)
                        # This is acquisition time, now recorded by the injected budget clock.
                        new["sleep_context"]["source_updated_at"] = old["sleep_context"]["source_updated_at"]
                        self.assertEqual(new, old)
                        self.assertEqual(json.dumps(new, indent=2, default=str).encode(), content)
                    print("Full-run evidence:", "cold" if cold else "warm", len(candidate_calls),
                          "sends;", len(candidate_bytes), "legacy JSON files equal after six explicit allowed paths",
                          "; external baseline" if baseline_path else "; repeatability only")

    def test_hosted_runs_keep_only_published_json_and_pay_cold_source_cost(self):
        baseline_path = os.environ.get("S11_PARITY_BASELINE")
        baseline = load_module_by_path("hosted_seed_baseline", Path(baseline_path)) if baseline_path else module
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed"
            self.seed(baseline, seed)
            for index in (1, 2):
                runner = root / ("runner-" + str(index))
                runner.mkdir()
                for path in seed.glob("*.json"):
                    (runner / path.name).write_bytes(path.read_bytes())
                self.assertFalse((runner / "state").exists())
                with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
                    calls, exported = self.run_producer(module, runner)
                self.assertEqual(len(calls), 31)
                fresh = json.loads(exported["latest.json"])["source_freshness"]
                self.assertEqual(fresh["budget"]["requests_this_run"], 31)
                ledgers = list((runner / "state/request-budget").glob("*/ledger.json"))
                self.assertEqual(len(ledgers), 1)
                ledger = json.loads(ledgers[0].read_text())
                # The night base crosses UTC midnight during this invocation.
                self.assertEqual(sum(sum(sum(v.values()) for v in day.values())
                                     for day in ledger["days"].values()), 31)
                self.assertEqual(fresh["schedule"]["requested_interval_seconds"], 60)
                # Carry forward exactly the published JSON, never runner state.
                for name, content in exported.items():
                    (seed / name).write_bytes(content)
            print("Hosted published-JSON-only runs: 31, 31 sends; independent fresh ledgers")


if __name__ == "__main__":
    unittest.main()
