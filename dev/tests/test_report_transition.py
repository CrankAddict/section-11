"""Offline v11.84 transition, paired-summary and report example contracts.

No live requests or athlete data. Generated manifests/installations stay in
TemporaryDirectory under the caller's test scratch. This is source validation,
not a claim about arbitrary model-generated reports.
"""
import contextlib
import copy
import io
import json
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from _harness import (REPO_ROOT, SYNC_PATH, NetworkBlocked, install_verb_guard,
                      load_module_by_path, restore_verb_guard)
import test_init_update_distribution as dist

mod = load_module_by_path("s11_report_transition", SYNC_PATH)
originals = None
REPORTS = REPO_ROOT / "examples/reports"
RENAMES = {
    f"{old}_REPORT_{kind}.md": f"{new}_REPORT_{kind}.md"
    for old, new in (("WEEK" + "LY", "7_DAY"), ("BLO" + "CK", "28_DAY"))
    for kind in ("TEMPLATE", "EXAMPLES")
}


def setUpModule():
    global originals
    originals = install_verb_guard(mod.requests)


def tearDownModule():
    restore_verb_guard(mod.requests, originals)


def stale_references(root):
    found = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in (".md", ".py", ".json", ".cjs", ".yml"):
            continue
        if path.name in RENAMES or path.name in ("manifest.json", "changelog.json"):
            continue
        content = path.read_text()
        if path.name == "SECTION_11.md":
            # Historical release notes are the one prose exception.
            content = content.split("### Changelog", 1)[-1]
            content = re.split(r"\n## ", content, maxsplit=1)[-1]
        for name in RENAMES:
            if name in content:
                found.append((path.relative_to(root).as_posix(), name))
    return found


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 7, 14, 12, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


def ride(**changes):
    row = {"id": "synthetic-ride", "type": "VirtualRide",
           "start_date_local": "2026-06-24T10:00:00", "moving_time": 3600,
           "elapsed_time": 3600, "name": "Synthetic ride",
           "paired_event_id": 42, "icu_training_load": 40}
    row.update(changes)
    return row


class PairedSummary(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sync = mod.IntervalsSync("synthetic", "synthetic")
        self.sync.data_dir = Path(tmp.name)
        self.sync._intervals_data = {}
        self.event = {"id": 42, "name": "Synthetic paired plan",
                      "paired_activity_id": "synthetic-ride", "moving_time": 3600,
                      "workout_doc": {"duration": 3600, "steps": []}}
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(mod, "datetime", Clock))
        for method, value in (("_build_terrain_for_activity", {}),
                              ("_build_weather_for_activity", {}),
                              ("_get_activity_messages", ("ok", [])),
                              ("_fetch_activity_power_curve", ("no_data", None))):
            self.stack.enter_context(mock.patch.object(self.sync, method, return_value=value))

    def formatted(self, act=None, events=None, prior=None):
        return self.sync._format_activities(
            [act or ride()], paired_events=events,
            previous_latest_lookup=prior)[0]

    def test_expired_pairing_without_retained_summary_adds_no_request(self):
        with mock.patch.object(self.sync, "_intervals_get", side_effect=AssertionError("extra request")) as get:
            self.assertEqual(self.sync._prepare_session_structures(
                [ride()], [], {}, now=Clock.now(timezone.utc)), {})
            row = self.formatted(events=[])
        get.assert_not_called()
        self.assertFalse(row["has_structure"])
        self.assertEqual(row["interval_data"]["plan_match"],
                         {"method": "plan_match_v2", "status": "not_assessed",
                          "plan": {"event_id": "42", "name": None},
                          "issues": ["detail_unavailable"]})

    def test_fetched_exact_event_name_and_explicit_duration_are_reused(self):
        row = self.formatted(events=[self.event])
        summary = row["interval_data"]["plan_match"]
        self.assertEqual(summary["status"], "no_steps")
        self.assertEqual(summary["plan"]["name"], self.event["name"])
        self.assertEqual(summary["plan"]["duration_s"], 3600)
        self.assertNotIn("steps", summary)
        # Current event identity and empty steps are refreshed across all 28 days.
        self.assertTrue(row["plan_pairing"]["duration"]["within_tolerance"])

    def test_pairing_conflict_ambiguity_and_absent_name_never_invent_metadata(self):
        cases = [([dict(self.event, paired_activity_id="different")], "pairing_conflict"),
                 ([self.event, self.event], "ambiguous_pairing"),
                 ([dict(self.event, athlete_id=9)], "pairing_conflict")]
        for events, issue in cases:
            with self.subTest(issue=issue):
                summary = self.formatted(ride(athlete_id=8), events)["interval_data"]["plan_match"]
                self.assertEqual(summary["status"], "not_assessed")
                self.assertEqual(summary["plan"], {"event_id": "42", "name": None})
                self.assertIn(issue, summary["issues"])
        event = {k: v for k, v in self.event.items() if k != "name"}
        self.assertIsNone(self.formatted(events=[event])["interval_data"]["plan_match"]["plan"]["name"])

    def test_retained_assessments_and_detail_are_preserved(self):
        for status in ("followed", "partly_followed", "not_followed"):
            summary = {"method": "plan_match_v1", "status": status,
                       "issues": ["last_captured"], "plan": {"event_id": "42"}}
            saved = {"synthetic-ride": {"structure_summary": copy.deepcopy(summary)}}
            current = self.formatted(prior=saved)["interval_data"]["plan_match"]
            self.assertEqual(current["status"], status)
            self.assertTrue(current["assessment_retained"])
            self.assertIsNone(current["plan"]["name"])
            self.assertEqual(saved["synthetic-ride"]["structure_summary"], summary)
        block = {"status": "no_steps", "plan": {"event_id": "42", "name": "Captured"}}
        self.sync._intervals_data = {"activities": [
            {"activity_id": "synthetic-ride", "session_structure": block}]}
        row = self.formatted(events=[])
        self.assertTrue(row["has_structure"])
        self.assertEqual(row["interval_data"]["plan_match"]["status"], "no_steps")
        self.assertEqual(row["interval_data"]["plan_match"]["plan"]["name"], "Captured")

    def test_cold_start_legacy_fallback_and_unassessed_identity_refresh(self):
        for status in ("unknown", "not_assessed"):
            saved = {"synthetic-ride": {"structure_summary":
                     {"method": "plan_match_v2", "status": status,
                      "issues": ["detail_unavailable"]}}}
            summary = self.formatted(events=[self.event], prior=saved)["interval_data"]["plan_match"]
            self.assertEqual(summary["status"], "no_steps")
            self.assertEqual(summary["plan"]["name"], self.event["name"])

    def test_unpaired_and_walk_hike_keep_their_existing_statuses(self):
        for pairing in (None,):
            summary = self.formatted(ride(paired_event_id=pairing))["interval_data"]["plan_match"]
            self.assertEqual(summary, {"method": "plan_match_v2", "status": "unknown",
                                       "issues": ["detail_unavailable"]})
        for sport in ("Walk", "Hike"):
            row = self.formatted(ride(type=sport), [self.event])
            self.assertEqual(row["interval_data"]["plan_match"]["issues"], ["sport_out_of_scope"])
            self.assertEqual(row["interval_data"]["plan_match"]["status"], "unknown")
            self.assertFalse(row["has_structure"])

    def test_collect_uses_existing_activity_and_resolved_event_response(self):
        self.sync.week_start_day = 6
        calls = []
        act = ride(start_date_local="2026-07-12T10:00:00")
        event = dict(self.event, start_date_local="2026-07-12T10:00:00", category="WORKOUT")
        def get(endpoint, params=None):
            calls.append((endpoint, params))
            if endpoint == "activities":
                return [act]
            if endpoint == "events":
                return [] if (params or {}).get("category") else [event]
            if endpoint == "wellness":
                return [{"id": "2026-07-14", "ctl": 40, "atl": 42}]
            if endpoint.startswith("wellness/"):
                return {"ctl": 40, "atl": 42}
            return {}
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(self.sync, "_intervals_get", side_effect=get))
            for method, value in (("_generate_saved_workouts", None),
                                  ("_generate_terrain", set()), ("_generate_route_weather", {}),
                                  ("_generate_intervals", set()), ("_prepare_session_structures", {})):
                stack.enter_context(mock.patch.object(self.sync, method, return_value=value))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            result = self.sync.collect_training_data()
        summary = result["recent_activities"][0]["interval_data"]["plan_match"]
        self.assertEqual(summary["status"], "no_steps")
        self.assertEqual(summary["plan"]["name"], event["name"])
        event_calls = [params for endpoint, params in calls if endpoint == "events"]
        self.assertEqual(len(event_calls), 2)  # Existing plan and health-marker requests.
        plans = [params for params in event_calls if params.get("resolve") == "true"]
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["oldest"], "2026-06-17")
        self.assertEqual([p["category"] for p in event_calls if "category" in p], ["INJURED,SICK"])
        self.assertFalse(any(endpoint.startswith("events/") for endpoint, _ in calls))
        self.assertEqual(self.sync.INTERVAL_RETENTION_DAYS, 14)


class Transition(unittest.TestCase):
    def test_normal_generator_init_and_update_keep_all_eight_files_managed(self):
        files = {"examples/reports/" + name: (REPORTS / name).read_bytes()
                 for name in list(RENAMES) + list(RENAMES.values())}
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            dist.write_tree(repo, files)
            with dist.working_directory(repo), contextlib.redirect_stdout(io.StringIO()):
                mod.do_generate_manifest()
            manifest = json.loads((repo / "manifest.json").read_text())
        self.assertEqual(set(manifest["files"]), set(files))
        installed = dist.run_init(dist.repo_archive(manifest, files=files), bootstrap=False)
        self.assertEqual({p: b for p, b in installed.installed.items() if p != "manifest.json"}, files)
        before = {"section11/examples/reports/" + name: b"old report\n" for name in RENAMES}
        def get(url, **kwargs):
            return dist.FakeResponse(files[url.removeprefix(dist.sync_mod.SECTION11_REPO_RAW + "/")])
        updated = dist.run_update(before, ["y"], manifest=manifest, patches=[
            mock.patch.object(dist.requests, "get", side_effect=get)])
        for name, body in files.items():
            self.assertEqual(updated.files["section11/" + name], body)
        self.assertEqual(len(updated.prompts), 1)
        self.assertNotIn("orphaned", updated.prompts[0])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist.write_tree(root, files)
            self.assertEqual(mod._find_orphaned_files(manifest["files"], root), [])
            bad = dict(manifest["files"])
            removed = "examples/reports/" + next(iter(RENAMES))
            del bad[removed]
            self.assertEqual(mod._find_orphaned_files(bad, root), [removed])

    def test_pointer_date_target_and_reference_sweep(self):
        for old, new in RENAMES.items():
            pointer = (REPORTS / old).read_text()
            self.assertIn("Renamed in v11.84", pointer)
            self.assertIn(f"]({new})", pointer)
            self.assertIn("first release after 31 December 2026", pointer)
            self.assertIn("safe to delete", pointer)
            self.assertLess(len(pointer.splitlines()), 10)
        self.assertEqual(stale_references(REPO_ROOT), [])

    def test_reference_sweep_rejects_stale_link_but_accepts_new_target_and_training_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "notes.md"
            doc.write_text("weekly load, training block, " + next(iter(RENAMES.values())))
            self.assertEqual(stale_references(root), [])
            doc.write_text("use " + next(iter(RENAMES)))
            self.assertEqual(len(stale_references(root)), 1)


class ReportContracts(unittest.TestCase):
    def reports(self, stem):
        return re.findall(r"\x60\x60\x60text\n(.*?)\x60\x60\x60", (REPORTS / f"{stem}_REPORT_EXAMPLES.md").read_text(), re.S)

    def assert_layout(self, block, stem):
        self.assertTrue(block.splitlines()[1].startswith("Data updated:"))
        self.assertNotRegex(block, r"[·|↑↓→]|\b[nN]/[aA]\b|\[[^\]]+\]")
        self.assertFalse(any(line.startswith(("  ", "- ")) for line in block.splitlines()))
        self.assertNotRegex(block, r"no_steps|not_assessed|partly_followed|plan_match_v")
        self.assertNotIn("High drift:", block)
        self.assertNotIn("Planned TSS:", block)
        if "**Fun facts" in block:
            self.assertLess(block.index("**Fun facts"), block.index("**Interpretation**"))
        for line in block.splitlines():
            if line.startswith("HRRc:"):
                self.assertNotRegex(line, r"stable|improving|declining|trend")
        if stem == "7_DAY":
            self.assertNotRegex(block, r"Best efforts|Power curve:|HR curve:|Most work in a week:")
            if "**Next 7 days**" in block:
                self.assertNotRegex(block.split("**Next 7 days**")[1], r"\d\d:\d\d")
        if stem == "28_DAY":
            self.assertNotRegex(block, r"(?m)Ceilings:|Ramp rate:|e?FTP:|W/kg:|28-day progression|^Peak ")

    def test_example_layout_missing_values_and_fun_fact_order(self):
        for stem in ("7_DAY", "28_DAY", "SEASON"):
            reports = self.reports(stem)
            self.assertEqual(len(reports), 2)
            for block in reports:
                self.assert_layout(block, stem)
        good = self.reports("7_DAY")[0]
        for bad in (good.replace("HRRc: 31 bpm", "HRRc: 31 bpm declining"),
                    good.replace("45m, Easy spin", "45m, Easy spin, 09:00"),
                    good.replace("**Intensity (cycling", "Power curve: higher (cycling")):
            with self.assertRaises(AssertionError):
                self.assert_layout(bad, "7_DAY")

    def assert_equivalents(self, block):
        work, work_n, work_basis = re.search(
            r"Work: (\d+) kJ\n\(energy of about ([\d.]+) (.*?)\)", block).groups()
        carbs, carb_n, carb_basis = re.search(
            r"Carbs used: (\d+) g\n\(about ([\d.]+) (.*?)\)", block).groups()
        self.assertEqual(work_basis, carb_basis)
        grams = 27 if carb_basis == "medium bananas" else int(
            re.search(r"\*\*Equivalents \(your (\d+) g bottles\)\*\*", block).group(1))
        self.assertEqual(float(carb_n), round(float(carbs) / grams, 1))
        self.assertEqual(float(work_n), round(float(work) / (105 if carb_basis == "medium bananas" else 4 * grams), 1))
        self.assertNotRegex(block, r"kcal|mechanical|USDA")

    def test_full_example_fact_inventory_and_equivalent_arithmetic(self):
        for stem in ("7_DAY", "28_DAY", "SEASON"):
            block = self.reports(stem)[0]
            for label in ("Max power (1 s):", "Max HR:", "Longest ride:", "Distance ridden:", "Climbed:",
                          "Work:", "Carbs used:", "Most work in a day:", "Time in the saddle:"):
                self.assertIn(label, block)
            self.assert_equivalents(block)
            peaks_block = block.split("**Peaks", 1)[1].split("Time in the saddle:")[0] if "**Peaks" in block else ""
            peaks = re.findall(r"^(5 s|1 min|5 min|20 min|60 min):", peaks_block, re.M)
            self.assertEqual(peaks, [] if stem == "28_DAY" else ["5 s", "1 min", "5 min", "20 min", "60 min"])
            self.assertNotRegex(block, r"Climbed: 0\b")
        banana = self.reports("7_DAY")[0]
        for bad in (banana.replace("about 9.3 medium", "about 10.0 medium"),
                    banana.replace("about 28.6 medium", "about 30.0 medium"),
                    banana.replace("about 28.6 medium", "about 27.8 medium")):
            with self.assertRaises(AssertionError):
                self.assert_equivalents(bad)
        self.assertIn("**Equivalents (your 60 g bottles)**", self.reports("28_DAY")[0])
        self.assertIn("(energy of about 58.3 bottles)", self.reports("28_DAY")[0])

    def test_plan_counts_and_marker_only_highlights(self):
        first, second = self.reports("7_DAY")
        for block in (first, second):
            line = re.search(r"^Plan: (.*)$", block, re.M).group(1)
            self.assertNotRegex(line, r"\b0 |not.assessed|_")
            self.assertNotIn("**Sessions**", block)
            self.assertNotRegex(block, r"(?m)^[✅⚠️❌].*(?:Walk|Hike)")
        self.assertIn("Plan: 1 partly followed\nPlanned without steps: 2", first)
        highlights = first.split("**Highlights**\n")[1].split("\n\n", 1)[0]
        self.assertEqual(highlights, "⚠️ 10 Jul Stepped, step 2 below target")
        self.assertNotIn("**Highlights**", second)
        self.assertNotIn("✅", second)
        block = self.reports("28_DAY")[0]
        self.assertIn("Rides: 12 of 14 planned", block)
        self.assertIn("Walks: 3 of 3 planned", block)
        self.assertNotIn("Walks: 3 of 3 planned ✅", block)
        self.assertIn("Checked: 9 of 12 followed", block)

    def test_every_warning_and_failure_survives_highlight_selection(self):
        def check(block, required):
            highlights = block.split("**Highlights**\n")[1].split("\n\n", 1)[0].splitlines()
            for row in required:
                self.assertIn(row, highlights)
            self.assertTrue(all(row.startswith(("✅ ", "⚠️ ", "❌ ")) for row in highlights))
        block = self.reports("28_DAY")[0]
        required = ["⚠️ 18 Jun Intervals, steps off", "⚠️ 25 Jun Hill, steps off",
                    "⚠️ 10 Jul Stepped, step 2 below target"]
        check(block, required)
        for row in required:
            with self.assertRaises(AssertionError):
                check(block.replace(row + "\n", ""), required)
        fragment = (REPORTS / "7_DAY_REPORT_EXAMPLES.md").read_text().split("## Deviating sets fragment")[1]
        check(fragment, ["⚠️ 13 Jul VO2, set 3 stopped", "❌ 14 Jul Tempo, steps off"])
        self.assertIn("Set 3 (320 W): 2/8, 305 W avg", fragment)
        self.assertIn("Below target: reps 3-4, 290/288 W", fragment)
        self.assertIn("Not ridden: reps 5-8", fragment)

    def test_report_environment_uses_flag_and_labels_indoor_values(self):
        for stem in ("7_DAY", "28_DAY", "SEASON"):
            template = (REPORTS / f"{stem}_REPORT_TEMPLATE.md").read_text()
            examples = (REPORTS / f"{stem}_REPORT_EXAMPLES.md").read_text()
            self.assertNotRegex(template + examples, r"(?i)virtual|zwift")
            for term in ("solely from the emitted fact environment", "Never infer environment from names",
                         "Any indoor distance, speed or climbing outside the split"):
                self.assertIn(term, template)
        sync = mod.IntervalsSync("synthetic", "synthetic")
        for flag, name, expected in ((True, "Outdoor road loop", "indoor_virtual"),
                                     (False, "Indoor trainer ride", "outdoor"),
                                     (None, "Outdoor road loop", "unknown")):
            row = {"id": "synthetic", "type": "Ride", "date": "2026-07-09",
                   "indoor": flag, "name": name, "source": "conflicting source app"}
            raw = {"synthetic": {"id": "synthetic", "type": "Ride",
                   "start_date_local": "2026-07-09T12:00:00", "trainer": flag}} if flag is not None else {}
            self.assertEqual(sync._fact_activity(row, formatted=True, raw_by_id=raw)["environment"], expected)
            self.assertEqual(sync._fact_activity(row, formatted=True)["environment"], "unknown")
        self.assertIn("Longest ride: 9 Jul Easy spin, 20m\nDistance: 8 km (indoor)", self.reports("7_DAY")[1])

    def test_chunk_totals_order_and_seven_day_agreement(self):
        block, sparse = self.reports("28_DAY")
        self.assertIn("Weeks: 17 Jun, 24 Jun, 1 Jul, 8 Jul", block)
        weekly = block.split("**Week by week")[1].split("**Wellness")[0]
        hours = [float(v.removesuffix("h")) for v in re.search(r"^Hours: (.*)$", weekly, re.M).group(1).split(", ")]
        tss = [int(v) for v in re.search(r"^TSS: (.*)$", weekly, re.M).group(1).split(", ")]
        self.assertEqual(hours, [6, 6.5, 4.75, 5])
        self.assertEqual(tss, [270, 300, 220, 235])
        total_hours, sessions, total_tss = re.search(
            r"Total: ([\d.]+)h, (\d+) sessions, (\d+) TSS", block).groups()
        self.assertEqual(sum(hours), float(total_hours))
        self.assertEqual(sum(tss), int(total_tss))
        self.assertIn("Hours: 5h", self.reports("7_DAY")[0])
        self.assertIn("TSS: 235", self.reports("7_DAY")[0])
        sections = ("**Totals**", "**Plan**", "**Fitness", "**Week by week",
                    "**Wellness", "**Intensity (", "**Highlights**", "**Key session:",
                    "**Best efforts", "**DFA a1", "**Section 11 flags**", "**Fun facts", "**Interpretation**")
        positions = [block.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions))
        paragraphs = block.split("**Interpretation**\n")[1].strip().split("\n\n")
        self.assertEqual([p.split(":")[0] for p in paragraphs], ["Load", "Quality", "Watch", "Next"])
        self.assertIn("Tempo 21 Jun: 3.8%\nTempo 28 Jun: 3.4% (plan changes power)", block)
        self.assertIn("HRV/RHR/Sleep N (24 Jun): 6/7 days", block)
        self.assertNotIn("N (17 Jun)", block)
        self.assertIn("Hours: 1h, 0h, 0h, 0.67h", sparse)
        self.assertIn("EF: 1.20, unavailable, unavailable, 1.23", sparse)
        self.assertEqual((datetime(2026, 7, 14) - datetime(2026, 6, 17)).days + 1, 28)

    def test_season_acwr_phase_gaps_and_sunday_boundaries(self):
        block, sparse = self.reports("SEASON")
        values = [None, None, None, .75, .9, 1.1, 1.3, 1.4]
        bins = [sum(v is not None and v < .8 for v in values),
                sum(v is not None and .8 <= v <= 1.3 for v in values),
                sum(v is not None and 1.3 < v <= 1.5 for v in values)]
        self.assertEqual([int(x) for x in re.findall(r"ACWR (?!known).*?: (\d+)", block)], bins)
        self.assertIn("ACWR known: 5 of 8 weeks", block)
        self.assertIn("ACWR above 1.3: none", sparse)
        self.assertIn("ACWR known: 1 of 2 weeks", sparse)
        self.assertEqual(datetime(2026, 5, 17).weekday(), 6)
        self.assertEqual((datetime(2026, 7, 11) - datetime(2026, 5, 17)).days + 1, 56)
        self.assertIn("17 May-20 Jun: Build 4 weeks, Deload 1\n21-27 Jun: no detected phase\n28 Jun-11 Jul: Base 2 weeks", block)
        yoy = block.split("**June 2026 (June 2025 in brackets)**")[1].split("**Notable**")[0]
        self.assertNotRegex(yoy, r"\bvs\b|\(\+|\(-|difference")
        self.assertNotIn("none", block.split("**Notable**")[1].split("**Fun facts")[0])
        self.assertEqual(block.count("Longest ride:"), 1)
        self.assertIn("Longest ride: 28 Jun Meadow, 2h45m\nDistance: 72 km (outdoor)", block)
        self.assertNotIn("Previous phase:", sparse)

    def test_sources_aliases_dfa_and_omission_contracts(self):
        for stem, source in (("7_DAY", "latest.json.fun_facts.rolling_7d"),
                             ("28_DAY", "latest.json.fun_facts.rolling_28d"),
                             ("SEASON", "history.json.fun_facts.season")):
            text = (REPORTS / f"{stem}_REPORT_TEMPLATE.md").read_text()
            for term in (source, "USDA medium-banana fallback", "27 g carbohydrate",
                         "105 kcal per medium banana", "work_kj / 105", "carbs_used / 27",
                         "work_kj / (4 * grams per bottle)", "not fueling advice",
                         "current official dossier", "whether in prose"):
                self.assertIn(term, text)
        block = (REPORTS / "28_DAY_REPORT_TEMPLATE.md").read_text()
        for term in ("rolling_7d_chunks", "14 days", "dfa_a1_profile_28d", "drift_sessions",
                     "wellness_28d", "lt2_estimate.n_sessions_indoor", "NEVER"):
            self.assertIn(term, block)
        for path in (REPO_ROOT / "SECTION_11.md", REPO_ROOT / "SKILL.md"):
            text = path.read_text()
            self.assertIn('"weekly report"', text)
            self.assertIn('"block report"', text)
            self.assertIn("not_assessed", text)

    def test_website_description_and_expected_assertion_agree(self):
        pages = json.loads((REPO_ROOT / ".github/site/pages.json").read_text())
        desc = next(p["description"] for p in pages if p["route"] == "reports.html")
        self.assertIn("7-day, 28-day and season", desc)
        self.assertIn(desc, (REPO_ROOT / ".github/site/test.cjs").read_text())


if __name__ == "__main__":
    unittest.main()
