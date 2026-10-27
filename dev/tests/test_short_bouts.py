"""Synthetic bout evidence and protocol arithmetic, never a coaching API."""
import copy
import json
import math
import re
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

import test_session_structure as base
from _harness import install_verb_guard, restore_verb_guard

Sync = base.Sync


def setUpModule():
    global originals
    originals = install_verb_guard(base.mod.requests)


def tearDownModule():
    restore_verb_guard(base.mod.requests, originals)


def power_result(row, target, duration=30, offset=0):
    """Protocol oracle over already validated rows, independent of producer."""
    _, _, end, _, start, observed, joules, _ = row
    if 20 < duration <= 60:
        end = min(end, max(0, row[0] + offset + duration - 1))
    if end <= start or observed <= 0 or observed / (end - start) < .95:
        return None
    mean = joules / observed
    return target - max(3, target * .01) <= mean <= target + max(3, target * .05)


def time_result(row, duration, offset):
    nominal, start, end, observed = row[:4]
    if nominal < 0 or end <= start:
        return None
    if duration - 1 - (end - start) > offset:
        return False
    return True if observed / (end - start) >= .95 else None


def sprint_result(row, target):
    """The observed W-second peak alone judges a validated sprint power target."""
    return None if row[1] is None or row[2] is None else row[2] >= target


def count_result(sets, offset=0, constraints=True):
    """Synthetic same-role prescription; a missing evaluator blocks aggregation."""
    complete, results, patterns = [], [], set()
    for step in sets:
        count, duration, rest = step["repeat"]
        patterns.add((duration, rest))
        if len(step["bouts"]) != count:
            return None
        for index, row in enumerate(step["bouts"]):
            complete.append(time_result(row, duration, offset))
            if duration <= 20:
                peaks = step.get("sprints", [])
                if (len(peaks) != count or "sprint_target_w" not in step
                        or step.get("sprint_window_s") != max(3, math.ceil(.30 * duration))):
                    return None
                results.append(sprint_result(peaks[index], step["sprint_target_w"]))
            else:
                results.append(power_result(row, step["target_w"], duration, offset))
    if (not results or any(x is not True for x in complete) or None in results
            or len(patterns) != 1 or constraints is not True):
        return None
    return sum(results), len(results), sum(results) / len(results) >= .95


class BoutEvidence(unittest.TestCase):
    setUp = base.Structure.setUp
    build = base.Structure.build
    repeated = base.LiveShape.repeated
    resolve = base.LiveShape.resolve

    def fixed(self):
        with mock.patch.object(self.sync, "_structure_offset", return_value=0):
            return self.build()

    def test_both_transitions_excluded_only_from_adherence(self):
        self.repeated(count=3, lag=0)
        self.streams["watts"][61] = 100
        block = self.fixed()
        row = block["steps"][1]["bouts"][0]
        self.assertEqual(row, [60, 61, 90, 29, 62, 27, 7560, 0])
        self.assertTrue(time_result(row, 30, 0))
        self.assertTrue(power_result(row, 280))
        # Standard set metrics still include the low transition second.
        self.assertEqual(block["steps"][1]["actual"][2], round((87 * 280 - 180) / 87, 1))
        self.streams["watts"][89] = 0
        row = self.fixed()["steps"][1]["bouts"][0]
        self.assertEqual(row[5:], [27, 7560, 0])
        self.assertTrue(power_result(row, 280))
        self.assertTrue(time_result(row, 30, 0))
        # A nearby low second inside the adherence window still counts.
        self.streams["watts"][88] = 0
        row = self.fixed()["steps"][1]["bouts"][0]
        self.assertEqual(row[5:], [27, 7280, 1])
        self.assertFalse(power_result(row, 280))

    def test_standard_coverage_cannot_be_replaced_by_adherence_coverage(self):
        self.repeated(count=3, lag=0)
        self.streams["watts"][61:63] = [None, None]
        block = self.fixed()
        row = block["steps"][1]["bouts"][0]
        self.assertEqual(row[3], 27)
        self.assertEqual(row[5], 26)
        self.assertTrue(power_result(row, 280))  # 26/27 >=95%, but 27/29 <95%.
        self.assertIsNone(time_result(row, 30, 0))
        self.assertIsNone(count_result([block["steps"][1]]))
        self.assertGreater(block["steps"][1]["actual"][6], 95)

    def test_missing_bout_retained_even_when_set_coverage_passes(self):
        self.repeated(count=24, lag=0)
        self.streams["watts"][61:90] = [None] * 29
        block = self.fixed()
        step = block["steps"][1]
        self.assertGreater(step["actual"][6], 95)
        self.assertEqual(len(step["bouts"]), 24)
        self.assertEqual(step["bouts"][0], [60, 61, 90, 0, 62, 0, None, None])
        self.assertIsNone(count_result([step]))
        step["bouts"].pop(0)
        self.assertIsNone(count_result([step]))  # Never silently use 23/23.

    def test_zero_invalid_fractional_support_and_no_last_sample_extrapolation(self):
        times = [0, 1, 1.5, 2, 2.25, 3, 4, 5, 6, 7, 8]
        watts = [999, None, 0, 200, 400, -1, True, float("nan"), float("inf"), 0, 999]
        rows = self.sync._structure_bouts([(0, 1, 9, 2, 9)], times, watts)
        self.assertEqual(rows, [[0, 1, 9, 2.5, 2, 2, 350, 1]])
        json.dumps(rows, allow_nan=False)

    def test_each_set_order_shift_and_offset(self):
        self.repeated(count=4, lag=8)
        self.act["workout_shift_secs"] = 5
        block = self.build()
        self.assertEqual(block["offset_s"], 3)
        rows = block["steps"][1]["bouts"]
        self.assertEqual([r[0] for r in rows], [65, 105, 145, 185])
        self.assertEqual(rows[0][:6], [65, 69, 98, 29, 70, 27])
        self.assertEqual(block["bout_metrics_version"], 4)
        self.assertEqual(block["version"], 6)

    def test_recording_pause_does_not_move_bouts(self):
        self.repeated(count=3, lag=0)
        before = self.build()
        self.streams["time"] = [t if t <= 75 else t + 70 for t in self.streams["time"]]
        self.act["elapsed_time"] += 70
        self.assertEqual(self.build(), before)

    def test_clipped_main_bout_uses_standard_deficit_and_selected_offset(self):
        self.repeated(count=3, lag=3)
        # Remove final recovery and cool-down: the last work ends at nominal 170.
        self.event["workout_doc"]["steps"] = self.event["workout_doc"]["steps"][:-2]
        self.event["workout_doc"]["duration"] = 170
        for horizon, expected in ((173, True), (170, True), (169, False), (143, None)):
            self.act["elapsed_time"] = horizon
            streams = {k: v[:horizon + 1] for k, v in self.streams.items()}
            with mock.patch.object(self.sync, "_structure_offset", return_value=3):
                block = self.sync._build_session_structure(self.act, self.event, streams, [])
            row = block["steps"][1]["bouts"][-1]
            self.assertIs(time_result(row, 30, 3), expected)
            self.assertEqual(row[2], min(173, horizon))
            self.assertEqual(row[4], min(145, horizon))
        self.assertIsNone(time_result([-1, 1, 30, 29, 2, 28, 7840, 0], 30, 3))

    def test_one_second_bouts_have_empty_evaluation_windows(self):
        rows = self.sync._structure_bouts([(0, 1, 1, 1, 1), (2, 3, 3, 3, 3)],
                                          list(range(5)), [280] * 5)
        self.assertEqual(rows[0], [0, 1, 1, 0, 1, 0, None, None])
        self.assertIsNone(time_result(rows[0], 1, 0))
        self.assertIsNone(power_result(rows[0], 280))

    def test_detection_boundaries_and_unsupported_fallback(self):
        for count, rest, compressed in ((2, 10, False), (3, 59, True), (3, 60, False)):
            self.repeated(count=count, lag=0, rest=rest)
            block = self.build()
            self.assertEqual(block["bout_metrics_version"], 4)
            self.assertEqual(any("bouts" in s for s in block["steps"]), compressed)
            if not compressed:
                self.assertTrue(any("adherence" in s for s in block["steps"]))
        for mutation in ("unequal", "nested", "range"):
            self.repeated(count=3, lag=0)
            steps = self.event["workout_doc"]["steps"]
            if mutation == "unequal":
                steps[3]["power"]["value"] += 1
            elif mutation == "nested":
                steps[1] = {"steps": steps[1:3], "reps": 3, "duration": 120}
            else:
                for s in steps[1:-1]:
                    value = s["power"]["value"]
                    s["power"] = {"units": "w", "min": value - 1, "max": value + 1}
            block = self.build()
            if mutation == "nested":
                self.assertNotIn("bout_metrics_version", block)
            else:
                self.assertEqual(block["bout_metrics_version"], 4)
            self.assertTrue(all("bouts" not in s for s in block["steps"]))

    def test_set_means_can_pass_with_failed_atomic_bouts(self):
        self.repeated(count=10, lag=0)
        means = [140, 140] + [315] * 8  # Pooled mean 280; no bout is inside 277..294.
        for n, mean in enumerate(means):
            self.streams["watts"][60 + n * 40:90 + n * 40] = [mean] * 30
        step = self.fixed()["steps"][1]
        self.assertTrue(step["match"])
        self.assertEqual(step["actual"][2], 280)
        self.assertEqual(count_result([step]), (0, 10, False))

    def test_summary_identical_when_bout_payload_removed(self):
        self.repeated(count=24)
        block = self.build()
        stripped = copy.deepcopy(block)
        stripped.pop("bout_metrics_version")
        stripped["version"] = 4
        for step in stripped["steps"]:
            step.pop("bouts", None)
            step.pop("adherence", None)
        self.assertEqual(self.sync._structure_summary(block), self.sync._structure_summary(stripped))
        self.assertNotIn("bouts", json.dumps(self.sync._structure_summary(block)))

    def test_maximum_raw_atoms_retained_and_overflow_revokes_mapping(self):
        # 2 ordinary steps + 4999 work/recovery pairs = 10,000 raw atoms.
        self.repeated(count=4999, lag=0)
        block = self.build()
        self.assertEqual(len(block["steps"][1]["bouts"]), 4999)
        self.assertEqual(len(block["steps"]), 3)
        self.assertLess(len(json.dumps(self.sync._structure_summary(block))), 500)
        doc = self.event["workout_doc"]
        doc["steps"].append({"duration": 1, "power": {"units": "w", "value": 110}})
        doc["duration"] += 1
        block = self.build()
        self.assertIn("truncated", block["issues"])
        self.assertNotIn("bout_metrics_version", block)
        self.assertFalse(any("bouts" in step for step in block["steps"]))

    def test_added_measurement_pass_is_linear(self):
        class Counted(list):
            reads = 0

            def __getitem__(self, key):
                self.reads += 1
                return super().__getitem__(key)

        times = Counted(range(20001))
        windows = [(i, i + 1, i + 3, i + 2, i + 3) for i in range(0, 20000, 4)]
        rows = self.sync._structure_bouts(windows, times, [280] * len(times))
        self.assertEqual(len(rows), 5000)
        self.assertLess(times.reads, 10 * (len(times) + len(windows)))


class DurationEvidence(unittest.TestCase):
    setUp = base.Structure.setUp
    build = base.Structure.build
    fixed = BoutEvidence.fixed

    def sequence(self, sequence):
        self.event["workout_doc"] = {"duration": sum(d for d, _ in sequence), "steps": [
            {"duration": d, "power": {"units": "w", "value": p}} for d, p in sequence]}
        watts = [p for d, p in sequence for _ in range(d)] + [0]
        self.act["elapsed_time"] = len(watts) - 1
        self.streams = {"time": list(range(len(watts))), "watts": watts}

    def test_single_short_step_long_recovery_independent_of_count(self):
        for count, duration, rest in ((1, 30, 90), (8, 30, 90), (6, 40, 120)):
            self.sequence([(duration, 300), (rest, 90)] * count)
            self.streams["watts"][1] = 200
            block = self.fixed()
            self.assertEqual(len(block["steps"]), count * 2)
            for n in range(count):
                step = block["steps"][2 * n]
                start = n * (duration + rest)
                self.assertNotIn("bouts", step)
                self.assertEqual(step["adherence"], [start + 2, duration - 3, 300 * (duration - 3), 0])
                self.assertEqual(step["actual"][:2], [start + 1, start + duration])
                self.assertEqual(step["actual"][6], 100)
                self.assertNotIn("adherence", block["steps"][2 * n + 1])
            self.assertEqual(block["steps"][0]["actual"][2], round(300 - 100 / (duration - 1), 1))

    def test_prescribed_duration_boundary_not_clipped_duration(self):
        for duration in (10, 20, 21, 60, 61):
            self.sequence([(duration, 300), (120, 90)])
            self.streams["watts"][1] = 200
            step = self.fixed()["steps"][0]
            self.assertEqual(step["actual"][:2], [1, duration])
            self.assertEqual(step["actual"][2], round(300 - 100 / (duration - 1), 1))
            self.assertEqual("adherence" in step, duration <= 60)
            if duration <= 60:
                observed = duration - (3 if duration > 20 else 2)
                self.assertEqual(step["adherence"], [2, observed, observed * 300, 0])
        self.sequence([(61, 300)])
        self.act["elapsed_time"] = 55
        self.streams = {k: v[:56] for k, v in self.streams.items()}
        step = self.fixed()["steps"][0]
        self.assertEqual(step["duration_s"], 61)
        self.assertLess(step["actual"][1] - step["actual"][0], 60)
        self.assertNotIn("adherence", step)

    def test_compressed_long_bouts_keep_first_retained_second(self):
        for duration in (60, 61, 90, 180):
            self.sequence([(duration, 300), (30, 90)] * 3)
            self.streams["watts"][1] = 200
            block = self.fixed()
            step = block["steps"][0]
            self.assertEqual(step["repeat"], [3, duration, 30])
            row = step["bouts"][0]
            exclusion = 2 if duration <= 60 else 1
            self.assertEqual(row[:4], [0, 1, duration, duration - 1])
            observed = duration - exclusion - (1 if duration <= 60 else 0)
            self.assertEqual(row[4:6], [exclusion, observed])
            self.assertEqual(row[6], 300 * observed - (100 if duration > 60 else 0))
            self.assertTrue(time_result(row, duration, 0))

    def test_pyramid_steps_keep_own_duration_and_mixed_gate(self):
        self.sequence([(40, 300), (90, 90), (30, 310), (90, 90), (20, 320), (90, 90)])
        block = self.fixed()
        rows = [s["adherence"] for s in block["steps"] if "adherence" in s]
        self.assertEqual(rows, [[2, 37, 11100, 0], [132, 27, 8370, 0], [252, 18, 5760, 0]])
        self.assertFalse(any("bouts" in s for s in block["steps"]))
        summary = self.sync._structure_summary(block)
        self.assertEqual(summary["steps"], [[39, 300, 300, True], [89, 90, 90, True],
            [29, 310, 310, True], [89, 90, 90, True], [19, 320, 320, True], [89, 90, 90, True]])
        self.assertNotIn("adherence", json.dumps(summary))
        sets = [{"target_w": p, "repeat": [1, d, 90], "bouts": [[0, 1, d, d - 1, 2, d - 2, p * (d - 2), 0]]}
                for d, p in ((40, 300), (30, 310), (20, 320))]
        self.assertIsNone(count_result(sets))  # Duration-based exclusion does not authorize a mixed aggregate.

    def test_single_step_missing_power_and_trailing_zero_do_not_change_completion(self):
        self.sequence([(30, 300), (90, 90)])
        self.streams["watts"][1:3] = [None, None]
        step = self.fixed()["steps"][0]
        self.assertEqual(step["actual"][6], round(2700 / 29, 2))
        self.assertIsNone(step["actual"][2])
        self.assertEqual(step["adherence"], [2, 26, 7800, 0])
        self.sequence([(30, 300), (90, 90)])
        self.streams["watts"][29] = 0
        step = self.fixed()["steps"][0]
        self.assertEqual(step["actual"][:2], [1, 30])
        self.assertEqual(step["actual"][6], 100)
        self.assertEqual(step["adherence"], [2, 27, 8100, 0])

    def test_single_step_empty_missing_and_range_evidence(self):
        for duration in (1, 2):
            self.sequence([(duration, 300), (90, 90)])
            self.assertEqual(self.fixed()["steps"][0]["adherence"], [duration, 0, None, None])
        self.sequence([(30, 300), (90, 90)])
        self.streams["watts"][:30] = [None] * 30
        self.assertEqual(self.fixed()["steps"][0]["adherence"], [2, 0, None, None])
        self.sequence([(30, 300), (90, 90)])
        self.event["workout_doc"]["steps"][0]["power"] = {"units": "w", "min": 290, "max": 310}
        step = self.fixed()["steps"][0]
        self.assertEqual(step["target_w"], [290, 310])
        self.assertEqual(step["adherence"], [2, 27, 8100, 0])


class TrailingBoundary(unittest.TestCase):
    setUp = base.Structure.setUp
    build = base.Structure.build
    fixed = BoutEvidence.fixed
    sequence = DurationEvidence.sequence

    def test_missing_final_second_does_not_remove_last_supported_second(self):
        for count, rest in ((1, 90), (3, 15)):
            for final in (None, -1, True, float("nan"), 0, 50):
                with self.subTest(count=count, final=final):
                    self.sequence([(30, 300), (rest, 90)] * count)
                    self.streams["watts"][28] = 270
                    self.streams["watts"][29] = final
                    step = self.fixed()["steps"][0]
                    row = step["bouts"][0] if count == 3 else [0, *step["actual"][:2],
                        None, *step["adherence"]]
                    self.assertEqual(row[4:], [2, 27, 8070, 0])
                    valid_final = final in (0, 50) and final is not False
                    if count == 3:
                        self.assertEqual(row[3], 29 if valid_final else 28)
                    self.assertTrue(power_result(row, 300))

    def test_fractional_final_support_is_excluded_without_rounding(self):
        self.sequence([(30, 300), (90, 90)])
        self.streams["time"].insert(30, 29.25)
        self.streams["watts"][29:30] = [0, None]
        step = self.fixed()["steps"][0]
        self.assertEqual(step["actual"][6], round(28.25 / 29 * 100, 2))
        self.assertEqual(step["adherence"], [2, 27, 8100, 0])
        # Supported fractional time inside the window remains measured exactly.
        rows = self.sync._structure_bouts([(0, 1, 30, 2, 29)],
            [0, 1, 2, 28, 28.5, 29, 29.25, 30],
            [900, 100, 300, 200, 400, 0, None, 900])
        self.assertEqual(rows[0], [0, 1, 30, 3.25, 2, 2, 600, 0])

    def test_end_clipping_precedes_no_extra_observed_exclusion(self):
        for count, rest in ((1, 90), (3, 15)):
            for horizon, observed, complete in ((33, 27, True), (32.5, 27, True),
                                                (32, 27, True), (31.5, 26.5, True),
                                                (30, 25, True), (29, 24, False)):
                with self.subTest(count=count, horizon=horizon):
                    self.sequence([(30, 300), (rest, 90)] * count)
                    last = (count - 1) * (30 + rest)
                    end = last + horizon
                    self.act["elapsed_time"] = end
                    self.streams = {"time": list(range(math.floor(end) + 1)),
                                    "watts": [300] * (math.floor(end) + 1)}
                    if end != math.floor(end):
                        self.streams["time"].append(end)
                        self.streams["watts"].append(300)
                    with mock.patch.object(self.sync, "_structure_offset", return_value=3):
                        block = self.build()
                    step = block["steps"][0]
                    row = step["bouts"][-1] if count == 3 else [0, *step["actual"][:2],
                        step["actual"][1] - step["actual"][0], *step["adherence"]]
                    self.assertEqual(row[2], min(last + 33, end))
                    self.assertEqual(row[4:], [last + 5, observed, observed * 300, 0])
                    self.assertIs(time_result(row, 30, 3), complete)

    def test_twenty_sixty_and_sixty_one_with_trailing_dip(self):
        for count, rest in ((1, 90), (3, 15)):
            for duration in (20, 21, 60, 61):
                self.sequence([(duration, 300), (rest, 90)] * count)
                self.streams["watts"][duration - 1] = 0
                step = self.fixed()["steps"][0]
                self.assertEqual(step["actual"][6], 100)
                if count == 3:
                    row = step["bouts"][0]
                    self.assertEqual(row[:4], [0, 1, duration, duration - 1])
                    if duration == 61:
                        self.assertEqual(row[4:], [1, 60, 17700, 1])
                        continue
                    adherence = row[4:]
                elif duration == 61:
                    self.assertNotIn("adherence", step)
                    self.assertEqual(step["actual"][2], 295)
                    continue
                else:
                    adherence = step["adherence"]
                if duration == 20:
                    self.assertEqual(adherence, [2, 18, 5100, 1])
                    sprint = step["sprints"][0] if count == 3 else step["sprint"]
                    self.assertEqual(sprint, [5400 / 19, 1, 300])
                    self.assertEqual(step["sprint_window_s"], 6)
                else:
                    self.assertEqual(adherence, [2, duration - 3, 300 * (duration - 3), 0])


class Arithmetic(unittest.TestCase):
    def row(self, mean, duration=30):
        observed = duration - (3 if 20 < duration <= 60 else 2)
        return [0, 1, duration, duration - 1, 2, observed, mean * observed, 0]

    def test_inclusive_asymmetric_edges_and_adjacent_misses(self):
        for target in (50, 300, 400):
            low, high = target - max(3, target * .01), target + max(3, target * .05)
            for mean, expected in ((low, True), (high, True), (low - .00001, False),
                                   (high + .00001, False)):
                self.assertIs(power_result(self.row(mean), target), expected)
        self.assertFalse(power_result(self.row(296.999), 300))
        self.assertEqual(round(296.999, 1), 297.0)

    def test_coverage_edge_uses_exact_observed_seconds(self):
        row = self.row(300, duration=23)
        row[5:7] = [19, 5700]
        self.assertTrue(power_result(row, 300, duration=23))
        row[5] = math.nextafter(19, 0)
        row[6] = 300 * row[5]
        self.assertIsNone(power_result(row, 300, duration=23))

    def test_count_gate_all_sets_constraints_and_mixed_pattern(self):
        sets = [{"target_w": t, "repeat": [10, 30, 15],
                 "bouts": [self.row(t) for _ in range(10)]} for t in (300, 310, 320)]
        sets[1]["bouts"][5] = self.row(305.8)
        self.assertEqual(count_result(sets), (29, 30, True))
        sets[2]["bouts"][0] = self.row(310)
        self.assertEqual(count_result(sets), (28, 30, False))
        self.assertIsNone(count_result(sets, constraints=None))
        sets[2]["repeat"][2] = 20
        self.assertIsNone(count_result(sets))


class SprintEvidence(unittest.TestCase):
    setUp = base.Structure.setUp
    build = base.Structure.build
    fixed = BoutEvidence.fixed
    sequence = DurationEvidence.sequence

    def single(self, powers, duration=10, target=700):
        self.sequence([(duration, target), (90, 90)])
        self.streams["watts"][1:duration] = powers
        return self.fixed()

    def test_target_or_above_never_average_or_upper_band(self):
        for powers, peak, expected in (([400] + [702] * 3 + [600] * 5, 702, True),
                                       ([699] * 9, 699, False),
                                       ([525, 900] + [525] * 7, 650, False),
                                       ([760] * 9, 760, True),
                                       ([700] * 9, 700, True)):
            block = self.single(powers)
            step = block["steps"][0]
            self.assertEqual(step["sprint_target_w"], 700)
            self.assertEqual(step["sprint_window_s"], 3)
            self.assertEqual(step["sprint"][0], sum(powers) / 9)
            self.assertEqual(step["sprint"][2], peak)
            self.assertIs(sprint_result(step["sprint"], step["sprint_target_w"]), expected)
            self.assertEqual(step["actual"][:2], [1, 10])
            self.assertEqual(step["actual"][6], 100)
            self.assertEqual(step["adherence"], [2, 8, sum(powers[1:]), 0])

    def test_twenty_sprint_twenty_one_average_and_range_lower_bound(self):
        for duration in (20, 21):
            step = self.single([760] * (duration - 1), duration)["steps"][0]
            if duration == 20:
                self.assertTrue(sprint_result(step["sprint"], 700))
            else:
                self.assertNotIn("sprint", step)
                self.assertNotIn("sprint_target_w", step)
                self.assertNotIn("sprint_window_s", step)
                self.assertFalse(power_result([0, 1, 21, 20] + step["adherence"], 700, duration=21))
        for peak, expected in ((699, False), (700, True), (900, True)):
            self.single([peak] * 9)
            self.event["workout_doc"]["steps"][0]["power"] = {"units": "w", "min": 700, "max": 800}
            step = self.fixed()["steps"][0]
            self.assertEqual(step["target_w"], [700, 800])
            self.assertEqual(step["sprint_target_w"], 700)
            self.assertIs(sprint_result(step["sprint"], step["sprint_target_w"]), expected)
            atomic = {"target_w": step["target_w"], "sprint_target_w": step["sprint_target_w"],
                      "sprint_window_s": step["sprint_window_s"],
                      "repeat": [1, 10, 90], "sprints": [step["sprint"]],
                      "bouts": [[0, 1, 10, 9] + step["adherence"]]}
            self.assertEqual(count_result([atomic]), (int(expected), 1, expected))
        self.act.update(type="Ride", trainer=False)
        self.assertEqual(self.fixed()["steps"][0]["sprint"], step["sprint"])

    def test_window_scales_with_prescribed_duration_for_single_and_set(self):
        for duration, width in ((5, 3), (10, 3), (11, 4), (15, 5), (20, 6)):
            with self.subTest(duration=duration):
                block = self.single([700] * (duration - 1), duration)
                step = block["steps"][0]
                self.assertEqual(step["sprint_window_s"], width)
                self.assertEqual(step["sprint"], [700, 1, 700])
                self.assertEqual(step["actual"][:2], [1, duration])
                self.assertEqual(step["actual"][6], 100)
                self.sequence([(90, 90)] + [(duration, 700), (30, 90)] * 3 + [(90, 90)])
                step = self.fixed()["steps"][1]
                self.assertEqual(step["sprint_window_s"], width)
                self.assertEqual(step["sprints"], [[700, 91 + n * (duration + 30), 700] for n in range(3)])
                self.assertEqual(count_result([step]), (3, 3, True))
                step["sprint_window_s"] = width + 1
                self.assertIsNone(count_result([step]))

    def test_twenty_second_peak_cannot_use_three_second_pass(self):
        powers = [800] * 3 + [500] * 16
        block = self.single(powers, 20)
        step = block["steps"][0]
        self.assertEqual(step["sprint_window_s"], 6)
        self.assertEqual(step["sprint"], [10400 / 19, 1, 650])
        self.assertFalse(sprint_result(step["sprint"], 700))
        times = list(range(21))
        self.assertEqual(self.sync._structure_sprints([(1, 20, 3)], times, [0] + powers + [0], times)[0][2], 800)
        self.assertTrue(time_result([0, 1, 20, 19] + step["adherence"], 20, 0))
        # Exactly target still passes over all six seconds, without tolerance.
        step = self.single([800] * 3 + [600] * 16, 20)["steps"][0]
        self.assertEqual(step["sprint"][2], 700)
        self.assertTrue(sprint_result(step["sprint"], 700))
        for power, expected in ((699, False), (700, True), (900, True)):
            self.single([power] * 19, 20)
            self.event["workout_doc"]["steps"][0]["power"] = {"units": "w", "min": 700, "max": 800}
            step = self.fixed()["steps"][0]
            self.assertEqual((step["sprint_window_s"], step["sprint_target_w"]), (6, 700))
            self.assertIs(sprint_result(step["sprint"], 700), expected)

    def test_scaled_window_requires_consecutive_time_and_survives_clipping(self):
        powers = ([700] * 5 + [None]) * 3 + [700]
        step = self.single(powers, 20)["steps"][0]
        self.assertEqual(step["sprint_window_s"], 6)
        self.assertEqual(step["sprint"], [700, None, None])
        self.assertIsNone(sprint_result(step["sprint"], 700))
        # A raw recording stop also breaks continuity despite clock compression.
        self.single([700] * 19, 20)
        self.streams["time"] = [t + 70 * (t // 5) for t in self.streams["time"]]
        self.act["elapsed_time"] = self.streams["time"][-1]
        step = self.fixed()["steps"][0]
        self.assertEqual(step["actual"][6], 100)
        self.assertEqual(step["sprint"], [700, None, None])
        # End clipping must not shorten W using the measured duration.
        self.sequence([(90, 90), (20, 700)])
        for key in self.streams:
            self.streams[key] = self.streams[key][:97]
        self.act["elapsed_time"] = 96
        step = self.fixed()["steps"][1]
        self.assertEqual(step["actual"][:2], [91, 96])
        self.assertEqual(step["sprint_window_s"], 6)
        self.assertEqual(step["sprint"], [700, None, None])

    def test_three_consecutive_seconds_not_three_samples_or_disjoint_time(self):
        for powers in ([700, 700] + [None] * 7,
                       [700, 700, None, 700, 700, None, 700, 700, None]):
            step = self.single(powers)["steps"][0]
            self.assertEqual(step["sprint"], [700, None, None])
            self.assertIsNone(sprint_result(step["sprint"], 700))
            self.assertLess(step["actual"][6], 95)
        helper = self.sync._structure_sprints
        times = [0, .5, 1, 1.5]
        self.assertEqual(helper([(0, 3, 3)], times, [700] * 4, times), [[700, None, None]])
        times = list(range(6))
        for invalid in (None, -1, True, float("nan"), float("inf")):
            self.assertEqual(helper([(0, 5, 3)], times, [700, 700, invalid, 700, 700, 700], times),
                             [[700, None, None]])
        self.assertEqual(helper([(1, 5, 3)], times, [0] * 6, times), [[0, 1, 0]])

    def test_fractional_peak_includes_shifted_endpoints_and_clipping(self):
        times = [0, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6]
        watts = [9999, 100, 800, 800, 800, 800, 800, 800, 100, 100, 100, 9999]
        rows = self.sync._structure_sprints([(1, 6, 3)], times, watts, times)
        self.assertEqual(rows, [[520, 1.5, 800]])
        # The optimum can start between sample timestamps at end minus 3 s.
        times = [0, 1, 1.25, 2.25, 3.25, 4.25, 5]
        watts = [9999, 0, 900, 900, 800, 1200, 9999]
        row = self.sync._structure_sprints([(1, 5, 3)], times, watts, times)[0]
        self.assertEqual(row[1:], [2, 2825 / 3])
        times = [0, 1, 1.4, 2.4, 3.4, 4.4, 5]
        watts = [9999, 0, 900, 900, 900, 0, 9999]
        row = self.sync._structure_sprints([(1, 5, 3)], times, watts, times)[0]
        self.assertAlmostEqual(row[1], 1.4)
        self.assertAlmostEqual(row[2], 900)
        self.assertIsNone(self.sync._structure_sprints([(1, 3.75, 3)], times, watts, times)[0][2])

    def test_fractional_rolling_peak_matches_independent_grid_oracle(self):
        available = {width: 0 for width in (3, 4, 5, 6)}
        for seed in range(30):
            times = [i / 4 for i in range(41) if (i + seed) % 11 != 0]
            watts = [None if seed % 3 == 0 and (i + seed) % 13 == 0 else (i * 79 + seed * 31) % 1001
                     for i in range(len(times))]
            # Independently expand supported quarter-second cells, not the
            # producer's prefix integrals or endpoint-candidate algorithm.
            cells = []
            for tick in range(4, 39):
                at = tick / 4
                found = None
                for i in range(len(times) - 1):
                    if times[i] <= at and at + .25 <= min(times[i] + 1, times[i + 1]):
                        found = watts[i]
                        break
                cells.append(found)
            observed = [value for value in cells if value is not None]
            for width in (3, 4, 5, 6):
                size = width * 4
                candidates = [(sum(cells[n:n + size]) / size, 1 + n / 4)
                              for n in range(len(cells) - size + 1) if None not in cells[n:n + size]]
                peak, start = max(candidates, key=lambda row: (row[0], -row[1])) if candidates else (None, None)
                actual = self.sync._structure_sprints([(1, 9.75, width)], times, watts, times)[0]
                self.assertEqual(actual, [sum(observed) / len(observed) if observed else None, start, peak])
                available[width] += peak is not None
        self.assertTrue(all(count >= 20 for count in available.values()))

    def test_standard_bounds_offset_and_recording_gap_are_preserved(self):
        block = self.single([702] * 3 + [100] * 6)
        self.assertEqual(block["steps"][0]["sprint"][1:], [1, 702])
        self.streams["watts"][0] = 9999  # Excluded leading sample cannot raise peak.
        self.streams["watts"][10] = 9999  # Recovery is outside this standard window.
        self.assertEqual(self.fixed()["steps"][0]["sprint"], block["steps"][0]["sprint"])
        self.sequence([(5, 700), (90, 90)])
        self.streams["time"] = [t if t < 3 else t + 70 for t in self.streams["time"]]
        self.act["elapsed_time"] += 70
        step = self.fixed()["steps"][0]
        self.assertEqual(step["actual"][:2], [1, 5])
        self.assertEqual(step["actual"][6], 100)
        self.assertEqual(step["sprint"], [700, None, None])
        self.sequence([(10, 700), (90, 90)])
        self.streams["watts"] = [90] * 3 + [700] * 10 + [90] * 88
        with mock.patch.object(self.sync, "_structure_offset", return_value=3):
            shifted = self.build()["steps"][0]
        self.assertEqual(shifted["sprint"], [700, 4, 700])
        self.assertEqual(shifted["actual"][:2], [4, 13])

    def test_atomic_compressed_sprints_and_latest_summary_unchanged(self):
        self.sequence([(90, 90)] + [(10, 700), (30, 90)] * 20 + [(90, 90)])
        self.streams["watts"][91:100] = [699] * 9
        block = self.fixed()
        step = block["steps"][1]
        self.assertEqual(step["sprint_target_w"], 700)
        self.assertEqual(len(step["sprints"]), 20)
        self.assertEqual(step["sprints"][0], [699, 91, 699])
        self.assertEqual(count_result([step]), (19, 20, True))
        step["sprints"][1][2] = 699
        self.assertEqual(count_result([step]), (18, 20, False))
        step["sprints"][1][2] = None
        self.assertIsNone(count_result([step]))
        stripped = copy.deepcopy(block)
        for row in stripped["steps"]:
            for key in ("sprints", "sprint", "sprint_target_w", "sprint_window_s"):
                row.pop(key, None)
        self.assertEqual(self.sync._structure_summary(block), self.sync._structure_summary(stripped))
        self.assertNotIn("sprint", json.dumps(self.sync._structure_summary(block)))

    def test_maximum_atoms_keep_all_sprint_rows(self):
        self.sequence([(90, 90)] + [(10, 700), (5, 90)] * 4999 + [(90, 90)])
        block = self.fixed()
        step = block["steps"][1]
        self.assertEqual(len(step["sprints"]), 4999)
        self.assertEqual(step["sprints"][0], [700, 91, 700])
        self.assertEqual(step["sprints"][-1], [700, 91 + 4998 * 15, 700])
        self.assertEqual(count_result([step]), (4999, 4999, True))
        self.assertNotIn("sprint", json.dumps(self.sync._structure_summary(block)))


class BoutCache(unittest.TestCase):
    setUp = base.Structure.setUp
    repeated = base.LiveShape.repeated
    resolve = base.LiveShape.resolve
    prepare = base.Cache.prepare
    previous = base.Cache.previous

    def test_version_five_marker_four_refreshes_then_current_cache_hits(self):
        self.repeated(count=3)
        with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("ok", self.streams)) as fetch:
            current = self.prepare()
            old = copy.deepcopy(current)
            old["version"] = 5
            self.assertEqual(old["bout_metrics_version"], 4)
            old["steps"][1]["bouts"][0][5:7] = [28, 1234]
            corrected = self.prepare(self.previous(old))
            self.assertEqual(corrected, current)
            self.assertEqual(corrected["version"], 6)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(self.prepare(self.previous(corrected)), current)
            self.assertEqual(fetch.call_count, 2)

    def test_old_version_five_semantics_refresh_once_then_hit(self):
        for kind in ("set", "short", "long", "sprint", "fixed_sprint"):
            if kind == "set":
                self.repeated(count=3)
            else:
                self.act, self.event, self.streams = base.inputs(
                    duration={"short": 30, "long": 100, "sprint": 10, "fixed_sprint": 20}[kind])
            self.sync._intervals_data = {}
            with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("ok", self.streams)) as fetch:
                current = self.prepare()
                old = copy.deepcopy(current)
                if kind == "set":
                    old["bout_metrics_version"] = 1
                elif kind == "sprint":
                    old["bout_metrics_version"] = 2
                elif kind == "fixed_sprint":
                    old["bout_metrics_version"] = 3
                else:
                    old.pop("bout_metrics_version")
                for step in old["steps"]:
                    for key in (("sprint_window_s",) if kind == "fixed_sprint" else
                                ("adherence", "sprint", "sprint_target_w", "sprint_window_s")):
                        step.pop(key, None)
                    if kind == "fixed_sprint":
                        step["sprint"][2] = 999  # Stale fixed-width evidence must be rebuilt.
                corrected = self.prepare(self.previous(old))
                self.assertEqual(corrected, current)
                self.assertEqual(corrected["version"], 6)
                self.assertEqual(fetch.call_count, 2)
                self.assertEqual(self.prepare(self.previous(corrected)), current)
                self.assertEqual(fetch.call_count, 2)
            with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("transient", "unavailable")) as fetch:
                stale = self.prepare(self.previous(old))
                self.assertNotIn("bout_metrics_version", stale)
                self.assertFalse(any("adherence" in s or "bouts" in s or "sprint" in s for s in stale["steps"]))
                self.prepare(self.previous(stale), base.NOW + timedelta(minutes=30))
                self.assertEqual(fetch.call_count, 1)  # Preserve failed-refresh backoff.

    def test_version_four_rebuild_complete_hit_and_failure_revocation(self):
        self.repeated(count=3)
        with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("ok", self.streams)) as fetch:
            initial = self.prepare()
            old = copy.deepcopy(initial)
            old["version"] = 4
            old.pop("bout_metrics_version")
            old["steps"][1].pop("bouts")
            rebuilt = self.prepare(self.previous(old))
            self.assertEqual(rebuilt, initial)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(self.prepare(self.previous(rebuilt)), rebuilt)
            self.assertEqual(fetch.call_count, 2)
            self.event["workout_doc"]["steps"][0]["text"] = "changed definition"
            changed = self.prepare(self.previous(rebuilt))
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(changed["cache"]["plan_key"], rebuilt["cache"]["plan_key"])
            self.event["workout_doc"]["steps"][0]["power"]["value"] += 1
            changed = self.prepare(self.previous(changed))
            self.assertEqual(fetch.call_count, 4)
            self.assertNotEqual(changed["cache"]["plan_key"], rebuilt["cache"]["plan_key"])
        with mock.patch.object(self.sync, "_fetch_activity_streams", return_value=("transient", "unavailable")):
            stale = self.prepare(self.previous(changed), base.NOW + timedelta(days=1))
        self.assertEqual(stale["cache"]["status"], "stale")
        self.assertNotIn("bout_metrics_version", stale)
        self.assertFalse(any("bouts" in s for s in stale["steps"]))


class BoutPlacement(unittest.TestCase):
    setUp = base.Placement.setUp
    fresh_sync = base.Placement.fresh_sync
    capture = base.Placement.capture
    persist = base.Placement.persist
    cycle = base.Placement.cycle
    repeated = base.LiveShape.repeated
    resolve = base.LiveShape.resolve

    def test_expiry_removes_bouts_without_older_stream_backfill(self):
        self.repeated(count=3)
        first = self.capture()
        self.assertEqual(self.sync._intervals_data["activities"][0]["session_structure"]["bout_metrics_version"], 4)
        self.assertNotIn('"bouts"', json.dumps(first))
        with mock.patch.object(Sync, "_fetch_activity_streams", side_effect=AssertionError("expired refetch")), \
                mock.patch.object(Sync, "_fetch_activity_intervals", side_effect=AssertionError("expired detail")):
            row = self.cycle(base.NOW + timedelta(days=15))
        self.assertFalse(row["has_structure"])
        self.assertNotIn('"bouts"', json.dumps(row))
        self.assertIsNone(row["interval_data"]["compliance"]["on_target"])
        self.assertEqual(self.sync._intervals_data["activities"], [])


class Documentation(unittest.TestCase):
    def test_synthetic_schema_example_and_compliance_contract(self):
        root = Path(__file__).resolve().parents[2]
        schema = (root / "examples/json-examples/README.md").read_text()
        fragment = schema.split("## Short-set detail fragment (synthetic)", 1)[1].split("## Files", 1)[0]
        block = json.loads(re.search(r"```json\n(.*?)\n```", fragment, re.S).group(1))
        self.assertEqual((block["version"], block["bout_metrics_version"]), (6, 4))
        rows = block["steps"][0]["bouts"]
        self.assertEqual([time_result(row, 30, 2) for row in rows], [True] * 3)
        self.assertEqual([power_result(row, 300, offset=2) for row in rows], [True, True, False])
        self.assertEqual([r[0] for r in rows], [600, 645, 690])
        template = (root / "examples/reports/POST_WORKOUT_REPORT_TEMPLATE.md").read_text()
        line = next(x for x in template.splitlines() if x.startswith("Compliance:"))
        self.assertIn("N/M atomic steps or work bouts", line)
        self.assertNotIn("steps or sets on target", line)
        self.assertIn("set 2 12/13 on target", line)
        examples = (root / "examples/reports/POST_WORKOUT_REPORT_EXAMPLES.md").read_text()
        self.assertIn("On target: 29/30 bouts (97%)", examples)
        self.assertIn("Adherence: not evaluable\nReason: individual bout detail expired", examples)
        self.assertIn("Main work: incomplete\nSet 3/bout 10: 4s standard deficit", examples)


if __name__ == "__main__":
    unittest.main()
