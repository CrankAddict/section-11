"""Offline admission, persistence and actual-send boundary acceptance checks."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import requests
from _harness import (BudgetClock as Clock, BudgetDateTime, load_module_by_path,
                      SYNC_PATH, PUSH_PATH, NetworkBlocked)

sync_mod = load_module_by_path("budget_sync", SYNC_PATH)
push_mod = load_module_by_path("budget_push", PUSH_PATH)
sync_mod.datetime = BudgetDateTime
push_mod.datetime = BudgetDateTime


def response(status=200, payload=None, headers=None):
    out = requests.Response()
    out.status_code = status
    out._content = json.dumps(payload if payload is not None else {}).encode()
    out.headers.update(headers or {})
    return out


class BudgetCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = Clock()
        self.data_dir = Path(self.tmp.name) / "data"
        self.data_dir.mkdir()
        override = mock.patch.dict(os.environ, {"SECTION11_STATE_DIR": str(Path(self.tmp.name) / "state")})
        override.start()
        self.addCleanup(override.stop)
        self.sync = sync_mod.IntervalsSync("i123", "synthetic")
        self.sync.data_dir = self.data_dir
        self.budget = self.new_budget()
        self.sync._request_budget = self.budget
        self.sent = []
        self.replies = []

        def boundary(session, prepared, **kwargs):
            if not self.budget.degraded and self.budget._handle is None:
                raise NetworkBlocked("send bypassed budget")
            if not self.budget.degraded:
                disk = json.loads((self.budget.root / "ledger.json").read_text())
                if disk["last_run"]["count"] != self.budget.count:
                    raise NetworkBlocked("send was not durably charged")
            if len(self.sent) >= self.budget.count:
                raise NetworkBlocked("multiple sends for one admission")
            self.sent.append((prepared.method, prepared.url))
            return self.replies.pop(0) if self.replies else response()

        self.guard = mock.patch.object(requests.sessions.Session, "send", boundary)
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.addCleanup(mock.patch.stopall)

    def new_budget(self, module=sync_mod, caller="sync"):
        return module.RequestBudget(self.data_dir, caller, module.RequestBudgetRefused,
                                    module.RequestBudget.fingerprint("i123", "synthetic"),
                                    clock=self.clock, sleep=self.clock.sleep, jitter=lambda: 0)

    def request(self, priority="core", endpoint="activities"):
        return self.budget.request(requests, "get", "https://intervals.icu/api/v1/athlete/i123/" + endpoint,
                                   endpoint, priority, timeout=(5, 30))

    def state(self):
        with self.budget._lock():
            self.budget._load()
            return self.budget.state

    def set_spent(self, sync=0, push=0):
        with self.budget._lock():
            self.budget._load()
            self.budget.state["days"][self.budget.day] = {
                "sync": {"seed": sync}, "push": {"seed": push}}
            self.budget._save()

    def test_guard_rejects_bypass(self):
        with self.assertRaises(NetworkBlocked):
            requests.get("https://intervals.icu/api/v1/athlete/i123", timeout=1)

    def test_shared_blocks_are_identical(self):
        def block(path):
            text = path.read_text()
            return text.split("# Shared request controller.", 1)[1].split("# End shared request controller.", 1)[0]
        self.assertEqual(block(SYNC_PATH), block(PUSH_PATH))

    def test_429_120_stops_run_and_restart_until_full_hold(self):
        self.replies = [response(429, headers={"Retry-After": "120"})]
        start = self.clock()
        self.request()
        self.assertEqual(self.state()["hold_until"], start + 120)
        with self.assertRaises(sync_mod.RequestBudgetRefused):
            self.request()
        self.clock.now += 119
        restarted = self.new_budget()
        with self.assertRaises(sync_mod.RequestBudgetRefused):
            restarted.request(requests, "get", "https://intervals.icu", "profile", "core", timeout=1)
        self.clock.now += 1
        self.budget = self.new_budget()
        self.sent.clear()
        self.request()
        self.assertEqual(self.budget.count, 1)

    def test_http_date_is_not_capped(self):
        from email.utils import format_datetime
        target = datetime.fromtimestamp(self.clock() + 172800, timezone.utc)
        self.replies = [response(429, headers={"Retry-After": format_datetime(target)})]
        self.request()
        self.assertEqual(self.state()["hold_until"], target.timestamp())

    def test_headerless_backoff_grows_and_caps(self):
        for expected in (60, 120, 240, 480, 900, 900):
            self.budget = self.new_budget()
            self.sent.clear()
            start = self.clock()
            self.replies = [response(429)]
            self.request()
            self.assertEqual(self.state()["hold_until"], start + expected)
            self.clock.now += expected

    def test_reserve_boundary_and_one_extra(self):
        self.state()
        expected = self.budget.expected_core()
        self.set_spent(sync=7000 - expected)
        with self.assertRaises(sync_mod.RequestBudgetRefused):
            self.request("optional", "messages")
        self.set_spent(sync=6999 - expected)
        self.request("optional", "messages")
        with self.assertRaises(sync_mod.RequestBudgetRefused):
            self.request("optional", "messages")
        self.request()
        self.assertEqual(len(self.sent), 2)

    def test_window_201_waits_for_oldest(self):
        with self.budget._lock():
            self.budget._load()
            self.budget.state["window"] = [self.clock() - 899] * 200
            self.budget._save()
        with self.assertRaises(sync_mod.RequestBudgetRefused):
            self.request()
        self.clock.now += 1
        self.request()
        self.assertEqual(len(self.sent), 1)

    def test_daily_reset_and_clock_rollback(self):
        self.set_spent(sync=7000)
        with self.assertRaises(sync_mod.RequestBudgetRefused):
            self.request()
        self.clock.now += 86400
        self.request()
        self.clock.now -= 86400
        with self.assertRaises(sync_mod.RequestBudgetRefused):
            self.request()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(len(self.state_without_load()["days"]), 2)

    def test_midnight_hold_expires_for_first_core_send(self):
        self.clock.now = datetime(2026, 10, 28, 23, 59, 50, tzinfo=timezone.utc).timestamp()
        start = self.clock()
        self.set_spent(sync=6999)
        self.replies = [response(429, headers={"Retry-After": "60"})]
        self.request()
        self.clock.now = start + 59
        self.budget = self.new_budget()
        self.sent.clear()
        with self.assertRaisesRegex(sync_mod.RequestBudgetRefused, "provider hold active"):
            self.request()
        self.assertEqual(self.budget.day, "2026-10-29")
        self.assertEqual(self.budget._remaining(), 7000)
        self.assertEqual(self.sent, [])
        self.clock.now = start + 60
        self.budget = self.new_budget()
        self.request()
        state = self.state()
        self.assertEqual(state["hold_until"], start + 60)
        self.assertEqual(sum(state["days"]["2026-10-28"]["sync"].values()), 7000)
        self.assertEqual(state["days"]["2026-10-29"]["sync"], {"activities": 1})
        self.assertEqual(self.budget._remaining(), 6999)
        self.assertEqual(state["window"], [start, start + 60])
        self.assertEqual(len(self.sent), 1)

    def test_midnight_hold_optional_expiry_with_sustainable_sync_spacing(self):
        # A push hold must not change the observed 30-minute sync cadence.
        self.clock.now = datetime(2026, 10, 28, 23, 30, 50, tzinfo=timezone.utc).timestamp()
        first_sync = self.clock()
        self.set_spent(sync=7000, push=999)
        self.clock.now += 1740
        self.budget = self.new_budget(push_mod, "push")
        self.replies = [response(429, headers={"Retry-After": "60"})]
        self.request()
        self.clock.now += 60
        self.budget = self.new_budget()
        self.sent.clear()
        state = self.state()
        self.assertEqual(state["runs"], [first_sync, first_sync + 1800])
        self.assertEqual(state["hold_until"], self.clock())
        self.assertEqual(self.budget.day, "2026-10-29")
        self.assertEqual(self.budget._remaining(), 7000)
        self.assertEqual(self.budget.expected_core(), 192)
        self.request("optional", "messages")
        self.assertEqual(self.budget._remaining(), 6999)
        self.assertEqual(self.state()["days"]["2026-10-29"]["sync"], {"messages": 1})
        previous = self.state()["days"]["2026-10-28"]
        self.assertEqual(sum(previous["sync"].values()) + sum(previous["push"].values()), 8000)
        self.assertEqual(len(self.sent), 1)

    def test_one_minute_sync_spacing_across_midnight_reserves_core(self):
        self.clock.now = datetime(2026, 10, 28, 23, 59, 50, tzinfo=timezone.utc).timestamp()
        first_sync = self.clock()
        self.replies = [response(429, headers={"Retry-After": "60"})]
        self.request("optional", "messages")
        self.clock.now += 60
        self.budget = self.new_budget()
        self.sent.clear()
        state = self.state()
        self.assertEqual(state["runs"], [first_sync, first_sync + 60])
        self.assertEqual(state["hold_until"], self.clock())
        self.assertEqual(self.budget.day, "2026-10-29")
        self.assertEqual(self.budget._remaining(), 7000)
        self.assertEqual(self.budget.expected_core(), 5760)
        self.request("optional", "messages")
        self.set_spent(sync=7000 - self.budget.expected_core())
        with self.assertRaisesRegex(sync_mod.RequestBudgetRefused, "reserved for core reads"):
            self.request("optional", "messages")
        self.assertEqual(len(self.sent), 1)
        self.request()
        self.assertEqual(self.budget._remaining(), 5759)
        self.assertEqual(len(self.sent), 2)

    def test_expected_core_in_last_minutes_of_utc_day(self):
        self.clock.now = datetime(2026, 10, 28, 23, 57, 30, tzinfo=timezone.utc).timestamp()
        with self.budget._lock():
            self.budget._load()
            self.budget.state["runs"] = [self.clock() - 120, self.clock() - 60, self.clock()]
            self.budget._save()
        self.assertEqual(self.budget.expected_core(), 12)
        for seconds, expected in ((30, 8), (60, 4), (50, 4), (9, 4)):
            self.clock.now += seconds
            self.state()
            self.assertEqual(self.budget.expected_core(), expected)
        self.request()
        self.assertEqual(self.budget.expected_core(), 3)

    def state_without_load(self):
        return json.loads((self.budget.root / "ledger.json").read_text())

    def test_corrupt_and_deleted_ledger_do_not_refill(self):
        self.request()
        path = self.budget.root / "ledger.json"
        for corrupt in (True, False, True):
            if corrupt:
                path.write_text("{")
            else:
                path.unlink()
            other = self.new_budget()
            with self.assertRaises(sync_mod.RequestBudgetRefused):
                other.request(requests, "get", "https://intervals.icu", "profile", "core", timeout=1)
        self.assertEqual(len(self.sent), 1)

    def test_fresh_hosted_run_and_restart_count(self):
        self.request()
        other = self.new_budget()
        with other._lock():
            other._load()
            self.assertEqual(other._remaining(), 6999)
        self.assertEqual(self.state_without_load()["days"][self.budget.day]["sync"]["activities"], 1)

    def test_sync_push_share_hold_and_reserve(self):
        self.set_spent(sync=7000)
        with self.assertRaises(sync_mod.RequestBudgetRefused):
            self.request()
        self.budget = self.new_budget(push_mod, "push")
        self.request()
        self.replies = [response(429, headers={"Retry-After": "120"})]
        self.request()
        with self.assertRaises(sync_mod.RequestBudgetRefused):
            self.new_budget().request(requests, "get", "https://intervals.icu", "profile", "core", timeout=1)

    def test_write_reservation_refuses_two_and_protects_three(self):
        self.set_spent(sync=7000, push=998)
        push = push_mod.IntervalsPush("i123", "synthetic")
        push.data_dir = self.data_dir
        push._request_budget = self.new_budget(push_mod, "push")
        result = push.move_event(1, "2026-11-01")
        self.assertEqual(result["outcome"], "not_applied")
        self.assertEqual(self.sent, [])
        self.set_spent(sync=7000, push=997)
        self.budget = push._request_budget
        self.replies = [response(200, {"id": 1, "start_date_local": "2026-10-29T08:00:00"}),
                        response(500),
                        response(200, {"id": 1, "start_date_local": "2026-11-01T08:00:00"})]
        result = push.move_event(1, "2026-11-01")
        self.assertEqual(result["outcome"], "applied")
        self.assertEqual([m for m, u in self.sent], ["GET", "PUT", "GET"])
        self.assertFalse(any(p.name.startswith("ledger.") for p in self.data_dir.rglob("*")))

    def test_lock_excludes_other_controller_during_write(self):
        other = self.new_budget(push_mod, "push")
        with self.budget._lock():
            with self.assertRaises(push_mod.RequestBudgetRefused):
                with other.reserve_write():
                    self.fail("competing operation acquired lock")

    def test_refusal_does_not_increment_endpoint_or_retry_attempts(self):
        self.set_spent(sync=7000)
        self.assertEqual(self.sync._fetch_activity_power_curve("1"), ("transient", "request_budget"))
        self.assertEqual(self.sync._power_curve_fetches_used, 0)
        self.assertEqual(self.sync._read_retry_extra_attempts_used, 0)
        self.assertEqual(self.sync._fetch_activity_intervals("1"), ("deferred", "request_budget"))
        self.assertEqual(self.sync._fetch_activity_streams("1", ["time"]), ("deferred", "request_budget"))
        self.assertEqual(self.sync._stream_responses["1"][2], 0)
        self.assertEqual(self.sent, [])

    def test_refused_optional_generation_keeps_files_byte_identical(self):
        files = {}
        for name in ("latest.json", "history.json", "ftp_history.json"):
            path = self.data_dir / name
            path.write_bytes(b'{"last_good": true}\n')
            files[path] = path.read_bytes()
        self.set_spent(sync=7000)
        with self.assertRaises(sync_mod.RequestBudgetRefused):
            with contextlib.redirect_stdout(io.StringIO()):
                self.sync.generate_history()
        self.assertEqual({p: p.read_bytes() for p in files}, files)
        self.assertEqual(self.sent, [])

    def test_redirects_disabled_and_auth_errors_distinct(self):
        for code in (301, 401, 403, 404):
            self.replies = [response(code, headers={"Location": "https://intervals.icu/other"})]
            with self.assertRaises(requests.exceptions.HTTPError):
                self.sync._intervals_get("activities")
        self.assertEqual(len(self.sent), 4)
        self.assertEqual(self.state()["hold_until"], 0)

    def test_pacing_and_logged_remaining_header_does_not_lower_allowance(self):
        self.replies = [response(headers={"X-RateLimit-Limit": "2500,8000", "X-RateLimit-Remaining": "0,0"})]
        self.request()
        self.request()
        self.assertEqual(self.clock.sleeps, [.5])
        self.assertEqual(len(self.sent), 2)

    def test_lower_provider_limit_applies_and_headers_log_once_per_day(self):
        headers = {"X-RateLimit-Limit": "2500,1002", "X-RateLimit-Remaining": "0,0"}
        self.replies = [response(headers=headers), response(headers=headers)]
        self.request()
        self.request()
        with self.assertRaisesRegex(sync_mod.RequestBudgetRefused, "daily allowance exhausted"):
            self.request()
        self.assertEqual(self.budget._effective_allowances(), (1002, 2))
        log = (self.budget.root / "budget.log").read_text()
        self.assertEqual(log.count("X-RateLimit-Limit"), 1)
        self.assertEqual(log.count("X-RateLimit-Remaining"), 1)
        self.clock.now += 86400
        self.replies = [response(headers=headers)]
        self.request()
        self.assertEqual((self.budget.root / "budget.log").read_text().count("X-RateLimit-Limit"), 2)

    def test_absent_and_malformed_headers_cannot_invent_capacity(self):
        self.replies = [response(), response(headers={"X-RateLimit-Limit": "unknown,9000"})]
        self.request()
        self.request()
        self.assertEqual(self.budget._effective_allowances(), (8000, 7000))
        self.assertEqual(self.budget._remaining(), 6998)


    def test_folder_default_and_override(self):
        cls = sync_mod.RequestBudget
        for env in ({}, {"XDG_STATE_HOME": "/ignored"}, {"LOCALAPPDATA": "/ignored"}):
            self.assertEqual(cls.state_base(self.data_dir, env),
                             self.data_dir / "state/request-budget")
        self.assertEqual(cls.state_base(self.data_dir, {"SECTION11_STATE_DIR": self.tmp.name}),
                         Path(self.tmp.name) / "request-budget")

    def test_folder_and_key_scopes_are_separate_even_with_shared_override(self):
        identity = sync_mod.RequestBudget.fingerprint("i123", "synthetic")
        other = push_mod.RequestBudget(Path(self.tmp.name) / "other-data", "push",
                                      push_mod.RequestBudgetRefused, identity,
                                      clock=self.clock, sleep=self.clock.sleep, jitter=lambda: 0)
        separate = sync_mod.RequestBudget(self.data_dir, "sync", sync_mod.RequestBudgetRefused,
                                          sync_mod.RequestBudget.fingerprint("i123", "different"),
                                          clock=self.clock, sleep=self.clock.sleep, jitter=lambda: 0)
        self.assertNotEqual(other.root, self.budget.root)
        self.assertNotEqual(separate.root, self.budget.root)
        self.assertNotEqual(identity, sync_mod.RequestBudget.fingerprint("i456", "synthetic"))
        self.request()
        self.assertNotIn("synthetic", (self.budget.root / "ledger.json").read_text())
        self.assertNotIn("Authorization", (self.budget.root / "ledger.json").read_text())
        with separate._lock():
            separate._load()
            self.assertEqual(separate._remaining(), 7000)

    def test_private_modes(self):
        if os.name == "nt":
            self.skipTest("POSIX permissions")
        self.request()
        self.assertEqual(self.budget.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.budget.root.parent.stat().st_mode & 0o777, 0o700)
        for path in self.budget.root.iterdir():
            if path.is_file():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600, str(path))

    def test_override_inside_data_folder_is_allowed(self):
        with mock.patch.dict(os.environ, {"SECTION11_STATE_DIR": str(self.data_dir / "private")}):
            budget = self.new_budget()
        self.assertFalse(budget.degraded)
        self.assertEqual(budget.root.parent, self.data_dir / "private/request-budget")
        with budget._lock():
            budget._load()
            budget._save()
        self.assertTrue((budget.root / "ledger.json").is_file())

    def test_unwritable_state_allows_only_three_core_reads_and_one_warning(self):
        # Deliberately injected storage error. No actual permissions are changed.
        with mock.patch.object(self.budget, "_atomic", side_effect=PermissionError("synthetic unwritable")), \
                contextlib.redirect_stderr(io.StringIO()) as warning:
            for i in range(3):
                self.request()
            with self.assertRaises(sync_mod.RequestBudgetRefused):
                self.request()
            with self.assertRaises(sync_mod.RequestBudgetRefused):
                self.request("optional")
            with self.assertRaises(sync_mod.RequestBudgetRefused):
                with self.budget.reserve_write():
                    self.fail("unverified write reservation")
        self.assertEqual(len(self.sent), 3)
        self.assertEqual(warning.getvalue().count("Warning:"), 1)
        self.assertIn("today=unknown", self.budget.summary())
        self.assertEqual(list(self.data_dir.iterdir()), [])

    def test_uncreatable_state_and_lock_failure_do_not_dispatch_writes(self):
        for target in ("mkdir", "open"):
            budget = self.new_budget(push_mod, "push")
            patcher = mock.patch.object(Path, "mkdir", side_effect=OSError("synthetic create failure")) if target == "mkdir" else (
                mock.patch.object(os, "open", side_effect=OSError("synthetic lock open failure")))
            with patcher, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(push_mod.RequestBudgetRefused):
                    with budget.reserve_write():
                        self.fail("write admitted without durable reservation")
            self.assertTrue(budget.degraded)

    def test_unknown_capacity_still_honours_429_within_invocation(self):
        with mock.patch.object(self.budget, "_atomic", side_effect=OSError("synthetic failure")), \
                contextlib.redirect_stderr(io.StringIO()):
            self.replies = [response(429, headers={"Retry-After": "120"})]
            self.request()
            with self.assertRaises(sync_mod.RequestBudgetRefused):
                self.request()
        self.assertEqual(len(self.sent), 1)

    def test_retry_after_starts_at_response_receipt(self):
        class Delayed:
            def get(inner, url, **kwargs):
                self.clock.now += 30
                return response(429, headers={"Retry-After": "120"})
        start = self.clock()
        self.budget.request(Delayed(), "get", "https://intervals.icu", "profile", "core", timeout=1)
        self.assertEqual(self.state()["hold_until"], start + 150)

    def test_corrupt_ledger_retains_long_hold_across_midnight(self):
        self.replies = [response(429, headers={"Retry-After": "172800"})]
        self.request()
        (self.budget.root / "ledger.json").write_text("{}")
        self.clock.now += 86400
        self.budget = self.new_budget()
        with self.assertRaises(sync_mod.RequestBudgetRefused):
            self.request()
        self.assertEqual(len(self.sent), 1)

    def test_write_dispatched_then_verification_refused_is_unknown(self):
        push = push_mod.IntervalsPush("i123", "synthetic")
        push.data_dir = self.data_dir
        self.budget = self.new_budget(push_mod, "push")
        push._request_budget = self.budget

        @push_mod.budgeted_write
        def operation(client):
            client._intervals_request("get", client._url("events/1"), timeout=1)
            client._intervals_request("put", client._url("events/1"), timeout=1)
            client.request_budget._refuse("synthetic verification unavailable")

        self.assertEqual(operation(push)["outcome"], "unknown")
        self.assertEqual([method for method, url in self.sent], ["GET", "PUT"])
        self.assertFalse(any(p.name.startswith("ledger.") for p in self.data_dir.rglob("*")))

    def test_zero_send_summary_log_still_has_private_directory_modes(self):
        argv = ["sync.py", "--athlete-id", "i123", "--intervals-key", "synthetic",
                "--output", str(self.data_dir / "latest.json")]
        with mock.patch("sys.argv", argv), \
                mock.patch.object(sync_mod, "_run_sync"), \
                mock.patch.object(sync_mod, "_rotate_log_if_needed"), \
                mock.patch.object(sync_mod.IntervalsSync, "_budget_factory",
                                  staticmethod(lambda *args: self.budget)), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            sync_mod.main()
        self.assertEqual(output.getvalue().count("Intervals requests:"), 1)
        self.assertEqual((self.budget.root / "budget.log").read_text().count("Intervals requests:"), 1)
        self.assertEqual(self.budget.count, 0)
        if os.name != "nt":
            self.assertEqual(self.budget.root.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(self.budget.root.stat().st_mode & 0o777, 0o700)
            self.assertEqual((self.budget.root / "budget.log").stat().st_mode & 0o777, 0o600)
        self.assertFalse(any(p.name.startswith("ledger.") for p in self.data_dir.rglob("*")))

    @contextlib.contextmanager
    def attachment_transport(self, replies):
        from urllib.parse import urlsplit
        sent = []
        charged = self.budget.count

        def boundary(session, prepared, **kwargs):
            nonlocal charged
            self.assertFalse(kwargs["allow_redirects"])
            self.assertNotIn("Authorization", prepared.headers)
            self.assertNotIn("Cookie", prepared.headers)
            self.assertIsNone(urlsplit(prepared.url).username)
            self.assertIsNone(urlsplit(prepared.url).password)
            if urlsplit(prepared.url).hostname == "intervals.icu":
                charged += 1
                self.assertIsNotNone(self.budget._handle)
                disk = json.loads((self.budget.root / "ledger.json").read_text())
                self.assertEqual(disk["last_run"]["count"], charged)
                self.assertEqual(disk["days"][self.budget.day]["sync"]["attachment"], charged)
            self.assertEqual(self.budget.count, charged)
            sent.append(prepared.url)
            out = replies.pop(0)
            out._content_consumed = True
            return out

        with mock.patch.object(requests.sessions.Session, "send", boundary), \
                mock.patch("requests.sessions.get_netrc_auth",
                           return_value=("synthetic-user", "synthetic-password")):
            yield sent
        self.assertEqual(replies, [])

    def attachment_body(self):
        from test_route_validity import route_bytes
        return route_bytes()

    def attachment_ok(self):
        out = response()
        out._content = self.attachment_body()
        return out

    def baseline_route(self):
        from test_route_validity import FrozenClock
        path = os.environ.get("S11_PARITY_BASELINE")
        baseline = load_module_by_path("budget_attachment_baseline", Path(path)) if path else sync_mod
        source = baseline.IntervalsSync("i123", "synthetic")
        with mock.patch.object(baseline, "datetime", FrozenClock), \
                mock.patch.object(baseline.requests, "get", return_value=self.attachment_ok()):
            return source._download_and_parse_route("https://intervals.icu/route.gpx", "route.gpx")

    def test_attachment_on_host_to_off_host_matches_baseline(self):
        from test_route_validity import FrozenClock
        expected = self.baseline_route()
        replies = [response(302, headers={"Location": "https://files.example.invalid/route.gpx"}),
                   self.attachment_ok()]
        with self.attachment_transport(replies) as sent, \
                mock.patch.object(sync_mod, "datetime", FrozenClock):
            actual = self.sync._download_and_parse_route("https://intervals.icu/route.gpx", "route.gpx")
        self.assertEqual(actual, expected)
        self.assertEqual(actual["route_status"], "ok")
        self.assertEqual(self.budget.count, 1)
        self.assertEqual(len(sent), 2)

    def test_attachment_relative_on_host_hop_charges_each_send(self):
        replies = [response(302, headers={"Location": "../final.gpx"}), self.attachment_ok()]
        with self.attachment_transport(replies) as sent:
            result = self.sync._download_and_parse_route("https://intervals.icu/routes/start", "route.gpx")
        self.assertEqual(result["route_status"], "ok")
        self.assertEqual(sent, ["https://intervals.icu/routes/start", "https://intervals.icu/final.gpx"])
        self.assertEqual(self.budget.count, 2)

    def test_attachment_loop_missing_location_and_hop_limit_fail_cleanly(self):
        cases = [
            ([response(302, headers={"Location": "/route.gpx#same"})], 1),
            ([response(302)], 1),
            ([response(302, headers={"Location": "/" + str(i)}) for i in range(6)], 6),
        ]
        for replies, count in cases:
            with self.subTest(count=count), self.attachment_transport(replies) as sent:
                result = self.sync._download_and_parse_route("https://intervals.icu/route.gpx", "route.gpx")
            self.assertEqual(result, {"route_status": "failed", "route_error": "download failed"})
            self.assertEqual(len(sent), count)

    def test_attachment_five_redirects_are_allowed(self):
        replies = [response(code, headers={"Location": "/" + str(i)})
                   for i, code in enumerate((301, 302, 303, 307, 308))]
        replies.append(self.attachment_ok())
        with self.attachment_transport(replies) as sent:
            result = self.sync._download_and_parse_route("https://intervals.icu/route.gpx", "route.gpx")
        self.assertEqual(result["route_status"], "ok")
        self.assertEqual(len(sent), 6)
        self.assertEqual(self.budget.count, 6)

    def test_attachment_credentials_are_omitted_on_every_hop(self):
        replies = [response(302, headers={"Location": "//second:secret@intervals.icu/final.gpx?signature=synthetic"}),
                   self.attachment_ok()]
        with self.attachment_transport(replies) as sent:
            result = self.sync._download_and_parse_route(
                "https://first:secret@files.example.invalid/route.gpx", "route.gpx")
        self.assertEqual(result["route_status"], "ok")
        self.assertEqual(self.budget.count, 1)
        self.assertEqual(sent, ["https://files.example.invalid/route.gpx",
                                "https://intervals.icu/final.gpx?signature=synthetic"])

    def test_attachment_second_hop_refusal_preserves_last_good_outputs(self):
        from test_route_validity import event, attachment
        self.state()
        self.set_spent(sync=6999 - self.budget.expected_core())
        previous = {}
        for name in ("latest.json", "history.json", "ftp_history.json", "intervals.json",
                     "routes.json", "saved_workouts.json", "route_eta_history.json"):
            path = self.data_dir / name
            path.write_bytes(b'{"last_good":true,"last_attempt_at":"unchanged"}\n')
            previous[path] = (path.read_bytes(), path.stat().st_mtime_ns)
        rows = [event(attachments=[attachment(url="https://intervals.icu/route.gpx")])]

        @sync_mod.preserve_budget_outputs
        def route_generation(client):
            self.assertEqual(client._generate_terrain(rows), set())
            self.assertEqual(client._routes_data["events"][0]["route_error"], "download failed")
            (client.data_dir / "routes.json").write_text(json.dumps(client._routes_data))

        with self.attachment_transport([response(302, headers={"Location": "/second.gpx"})]) as sent:
            with self.assertRaises(sync_mod.RequestBudgetRefused):
                route_generation(self.sync)
        self.assertEqual(len(sent), 1)
        self.assertEqual(self.budget.count, 1)
        self.assertEqual(self.sync._read_retry_extra_attempts_used, 0)
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in previous}, previous)


if __name__ == "__main__":
    unittest.main()
