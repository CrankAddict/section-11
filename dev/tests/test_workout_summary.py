"""
Tests for the planned-workout workout_summary renderer in sync.py v3.134 to v3.136
(issue #28) and for the report templates that consume it.

Standard library only: unittest. Every workout_doc is synthetic and built inline;
power and HR values are invented, not an athlete's metrics or thresholds. Nothing
here reaches the network, real athlete data, credentials or a machine-specific path.

Run from the repository root:

    python3 -m unittest discover dev/tests

Use the same interpreter or virtual environment that runs sync.py.

What this module guards:

  1. No emitter assigns a role. The two-step repeat, nested alternating and flat
     alternating renderers used to label the second or lower step "rec" whenever it
     came second or sat 10 W / 5% lower, which misreports over-unders and active
     endurance connectors. A lower target is not evidence of recovery.
  2. No step or target inside a compressed block is lost. An expansion oracle turns
     the summary back into ordered (duration, target) steps and compares them with
     the expanded workout_doc, so the check enforces order, count and targets rather
     than the presence of words.
  3. The flat detector no longer skips the step after a trailing solo rep.
  4. Rendering only. Which workouts get a summary, the "×" / "sets" markers that
     _phase_stream2_features reads, the summary telemetry and hard_sessions_planned
     equal constants captured from sync.py v3.133 (public commit bef4c686).
  5. No silent partial or misstated summary (v3.135). A step, repeat block or
     unmatched nested child the renderer cannot show, and a target it cannot print
     as W or bpm (relative units, range bounds, an empty or null target, pace), is
     marked in place on every output path. v3.136: repeat semantics are never
     rendered flat, counts and durations must be valid, and the 2 W tolerance is
     checked on raw values. Every fixture step and repeat declares its expected
     rendering when built (P, T, A, X, R, XR); the oracle reads only those
     declarations, never calls sync.py and never inspects a count, duration, target
     or "steps" shape. It is shown to reject both rejected candidates' outputs.
     Markers are positional placeholders: an unmarked summary must list every step
     with its duration and primary target.
  6. Report consumption. The PRE and POST templates name the producer's markers,
     keep the labelled-recovery rule and the stated scope of an unmarked summary,
     and for a null or marked summary fall back to the description field each row
     tier actually carries. This is static text-to-producer checking; no report is
     rendered.

Out of scope by design: secondary targets (cadence, HR alongside power), which a
summary does not carry, and the alternating detectors' tolerance (targets within
2 W, durations within 2 s of the first compressed step), within which repeated
steps are shown at the first step's value.
"""

import json
import re
import unittest
from datetime import datetime, timedelta

from _harness import (NetworkBlocked, REPO_ROOT, SYNC_PATH, install_verb_guard,
                      load_module_by_path, restore_verb_guard)

sync_mod = load_module_by_path("s11_sync_summary", SYNC_PATH)

EXAMPLE_PATH = REPO_ROOT / "examples" / "json-examples" / "latest.example.json"
TEMPLATE_PATHS = {
    "PRE": REPO_ROOT / "examples" / "reports" / "PRE_WORKOUT_REPORT_TEMPLATE.md",
    "POST": REPO_ROOT / "examples" / "reports" / "POST_WORKOUT_REPORT_TEMPLATE.md",
}
STEP_MARK = sync_mod.IntervalsSync.SUMMARY_STEP_NOT_SUMMARIZED
REPEAT_MARK = sync_mod.IntervalsSync.SUMMARY_REPEAT_NOT_SUMMARIZED
TARGET_MARK = sync_mod.IntervalsSync.SUMMARY_TARGET_NOT_SHOWN

_ORIGINAL_VERBS = {}


def setUpModule():
    global _ORIGINAL_VERBS
    _ORIGINAL_VERBS = install_verb_guard(sync_mod.requests)


def tearDownModule():
    restore_verb_guard(sync_mod.requests, _ORIGINAL_VERBS)


# ── synthetic builders ───────────────────────────────────────────────────────

TARGET_KEYS = {"_power", "power", "_hr", "hr", "_pace", "pace"}
NOT_SHOWN = ("TARGET_NOT_SHOWN",)
STEP_TOKEN = ("STEP_NOT_SUMMARIZED",)
REPEAT_TOKEN = ("REPEAT_NOT_SUMMARIZED",)

# Every synthetic step and repeat declares, when it is built, what the summary must
# show for it: an atom (seconds, target), a step marker, an expanded repeat (count x
# children), a repeat marker, or (fuzz only) either of the last two. The oracle reads
# only these declarations. It never calls sync.py and never inspects a step's
# duration, count, target or "steps" shape, so it cannot share the renderer's rules.
# Entries hold the object itself, so an id is never reused by another object.
_DECLARED = {}


def _declare(obj, declaration):
    _DECLARED[id(obj)] = (obj, declaration)
    return obj


def declaration(step):
    entry = _DECLARED.get(id(step))
    if entry is None or entry[0] is not step:
        raise AssertionError(f"fixture step has no declared expectation: {step!r}")
    return entry[1]


def _author_seconds(duration):
    assert type(duration) is int and duration >= 1, f"not an author-valid duration: {duration!r}"
    return duration


def P(duration=None, watts=None, bpm=None, **extra):
    """
    One atomic step with a resolved `_power` / `_hr` value and no units: the form
    the renderer prints. Declares ("W", watts), else ("bpm", bpm), else no target;
    duration=None declares a step marker. Other target shapes use T(), other
    duration shapes A() or X().
    """
    assert not TARGET_KEYS & set(extra), "use T() for other target shapes"
    step = dict(extra)
    if watts is not None:
        step["_power"] = {"value": watts}
    if bpm is not None:
        step["_hr"] = {"value": bpm}
    if duration is None:
        return _declare(step, ("step_marked",))
    step["duration"] = duration
    target = ("W", watts) if watts is not None else ("bpm", bpm) if bpm is not None else None
    return _declare(step, ("atom", _author_seconds(duration), target))


def T(duration, expect, **targets):
    """A step with an arbitrary target shape and the summary target the author expects."""
    step = dict(targets)
    if duration is None:
        return _declare(step, ("step_marked",))
    step["duration"] = duration
    return _declare(step, ("atom", _author_seconds(duration), expect))


def A(fields, seconds, target=None):
    """An atomic step with arbitrary fields that the author expects shown as `seconds`."""
    return _declare(dict(fields), ("atom", _author_seconds(seconds), target))


def X(fields):
    """An atomic step the author expects marked [step not summarized]."""
    return _declare(dict(fields), ("step_marked",))


def R(reps, *steps, mode="expand", count=None, **extra):
    """
    A well-formed repeat. count defaults to reps and must be a whole number >= 1.
    mode "expand": shown as count x children; "marked": the author expects the
    renderer to mark this valid repeat; "either" (fuzz only): either is truthful.
    """
    count = reps if count is None else count
    assert type(count) is int and count >= 1, f"not an author-valid count: {count!r}"
    assert mode in ("expand", "marked", "either")
    step = {"reps": reps, "steps": list(steps), **extra}
    return _declare(step, ("repeat", count, mode, list(steps)))


def XR(fields):
    """A malformed or invalid repeat the author expects marked [repeat not summarized]."""
    return _declare(dict(fields), ("repeat_marked",))


def doc(*steps):
    return {"steps": list(steps)}


def make_sync():
    return sync_mod.IntervalsSync(athlete_id="i000000", intervals_api_key="synthetic")


TODAY = "2026-01-05"  # a Monday; the default training week starts Monday
FAR_DAY = "2026-01-20"


def event(workout_doc, date=TODAY, name="Session", description=""):
    return {"id": "e", "start_date_local": f"{date}T00:00:00", "name": name,
            "category": "WORKOUT", "type": "Ride", "description": description,
            "workout_doc": workout_doc}


def summarize(sync, workout_doc):
    """workout_summary exactly as _format_events produces it for a near-day row."""
    return sync._format_events([event(workout_doc)], today=TODAY)[0]["workout_summary"]


ROLE_LABEL = re.compile(r"\b(rec|recovery|rest)\b", re.IGNORECASE)


# ── expansion oracle ─────────────────────────────────────────────────────────

_STEP = re.compile(r"((?:\d+h)?(?:\d+m)?(?:\d+s)?)(?: @(\d+)(W|bpm)| \[target not shown\])?")

# Oracle tokens (STEP_TOKEN, REPEAT_TOKEN, NOT_SHOWN) are defined with the builders.


def _secs(text):
    total = 0
    for value, unit in re.findall(r"(\d+)([hms])", text):
        total += int(value) * {"h": 3600, "m": 60, "s": 1}[unit]
    return total


def _split_top(body):
    parts, depth, start, i = [], 0, 0, 0
    while i < len(body):
        ch = body[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and body.startswith(" + ", i):
            parts.append(body[start:i])
            start = i + 3
            i += 3
            continue
        i += 1
    parts.append(body[start:])
    return parts


def _expand_step(text):
    m = _STEP.fullmatch(text)
    if not m or not m.group(1):
        raise ValueError(f"unparseable step {text!r}")
    if m.group(2):
        target = (m.group(3), int(m.group(2)))
    elif text.endswith(" [target not shown]"):
        target = NOT_SHOWN
    else:
        target = None
    return [(_secs(m.group(1)), target)]


def _expand_body(body):
    out = []
    for term in _split_top(body):
        if term == "[step not summarized]":
            out.append(STEP_TOKEN)
            continue
        if term == "[repeat not summarized]":
            out.append(REPEAT_TOKEN)
            continue
        m = re.fullmatch(r"(\d+)×\((.+)\)", term)
        if m:
            out += int(m.group(1)) * _expand_body(m.group(2))
            continue
        m = re.fullmatch(r"\((.+)\)", term)
        if m:
            out += _expand_body(m.group(1))
            continue
        m = re.fullmatch(r"(\d+)×(.+)", term)
        if m:
            out += int(m.group(1)) * _expand_step(m.group(2))
            continue
        out += _expand_step(term)
    return out


def _expand_part(part):
    m = re.fullmatch(r"(\d+) × (.+)", part)
    if m:
        return int(m.group(1)) * _expand_part(m.group(2))
    m = re.fullmatch(r"(\d+) sets × (.+)", part)
    if m:
        return int(m.group(1)) * _expand_body(m.group(2))
    return _expand_body(part)


def expand_summary(summary):
    out = []
    for part in summary.split(" | "):
        out += _expand_part(part)
    return out


def _expected(step):
    """Expected items for one step, from its declaration only."""
    if not isinstance(step, dict):
        return [STEP_TOKEN]  # a non-object step can never be shown
    decl = declaration(step)
    kind = decl[0]
    if kind == "atom":
        return [(decl[1], decl[2])]
    if kind == "step_marked":
        return [STEP_TOKEN]
    if kind == "repeat_marked":
        return [REPEAT_TOKEN]
    _, count, mode, children = decl
    if mode == "marked":
        return [REPEAT_TOKEN]
    inner = []
    for child in children:
        inner += _expected(child)
    expansion = count * inner
    return [("EITHER", expansion)] if mode == "either" else expansion


def expand_doc(workout_doc):
    """Expected items for a workout_doc; may contain ("EITHER", expansion) items."""
    out = []
    for s in workout_doc["steps"]:
        out += _expected(s)
    return out


def _kind(item):
    return item if item in (STEP_TOKEN, REPEAT_TOKEN) else "atom"


def _resolve(want, got):
    """
    Resolve ("EITHER", expansion) items against the summary: find, by memoized
    search over summary positions, an expected sequence whose length and marker
    positions match the summary (a marker for the whole repeat, or its full
    expansion). Without EITHER items this is the expected sequence itself. If
    nothing matches, the unresolved expectation is returned (always a mismatch).
    """
    if not any(isinstance(i, tuple) and i and i[0] == "EITHER" for i in want):
        return list(want)
    memo = {}

    def reach(seq, pos):
        """{end position: flat expected items} for seq matched from pos."""
        key = (id(seq), pos)
        if key in memo:
            return memo[key]
        states = {pos: []}
        for item in seq:
            nxt = {}
            for p, flat in states.items():
                if isinstance(item, tuple) and item and item[0] == "EITHER":
                    if p < len(got) and got[p] == REPEAT_TOKEN:
                        nxt.setdefault(p + 1, flat + [REPEAT_TOKEN])
                    for e, sub in reach(item[1], p).items():
                        nxt.setdefault(e, flat + sub)
                elif p < len(got) and _kind(item) == _kind(got[p]):
                    nxt.setdefault(p + 1, flat + [item])
            states = nxt
            if not states:
                break
        memo[key] = states
        return states

    return reach(want, 0).get(len(got), [("UNMATCHED",)])


class OracleCase(unittest.TestCase):
    def setUp(self):
        self.sync = make_sync()

    def assertFaithful(self, workout_doc, summary, watt_tol=0, dur_tol=0, role_mark_ok=False):
        """
        Every atom present, in order, or marked in place; no role label.
        role_mark_ok: a compressed block prints one target per role, so a role whose
        steps are not all printable is marked as a whole. With this flag a marker may
        stand where a printable watt target was declared (never the reverse: a
        printed value where the declaration says it cannot be shown still fails).
        """
        self.assertIsNotNone(summary, "summary unexpectedly null")
        self.assertIsNone(ROLE_LABEL.search(summary),
                          f"summary assigns a step role: {summary!r}")
        try:
            got = expand_summary(summary)
        except ValueError as exc:
            self.fail(f"summary does not follow the summary grammar ({exc}): {summary!r}")
        want = _resolve(expand_doc(workout_doc), got)
        self.assertEqual(len(got), len(want),
                         f"step count changed (dropped or invented step): {summary!r}")
        for n, (g, w) in enumerate(zip(got, want)):
            if w in (STEP_TOKEN, REPEAT_TOKEN) or g in (STEP_TOKEN, REPEAT_TOKEN):
                self.assertEqual(g, w, f"step {n} marker mismatch: {summary!r}")
                continue
            (gd, gt), (wd, wt) = g, w
            if role_mark_ok and gt == NOT_SHOWN and isinstance(wt, tuple) and wt[0] == "W":
                self.assertLessEqual(abs(gd - wd), dur_tol, f"step {n} duration: {summary!r}")
                continue
            if wt == NOT_SHOWN or gt == NOT_SHOWN:
                self.assertEqual(gt, wt, f"step {n} target marker mismatch: {summary!r}")
                self.assertLessEqual(abs(gd - wd), dur_tol, f"step {n} duration: {summary!r}")
                continue
            self.assertLessEqual(abs(gd - wd), dur_tol, f"step {n} duration: {summary!r}")
            if wt is None:
                self.assertIsNone(gt, f"step {n} gained a target: {summary!r}")
            else:
                self.assertIsNotNone(gt, f"step {n} lost its target: {summary!r}")
                self.assertEqual(gt[0], wt[0], f"step {n} target type: {summary!r}")
                # Displayed values are whole numbers. Exact mode allows display rounding
                # (0.5); a tolerance is applied as stated, with no extra slack, so it
                # needs whole-number reference values in the fixture.
                self.assertLessEqual(abs(gt[1] - wt[1]), max(watt_tol, 0.5),
                                     f"step {n} target value: {summary!r}")

    def assertLossless(self, workout_doc, summary, watt_tol=0, dur_tol=0):
        """Faithful and carrying no marker: the summary is the whole plan."""
        self.assertIsNotNone(summary, "summary unexpectedly null")
        self.assertNotIn("[", summary, f"summary unexpectedly marked: {summary!r}")
        self.assertFaithful(workout_doc, summary, watt_tol, dur_tol)


# ── 0. network guard ─────────────────────────────────────────────────────────

class TestNetworkGuard(unittest.TestCase):
    def test_unpatched_http_is_refused(self):
        with self.assertRaises(NetworkBlocked):
            sync_mod.requests.get("https://intervals.icu/api/v1/athlete/i0")


# ── 1. two-step repeat ───────────────────────────────────────────────────────

class TestTwoStepRepeat(OracleCase):
    CASES = {
        # The five synthetic cases of the #28 design brief.
        "second_higher_active": (P(600, 175), P(600, 205)),
        "second_equal_active": (P(600, 205), P(600, 205)),
        "second_lower_active": (P(600, 245), P(600, 205)),
        "second_easy_recovery": (P(600, 245), P(600, 95)),
        "second_target_unknown": (P(600, 245), P(600)),
        # Nearby cases.
        "rest_first_order": (P(120, 100), P(300, 300)),
        "hr_second": (P(600, 245), P(600, bpm=150)),
        "hr_both": (P(600, bpm=160), P(600, bpm=140)),
        "first_target_unknown": (P(600), P(300, 205)),
    }

    def test_both_steps_rendered_by_the_step_describer(self):
        for name, (a, b) in self.CASES.items():
            with self.subTest(name):
                d = doc(R(3, a, b))
                summary = summarize(self.sync, d)
                expected = (f"3×({self.sync._describe_work_step(a)} + "
                            f"{self.sync._describe_work_step(b)})")
                self.assertEqual(summary, expected,
                                 "two-step repeat must render both steps alike, "
                                 "with no role label and no dropped target")
                self.assertLossless(d, summary)

    def test_genuine_easy_step_keeps_its_target_without_a_label(self):
        self.assertEqual(summarize(self.sync, doc(R(3, P(600, 245), P(600, 95)))),
                         "3×(10m @245W + 10m @95W)")

    def test_second_step_without_duration_is_marked_not_dropped(self):
        # v3.134 rendered "3×10m @245W", which read as complete. Returning None
        # instead would create a new null summary and could remove the only "×"
        # marker phase detection sees, so the gap is marked in place.
        d = doc(R(3, P(600, 245), P(None, 205)))
        summary = summarize(self.sync, d)
        self.assertEqual(summary, "3×(10m @245W + [step not summarized])")
        self.assertFaithful(d, summary)

    def test_unrenderable_first_step_still_bails(self):
        self.assertIsNone(summarize(self.sync, doc(R(3, P(None, 245), P(600, 205)))))


# ── 2. nested alternating ────────────────────────────────────────────────────

class TestNestedAlternating(OracleCase):
    def test_over_under_is_not_rest(self):
        d = doc(R(2, *([P(120, 290), P(120, 240)] * 3)))
        summary = summarize(self.sync, d)
        self.assertEqual(summary, "2 sets × 3×(2m @290W + 2m @240W)")
        self.assertLossless(d, summary)

    def test_single_set_has_no_sets_marker(self):
        d = doc(R(1, *([P(120, 290), P(120, 240)] * 3)))
        summary = summarize(self.sync, d)
        self.assertEqual(summary, "3×(2m @290W + 2m @240W)")
        self.assertLossless(d, summary)

    def test_leading_set_step_keeps_its_target(self):
        d = doc(R(2, P(600, 200), *([P(60, 300), P(60, 150)] * 3)))
        summary = summarize(self.sync, d)
        self.assertEqual(summary, "2 sets × (10m @200W + 3×(1m @300W + 1m @150W))",
                         "a leading set step must keep its target, not become 'set rec'")
        self.assertLossless(d, summary)

    def test_trailing_rep_is_written_out(self):
        d = doc(R(2, *([P(60, 300), P(60, 150)] * 3), P(60, 300)))
        summary = summarize(self.sync, d)
        self.assertEqual(summary, "2 sets × (3×(1m @300W + 1m @150W) + 1m @300W)")
        self.assertLossless(d, summary)

    def test_differing_tail_rest_is_written_out(self):
        d = doc(R(1, P(60, 300), P(60, 150), P(60, 300), P(60, 150),
                  P(60, 300), P(120, 150)))
        summary = summarize(self.sync, d)
        self.assertEqual(summary, "2×(1m @300W + 1m @150W) + (1m @300W + 2m @150W)")
        self.assertLossless(d, summary)


# ── 3. flat alternating (Pattern B) ──────────────────────────────────────────

class TestFlatAlternating(OracleCase):
    def test_flat_over_under_is_not_rest(self):
        d = doc(P(600, 150), *([P(120, 290), P(120, 240)] * 3), P(600, 140))
        summary = summarize(self.sync, d)
        self.assertEqual(summary, "10m @150W | 3×(2m @290W + 2m @240W) | 10m @140W")
        self.assertLossless(d, summary)

    def test_step_after_trailing_rep_is_not_skipped(self):
        # Tempo blocks with active connectors, a final tempo block, then a cool-down.
        # v3.133 counted the trailing rep and advanced count * 2, dropping the 150 W step.
        d = doc(P(900, 160), P(600, 230), P(600, 180), P(600, 230), P(600, 180),
                P(600, 230), P(600, 150))
        summary = summarize(self.sync, d)
        self.assertEqual(summary, "15m @160W | 2×(10m @230W + 10m @180W) + 10m @230W | 10m @150W",
                         "the step after a trailing solo rep was skipped")
        self.assertLossless(d, summary)

    def test_set_break_tail_rest_is_written_out(self):
        d = doc(P(600, 150), P(60, 300), P(60, 150), P(60, 300), P(60, 150),
                P(60, 300), P(180, 150), P(600, 140))
        summary = summarize(self.sync, d)
        self.assertEqual(summary,
                         "10m @150W | 2×(1m @300W + 1m @150W) + (1m @300W + 3m @150W) | 10m @140W")
        self.assertLossless(d, summary)

    def test_values_stay_within_existing_detector_tolerance(self):
        d = doc(P(600, 150), P(120, 290), P(120, 240), P(121, 292), P(118, 238),
                P(119, 288), P(122, 241), P(600, 140))
        summary = summarize(self.sync, d)
        self.assertLossless(d, summary, watt_tol=2, dur_tol=2)


# ── 4. availability, markers, telemetry and phase preservation ───────────────

def availability_fixtures():
    fixtures = {
        "two_higher": doc(P(600, 150), R(3, P(600, 175), P(600, 205)), P(600, 140)),
        "two_lower_active": doc(R(3, P(600, 245), P(600, 205))),
        "two_easy": doc(R(3, P(600, 245), P(600, 95))),
        "two_no_target": doc(R(5, P(60, 400), P(120))),
        "two_hr": doc(R(3, P(600, bpm=160), P(600, bpm=140))),
        "two_second_no_duration": doc(R(3, P(600, 245), P(None, 205))),
        "two_first_no_duration": doc(R(3, P(None, 245), P(600, 205), mode="marked")),
        "three_step_nested": doc(P(600, 150), R(3, P(300, 300), P(120, 120), P(300, 250), mode="marked")),
        "nested_over_under": doc(R(2, *([P(120, 290), P(120, 240)] * 3))),
        "nested_set_step": doc(R(2, P(600, 200), *([P(60, 300), P(60, 150)] * 3))),
        "nested_trailing": doc(R(2, *([P(60, 300), P(60, 150)] * 3), P(60, 300))),
        "flat_over_under": doc(P(600, 150), *([P(120, 290), P(120, 240)] * 3), P(600, 140)),
        "flat_trailing_cooldown": doc(P(900, 160), P(600, 230), P(600, 180), P(600, 230),
                                      P(600, 180), P(600, 230), P(600, 150)),
        "flat_two_pairs_only": doc(P(900, 160), P(600, 230), P(600, 180), P(600, 230),
                                   P(600, 150)),
        "flat_only": doc(P(3600, 160)),
        "flat_hr_only": doc(P(1800, bpm=130), P(1800, bpm=140)),
        "repeat_plus_distance_step": doc(P(600, 150), R(3, P(300, 300), P(120, 120)),
                                         X({"distance": 5000, "_power": {"value": 250}}),
                                         P(600, 140)),
        "merged_identical": doc(R(3, P(300, 300), P(120, 120)), R(3, P(300, 300), P(120, 120))),
        "formerly_merged": doc(R(3, P(300, 300), P(120, 120)), R(3, P(300, 300), P(120, 200))),
        # v3.135 incompleteness cases.
        "bail_among_valid": doc(R(3, P(300, 300), P(120, 120)),
                                R(2, P(60, 400), P(60, 100), P(60, 200), mode="marked")),
        "first_unrenderable_among_valid": doc(R(3, P(300, 300), P(120, 120)),
                                              R(3, P(None, 300), P(120, 120), mode="marked")),
        "range_target_flat": doc(P(600, 150), R(3, P(300, 300), P(120, 120)),
                                 T(600, NOT_SHOWN, _power={"start": 140, "end": 160})),
        "pace_target_repeat": doc(R(4, T(240, NOT_SHOWN,
                                         pace={"start": 90, "end": 95, "units": "%pace"}),
                                    P(120))),
        "power_range_with_hr": doc(R(3, T(600, NOT_SHOWN, _power={"start": 200, "end": 220},
                                          _hr={"value": 150}),
                                     P(300, 120))),
        "two_distance_steps": doc(R(3, P(300, 300), P(120, 120)),
                                  X({"distance": 1000}), X({"distance": 2000})),
        "flat_alternating_with_distance": doc(P(600, 150), *([P(120, 290), P(120, 240)] * 3),
                                              X({"distance": 3000, "_power": {"value": 150}}),
                                              P(600, 140)),
        "non_dict_step": doc(R(3, P(300, 300), P(120, 120)), "unparsed"),
        "markers_only_no_interval": doc(X({"distance": 5000}),
                                        R(3, P(300, 300), P(120, 120), P(300, 250), mode="marked")),
        # All-flat structured plan with the shape of the reported case (tempo blocks
        # of unequal length joined by active connectors); synthetic values.
        "all_flat_tempo_connectors": doc(P(900, 160), P(1200, 230), P(600, 180), P(900, 230),
                                         P(600, 180), P(600, 230), P(600, 150)),
    }
    fixtures.update(correction_fixtures())
    fixtures.update({name: d for name, (d, _) in invariant_cases().items()})
    return fixtures


def _base():
    return R(3, P(300, 300), P(120, 120))


def _pairs(work=None, rest=None, n=3):
    out = []
    for _ in range(n):
        out += [work() if work else P(60, 300), rest() if rest else P(60, 150)]
    return out


def _pct(value):
    return {"value": value, "units": "%ftp"}


def correction_fixtures():
    """Adjudicated checkpoint-2 correction classes, across every emitter."""
    return {
        # 1. Nested alternating repeat with an unmatched final child.
        "nested_trailer_other_target": doc(R(2, *_pairs(), P(60, 240))),
        "nested_trailer_untargeted": doc(R(2, *_pairs(), P(60))),
        "nested_trailer_longer": doc(R(2, *_pairs(), P(120, 300))),
        "nested_trailer_distance": doc(R(2, *_pairs(), X({"distance": 500}))),
        "nested_trailer_relative": doc(R(2, *_pairs(), T(60, NOT_SHOWN, power=_pct(90)))),
        "nested_set_step_and_trailer": doc(R(2, P(600, 200), *_pairs(), P(60, 240))),
        # 2. Relative units must not be labelled W or bpm, on every path.
        "flat_raw_percent_ftp": doc(_base(), T(600, NOT_SHOWN, power={"value": 80, "units": "%FTP"})),
        "flat_raw_hr_zone": doc(_base(), T(600, NOT_SHOWN, hr={"value": 2, "units": "hr_zone"})),
        "flat_raw_power_no_units": doc(_base(), T(600, NOT_SHOWN, power={"value": 200})),
        "two_step_relative_second": doc(R(3, P(600, 245), T(600, NOT_SHOWN, power=_pct(60)))),
        "nested_relative_pairs": doc(R(2, *_pairs(lambda: T(60, NOT_SHOWN, power=_pct(110)),
                                                  lambda: T(60, NOT_SHOWN, power=_pct(50))))),
        "nested_relative_tail_rest": doc(R(1, P(60, 300), P(60, 150), P(60, 300), P(60, 150),
                                           P(60, 300), T(120, NOT_SHOWN, power=_pct(150)))),
        "nested_relative_set_step": doc(R(2, T(600, NOT_SHOWN, power=_pct(60)), *_pairs())),
        "flat_alternating_relative": doc(P(600, 150),
                                         *_pairs(lambda: T(120, NOT_SHOWN, power=_pct(110)),
                                                 lambda: T(120, NOT_SHOWN, power=_pct(90))),
                                         P(600, 140)),
        "flat_alternating_relative_rest": doc(P(600, 150),
                                              *_pairs(lambda: P(120, 290),
                                                      lambda: T(120, NOT_SHOWN, power=_pct(80))),
                                              P(600, 140)),
        "flat_alternating_relative_tail": doc(P(600, 150), P(60, 300), P(60, 150), P(60, 300),
                                              P(60, 150), P(60, 300),
                                              T(180, NOT_SHOWN, power=_pct(150)), P(600, 140)),
        # 3. A present target is decided by key, not truthiness; no HR fall-through.
        "flat_empty_power": doc(_base(), T(600, NOT_SHOWN, power={})),
        "flat_null_power": doc(_base(), T(600, NOT_SHOWN, power=None)),
        "flat_empty_power_with_hr": doc(_base(), T(600, NOT_SHOWN, _power={}, _hr={"value": 150})),
        "flat_empty_hr": doc(_base(), T(600, NOT_SHOWN, hr={})),
        # 4. Range bounds are never discarded in favour of a scalar value.
        "flat_range_plus_value": doc(_base(), T(600, NOT_SHOWN, power={"start": 180, "end": 220,
                                                                       "value": 200, "units": "w"})),
        "two_step_range_plus_value": doc(R(3, T(600, NOT_SHOWN, power={"start": 180, "end": 220,
                                                                       "value": 200, "units": "w"}),
                                            P(600, 150))),
        "nested_rest_range_plus_value": doc(R(1, *_pairs(rest=lambda: T(60, NOT_SHOWN, _power={
            "start": 140, "end": 160, "value": 150})))),
        "raw_range_with_resolved_value": doc(_base(), T(600, NOT_SHOWN, power={"start": 70, "end": 80,
                                                                               "units": "%ftp"},
                                                        _power={"value": 225})),
        # Availability preservation: v3.134 declined these two-step blocks (its step
        # describer raised), so the summary must stay null whatever the new policy
        # could render. Expectations are irrelevant to a declined block.
        "two_step_first_string_hr": doc(R(3, T(600, NOT_SHOWN, hr={"value": "150"}), P(600, 150),
                                           mode="marked")),
        "two_step_first_infinite_power": doc(R(3, T(600, NOT_SHOWN, _power={"value": float("inf")}),
                                                P(600, 150), mode="marked")),
        # Supported and untargeted controls: printed, or duration only, unmarked.
        "control_raw_power_watts": doc(_base(), T(600, ("W", 200), power={"value": 200, "units": "w"})),
        "control_raw_hr_bpm": doc(_base(), T(600, ("bpm", 150), hr={"value": 150, "units": "bpm"})),
        "control_resolved_with_raw_relative": doc(_base(), T(600, ("W", 225), power=_pct(75),
                                                             _power={"value": 225})),
        "control_resolved_units_watts": doc(_base(), T(600, ("W", 210), _power={"value": 210, "units": "W"})),
        "control_untargeted": doc(_base(), P(600)),
    }


def _bad_pairs(**rest_fields):
    """Three (60 s @300 W, rest) pairs whose rest steps carry the given fields."""
    out = []
    for _ in range(3):
        out += [P(60, 300), X(dict({"_power": {"value": 150}}, **rest_fields))]
    return out


def _raw_pairs():
    """Plain dicts for a malformed repeat's children (never rendered, so undeclared)."""
    return [{"duration": 60, "_power": {"value": w}} for w in (300, 150) * 3]


INF, NAN = float("inf"), float("nan")
B = "BASE"


def invariant_cases():
    """
    v3.136 invariants: (workout_doc, exact expected summary or None). "BASE" in an
    expected string stands for the leading valid repeat "3×(5m @300W + 2m @120W) | ".
    """
    cases = {
        # 1. Repeat semantics never fall through to aggregate-duration rendering.
        "nested_repeat_aggregate": (
            doc(R(2, P(60, 300), R(3, P(30, 200), P(30, 100), duration=180))),
            "2×(1m @300W + 3×(30s @200W + 30s @100W))"),
        "nested_repeat_aggregate_first": (
            doc(R(2, R(3, P(30, 200), P(30, 100), duration=180), P(60, 150))),
            "2×(3×(30s @200W + 30s @100W) + 1m @150W)"),
        "nested_repeat_deep": (
            doc(R(2, P(60, 300), R(2, P(30, 250), R(2, P(10, 200), P(10, 100), duration=40),
                                   duration=140))),
            "2×(1m @300W + 2×(30s @250W + 2×(10s @200W + 10s @100W)))"),
        "nested_repeat_three_children": (
            doc(R(2, P(60, 300), R(2, P(20, 200), P(20, 150), P(20, 100), duration=120,
                                   mode="marked"))),
            "2×(1m @300W + [repeat not summarized])"),
        "nested_repeat_invalid_count_child": (
            doc(R(2, P(60, 300), XR({"reps": 0, "steps": _raw_pairs()[:2], "duration": 180}))),
            "2×(1m @300W + [repeat not summarized])"),
        "nested_repeat_first_without_duration": (
            doc(_base(), R(2, R(3, P(30, 200), P(30, 100)), P(60, 150), mode="marked")),
            B + "[repeat not summarized]"),
        "nested_unmatched_repeat_child": (
            doc(R(2, *_pairs(), R(3, P(30, 200), P(30, 100), duration=180))),
            "2 sets × (3×(1m @300W + 1m @150W) + 3×(30s @200W + 30s @100W))"),
        "nested_unmatched_malformed_child": (
            doc(R(2, *_pairs(), XR({"reps": 3, "steps": "bad", "duration": 180}))),
            "2 sets × (3×(1m @300W + 1m @150W) + [repeat not summarized])"),
        "nested_pair_repeat_like_child": (
            doc(_base(), R(2, P(60, 300), R(1, P(60, 150), duration=60, _power={"value": 150}),
                           P(60, 300), P(60, 150), P(60, 300), P(60, 150), mode="marked")),
            B + "[repeat not summarized]"),
        "malformed_steps_string": (
            doc(_base(), XR({"reps": 3, "steps": "bad", "duration": 180})), B + "[repeat not summarized]"),
        "malformed_steps_dict": (
            doc(_base(), XR({"reps": 3, "steps": {"duration": 60}, "duration": 180})),
            B + "[repeat not summarized]"),
        "malformed_steps_empty": (
            doc(_base(), XR({"reps": 3, "steps": [], "duration": 180})), B + "[repeat not summarized]"),
        "malformed_reps_without_steps": (
            doc(_base(), XR({"reps": 3, "duration": 180, "_power": {"value": 200}})),
            B + "[repeat not summarized]"),
        "malformed_steps_without_reps": (
            doc(_base(), XR({"steps": _raw_pairs()[:2], "duration": 120})), B + "[repeat not summarized]"),
        # 3. Repeat counts.
        "invalid_count_zero_only": (doc(XR({"reps": 0, "steps": _raw_pairs()})), None),
        "invalid_count_two_step": (
            doc(_base(), XR({"reps": 0, "steps": _raw_pairs()[:2]})), B + "[repeat not summarized]"),
        "count_float_whole": (doc(R(3.0, P(60, 300), P(60, 150), count=3)), "3×(1m @300W + 1m @150W)"),
        "count_one": (doc(R(1, P(600, 245), P(600, 150))), "1×(10m @245W + 10m @150W)"),
        # 4. Durations.
        "invalid_duration_two_step_second": (
            doc(R(3, P(600, 245), X({"duration": -60, "_power": {"value": 200}}))),
            "3×(10m @245W + [step not summarized])"),
        "two_step_first_zero_duration": (
            doc(_base(), R(3, X({"duration": 0, "_power": {"value": 200}}), P(600, 150), mode="marked")),
            B + "[repeat not summarized]"),
        "invalid_duration_nested_pairs": (
            doc(_base(), R(2, *_bad_pairs(duration=-60), mode="marked")), B + "[repeat not summarized]"),
        "invalid_duration_flat_alternating_only": (
            doc(P(600, 150), *[s for _ in range(3) for s in
                               (P(120, 290), X({"duration": -120, "_power": {"value": 240}}))],
                P(600, 140)),
            None),
        "invalid_duration_string_breaks_flat_block": (
            doc(P(600, 150), *_pairs(), X({"duration": "60", "_power": {"value": 300}}),
                P(60, 150), P(600, 140)),
            "10m @150W | 3×(1m @300W + 1m @150W) | [step not summarized] | 1m @150W | 10m @140W"),
        "duration_float_nested": (
            doc(R(2, *[s for _ in range(3) for s in
                       (A({"duration": 60.0, "_power": {"value": 300}}, 60, ("W", 300)),
                        A({"duration": 60.0, "_power": {"value": 150}}, 60, ("W", 150)))])),
            "2 sets × 3×(1m @300W + 1m @150W)"),
        "duration_float_flat_alternating": (
            doc(P(600, 150), *[s for _ in range(3) for s in
                               (A({"duration": 120.0, "_power": {"value": 290}}, 120, ("W", 290)),
                                A({"duration": 120.0, "_power": {"value": 240}}, 120, ("W", 240)))],
                P(600, 140)),
            "10m @150W | 3×(2m @290W + 2m @240W) | 10m @140W"),
        "duration_fraction_flat": (
            doc(_base(), A({"duration": 90.5, "_power": {"value": 200}}, 90, ("W", 200))),
            B + "1m30s @200W"),
        # 2. Raw 2 W tolerance before display rounding.
        "tolerance_flat_over": (
            doc(P(60, 300), P(60, 150), P(60, 302.4), P(60, 150), P(60, 300), P(60, 150)),
            "3×(1m [target not shown] + 1m @150W)"),
        "tolerance_flat_within": (
            doc(P(60, 300), P(60, 150), P(60, 301.9), P(60, 150), P(60, 298.1), P(60, 150)),
            "3×(1m @300W + 1m @150W)"),
        "tolerance_flat_rest_over": (
            doc(P(60, 300), P(60, 150), P(60, 300), P(60, 152.4), P(60, 300), P(60, 150)),
            "3×(1m @300W + 1m [target not shown])"),
        "tolerance_nested_over": (
            doc(R(2, P(60, 300), P(60, 150), P(60, 302.4), P(60, 150), P(60, 300), P(60, 150))),
            "2 sets × 3×(1m [target not shown] + 1m @150W)"),
        "tolerance_nested_within": (
            doc(R(2, P(60, 300), P(60, 150), P(60, 301.9), P(60, 150), P(60, 298.1), P(60, 150))),
            "2 sets × 3×(1m @300W + 1m @150W)"),
        "tolerance_nested_trailing_over": (
            doc(R(2, *_pairs(), P(60, 302.4))),
            "2 sets × (3×(1m [target not shown] + 1m @150W) + 1m [target not shown])"),
        "tolerance_flat_tail_rest_over": (
            doc(P(600, 150), P(60, 300), P(60, 150), P(60, 300), P(60, 150), P(60, 300),
                P(180, 152.4), P(600, 140)),
            "10m @150W | 2×(1m @300W + 1m @150W) + (1m @300W + 3m [target not shown]) | 10m @140W"),
        # 6. String target values are never printed.
        "string_target_flat": (
            doc(_base(), T(600, NOT_SHOWN, _power={"value": "200"})), B + "10m [target not shown]"),
        "string_target_raw_watts": (
            doc(R(3, P(600, 245), T(600, NOT_SHOWN, power={"value": "60", "units": "w"}))),
            "3×(10m @245W + 10m [target not shown])"),
        "string_target_hr": (
            doc(_base(), T(600, NOT_SHOWN, _hr={"value": "150"})), B + "10m [target not shown]"),
    }
    for label, value in (("zero", 0), ("negative", -1), ("fraction", 2.5), ("bool", True),
                         ("string", "3"), ("null", None), ("inf", INF), ("nan", NAN)):
        cases[f"invalid_count_{label}"] = (
            doc(_base(), XR({"reps": value, "steps": _raw_pairs()})), B + "[repeat not summarized]")
    for label, value in (("negative", -60), ("zero", 0), ("below_one", 0.4), ("bool", True),
                         ("string", "600"), ("inf", INF), ("nan", NAN), ("null", None)):
        cases[f"invalid_duration_flat_{label}"] = (
            doc(_base(), X({"duration": value, "_power": {"value": 200}})), B + "[step not summarized]")
    for label, value in (("negative", -60), ("below_one", 0.4), ("bool", True), ("string", "600")):
        # v3.134 accepted these first steps as describable, so the block still renders
        # (availability kept); the step itself is now marked.
        cases[f"invalid_duration_two_step_first_{label}"] = (
            doc(R(3, X({"duration": value, "_power": {"value": 200}}), P(600, 150))),
            "3×([step not summarized] + 10m @150W)")
    return {name: (d, None if want is None else want.replace("BASE", "3×(5m @300W + 2m @120W) | "))
            for name, (d, want) in cases.items()}


# Captured by running availability_fixtures() through sync.py v3.133 at bef4c686 and
# re-checked identical on v3.134 (checkpoint 1) for every fixture:
# (summary is null, summary carries a "×" or "sets" marker, hard_sessions_planned
# for a single generically named WORKOUT row dated today).
BASELINE_V3133 = {
    "two_higher": (False, True, 1),
    "two_lower_active": (False, True, 1),
    "two_easy": (False, True, 1),
    "two_no_target": (False, True, 1),
    "two_hr": (False, True, 1),
    "two_second_no_duration": (False, True, 1),
    "two_first_no_duration": (True, False, 0),
    "three_step_nested": (True, False, 0),
    "nested_over_under": (False, True, 1),
    "nested_set_step": (False, True, 1),
    "nested_trailing": (False, True, 1),
    "flat_over_under": (False, True, 1),
    "flat_trailing_cooldown": (False, True, 1),
    "flat_two_pairs_only": (True, False, 0),
    "flat_only": (True, False, 0),
    "flat_hr_only": (True, False, 0),
    "repeat_plus_distance_step": (False, True, 1),
    "merged_identical": (False, True, 1),
    "formerly_merged": (False, True, 1),
    "bail_among_valid": (False, True, 1),
    "first_unrenderable_among_valid": (False, True, 1),
    "range_target_flat": (False, True, 1),
    "pace_target_repeat": (False, True, 1),
    "power_range_with_hr": (False, True, 1),
    "two_distance_steps": (False, True, 1),
    "flat_alternating_with_distance": (False, True, 1),
    "non_dict_step": (False, True, 1),
    "markers_only_no_interval": (True, False, 0),
    "all_flat_tempo_connectors": (True, False, 0),
    "nested_trailer_other_target": (False, True, 1),
    "nested_trailer_untargeted": (False, True, 1),
    "nested_trailer_longer": (False, True, 1),
    "nested_trailer_distance": (False, True, 1),
    "nested_trailer_relative": (False, True, 1),
    "nested_set_step_and_trailer": (False, True, 1),
    "flat_raw_percent_ftp": (False, True, 1),
    "flat_raw_hr_zone": (False, True, 1),
    "flat_raw_power_no_units": (False, True, 1),
    "two_step_relative_second": (False, True, 1),
    "nested_relative_pairs": (False, True, 1),
    "nested_relative_tail_rest": (False, True, 1),
    "nested_relative_set_step": (False, True, 1),
    "flat_alternating_relative": (False, True, 1),
    "flat_alternating_relative_rest": (False, True, 1),
    "flat_alternating_relative_tail": (False, True, 1),
    "flat_empty_power": (False, True, 1),
    "flat_null_power": (False, True, 1),
    "flat_empty_power_with_hr": (False, True, 1),
    "flat_empty_hr": (False, True, 1),
    "flat_range_plus_value": (False, True, 1),
    "two_step_range_plus_value": (False, True, 1),
    "nested_rest_range_plus_value": (False, True, 1),
    "raw_range_with_resolved_value": (False, True, 1),
    "two_step_first_string_hr": (True, False, 0),
    "two_step_first_infinite_power": (True, False, 0),
    "control_raw_power_watts": (False, True, 1),
    "control_raw_hr_bpm": (False, True, 1),
    "control_resolved_with_raw_relative": (False, True, 1),
    "control_resolved_units_watts": (False, True, 1),
    "control_untargeted": (False, True, 1),
    # v3.136 invariant fixtures (all identical on v3.133 and v3.134).
    "nested_repeat_aggregate": (False, True, 1),
    "nested_repeat_aggregate_first": (False, True, 1),
    "nested_repeat_deep": (False, True, 1),
    "nested_repeat_three_children": (False, True, 1),
    "nested_repeat_invalid_count_child": (False, True, 1),
    "nested_repeat_first_without_duration": (False, True, 1),
    "nested_unmatched_repeat_child": (False, True, 1),
    "nested_unmatched_malformed_child": (False, True, 1),
    "nested_pair_repeat_like_child": (False, True, 1),
    "malformed_steps_string": (False, True, 1),
    "malformed_steps_dict": (False, True, 1),
    "malformed_steps_empty": (False, True, 1),
    "malformed_reps_without_steps": (False, True, 1),
    "malformed_steps_without_reps": (False, True, 1),
    "invalid_count_zero_only": (False, True, 1),
    "invalid_count_two_step": (False, True, 1),
    "count_float_whole": (False, True, 1),
    "count_one": (False, True, 1),
    "invalid_duration_two_step_second": (False, True, 1),
    "two_step_first_zero_duration": (False, True, 1),
    "invalid_duration_nested_pairs": (False, True, 1),
    "invalid_duration_flat_alternating_only": (False, True, 1),
    "duration_float_nested": (False, True, 1),
    "duration_float_flat_alternating": (False, True, 1),
    "duration_fraction_flat": (False, True, 1),
    "tolerance_flat_over": (False, True, 1),
    "tolerance_flat_within": (False, True, 1),
    "tolerance_flat_rest_over": (False, True, 1),
    "tolerance_nested_over": (False, True, 1),
    "tolerance_nested_within": (False, True, 1),
    "tolerance_nested_trailing_over": (False, True, 1),
    "tolerance_flat_tail_rest_over": (False, True, 1),
    "string_target_flat": (False, True, 1),
    "string_target_raw_watts": (False, True, 1),
    "string_target_hr": (False, True, 1),
    "invalid_duration_string_breaks_flat_block": (True, False, 0),
    "invalid_count_zero": (False, True, 1),
    "invalid_count_negative": (False, True, 1),
    "invalid_count_fraction": (False, True, 1),
    "invalid_count_bool": (False, True, 1),
    "invalid_count_string": (False, True, 1),
    "invalid_count_null": (False, True, 1),
    "invalid_count_inf": (False, True, 1),
    "invalid_count_nan": (False, True, 1),
    "invalid_duration_flat_negative": (False, True, 1),
    "invalid_duration_flat_zero": (False, True, 1),
    "invalid_duration_flat_below_one": (False, True, 1),
    "invalid_duration_flat_bool": (False, True, 1),
    "invalid_duration_flat_string": (False, True, 1),
    "invalid_duration_flat_inf": (False, True, 1),
    "invalid_duration_flat_nan": (False, True, 1),
    "invalid_duration_flat_null": (False, True, 1),
    "invalid_duration_two_step_first_negative": (False, True, 1),
    "invalid_duration_two_step_first_below_one": (False, True, 1),
    "invalid_duration_two_step_first_bool": (False, True, 1),
    "invalid_duration_two_step_first_string": (False, True, 1),
}
# Totals over every fixture except V3136_AVAILABILITY_CHANGES (113 events).
BASELINE_V3133_STATS = {"attempted": 113, "success": 104, "patternA": 93, "patternB": 11,
                        "bail_no_workout_doc": 0, "bail_no_match": 9}
BASELINE_V3133_WEEK = {"hard_sessions_planned": 104, "current_week_hard_days_total": 106}


class TestRenderingOnlyPreservation(unittest.TestCase):
    def setUp(self):
        self.sync = make_sync()
        self.fixtures = availability_fixtures()
        self.assertEqual(set(self.fixtures), set(BASELINE_V3133))

    def _rows(self):
        # Totals are compared over every fixture whose availability v3.136 keeps.
        events = [event(d, name=f"Session {n}") for n, (name, d) in enumerate(self.fixtures.items())
                  if name not in V3136_AVAILABILITY_CHANGES]
        return self.sync._format_events(events, today=TODAY)

    def test_null_status_and_markers_match_v3133(self):
        for name, d in self.fixtures.items():
            with self.subTest(name):
                summary = summarize(self.sync, d)
                is_null = summary is None
                marker = bool(summary) and ("×" in summary or "sets" in summary.lower())
                expected = V3136_AVAILABILITY_CHANGES.get(name, (None, BASELINE_V3133[name]))[1]
                self.assertEqual((is_null, marker), expected[:2],
                                 "summary availability or phase marker changed")

    def test_summary_stats_match_v3133(self):
        self._rows()
        self.assertEqual(self.sync._summary_stats, BASELINE_V3133_STATS,
                         "workout_summary_stats telemetry changed")

    def test_hard_sessions_planned_per_workout_match_v3133(self):
        for name, d in self.fixtures.items():
            with self.subTest(name):
                rows = self.sync._format_events([event(d)], today=TODAY)
                features = self.sync._phase_stream2_features(rows, {}, {}, TODAY)
                expected = V3136_AVAILABILITY_CHANGES.get(name, (None, BASELINE_V3133[name]))[1]
                self.assertEqual(features["hard_sessions_planned"], expected[2],
                                 "hard_sessions_planned changed for a generically named workout")

    def test_week_hard_totals_match_v3133(self):
        features = self.sync._phase_stream2_features(
            self._rows(), {}, {}, TODAY, weekly_rows=[{"hard_days": 2}])
        self.assertEqual({k: features[k] for k in BASELINE_V3133_WEEK}, BASELINE_V3133_WEEK)


class TestOracleAcrossFixtures(OracleCase):
    def test_every_summary_is_faithful_and_unmarked_means_complete(self):
        # The stated scope: 2 W / 2 s detector tolerance, and whole-role marking.
        for name, d in availability_fixtures().items():
            summary = summarize(self.sync, d)
            if summary is None:
                continue
            with self.subTest(name):
                self.assertFaithful(d, summary, watt_tol=2, dur_tol=2, role_mark_ok=True)
                if "[" not in summary:
                    self.assertLossless(d, summary, watt_tol=2, dur_tol=2)


class TestIncompleteSummariesMarked(OracleCase):
    """v3.135: content that cannot render is marked in place, never dropped."""

    CASES = {
        "repeat_plus_distance_step": "10m @150W | 3×(5m @300W + 2m @120W) | [step not summarized] | 10m @140W",
        "bail_among_valid": "3×(5m @300W + 2m @120W) | [repeat not summarized]",
        "first_unrenderable_among_valid": "3×(5m @300W + 2m @120W) | [repeat not summarized]",
        "range_target_flat": "10m @150W | 3×(5m @300W + 2m @120W) | 10m [target not shown]",
        "pace_target_repeat": "4×(4m [target not shown] + 2m)",
        "power_range_with_hr": "3×(10m [target not shown] + 5m @120W)",
        "two_distance_steps": "3×(5m @300W + 2m @120W) | [step not summarized] | [step not summarized]",
        "flat_alternating_with_distance": "10m @150W | 3×(2m @290W + 2m @240W) | [step not summarized] | 10m @140W",
        "non_dict_step": "3×(5m @300W + 2m @120W) | [step not summarized]",
    }

    CORRECTION_CASES = {
        "nested_trailer_other_target": "2 sets × (3×(1m @300W + 1m @150W) + 1m @240W)",
        "nested_trailer_untargeted": "2 sets × (3×(1m @300W + 1m @150W) + 1m)",
        "nested_trailer_longer": "2 sets × (3×(1m @300W + 1m @150W) + 2m @300W)",
        "nested_trailer_distance": "2 sets × (3×(1m @300W + 1m @150W) + [step not summarized])",
        "nested_trailer_relative": "2 sets × (3×(1m @300W + 1m @150W) + 1m [target not shown])",
        "nested_set_step_and_trailer": "2 sets × (10m @200W + 3×(1m @300W + 1m @150W) + 1m @240W)",
        "flat_raw_percent_ftp": "3×(5m @300W + 2m @120W) | 10m [target not shown]",
        "flat_raw_hr_zone": "3×(5m @300W + 2m @120W) | 10m [target not shown]",
        "flat_raw_power_no_units": "3×(5m @300W + 2m @120W) | 10m [target not shown]",
        "two_step_relative_second": "3×(10m @245W + 10m [target not shown])",
        "nested_relative_pairs": "2 sets × 3×(1m [target not shown] + 1m [target not shown])",
        "nested_relative_tail_rest": "2×(1m @300W + 1m @150W) + (1m @300W + 2m [target not shown])",
        "nested_relative_set_step": "2 sets × (10m [target not shown] + 3×(1m @300W + 1m @150W))",
        "flat_alternating_relative": "10m @150W | 3×(2m [target not shown] + 2m [target not shown]) | 10m @140W",
        "flat_alternating_relative_rest": "10m @150W | 3×(2m @290W + 2m [target not shown]) | 10m @140W",
        "flat_alternating_relative_tail": "10m @150W | 2×(1m @300W + 1m @150W) + (1m @300W + 3m [target not shown]) | 10m @140W",
        "flat_empty_power": "3×(5m @300W + 2m @120W) | 10m [target not shown]",
        "flat_null_power": "3×(5m @300W + 2m @120W) | 10m [target not shown]",
        "flat_empty_power_with_hr": "3×(5m @300W + 2m @120W) | 10m [target not shown]",
        "flat_empty_hr": "3×(5m @300W + 2m @120W) | 10m [target not shown]",
        "flat_range_plus_value": "3×(5m @300W + 2m @120W) | 10m [target not shown]",
        "two_step_range_plus_value": "3×(10m [target not shown] + 10m @150W)",
        "nested_rest_range_plus_value": "3×(1m @300W + 1m [target not shown])",
        "raw_range_with_resolved_value": "3×(5m @300W + 2m @120W) | 10m [target not shown]",
    }
    CONTROL_CASES = {
        "control_raw_power_watts": "3×(5m @300W + 2m @120W) | 10m @200W",
        "control_raw_hr_bpm": "3×(5m @300W + 2m @120W) | 10m @150bpm",
        "control_resolved_with_raw_relative": "3×(5m @300W + 2m @120W) | 10m @225W",
        "control_resolved_units_watts": "3×(5m @300W + 2m @120W) | 10m @210W",
        "control_untargeted": "3×(5m @300W + 2m @120W) | 10m",
    }
    # What the rejected checkpoint-2 candidate emitted for some of the fixtures
    # above. The oracle must reject every one; a mirrored oracle accepted them.
    REJECTED_OUTPUTS = {
        "nested_trailer_other_target": "2 sets × 3×(1m @300W + 1m @150W)",
        "flat_raw_percent_ftp": "3×(5m @300W + 2m @120W) | 10m @80W",
        "flat_raw_hr_zone": "3×(5m @300W + 2m @120W) | 10m @2bpm",
        "flat_empty_power": "3×(5m @300W + 2m @120W) | 10m",
        "flat_empty_power_with_hr": "3×(5m @300W + 2m @120W) | 10m @150bpm",
        "flat_range_plus_value": "3×(5m @300W + 2m @120W) | 10m @200W",
        "nested_relative_pairs": "2 sets × 3×(1m @110W + 1m @50W)",
        "flat_alternating_relative_rest": "10m @150W | 3×(2m @290W + 2m @80W) | 10m @140W",
        "two_step_range_plus_value": "3×(10m @200W + 10m @150W)",
    }

    def test_correction_classes_on_every_emitter(self):
        fixtures = availability_fixtures()
        for name, expected in self.CORRECTION_CASES.items():
            with self.subTest(name):
                summary = summarize(self.sync, fixtures[name])
                self.assertEqual(summary, expected)
                self.assertFaithful(fixtures[name], summary)

    def test_supported_and_untargeted_controls_stay_unmarked(self):
        fixtures = availability_fixtures()
        for name, expected in self.CONTROL_CASES.items():
            with self.subTest(name):
                summary = summarize(self.sync, fixtures[name])
                self.assertEqual(summary, expected)
                self.assertLossless(fixtures[name], summary)

    def test_role_with_mixed_printability_is_marked_as_a_whole(self):
        # Third rest carries a relative target; the other two are printable watts.
        d = doc(P(600, 150), P(120, 290), P(120, 150), P(120, 290), P(120, 150),
                P(120, 290), T(120, NOT_SHOWN, power=_pct(150)), P(600, 140))
        summary = summarize(self.sync, d)
        self.assertEqual(summary, "10m @150W | 3×(2m @290W + 2m [target not shown]) | 10m @140W")
        self.assertFaithful(d, summary, role_mark_ok=True)
        with self.assertRaises(AssertionError):
            self.assertFaithful(d, summary)  # strict mode sees the covered 150 W steps
        with self.assertRaises(AssertionError):
            self.assertFaithful(d, "10m @150W | 3×(2m @290W + 2m @150W) | 10m @140W",
                                role_mark_ok=True)

    def test_oracle_rejects_the_rejected_candidate_outputs(self):
        fixtures = availability_fixtures()
        for name, wrong in self.REJECTED_OUTPUTS.items():
            with self.subTest(name):
                with self.assertRaises(AssertionError):
                    self.assertFaithful(fixtures[name], wrong)

    def test_exact_marked_output(self):
        fixtures = availability_fixtures()
        for name, expected in self.CASES.items():
            with self.subTest(name):
                summary = summarize(self.sync, fixtures[name])
                self.assertEqual(summary, expected)
                self.assertFaithful(fixtures[name], summary)

    def test_markers_cannot_create_a_phase_marker(self):
        for mark in (STEP_MARK, REPEAT_MARK, TARGET_MARK):
            with self.subTest(mark):
                self.assertTrue(mark.startswith("[") and mark.endswith("]"))
                self.assertNotIn("×", mark)
                self.assertNotIn("sets", mark.lower())

    def test_marked_parts_never_merge_but_complete_parts_still_do(self):
        fixtures = availability_fixtures()
        self.assertNotIn("2 ×", summarize(self.sync, fixtures["two_distance_steps"]))
        self.assertEqual(summarize(self.sync, fixtures["merged_identical"]),
                         "2 × 3×(5m @300W + 2m @120W)")

    def test_untargeted_step_still_renders_duration_only(self):
        self.assertEqual(summarize(self.sync, doc(R(5, P(60, 400), P(120)))),
                         "5×(1m @400W + 2m)")

    def test_marker_only_content_stays_null(self):
        self.assertIsNone(summarize(self.sync, availability_fixtures()["markers_only_no_interval"]))


# v3.136 is allowed to change summary availability only where an invalid input used
# to masquerade as a complete workout. These are the only such fixtures:
# name -> (v3.134 tuple, v3.136 tuple), tuples as in BASELINE_V3133.
V3136_AVAILABILITY_CHANGES = {
    # Zero-count repeat was the only interval: v3.134 "3×(1m @300W + 1m @150W)".
    "invalid_count_zero_only": ((False, True, 1), (True, False, 0)),
    # Negative rest durations formed a block: v3.134 "... 3×(2m @290W + 0s @240W) ...".
    "invalid_duration_flat_alternating_only": ((False, True, 1), (True, False, 0)),
    # The reverse direction, also malformed input only: v3.134's flat detector raised
    # on the string duration and discarded the valid block before it (null summary);
    # v3.136 keeps the block and marks the step, so the summary is marked, not complete.
    "invalid_duration_string_breaks_flat_block": ((True, False, 0), (False, True, 1)),
}


class TestV3136Invariants(OracleCase):
    """Repeat semantics, counts, durations, raw tolerance and string targets."""

    # Outputs of the blocked v3.135 candidate (reproduce_blockers.py and adjacent
    # cases). The oracle must reject every one.
    BLOCKED_OUTPUTS = {
        "nested_repeat_aggregate": "2×(1m @300W + 3m)",
        "malformed_steps_string": "3×(5m @300W + 2m @120W) | 3m",
        "tolerance_flat_over": "3×(1m @300W + 1m @150W)",
        "invalid_count_zero_only": "3×(1m @300W + 1m @150W)",
        "invalid_duration_flat_negative": "3×(5m @300W + 2m @120W) | 0s @200W",
        "tolerance_nested_over": "2 sets × 3×(1m @300W + 1m @150W)",
        "nested_unmatched_repeat_child": "2 sets × (3×(1m @300W + 1m @150W) + 3m)",
        "invalid_duration_flat_alternating_only": "10m @150W | 3×(2m @290W + 0s @240W) | 10m @140W",
        "count_float_whole": "3.0×(1m @300W + 1m @150W)",
        "duration_float_nested": "2 sets × 3×(1.0m @300W + 1.0m @150W)",
    }

    def test_exact_output(self):
        for name, (d, expected) in invariant_cases().items():
            with self.subTest(name):
                self.assertEqual(summarize(self.sync, d), expected)

    def test_every_invariant_output_is_faithful(self):
        for name, (d, expected) in invariant_cases().items():
            if expected is None:
                continue
            with self.subTest(name):
                self.assertFaithful(d, summarize(self.sync, d), watt_tol=2, role_mark_ok=True)

    def test_oracle_rejects_blocked_candidate_outputs(self):
        cases = invariant_cases()
        for name, wrong in self.BLOCKED_OUTPUTS.items():
            with self.subTest(name):
                with self.assertRaises(AssertionError):
                    self.assertFaithful(cases[name][0], wrong, watt_tol=2, role_mark_ok=True)

    def test_oracle_expectations_do_not_depend_on_production(self):
        # The expected items for a malformed repeat, an invalid count and an invalid
        # duration come from their declarations even though the same dicts would
        # satisfy any list-shape test: a declared-marked repeat whose "steps" is a
        # valid list still expects the repeat marker.
        d = doc(XR({"reps": 0, "steps": _raw_pairs()}))
        self.assertEqual(expand_doc(d), [REPEAT_TOKEN])
        d = doc(X({"duration": 60, "_power": {"value": 200}}))
        self.assertEqual(expand_doc(d), [STEP_TOKEN])
        with self.assertRaises(AssertionError):
            expand_doc(doc({"reps": 3, "steps": _raw_pairs()}))  # undeclared

    def test_availability_changes_are_only_the_declared_invalid_inputs(self):
        for name, (before, after) in V3136_AVAILABILITY_CHANGES.items():
            with self.subTest(name):
                self.assertTrue(name.startswith("invalid_"))
                self.assertEqual(BASELINE_V3133[name], before)
                rows = self.sync._format_events([event(availability_fixtures()[name])], today=TODAY)
                summary = rows[0]["workout_summary"]
                hard = self.sync._phase_stream2_features(rows, {}, {}, TODAY)["hard_sessions_planned"]
                marker = bool(summary) and ("×" in summary or "sets" in summary.lower())
                self.assertEqual((summary is None, marker, hard), after)


# ── 5. tier behaviour unchanged ──────────────────────────────────────────────

class TestTierFieldsUnchanged(unittest.TestCase):
    def setUp(self):
        self.sync = make_sync()

    def test_near_and_far_rows(self):
        flat = doc(P(900, 160), P(600, 230), P(600, 180), P(600, 230), P(600, 150))
        desc = "15m 160w\n10m 230w\n10m 180w active\n10m 230w"
        near, far_null, far_summary = self.sync._format_events(
            [event(flat, description=desc),
             event(flat, date=FAR_DAY, description=desc),
             event(doc(R(3, P(600, 245), P(600, 205))), date=FAR_DAY, description=desc)],
            today=TODAY)
        self.assertIsNone(near["workout_summary"])
        self.assertEqual(near["description"], desc)
        self.assertNotIn("description_preview", near)
        self.assertIsNone(far_null["workout_summary"])
        self.assertNotIn("description", far_null)
        self.assertEqual(far_null["description_preview"], "15m 160w\n10m 230w\n10m 180w active")
        self.assertIsNotNone(far_summary["workout_summary"])
        self.assertNotIn("description", far_summary)
        self.assertNotIn("description_preview", far_summary)


# ── 5b. report template consumption contract ─────────────────────────────────

class TestReportTemplateFallbackContract(unittest.TestCase):
    """
    PRE and POST read today's and tomorrow's rows. The fields each template names
    for a null or marked summary must be the fields the producer actually puts on
    the row tier being read, and the tier boundary the template states must match
    the producer's.
    """

    INSTRUCTION = "Use workout_summary as source"
    FALLBACK = re.compile(r"If workout_summary is null or carries a marker, (.+?); if that field")
    NEAR_RULE = re.compile(r"`description` \(entries up to (\d+) days ahead\)")
    FAR_RULE = re.compile(r"`description_preview` \(later entries; its first (\d+) lines only")

    def setUp(self):
        self.sync = make_sync()
        self.lines = {}
        for name, path in TEMPLATE_PATHS.items():
            hits = [l for l in path.read_text(encoding="utf-8").splitlines()
                    if self.INSTRUCTION in l]
            self.assertEqual(len(hits), 1, f"{name}: expected one planned-workout instruction")
            self.lines[name] = hits[0]

    def _row(self, day_offset, workout_doc, description):
        date = (datetime.strptime(TODAY, "%Y-%m-%d") + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        return self.sync._format_events([event(workout_doc, date=date, description=description)],
                                        today=TODAY)[0]

    def test_old_fallback_and_recovery_omission_are_gone(self):
        for name, line in self.lines.items():
            with self.subTest(name):
                self.assertNotIn("If workout_summary is null, use description_preview.", line)
                self.assertNotIn("omit warmup/cooldown/recovery steps", line)

    def test_labelled_recovery_rule_is_kept(self):
        for name, line in self.lines.items():
            with self.subTest(name):
                self.assertIn("omit a warm-up, cool-down or recovery step only where the plan "
                              "labels it so, since a lower target alone does not make a step "
                              "recovery", line)

    def test_unmarked_summary_scope_is_stated_not_overclaimed(self):
        for name, line in self.lines.items():
            with self.subTest(name):
                self.assertNotIn("a summary without it is complete", line)
                self.assertIn("A summary without a marker lists every step with its duration "
                              "and its power target (or HR target when no power target is set)",
                              line)
                self.assertIn("secondary targets such as cadence or an HR target set alongside "
                              "power", line)
                self.assertIn("shows them at the first step's value when each is within 2 W "
                              "and 2 s of that first step", line)

    def test_marked_summary_without_description_is_reported_as_incomplete(self):
        for name, line in self.lines.items():
            with self.subTest(name):
                self.assertIn("report a marked summary as given and say it is incomplete", line)
                self.assertIn("for a null summary give the workout name and duration", line)

    def test_template_names_every_producer_marker(self):
        for name, line in self.lines.items():
            for mark in (STEP_MARK, REPEAT_MARK, TARGET_MARK):
                with self.subTest(template=name, mark=mark):
                    self.assertIn(f"`{mark}`", line)

    def test_named_fields_match_the_row_each_tier_carries(self):
        flat = availability_fixtures()["all_flat_tempo_connectors"]
        desc = "15m 160w\n20m 230w\n10m 180w active\n15m 230w"
        for name, line in self.lines.items():
            with self.subTest(name):
                fallback = self.FALLBACK.search(line)
                self.assertIsNotNone(fallback, "fallback rule missing")
                named = set(re.findall(r"`([a-z_]+)`", fallback.group(1)))
                self.assertEqual(named, {"description", "description_preview"})
                near_days = int(self.NEAR_RULE.search(line).group(1))
                preview_lines = int(self.FAR_RULE.search(line).group(1))
                for offset in (0, 1, near_days):
                    row = self._row(offset, flat, desc)
                    self.assertIsNone(row["workout_summary"])
                    self.assertEqual(row.get("description"), desc,
                                     f"day +{offset}: template says description")
                    self.assertNotIn("description_preview", row)
                for offset in (near_days + 1, 20):
                    row = self._row(offset, flat, desc)
                    self.assertIsNone(row["workout_summary"])
                    self.assertNotIn("description", row,
                                     f"day +{offset}: template says description_preview")
                    self.assertEqual(row.get("description_preview"),
                                     "\n".join(desc.split("\n")[:preview_lines]),
                                     "preview length differs from what the template states")

    def test_marked_summary_near_row_carries_description(self):
        marked = availability_fixtures()["repeat_plus_distance_step"]
        row = self._row(1, marked, "3x 5m 300w / 2m 120w\n5km steady")
        self.assertIn("[", row["workout_summary"])
        self.assertEqual(row["description"], "3x 5m 300w / 2m 120w\n5km steady")

    def test_far_marked_row_has_no_description_field(self):
        # Tiering is unchanged: a far row with a non-null summary carries neither
        # field, so the template's "absent or empty" rule is what applies there.
        row = self._row(20, availability_fixtures()["repeat_plus_distance_step"], "x")
        self.assertIn("[", row["workout_summary"])
        self.assertNotIn("description", row)
        self.assertNotIn("description_preview", row)


# ── 6. fictional example consistency ─────────────────────────────────────────

class TestFictionalExampleConsistency(unittest.TestCase):
    # Workout structures the example's interval summaries stand for. Rest steps are
    # untargeted because the example states no rest target.
    PRODUCIBLE = {
        "VO2max Intervals": doc(P(600, 155), P(600, 185), R(5, P(240, 310), P(180)), P(900, 140)),
        "Sweet Spot": doc(P(600, 155), R(3, P(720, 245), P(300)), P(900, 140)),
        "Endurance + Openers": doc(P(5400, 160), R(3, P(60, 280), P(120)), P(600, 140)),
    }
    # Pre-existing flat-only strings the producer does not emit (it returns null for
    # all-flat workouts). Out of scope for #28; pinned so new drift is caught.
    PRE_EXISTING_FLAT_ONLY = {
        "Endurance - Tuesday": "2h @160W",
        "Recovery Spin": "1h @140W",
        "Long Endurance": "3h @165W",
    }

    def setUp(self):
        self.sync = make_sync()
        data = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
        self.rows = {r["name"]: r["workout_summary"] for r in data["planned_workouts"]}

    def test_no_example_summary_assigns_a_role(self):
        for name, summary in self.rows.items():
            with self.subTest(name):
                self.assertIsNone(ROLE_LABEL.search(summary or ""),
                                  f"example summary uses a role label: {summary!r}")

    def test_interval_summaries_are_producer_output(self):
        for name, workout_doc in self.PRODUCIBLE.items():
            with self.subTest(name):
                self.assertEqual(self.rows[name], summarize(self.sync, workout_doc),
                                 "example workout_summary is not what sync.py produces")

    def test_every_example_row_is_accounted_for(self):
        self.assertEqual(set(self.rows), set(self.PRODUCIBLE) | set(self.PRE_EXISTING_FLAT_ONLY))
        for name, summary in self.PRE_EXISTING_FLAT_ONLY.items():
            self.assertEqual(self.rows[name], summary)


if __name__ == "__main__":
    unittest.main()
