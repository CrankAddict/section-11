"""Offline portable slow-cache contract; every producer clock is injected."""
import contextlib
import copy
import io
import json
import os
import shutil
import tempfile
import textwrap
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import test_source_schedule as source
import test_request_budget_runs as runs
from _harness import REPO_ROOT

mod = source.sync_mod


def mixed_profile():
    """Synthetic six-sport profile with the API's nullable field shapes."""
    profile = {name: None for name in mod.AcquisitionStore.PROFILE_FIELDS}
    profile.update(id="i123", timezone="UTC", icu_weight=70, sportSettings=[])
    for sport in ("Ride", "Run", "Swim", "Walk", "NordicSki", "Other"):
        setting = {name: None for name in mod.AcquisitionStore.SPORT_FIELDS}
        setting["types"] = [sport, "VirtualRide"] if sport == "Ride" else [sport]
        if sport == "Ride":
            setting.update(ftp=250, power_zones=[55, 75, 90, 105, 120, 150, 999])
        profile["sportSettings"].append(setting)
    return profile


class HostedCase(unittest.TestCase):
    produce = source.SourceCase.produce

    def setUp(self):
        source.SourceCase.setUp(self)
        self.profile = mixed_profile()
        self.runner_number = 0
        self.remote = None
        self.published = {}
        self.stage = self.root / "runner-temp/section11-slow-cache"
        self.stage.mkdir(parents=True)
        self.environment = mock.patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
            "SECTION11_EXPORT_EVENT": "workflow_dispatch",
            "RUNNER_TEMP": str(self.stage.parent), "GITHUB_WORKSPACE": str(self.data),
            "GITHUB_REPOSITORY_ID": "12345", "GITHUB_REF_NAME": "main", "GITHUB_OUTPUT": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.new_runner()

    def new_sync(self):
        return source.SourceCase.new_sync(self)

    def new_runner(self, seconds=0, restore=True):
        self.clock.now += seconds
        self.runner_number += 1
        self.data = self.root / ("runner-" + str(self.runner_number))
        self.data.mkdir()
        for name, value in self.published.items():
            (self.data / name).write_bytes(value)
        for path in self.stage.iterdir():
            if path.is_file() or path.is_symlink():
                path.unlink()
        if restore and self.remote is not None:
            (self.stage / "cache.json").write_bytes(self.remote)
        os.environ["SECTION11_STATE_DIR"] = str(self.data / "state")
        os.environ["GITHUB_WORKSPACE"] = str(self.data)
        self.new_sync()
        self.sync._request_budget = mod.HostedRequestBudget(
            self.data, "sync", mod.RequestBudgetRefused,
            mod.RequestBudget.fingerprint("i123", "synthetic"), clock=self.clock,
            sleep=self.clock.sleep, jitter=lambda: 0)
        if getattr(self, "zero_latency", False):
            self.sync._request_budget.SEND_INTERVAL = 0

    def publish(self, data):
        self.published = {p.name: p.read_bytes() for p in self.data.glob("*.json")}
        path = self.stage / "next.json"
        changed = path.exists()
        if changed:
            self.remote = path.read_bytes()
        return changed

    def seed(self):
        self.produce()
        self.publish(None)
        self.new_runner(60)
        data = self.produce()
        self.publish(data)
        return data

    def test_path_move_true_age_quiet_changed_only_and_key_independence(self):
        first = self.seed()
        self.assertIsNotNone(self.remote)
        before = self.remote
        stamp = first["source_freshness"]["sources"]["profile"]["last_success_at"]
        previous_day = self.Date.now().date()
        self.new_runner(60)
        data = self.produce()
        crossed = self.Date.now().date() != previous_day
        self.assertEqual(len(self.sent), 6 if crossed else 4)
        self.assertEqual(self.publish(data), crossed)
        if not crossed:
            self.assertEqual(self.remote, before)
        self.assertEqual(data["source_freshness"]["sources"]["profile"]["last_success_at"], stamp)
        self.assertGreater(data["source_freshness"]["sources"]["profile"]["age_seconds"], 0)
        envelope = json.loads(before)
        self.assertEqual(set(e["group"] for e in envelope["entries"]), {"profile", "aggregate_curves"})
        for forbidden in ("synthetic", str(self.data), "ledger", "generation", "authorization"):
            self.assertNotIn(forbidden, before.decode())
        other = mod.IntervalsSync("i123", "different")
        other.data_dir, other._acquisition = self.data, self.sync._acquisition
        other._cached_script_hash = "frozen-input"
        self.assertEqual(mod.HostedSlowCache(other).scope, envelope["scope"])
        budget = data["source_freshness"]["budget"]
        self.assertEqual(budget["scope"], "hosted_invocation")
        for field in ("requests_today", "sync_requests_today", "sync_daily_limit", "sync_remaining"):
            self.assertIsNone(budget[field])

    def test_mixed_profile_export_restore_and_four_send_quiet_tick(self):
        self.seed()
        initial = next(row for row in json.loads(self.remote)["entries"] if row["group"] == "profile")
        projected = mod.AcquisitionStore.project("profile", self.profile)
        self.assertEqual(initial["payload"], projected)
        self.assertEqual(initial["payload"]["sportSettings"][0]["power_zones"],
                         [55, 75, 90, 105, 120, 150, 999])
        self.assertTrue(all(row["power_zones"] is None
                            for row in initial["payload"]["sportSettings"][1:]))
        # Allow any selected night-base date rollover to finish before the quiet tick.
        for _ in range(2):
            self.new_runner(60)
            data = self.produce()
            self.publish(data)
        self.assertEqual(len(self.sent), 4)
        self.assertFalse(data["source_freshness"]["warnings"])
        entry = next(row for row in self.sync._acquisition.entries.values() if row["group"] == "profile")
        self.assertEqual(entry["payload"], projected)
        self.assertEqual(entry["last_success"], initial["last_success"])
        self.assertNotIn(entry["key"], self.sync._acquisition.acquired)

    def test_every_projected_profile_field_preserves_null_and_rejects_nested_shapes(self):
        self.seed()
        good = json.loads(self.remote)
        cache = self.sync._hosted_cache
        for field in sorted(mod.AcquisitionStore.PROFILE_FIELDS):
            with self.subTest(profile_field=field):
                envelope = copy.deepcopy(good)
                row = next(r for r in envelope["entries"] if r["group"] == "profile")
                row["payload"][field] = None
                self.assertEqual(mod.AcquisitionStore.project("profile", row["payload"]), row["payload"])
                restored = next(r for r in cache.validate(envelope).values() if r["group"] == "profile")
                self.assertIsNone(restored["payload"][field])
                if field != "sportSettings":
                    for bad in ({}, []):
                        row["payload"][field] = bad
                        with self.assertRaisesRegex(ValueError, "^profile shape$"):
                            cache.validate(envelope)
        for field in sorted(mod.AcquisitionStore.SPORT_FIELDS):
            with self.subTest(sport_field=field):
                envelope = copy.deepcopy(good)
                row = next(r for r in envelope["entries"] if r["group"] == "profile")
                row["payload"]["sportSettings"][0][field] = None
                self.assertEqual(mod.AcquisitionStore.project("profile", row["payload"]), row["payload"])
                restored = next(r for r in cache.validate(envelope).values() if r["group"] == "profile")
                self.assertIsNone(restored["payload"]["sportSettings"][0][field])
                for bad in ({"unexpected": 1}, [[1]], [{}]):
                    row["payload"]["sportSettings"][0][field] = bad
                    with self.assertRaisesRegex(ValueError, "^sport shape$"):
                        cache.validate(envelope)

    def test_diagnostic_categories_never_echo_exception_values(self):
        self.seed()
        self.new_runner(3601)
        data = self.produce()
        cache = self.sync._hosted_cache
        path = self.stage / "next.json"
        path.unlink()
        cases = [(ValueError("sport shape"), "sport shape"),
                 (ValueError("curve shape"), "curve shape"),
                 (ValueError("oversize envelope"), "oversize envelope"),
                 (ValueError("private-payload-example"), "ValueError"),
                 (ValueError(["private-payload-example"]), "ValueError"),
                 (PermissionError("private-payload-example", "/example/private-file"), "PermissionError"),
                 (TypeError("private-payload-example"), "TypeError"),
                 (KeyError("private-payload-example"), "KeyError"),
                 (json.JSONDecodeError("private-payload-example", "private-payload-example", 0),
                  "JSONDecodeError")]
        for error, category in cases:
            for operation, target, reason in ((cache.restore, "_read", "restore rejected"),
                                               (lambda: cache.export(data), "validate", "export refused")):
                with self.subTest(category=category, operation=target):
                    output = io.StringIO()
                    with mock.patch.object(cache, target, side_effect=error), contextlib.redirect_stdout(output):
                        operation()
                    self.assertEqual(output.getvalue().strip(),
                        "hosted_cache_unavailable: " + reason + " (" + category
                        + "); normal reads remain available.")
                    self.assertFalse(path.exists())

    def test_whole_envelope_validation_and_no_partial_import(self):
        self.seed()
        good = json.loads(self.remote)
        mutations = []
        def change(fn):
            value = copy.deepcopy(good)
            fn(value)
            mutations.append(value)
        change(lambda e: e.update(unknown=1))
        change(lambda e: e.update(version=2))
        change(lambda e: e["scope"].update(repository="54321"))
        change(lambda e: e["scope"].update(athlete="0" * 64))
        change(lambda e: e["scope"].update(producer="other"))
        change(lambda e: e["entries"][0].update(unknown=1))
        change(lambda e: e["entries"][0].update(group="activities"))
        change(lambda e: e["entries"][-1]["descriptor"].update(endpoint="../wellness"))
        change(lambda e: e["entries"][-1]["descriptor"]["params"].update(unexpected=True))
        change(lambda e: e["entries"][0].update(last_success=self.clock() + 999))
        change(lambda e: e["entries"][0].update(last_attempt=0))
        change(lambda e: e["entries"][0].update(ttl=1))
        change(lambda e: next(r for r in e["entries"] if r["group"] == "aggregate_curves").update(payload={"list": [{}]}))
        change(lambda e: e["entries"].append(copy.deepcopy(e["entries"][0])))
        for value in mutations:
            with self.subTest(value=value.get("version")):
                self.new_runner()
                (self.stage / "cache.json").write_text(json.dumps(value))
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertTrue(self.sync.begin_tick())
                self.assertEqual(self.sync._acquisition.entries, {})
                self.assertEqual(self.sync._acquisition.warnings, [])
        for body in (b"{", b'{"version":1,"version":1}', b" " * (mod.HostedSlowCache.MAX_BYTES + 1)):
            self.new_runner()
            (self.stage / "cache.json").write_bytes(body)
            with contextlib.redirect_stdout(io.StringIO()):
                self.sync.begin_tick()
            self.assertEqual(self.sync._acquisition.entries, {})

    def test_symlink_directory_and_nested_payload_traps(self):
        self.seed()
        good = json.loads(self.remote)
        self.new_runner()
        target = self.stage / "cache.json"
        target.unlink()
        target.symlink_to(self.data / "latest.json")
        with contextlib.redirect_stdout(io.StringIO()):
            self.sync.begin_tick()
        self.assertEqual(self.sync._acquisition.entries, {})
        target.unlink()
        target.mkdir()
        with self.assertRaises(ValueError):
            self.sync._hosted_cache._read(target)
        target.rmdir()
        for value in ({"unexpected": "field"}, {"sportSettings": [{"ftp": {"unexpected": 1}}]}):
            bad = copy.deepcopy(good)
            row = next(e for e in bad["entries"] if e["group"] == "profile")
            row["payload"] = value
            with self.assertRaises(ValueError):
                self.sync._hosted_cache.validate(bad)

    def test_no_export_on_failed_core_slow_refresh_hold_or_unpublished_object(self):
        self.seed()
        for failure in ("events", "power-curves"):
            self.new_runner(21601)
            self.refuse = lambda path, query: path.endswith(failure)
            with contextlib.redirect_stdout(io.StringIO()):
                if failure == "events":
                    before = (self.data / "latest.json").read_bytes()
                    with self.assertRaises(source.requests.exceptions.HTTPError):
                        self.produce()
                    self.assertEqual((self.data / "latest.json").read_bytes(), before)
                else:
                    self.produce()
            self.assertFalse((self.stage / "next.json").exists())
            self.assertEqual(self.sync.request_budget.count, len(self.sent))
            self.assertTrue(self.sync.request_budget.stopped)
            self.refuse = None
        self.new_runner(60)
        data = self.produce()
        path = self.stage / "next.json"
        path.unlink(missing_ok=True)
        self.assertFalse(self.sync._hosted_cache.export(copy.deepcopy(data)))
        self.assertFalse(path.exists())

    def test_slow_failure_retains_real_age_then_success_clears(self):
        self.seed()
        self.new_runner(21601)
        self.refuse = lambda path, query: path.endswith("power-curves")
        data = self.produce()
        self.assertNotEqual(data["source_freshness"]["sources"]["aggregate_curves"]["status"], "fresh")
        self.assertFalse((self.stage / "next.json").exists())
        self.refuse = None
        self.new_runner(60)
        data = self.produce()
        self.assertEqual(data["source_freshness"]["sources"]["aggregate_curves"]["status"], "fresh")
        self.assertTrue((self.stage / "next.json").exists())

    def test_over_cap_uses_current_outputs_and_resumes_without_data_warning(self):
        self.seed()
        self.new_runner(3601)
        with mock.patch.object(mod.HostedSlowCache, "MAX_ENTRIES", 1):
            data = self.produce()
        self.assertFalse((self.stage / "next.json").exists())
        self.assertFalse(data["source_freshness"]["warnings"])
        self.assertEqual(json.loads((self.data / "latest.json").read_text()), data)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(self.sync._hosted_cache.export(data))
        self.assertEqual(json.loads((self.data / "latest.json").read_text()), data)

    def test_on_demand_gaps_and_miss(self):
        self.zero_latency = True  # Gap/TTL experiment, not a transport-duration experiment.
        self.seed()
        original, published, base = self.remote, self.published, self.clock()
        counts = {}
        for gap in (300, 7200, 21601, 8 * 86400):
            self.remote, self.published, self.clock.now = original, published, base
            self.new_runner(gap)
            data = self.produce()
            counts[gap] = len(self.sent)
            self.assertEqual(data["export_freshness"]["mode"], "on_demand")
            self.assertIsNone(data["export_freshness"]["expected_update_by"])
            crossed = self.Date.now().date() != datetime.fromtimestamp(base, timezone.utc).date()
            self.assertEqual(self.publish(data), gap >= 3600 or crossed,
                             (gap, base, self.clock(), counts,
                              {k: (v["status"], v["reason"]) for k, v in data["source_freshness"]["sources"].items()}))
        late = datetime.fromtimestamp(base, timezone.utc).hour == 23
        self.assertEqual(counts, {300: 6 if late else 4, 7200: 7 if late else 5, 21601: 9, 691200: 9})
        print("On-demand no-activity sends:", counts)
        self.new_runner(300, restore=False)
        data = self.produce()
        self.assertGreater(len(self.sent), 4)
        self.assertFalse(data["source_freshness"]["warnings"])

    def test_hosted_never_uses_daily_allowance_or_sync_spacing(self):
        self.sync.begin_tick()
        budget = self.sync.request_budget
        budget.state["days"][budget.day]["sync"] = {"seed": 99999}
        budget.state["provider_limit"] = 0
        budget._save()
        data = self.produce()
        self.assertEqual(data["source_freshness"]["schedule"]["state"], "running")
        self.assertFalse(any(w["code"] in ("budget_paused", "budget_step_down")
                             for w in data["source_freshness"]["warnings"]))
        self.publish(data)
        self.new_runner(1)
        self.assertTrue(self.sync.begin_tick())

    def test_restored_training_outputs_equal_admitted_uncached_outputs(self):
        self.zero_latency = True
        self.seed()
        native, remote, stamp = copy.deepcopy(self.published), self.remote, self.clock()
        products, counts = [], []
        for restored in (False, True):
            self.published, self.remote, self.clock.now = copy.deepcopy(native), remote, stamp
            self.new_runner(60, restore=restored)
            data = self.produce()
            counts.append(len(self.sent))
            # Real file mtimes and acquisition bookkeeping are the only differences.
            data.pop("source_freshness")
            data.pop("data_overview")
            products.append(data)
        self.assertEqual(products[0], products[1])
        crossed = self.Date.now().date() != datetime.fromtimestamp(stamp, timezone.utc).date()
        self.assertEqual(counts, [7, 6 if crossed else 4])

    def test_local_manual_old_workflow_and_supported_hosted_activation(self):
        for env, cls in (({"GITHUB_ACTIONS": "", "SECTION11_EXPORT_MODE": "manual"}, mod.RequestBudget),
                         ({"GITHUB_ACTIONS": "", "SECTION11_EXPORT_MODE": "local_scheduled"}, mod.RequestBudget),
                         ({"GITHUB_ACTIONS": "true", "SECTION11_EXPORT_EVENT": ""}, mod.RequestBudget),
                         ({"GITHUB_ACTIONS": "true", "SECTION11_EXPORT_EVENT": "workflow_dispatch"}, mod.HostedRequestBudget),
                         ({"GITHUB_ACTIONS": "true", "SECTION11_EXPORT_EVENT": "schedule",
                           "SECTION11_EXPORT_CRON": "7,37 * * * *"}, mod.HostedRequestBudget)):
            with mock.patch.dict(os.environ, env), mock.patch.object(
                    mod.IntervalsSync, "_budget_factory", mod.RequestBudget), mock.patch.object(
                    mod.time, "time", self.clock):
                sync = mod.IntervalsSync("i123", "synthetic")
                sync.data_dir = self.data
                self.assertIs(type(sync.request_budget), cls)
                sync._acquisition = self.sync._acquisition if hasattr(self.sync, "_acquisition") else None
                if cls is mod.RequestBudget:
                    self.assertIsNone(mod.HostedSlowCache(sync).stage)

    def test_transfer_failure_is_not_data_failure(self):
        self.seed()
        self.new_runner(3601)
        # Simulate only the remote-output write, not source acquisition storage.
        with mock.patch.object(mod.HostedSlowCache, "canonical", side_effect=ValueError("synthetic transfer limit")):
            data = self.produce()
        self.assertFalse(data["source_freshness"]["warnings"])
        self.assertEqual(json.loads((self.data / "latest.json").read_text()), data)
        self.assertFalse((self.stage / "next.json").exists())

    def test_failed_second_generation_cannot_export_prior_object(self):
        self.seed()
        self.new_runner(3601)
        data = self.produce()
        (self.stage / "next.json").unlink()
        with mock.patch.object(self.sync, "_intervals_get", side_effect=ValueError("synthetic shape failure")):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                self.sync.collect_training_data()
        self.assertFalse(self.sync._hosted_cache.export(data))
        self.assertFalse((self.stage / "next.json").exists())

    def test_large_population_fourfold_transport_headroom(self):
        self.seed()
        envelope = json.loads(self.remote)
        self.assertEqual(next(e["payload"] for e in envelope["entries"] if e["group"] == "profile"),
                         mod.AcquisitionStore.project("profile", mixed_profile()))
        curve = next(e for e in envelope["entries"] if e["group"] == "aggregate_curves")
        curve["payload"] = {"list": [{"id": curve["descriptor"]["params"]["curves"].split(",")[0],
                                     "secs": list(range(1, 7201)), "watts": [200] * 7200}],
                            "activities": []}
        # Full two-hour curves across fourteen distinct typed requests.
        for typ in list(mod.IntervalsSync.REPORT_SPORTS)[:12]:
            row = copy.deepcopy(curve)
            row["descriptor"]["params"]["type"] = typ
            row["descriptor"]["params"]["subMaxEfforts"] = 3
            if row["descriptor"] not in [r["descriptor"] for r in envelope["entries"]]:
                envelope["entries"].append(row)
        for index in range(400):
            envelope["entries"].append({
                "group": "messages", "descriptor": {"origin": "https://intervals.icu/api/v1",
                    "endpoint": "activity/sample-" + str(index) + "/messages", "params": {}, "schema": 1},
                "payload": ["Synthetic note. " * 20], "last_attempt": self.clock(), "last_success": self.clock(),
                "ttl": 21600, "dependency": "0" * 64})
        cache = self.sync._hosted_cache
        self.assertEqual(len(cache.validate(envelope)), len(envelope["entries"]))
        size = len(cache.canonical(envelope))
        self.assertGreaterEqual(cache.MAX_BYTES, 4 * size)
        self.assertGreaterEqual(cache.MAX_ENTRIES, 4 * len(envelope["entries"]))
        print("Large synthetic slow envelope:", len(envelope["entries"]), "entries;", size, "bytes")

    def measure_ninety_day_portable_curve_windows_do_not_accumulate(self):
        self.zero_latency = True
        self.clock.now = datetime(2026, 10, 28, 12, tzinfo=timezone.utc).timestamp()
        self.seed()
        inventory = set(self.published)
        start = self.clock()
        sizes, counts = [], []
        for day in range(90):
            self.clock.now = start + day * 86400
            self.new_runner()
            data = self.produce()
            self.publish(data)
            envelope = json.loads(self.remote)
            self.assertEqual(len(envelope["entries"]), 3, (day,
                {k: (v["status"], v["reason"]) for k, v in data["source_freshness"]["sources"].items()},
                [(e["descriptor"], e["key"] in self.sync._acquisition.consumed)
                 for e in self.sync._acquisition.entries.values() if e["group"] in mod.HostedSlowCache.GROUPS]))
            counts.append(len(self.sent))
            sizes.append(len(self.remote))
            self.assertFalse(data["source_freshness"]["warnings"])
            self.assertEqual(set(self.published), inventory)
        self.assertLess(max(sizes) - min(sizes), 128)
        self.assertGreaterEqual(mod.HostedSlowCache.MAX_BYTES, 4 * max(sizes))
        print("Ninety-day hosted portable windows:", max(sizes), "bytes; 3 entries; sends", sum(counts))

    def test_mixed_date_window_is_not_persisted_or_relabelled(self):
        self.seed()
        self.new_runner(21601)
        data = self.produce()
        cache = self.sync._hosted_cache
        entry = next(e for e in self.sync._acquisition.entries.values() if e["group"] == "aggregate_curves")
        # The existing producer can straddle midnight between constructing bounds.
        # An unrecognized range remains usable this run but is not remotely saved.
        entry["descriptor"]["params"]["curves"] = "r.2026-10-02.2026-10-28,r.2026-09-04.2026-10-01"
        (self.stage / "next.json").unlink(missing_ok=True)
        before = (self.data / "latest.json").read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(cache.export(data))
        self.assertEqual((self.data / "latest.json").read_bytes(), before)
        self.assertFalse((self.stage / "next.json").exists())

    def measure_actual_hosted_day_totals_and_pending_native_savings(self):
        # Use a midnight start and a 19-activity population.
        self.clock.now = datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp()
        self.zero_latency = True  # Align model boundaries, independent of mock HTTP duration.
        with mock.patch.object(runs.FrozenDate, "fixed", self.Date.now(timezone.utc), create=True):
            self.rows = runs.activities()
        # Its native seed has settled empty power and pending detail/stream state.
        self.published = {"latest.json": json.dumps({"recent_activities": [
            {"id": row["id"], "power_curve": {}} for row in self.rows]}).encode()}
        self.new_runner()
        self.produce()
        self.publish(None)
        self.assertEqual(next(e["payload"] for e in json.loads(self.remote)["entries"]
                              if e["group"] == "profile"),
                         mod.AcquisitionStore.project("profile", mixed_profile()))
        seed = copy.deepcopy(self.published)
        start = datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp()
        results = {}
        for minutes in (30, 15):
            os.environ["SECTION11_EXPORT_EVENT"] = "schedule"
            os.environ["SECTION11_EXPORT_CRON"] = "*/" + str(minutes) + " * * * *"
            os.environ["GITHUB_EVENT_NAME"] = "schedule"
            for retained in (False, True):
                self.published, self.remote = copy.deepcopy(seed), None
                totals, saves, quiet, population = 0, 0, [], {}
                for elapsed in range(0, 86400, minutes * 60):
                    os.environ["GITHUB_RUN_NUMBER"] = str(elapsed // (minutes * 60) + 1)
                    self.clock.now = start + elapsed
                    self.new_runner(restore=retained)
                    data = self.produce()
                    totals += len(self.sent)
                    quiet.append(len(self.sent))
                    for _, path, _ in self.sent:
                        kind = path.rsplit("/", 1)[-1]
                        if kind == "i123":
                            kind = "profile"
                        if kind.startswith("i") and kind[1:].isdigit():
                            kind = "detail"
                        population[kind] = population.get(kind, 0) + 1
                    saves += int(self.publish(data))
                    self.assertEqual(data["source_freshness"]["schedule"]["state"], "running")
                    self.assertEqual(data["export_freshness"]["mode"], "hosted_scheduled")
                    self.assertEqual(set(self.published), set(seed))
                results[(minutes, retained)] = totals
                print("Hosted day:", minutes, "retained", retained, "sends", totals,
                      "saves", saves, "last", quiet[-1], "population", population)
                if retained:
                    self.assertEqual(quiet[-1], 4)
                    self.assertLessEqual(saves, 24)
                    self.assertEqual(population["profile"], 24)
                    self.assertEqual(population["messages"], 56)
                    self.assertEqual(population["power-curves"] + population["hr-curves"], 48)
                    # Remove the measured native retry work and restore the
                    # warm-at-start library pair to reconcile the aligned model.
                    aligned = totals - population["detail"] - population["streams"] + 2
                    self.assertEqual(aligned, {30: 328, 15: 520}[minutes])
                else:
                    aligned = totals - population["detail"] - population["streams"] + 2
                    self.assertEqual(aligned, {30: 1496, 15: 2984}[minutes])
        for minutes, saved in ((30, 1168), (15, 2464)):
            self.assertEqual(results[(minutes, False)] - results[(minutes, True)], saved)


class Workflow(unittest.TestCase):
    def test_staging_and_promotion_execute_outside_checkout(self):
        text = (REPO_ROOT / "examples/json-auto-sync/auto-sync.yml").read_text()
        def block(name):
            body = text.split("# BEGIN SLOW CACHE " + name + "\n")[1].split("# END SLOW CACHE " + name)[0]
            return textwrap.dedent(body)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            checkout, runner = root / "checkout", root / "temp"
            checkout.mkdir()
            runner.mkdir()
            (checkout / "sync.py").write_text("synthetic producer")
            output = root / "output.txt"
            env = {"RUNNER_TEMP": str(runner), "GITHUB_WORKSPACE": str(checkout), "GITHUB_OUTPUT": str(output),
                   "RUNNER_OS": "Linux", "GITHUB_REPOSITORY_ID": "12345",
                   "GITHUB_RUN_ID": "42", "GITHUB_RUN_ATTEMPT": "1"}
            prior = Path.cwd()
            try:
                os.chdir(checkout)
                with mock.patch.dict(os.environ, env):
                    exec(block("STAGING"), {})
                    stage = runner / "section11-slow-cache"
                    (stage / "next.json").write_text("{}")
                    exec(block("PROMOTION"), {})
                    self.assertEqual((stage / "cache.json").read_bytes(), b"{}")
                    self.assertEqual([p.name for p in checkout.iterdir()], ["sync.py"])
                    result = dict(line.split("=", 1) for line in output.read_text().splitlines())
                    self.assertEqual(result["ready"], "true")
                    self.assertTrue(result["key"].startswith(result["prefix"]))
                    self.assertLess(len(result["key"]), 512)
                    (stage / "next.json").symlink_to(checkout / "sync.py")
                    with self.assertRaises(ValueError):
                        exec(block("PROMOTION"), {})
            finally:
                os.chdir(prior)

    def test_pins_order_conditions_and_publication_separation(self):
        path = REPO_ROOT / "examples/json-auto-sync/auto-sync.yml"
        text = path.read_text()
        names = ["Restore slow sources", "Run sync", "Verify generated data",
                 "Publish data and update README", "Prepare changed slow sources for saving", "Save changed slow sources"]
        positions = [text.index("- name: " + name) for name in names]
        self.assertEqual(positions, sorted(positions))
        sha = "55cc8345863c7cc4c66a329aec7e433d2d1c52a9"
        for action in ("restore", "save"):
            self.assertIn("actions/cache/" + action + "@" + sha + " # v6.1.0", text)
        self.assertEqual(text.count("path: ${{ runner.temp }}/section11-slow-cache/cache.json"), 2)
        self.assertIn("steps.publish.outcome == 'success'", text)
        self.assertIn("steps.sync.outputs.cache_changed == 'true'", text)
        self.assertNotIn("always()", text)
        artifact = text.split("- name: Upload data files for download")[1].split("- name:")[0]
        self.assertNotIn("cache", artifact)
        self.assertNotIn("state", artifact)
        publication = text.split("# BEGIN DATA PUBLICATION RULES")[1].split("# END DATA PUBLICATION RULES")[0]
        self.assertNotIn("slow-cache", publication)
        self.assertNotIn("cache.json", publication)
        self.assertIn("timeout-minutes: 15", text)
        self.assertIn("cancel-in-progress: false", text)


if __name__ == "__main__":
    unittest.main()
