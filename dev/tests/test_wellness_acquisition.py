"""Paired four-read/one-read producer fixtures and independent slice assertions."""
import inspect
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from _harness import load_module_by_path
import test_request_budget_runs as producers


class WellnessParity(unittest.TestCase):
    run_producer = producers.FullRuns.run_producer
    seed = producers.FullRuns.seed
    normalize_state_notes = producers.FullRuns.normalize_state_notes

    def paired(self, day, days=7, variant="complete", profile=None, calendar=None):
        path = os.environ.get("S11_PARITY_BASELINE")
        if not path:
            self.skipTest("external frozen producer oracle requires S11_PARITY_BASELINE")
        baseline = load_module_by_path("wellness_oracle_" + variant, Path(path))
        self.days_back = days
        self.profile_fields = profile or {}
        self.calendar_rows = calendar or []
        stamp = datetime.fromisoformat(day).replace(hour=12, tzinfo=timezone.utc)
        self.rollover_after_wellness = variant == "date_rollover"
        self.rollover_start = stamp
        rows = [{"id": (stamp - timedelta(days=age)).date().isoformat(),
                 "ctl": 40 + age / 7, "atl": 50 + age / 3, "rampRate": 1.234567,
                 "sleepSecs": 25000 + age * 60, "weight": 70 + age / 100,
                 "hrv": 60, "restingHR": 48, "sleepQuality": 1,
                 "sportInfo": [{"type": "Ride", "eftp": 240, "wPrime": 18000, "pMax": 900}],
                 "updated": "same-token", "custom_field": {"zero": 0, "false": False}}
                for age in reversed(range(45))]
        day_payload = dict(rows[-1])
        if variant == "missing_dates":
            rows = [r for i, r in enumerate(rows) if i % 4]
            day_payload = next((dict(r) for r in rows if r["id"] == day), {})
        elif variant == "empty":
            rows, day_payload = [], None
        elif variant in ("today_missing_generated", "today_missing_404"):
            rows = rows[:-1]
            day_payload = ({"id": day, "ctl": 48.25, "atl": 51.75, "rampRate": 0,
                            "sportInfo": [{"type": "Ride", "eftp": 251.5}]}
                           if variant.endswith("generated") else None)
        elif variant == "yesterday_missing":
            rows = [r for r in rows if r["id"] != (stamp - timedelta(days=1)).date().isoformat()]
        elif variant == "computed_only":
            rows[-1] = {k: rows[-1][k] for k in ("id", "ctl", "atl", "rampRate", "sportInfo", "updated")}
            day_payload = dict(rows[-1])
        elif variant == "null_zero_missing":
            for i, row in enumerate(rows):
                row.update(sportInfo=None if i % 2 else [], sleepSecs=None if i % 3 else 0,
                           hrvSDNN=44.1234567, weight=0 if i % 2 else None, injury=0,
                           fatigue=None, mood=0, stress=None, comments="", hydration=False)
                row.pop("hrv")
            day_payload = dict(rows[-1])
        elif variant == "edited_unchanged_token":
            rows[-1].update(sleepSecs=31000, hrv=72.5, weight=69.25, sportInfo=[], ctl=51.25, atl=57.75, rampRate=2.25)
            day_payload = dict(rows[-1])
        elif variant == "duplicates_reversed":
            rows.insert(-1, dict(rows[-1], sleepSecs=28801, ctl=54.5))
            rows = list(reversed(rows))
            day_payload = next(dict(r) for r in rows if r["id"] == day)
        elif variant == "malformed_ids_and_extra_rows":
            rows += [{"id": None, "sleepSecs": "invalid"}, {"id": "not-a-date", "sleepSecs": {}},
                     {"id": (stamp + timedelta(days=1)).date().isoformat(), "sleepSecs": 99999}]
        elif variant == "malformed_values":
            rows[10]["sleepSecs"] = "not-numeric"
            rows[11]["sportInfo"] = []
        elif variant in ("planned_load", "health_notes", "new_completion"):
            self.calendar_rows = [{"id": 81, "start_date_local": day + "T08:00:00",
                "end_date_local": day + "T09:00:00", "category": "WORKOUT" if variant != "health_notes" else "NOTE",
                "type": "VirtualRide", "name": "Synthetic", "icu_training_load": 80,
                "moving_time": 3600, "description": "Synthetic plan"}]
            if variant == "new_completion":
                self.calendar_rows[0]["paired_activity_id"] = "i0"

        def range_payload(oldest, newest):
            selected = [dict(r) for r in rows if isinstance(r.get("id"), str) and oldest <= r["id"] <= newest]
            if variant == "malformed_values" and oldest < (stamp - timedelta(days=34)).date().isoformat():
                # The independent historical endpoint remains valid. The bad
                # current value is in the sleep-only part of the 35-date read.
                selected = [dict(r, sleepSecs=28800) if r.get("sleepSecs") == "not-numeric" else r for r in selected]
            if variant == "malformed_ids_and_extra_rows" and oldest == (stamp - timedelta(days=34)).date().isoformat():
                selected += [dict(r) for r in rows if not isinstance(r.get("id"), str) or r["id"] == "not-a-date"
                             or r["id"] > day]
            return selected
        self.wellness_range = range_payload
        self.wellness_day = lambda date: day_payload
        captured = {}
        cls = producers.module.IntervalsSync
        def capture(name, argument):
            original = getattr(cls, name)
            def wrapped(*args, **kwargs):
                bound = inspect.signature(original).bind(*args, **kwargs)
                captured[name] = json.loads(json.dumps(bound.arguments[argument]))
                return original(*args, **kwargs)
            return mock.patch.object(cls, name, wrapped)

        with tempfile.TemporaryDirectory() as temp, mock.patch.object(producers.FrozenDate, "fixed", stamp, create=True), \
                mock.patch.dict(os.environ, {"S11_TEST_BUDGET_START": stamp.isoformat()}):
            root = Path(temp)
            self.seed(baseline, root / "seed")
            before, after = root / "before", root / "after"
            shutil.copytree(root / "seed", before)
            shutil.copytree(root / "seed", after)
            old_calls, old_bytes = self.run_producer(baseline, before)
            with capture("_format_wellness", "wellness"), capture("_build_sleep_context", "wellness"), \
                    capture("_extract_power_model_from_wellness", "wellness_data"), \
                    capture("_build_weight_signal", "wellness_extended"):
                new_calls, new_bytes = self.run_producer(producers.module, after)
            self.assertEqual(len(old_bytes), 7)
            self.assertEqual(set(new_bytes), set(old_bytes))
            for name, content in old_bytes.items():
                if name != "latest.json":
                    self.assertEqual(new_bytes[name], content, (variant, name))
                else:
                    old, new = json.loads(content), json.loads(new_bytes[name])
                    fresh = new.pop("source_freshness")
                    self.assertEqual(fresh["sources"]["wellness"]["status"], "fresh")
                    self.normalize_state_notes(old, new)
                    new["sleep_context"]["source_updated_at"] = old["sleep_context"]["source_updated_at"]
                    self.assertEqual(json.dumps(new, indent=2, default=str).encode(), content, variant)
            old_wellness = [(p, q) for p, q in old_calls if "/wellness" in p]
            new_wellness = [(p, q) for p, q in new_calls if "/wellness" in p]
            self.assertEqual(len(old_wellness), 4)
            has_today = any(r.get("id") == day for r in rows)
            self.assertEqual(len(new_wellness), 4 if variant == "malformed_ids_and_extra_rows" else
                             2 if variant == "date_rollover" else 1 if has_today else 2)
            self.assertEqual(new_wellness[0][1]["oldest"], [(stamp - timedelta(days=max(days - 1, 34))).date().isoformat()])
            for method, depth in (("_format_wellness", days), ("_build_sleep_context", 35), ("_build_weight_signal", 28)):
                oldest = (stamp - timedelta(days=depth - 1)).date().isoformat()
                expected = [r for r in rows if isinstance(r.get("id"), str) and oldest <= r["id"] <= day]
                if method == "_build_sleep_context":
                    expected = range_payload(oldest, day)
                self.assertEqual(captured[method], expected, (variant, method))
            self.assertEqual(captured["_extract_power_model_from_wellness"], day_payload or {})
            latest = json.loads(new_bytes["latest.json"])
            if variant == "edited_unchanged_token":
                self.assertEqual(latest["current_status"]["fitness"]["ctl"], 51.25)
            print("Wellness parity:", variant, day, "days", days, "four ->", len(new_wellness),
                  "reads; seven files, two explicit diagnostic allowances")

    def test_all_wellness_slices_and_mutation_fixtures(self):
        for variant in ("complete", "missing_dates", "empty", "today_missing_generated", "today_missing_404",
                        "yesterday_missing", "computed_only", "null_zero_missing", "edited_unchanged_token",
                        "duplicates_reversed", "malformed_ids_and_extra_rows", "malformed_values",
                        "planned_load", "health_notes", "new_completion", "date_rollover"):
            with self.subTest(variant=variant):
                self.paired("2026-10-28", variant=variant)

    def test_display_bounds_date_edges_and_units(self):
        for day, days, profile in (("2026-10-28", 2, {}), ("2026-10-28", 45, {}),
                ("2028-03-01", 7, {}), ("2027-01-01", 7, {}),
                ("2026-10-25", 7, {"timezone": "Europe/Copenhagen"}),
                ("2026-10-28", 7, {"timezone": None}),
                ("2026-10-28", 7, {"timezone": "Pacific/Honolulu", "weight_pref_lb": True, "fahrenheit": True})):
            with self.subTest(day=day, days=days, profile=profile):
                self.paired(day, days, profile=profile)


if __name__ == "__main__":
    unittest.main()
