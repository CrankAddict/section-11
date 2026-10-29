"""Folder-local state, actual publication selection and local timer choices."""
import contextlib
import io
import json
import math
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from _harness import SYNC_PATH
import test_source_schedule as fixtures
from test_data_overview import workflow_rules

sync_mod, push_mod = fixtures.sync_mod, fixtures.push_mod


class StateLocation(unittest.TestCase):
    new_sync = fixtures.SourceCase.new_sync
    next_run = fixtures.SourceCase.next_run
    produce = fixtures.SourceCase.produce

    def setUp(self):
        fixtures.SourceCase.setUp(self)
        default = mock.patch.dict(os.environ, {"SECTION11_STATE_DIR": "", "GITHUB_ACTIONS": ""})
        default.start()
        self.addCleanup(default.stop)
        self.new_sync()

    def controller(self, module, folder, caller="sync", key="synthetic"):
        return module.RequestBudget(folder, caller, module.RequestBudgetRefused,
            module.RequestBudget.fingerprint("i123", key),
            clock=self.clock, sleep=self.clock.sleep, jitter=lambda: 0)

    def test_output_parent_selected_before_state_in_local_and_updater_layouts(self):
        for name in ("training-data", "updater-root"):
            root = self.root / name
            (root / "section11/examples").mkdir(parents=True)
            if name == "updater-root":
                (root / "Custom").mkdir()
                (root / "archives").mkdir()
            target = root / "latest.json"
            def run(sync, args, token, repo):
                budget = self.controller(sync_mod, sync.data_dir)
                sync._request_budget = budget
                self.assertEqual(sync.data_dir, root)
                self.assertEqual(budget.root.parent, root / "state/request-budget")
                self.assertTrue(sync.begin_tick())
                self.assertEqual(sync._acquisition.root.parent, root / "state/sources")
            with mock.patch("sys.argv", ["sync.py", "--athlete-id", "i123", "--intervals-key",
                                        "synthetic", "--output", str(target)]), \
                    mock.patch.object(sync_mod, "_run_sync", side_effect=run), \
                    mock.patch.object(sync_mod, "_rotate_log_if_needed"), \
                    contextlib.redirect_stdout(io.StringIO()):
                sync_mod.main()
            self.assertTrue((root / "state/README.md").is_file())

    def test_push_discovery_precedence_layout_cwd_explicit_and_missing(self):
        cwd = self.root / "cwd"
        cwd.mkdir()
        (cwd / "latest.json").write_text("{}")
        for name in ("training-data", "updater-root"):
            root = self.root / name
            script = root / "section11/examples/agentic/push.py"
            script.parent.mkdir(parents=True)
            (root / "latest.json").write_text("{}")
            with mock.patch.object(push_mod, "__file__", str(script)), mock.patch.object(Path, "cwd", return_value=cwd):
                self.assertEqual(push_mod.IntervalsPush.find_data_dir(), root)
                self.assertEqual(push_mod.IntervalsPush.find_data_dir(cwd), cwd)
                (root / "latest.json").unlink()
                self.assertEqual(push_mod.IntervalsPush.find_data_dir(), cwd)
        (cwd / "latest.json").unlink()
        with mock.patch.object(Path, "cwd", return_value=cwd), contextlib.redirect_stderr(io.StringIO()) as messages:
            push = push_mod.IntervalsPush("i123", "synthetic")
            push._budget_factory = lambda *args: self.controller(push_mod, args[0], "push")
            self.assertIsNone(push.data_dir)
            self.assertTrue(push.request_budget.degraded)
            with self.assertRaises(push_mod.RequestBudgetRefused):
                with push.request_budget.reserve_write():
                    self.fail("unknown capacity admitted a write")
        self.assertIn("--data-dir", messages.getvalue())
        self.assertIn("capacity is unknown", messages.getvalue())
        self.assertIsNone(push.request_budget.root)
        self.assertEqual(list(cwd.iterdir()), [])

    def test_cli_reads_check_interval_from_config_file(self):
        (self.root / ".sync_config.json").write_text(json.dumps({
            "athlete_id": "i123", "intervals_key": "synthetic", "check_interval_minutes": 5}))
        def run(sync, args, token, repo):
            sync._request_budget = self.controller(sync_mod, sync.data_dir)
            expected = 300 if args.output else 60
            self.assertEqual(sync.check_interval_seconds, expected)
            self.assertTrue(sync.begin_tick())
            self.assertEqual(sync._acquisition.schedule["requested_interval_seconds"], expected)
        for argv in (["--output", str(self.data / "latest.json")], []):
            with contextlib.chdir(self.root), \
                    mock.patch("sys.argv", ["sync.py"] + argv), \
                    mock.patch.object(sync_mod, "_run_sync", side_effect=run), \
                    mock.patch.object(sync_mod, "_rotate_log_if_needed"), \
                    contextlib.redirect_stdout(io.StringIO()):
                sync_mod.main()

    def test_push_cli_explicit_option_and_implicit_push_subcommand(self):
        for tail, handler in ((["list"], "_cmd_list"), (["--name", "Example"], "_cmd_push")):
            with mock.patch("sys.argv", ["push.py", "--athlete-id", "i123", "--api-key",
                                        "synthetic", "--data-dir", str(self.data)] + tail), \
                    mock.patch.object(push_mod, handler) as command:
                push_mod.main()
            self.assertEqual(command.call_args.args[1].data_dir, self.data)

    def test_default_shared_sync_push_count_and_separate_data_folders(self):
        self.produce()
        sync_budget = self.sync.request_budget
        prior = sum(sum(v.values()) for v in sync_budget.state["days"][sync_budget.day].values())
        push = push_mod.IntervalsPush("i123", "synthetic", data_dir=self.data)
        push._request_budget = self.controller(push_mod, self.data, "push")
        self.assertEqual(push.request_budget.root, sync_budget.root)
        self.sync, self.sent = push, []
        self.reply = lambda prepared, path, query: fixtures.response(200, {"id": 1, "name": "Updated"})
        self.assertTrue(push.update_event(1, {"name": "Updated"})["success"])
        ledger = json.loads((push.request_budget.root / "ledger.json").read_text())
        total = sum(sum(v.values()) for v in ledger["days"][push.request_budget.day].values())
        self.assertEqual(total, prior + len(self.sent))
        for override in ("", str(self.root / "shared-state")):
            with mock.patch.dict(os.environ, {"SECTION11_STATE_DIR": override}):
                first = self.controller(sync_mod, self.data)
                other = self.controller(sync_mod, self.root / "other")
                self.assertNotEqual(first.root, other.root)
                with other._lock():
                    other._load()
                    self.assertEqual(other._remaining(), 7000)
        self.assertIn("scope=local_data_folder_key_athlete", push.request_budget.summary())

    def test_override_contains_all_state_and_preserves_parent_readme(self):
        parent = self.root / "Documents"
        state = parent / "s11-state"
        state.mkdir(parents=True)
        readme = parent / "README.md"
        readme.write_bytes(b"Existing owner README.\n\xff")
        original = (readme.read_bytes(), readme.stat().st_mtime_ns, readme.stat().st_ino)
        if os.name != "nt":
            os.chmod(parent, 0o755)
            os.chmod(state, 0o755)
        with mock.patch.dict(os.environ, {"SECTION11_STATE_DIR": str(state)}):
            self.new_sync()
            self.produce()
            budget = self.sync.request_budget
            self.assertEqual(budget.root, state / "request-budget" / budget.identity)
            self.assertEqual(self.sync._acquisition.root, state / "sources" / budget.identity)
            self.assertEqual((state / "README.md").read_text(), sync_mod.AcquisitionStore.STATE_README)
            self.assertTrue((budget.root / "ledger.json").is_file())
            self.assertTrue(list((state / "sources").rglob("*.json")))
            # push must use this exact ledger, not just a similar path.
            push = self.controller(push_mod, self.data, "push")
            self.assertEqual(push.root, budget.root)
            with push._lock():
                push._load()
                self.assertEqual(push.state["days"], budget.state["days"])
            self.next_run()
            self.produce()
        self.assertEqual({p.name for p in parent.iterdir()}, {"README.md", "s11-state"})
        self.assertEqual((readme.read_bytes(), readme.stat().st_mtime_ns, readme.stat().st_ino), original)
        self.assertFalse((self.data / "state").exists())
        if os.name != "nt":
            self.assertEqual(parent.stat().st_mode & 0o777, 0o755)
            for path in [state] + list(state.rglob("*")):
                self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o600)

    def test_explicit_override_and_default_keep_independent_counts(self):
        default = self.controller(sync_mod, self.data)
        with default._lock():
            default._load()
            default.state["days"][default.day]["sync"] = {"seed": 31}
            default._save()
        prior = (default.root / "ledger.json").read_bytes()
        state = self.root / "override"
        with mock.patch.dict(os.environ, {"SECTION11_STATE_DIR": str(state)}):
            override = self.controller(sync_mod, self.data)
            self.assertEqual(override.identity, default.identity)
            self.assertNotEqual(override.root, default.root)
            with override._lock():
                override._load()
                self.assertEqual(override._remaining(), 7000)
                override.state["days"][override.day]["sync"] = {"seed": 7}
                override._save()
            push = self.controller(push_mod, self.data, "push")
            with push._lock():
                push._load()
                self.assertEqual(push.state["days"][push.day]["sync"], {"seed": 7})
        self.assertEqual((default.root / "ledger.json").read_bytes(), prior)
        restarted = self.controller(sync_mod, self.data)
        with restarted._lock():
            restarted._load()
            self.assertEqual(restarted._remaining(), 6969)

    def test_readme_created_rewritten_atomically_and_not_rewritten_when_equal(self):
        self.produce()
        path = self.data / "state/README.md"
        expected = sync_mod.AcquisitionStore.STATE_README
        self.assertEqual(path.read_text(), expected)
        self.assertIn("earlier API key or data-folder location", expected)
        self.assertIn("can be deleted; the active one changes on every check.", expected)
        old_folders = [path.parent / area / ("0" * 32) for area in ("request-budget", "sources")]
        for folder in old_folders:
            folder.mkdir(mode=0o700)
            (folder / "keep").write_bytes(b"old identity")
            if os.name != "nt":
                os.chmod(folder / "keep", 0o600)
        before = (path.stat().st_ino, path.stat().st_mtime_ns, path.read_bytes())
        self.next_run()
        self.produce()
        self.assertEqual((path.stat().st_ino, path.stat().st_mtime_ns, path.read_bytes()), before)
        path.write_bytes(b"outdated\xff")
        with mock.patch.object(sync_mod.os, "replace", wraps=os.replace) as replace:
            self.next_run()
            self.produce()
        self.assertEqual(path.read_text(), expected)
        self.assertTrue(any(call.args[1] == path for call in replace.call_args_list))
        path.unlink()
        self.next_run()
        self.produce()
        self.assertEqual(path.read_text(), expected)
        self.assertFalse(list(path.parent.glob(".readme-*")))
        for folder in old_folders:
            self.assertEqual((folder / "keep").read_bytes(), b"old identity")
        if os.name != "nt":
            for entry in [path.parent] + list(path.parent.rglob("*")):
                self.assertEqual(entry.stat().st_mode & 0o777, 0o700 if entry.is_dir() else 0o600)

    def test_state_excluded_by_real_producer_workflow_artifact_archive_and_publisher(self):
        self.profile.update(icu_api_key="private-sentinel", authorization="private-auth")
        data = self.produce()
        state = self.data / "state"
        self.assertTrue(list(state.rglob("*.json")))
        for path in state.rglob("*"):
            if path.is_file():
                for forbidden in ("private-sentinel", "private-auth", "synthetic", "Authorization"):
                    self.assertNotIn(forbidden, path.read_text())
        overview = data["data_overview"]
        self.assertEqual(overview["state_note"], sync_mod.DataOverview.STATE_NOTE)
        self.assertEqual(data["READ_THIS_FIRST"]["state_note"], overview["state_note"])
        self.assertEqual(data["source_freshness"]["budget"]["scope"], sync_mod.RequestBudget.SCOPE)
        self.assertFalse(any(f["path"].startswith("state/") for f in overview["files"] + overview["folders"]))
        rules = workflow_rules()
        plan = rules["plan"](self.data)
        self.assertEqual(plan["mode"], "declared")
        self.assertEqual(plan["saved"], overview["managed_files"])
        self.assertFalse(any(p.startswith("state/") for p in plan["touched"]))
        previous = self.root / "previous.json"
        previous.write_text("null")
        stage = self.root / "publication"
        rules["prepare"](self.data, previous, stage)
        self.assertFalse((stage / "files/state").exists())
        self.assertEqual((stage / "files/latest.json").read_bytes(), (self.data / "latest.json").read_bytes())
        self.assertEqual(json.loads((stage / "files/latest.json").read_text())["export_freshness"],
                         data["export_freshness"])
        # The manual artifact and daily archive use these exact fixed selections.
        workflow = (SYNC_PATH.parent / "json-auto-sync/auto-sync.yml").read_text()
        artifact = workflow.split("name: training-data\n", 1)[1].split("retention-days:", 1)[0]
        paths = [line.strip() for line in artifact.split("path: |", 1)[1].splitlines() if line.strip()]
        self.assertEqual(paths, ["latest.json", "history.json", "intervals.json", "routes.json",
                                 "saved_workouts.json", "ftp_history.json"])
        self.assertIn('cp latest.json "$ARCHIVE_PATH"', workflow)
        self.assertIn('git add -- "${SAVED[@]}" "$ARCHIVE_PATH"', workflow)
        # Exercise the direct publisher's selection without any remote transport.
        with mock.patch.object(self.sync, "publish_to_github", return_value="offline") as publish, \
                mock.patch.object(self.sync, "begin_tick", return_value=True), \
                mock.patch.object(self.sync, "should_generate_history", return_value=False), \
                mock.patch.object(self.sync, "collect_training_data", return_value=data), \
                mock.patch.object(self.sync, "check_upstream_updates"), \
                mock.patch.object(sync_mod, "notify_if_updates_available"), \
                contextlib.redirect_stdout(io.StringIO()):
            sync_mod._run_sync(self.sync, SimpleNamespace(generate_history=False, output=None,
                               days=7, debug=False), "synthetic-token", "synthetic-repo")
        self.assertEqual([call.kwargs.get("filepath", "latest.json") for call in publish.call_args_list],
                         ["latest.json", "intervals.json", "routes.json", "saved_workouts.json"])
        self.assertEqual(publish.call_args_list[0].args[0]["export_freshness"], data["export_freshness"])


class ChosenInterval(unittest.TestCase):
    setUp = fixtures.SourceCase.setUp
    new_sync = fixtures.SourceCase.new_sync
    next_run = fixtures.SourceCase.next_run
    produce = fixtures.SourceCase.produce

    def test_config_values_and_invalid_values(self):
        for value in (1, 2, 5, 10):
            self.assertEqual(sync_mod.IntervalsSync._check_interval({"check_interval_minutes": value}, {}), value * 60)
        self.assertEqual(sync_mod.IntervalsSync._check_interval({}, {}), 60)
        for value in (None, True, False, 0, -1, 3, 60, "2", 2.0, [], {}):
            with contextlib.redirect_stdout(io.StringIO()) as message:
                self.assertEqual(sync_mod.IntervalsSync._check_interval({"check_interval_minutes": value}, {}), 60)
            self.assertIn("Warning: invalid check_interval_minutes", message.getvalue())
        for value in (10, "invalid"):
            with contextlib.redirect_stdout(io.StringIO()) as message:
                self.assertEqual(sync_mod.IntervalsSync._check_interval(
                    {"check_interval_minutes": value}, {"GITHUB_ACTIONS": "true"}), 60)
            self.assertEqual(message.getvalue(), "")

    def test_timer_skips_without_false_warning_and_reports_chosen_interval(self):
        self.clock.now = datetime(2026, 10, 28, 12, tzinfo=timezone.utc).timestamp()
        start = self.clock()
        for minutes in (1, 2, 5, 10):
            self.data = self.root / str(minutes)
            self.data.mkdir()
            for elapsed in range(0, minutes * 60 + 1, 60):
                self.clock.now = start + elapsed
                self.new_sync()
                self.sync.check_interval_seconds = sync_mod.IntervalsSync._check_interval({"check_interval_minutes": minutes}, {})
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    data = self.produce()
                if elapsed in (0, minutes * 60):
                    self.assertIsNotNone(data)
                    self.assertEqual(data["source_freshness"]["schedule"]["requested_interval_seconds"], minutes * 60)
                    self.assertEqual(data["source_freshness"]["schedule"]["effective_interval_seconds"], minutes * 60)
                    if elapsed:
                        self.assertEqual(len(self.sent), 4)
                else:
                    self.assertIsNone(data)
                    self.assertEqual(self.sent, [])
                    self.assertNotIn("Sources need refresh", output.getvalue())
                    self.assertNotIn("source_stale", [w["code"] for w in self.sync._acquisition.warnings])

    def test_step_down_from_two_pause_boundary_and_restore_chosen(self):
        self.clock.now = datetime(2026, 10, 28, 0, tzinfo=timezone.utc).timestamp()
        self.sync.check_interval_seconds = 120
        self.produce()
        for interval, difference in ((300, 0), (600, 0), (None, -1)):
            self.next_run()
            self.sync.check_interval_seconds = 120
            store = sync_mod.AcquisitionStore(self.sync)
            self.sync._acquisition = store
            now = self.clock()
            midnight = datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp()
            remaining = 4 * math.ceil((midnight - now) / (interval or 600)) + store.committed(now) + difference
            budget = self.sync.request_budget
            with budget._lock():
                budget._load()
                budget.state["days"][budget.day]["sync"] = {"seed": 7000 - remaining}
                budget._save()
            self.assertFalse(self.sync.begin_tick())
            self.assertEqual(store.schedule["effective_interval_seconds"], interval)
            self.assertEqual(store.schedule["requested_interval_seconds"], 120)
            if interval is not None:
                self.assertEqual(store.reserve(), remaining)
        self.clock.now = midnight
        self.new_sync()
        self.sync.check_interval_seconds = 120
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertTrue(self.sync.begin_tick())
        self.assertEqual(self.sync._acquisition.schedule["effective_interval_seconds"], 120)
        self.assertIn("Request budget: checks restored to every 2 minutes.", output.getvalue())

    def test_hosted_schedule_ignores_local_choice(self):
        self.sync.check_interval_seconds = 600
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            self.produce()
        self.assertEqual(self.sync._acquisition.schedule["requested_interval_seconds"], 60)

    def test_chosen_interval_spans_midnight_without_an_extra_tick(self):
        self.clock.now = datetime(2026, 10, 28, 23, 59, 50, tzinfo=timezone.utc).timestamp()
        start = self.clock()
        self.sync.check_interval_seconds = 600
        self.assertTrue(self.sync.begin_tick())
        for elapsed, due in ((60, False), (599, False), (600, True)):
            self.clock.now = start + elapsed
            self.new_sync()
            self.sync.check_interval_seconds = 600
            self.assertEqual(self.sync.begin_tick(), due)
            self.assertEqual(self.sync.request_budget._remaining(), 7000)
            self.assertEqual(self.sync.request_budget.day, "2026-10-29")


if __name__ == "__main__":
    unittest.main()
