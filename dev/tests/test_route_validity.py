"""Planned-route states, identity, cache and calendar regression tests.

All routes are synthetic. Every HTTP boundary is mocked under the shared guard.
"""

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from _harness import (SYNC_PATH, NetworkBlocked, install_verb_guard,
                      load_module_by_path, restore_verb_guard)

sync_mod = load_module_by_path("s11_sync_routes", SYNC_PATH)
IntervalsSync = sync_mod.IntervalsSync
_originals = None


def setUpModule():
    global _originals
    _originals = install_verb_guard(sync_mod.requests)


def tearDownModule():
    restore_verb_guard(sync_mod.requests, _originals)


def points(profile="mountain"):
    # About 11 km, with a sustained climb and descent for the preservation replay.
    return [{"lat": 55 + i * .001, "lon": 12,
             "ele": (0 if profile == "flat" else
                     i % 8 if profile == "rolling" else
                     min(i, 100 - i) * 8)} for i in range(101)]


def route_bytes(fmt="gpx", declaration=False, track=None):
    track = points() if track is None else track
    if fmt == "gpx":
        rows = [f'<trkpt lat="{p["lat"]}" lon="{p["lon"]}">'
                + (f'<ele>{p["ele"]}</ele>' if "ele" in p else "") + '</trkpt>'
                for p in track]
        xml = '<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>' + ''.join(rows) + '</trkseg></trk></gpx>'
    else:
        rows = ['<Trackpoint><Position>'
                + f'<LatitudeDegrees>{p["lat"]}</LatitudeDegrees>'
                + f'<LongitudeDegrees>{p["lon"]}</LongitudeDegrees></Position>'
                + (f'<AltitudeMeters>{p["ele"]}</AltitudeMeters>' if "ele" in p else "")
                + '</Trackpoint>' for p in track]
        xml = '<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"><Courses><Course><Track>' + ''.join(rows) + '</Track></Course></Courses></TrainingCenterDatabase>'
    return (("<?xml version='1.0' encoding='UTF-8'?>\n" if declaration else "") + xml).encode()


def attachment(aid=12, fmt="gpx", **changes):
    return {"id": aid, "filename": f"route.{fmt}",
            "url": f"https://example.invalid/{aid}.{fmt}", **changes}


def event(eid=7, **changes):
    return {"id": eid, "name": "Synthetic route", "category": "RACE_C",
            "type": "Ride", "start_date_local": "2026-10-18T00:00:00",
            "attachments": [attachment()], **changes}


def response(content=None, status=200):
    return mock.Mock(status_code=status, content=route_bytes() if content is None else content)


class FrozenClock(datetime):
    current = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)


class RouteValidity(unittest.TestCase):
    def setUp(self):
        FrozenClock.current = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
        clock = mock.patch.object(sync_mod, "datetime", FrozenClock)
        clock.start()
        self.addCleanup(clock.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s = IntervalsSync.__new__(IntervalsSync)
        self.s.data_dir = Path(self.tmp.name)
        self.s._cached_script_hash = "synthetic_script"
        self.s.debug = False

    def run_routes(self, events=None, replies=None, units=None):
        with mock.patch.object(sync_mod.requests, "get", side_effect=replies or [response()]) as get:
            flags = self.s._generate_terrain(events or [event()], units)
        return flags, self.s._routes_data["events"], get

    def persist(self):
        (self.s.data_dir / self.s.ROUTES_FILE).write_text(json.dumps(self.s._routes_data))

    def advance(self, seconds):
        FrozenClock.current += timedelta(seconds=seconds)

    def test_network_guard_is_effective(self):
        with self.assertRaises(NetworkBlocked):
            self.s._download_and_parse_route("https://example.invalid/unmocked", "x.gpx")

    def test_gpx_and_tcx_with_and_without_declaration(self):
        for fmt in ("gpx", "tcx"):
            for declaration in (False, True):
                with self.subTest(fmt=fmt, declaration=declaration):
                    result = self.s._parse_route_file(route_bytes(fmt, declaration), f"x.{fmt}")
                    self.assertEqual(result["route_status"], "ok")
                    self.assertTrue(result["terrain_summary"]["climbs"])
                    self.assertTrue(result["terrain_summary"]["descents"])

    def test_root_dispatch_ignores_misleading_extension(self):
        result = self.s._parse_route_file(route_bytes("tcx", True), "wrong.gpx")
        self.assertEqual(result["route_status"], "ok")

    def test_fit_extension_and_binary_magic_are_unsupported(self):
        for data, filename in ((route_bytes(), "route.FIT"), (b"\x0e" + b"\x00" * 7 + b".FIT" + b"\x00" * 60, "wrong.gpx")):
            with self.subTest(filename=filename):
                self.assertEqual(self.s._parse_route_file(data, filename)["route_status"], "unsupported_format")
        _, rows, get = self.run_routes([event(attachments=[attachment(fmt="fit")])])
        get.assert_not_called()
        self.assertEqual(rows[0]["route_status"], "unsupported_format")
        self.assertIsNone(rows[0]["route_ref"]["revision"])
        self.persist()
        self.advance(86400)
        with mock.patch.object(self.s, "_download_and_parse_route", side_effect=AssertionError("FIT was reconsidered")):
            self.s._generate_terrain([event(attachments=[attachment(fmt="fit")])])
        self.assertEqual(self.s._routes_data["events"][0]["last_attempt_at"], rows[0]["last_attempt_at"])

    def test_malformed_xml_and_unknown_root(self):
        for data, status in ((b"<gpx", "failed"), (b"<other/>", "unsupported_format"), (b"", "failed"),
                             (b'<?xml version="1.0" encoding="nonexistent"?><gpx/>', "failed")):
            self.assertEqual(self.s._parse_route_file(data, "x.gpx")["route_status"], status)

    def test_legacy_error_dictionary_never_sets_has_terrain(self):
        with mock.patch.object(self.s, "_download_and_parse_route", return_value={"error": "bad route"}):
            flags = self.s._generate_terrain([event()])
        self.assertEqual(flags, set())
        row = self.s._routes_data["events"][0]
        self.assertEqual(row["route_status"], "failed")
        self.assertNotIn("terrain_summary", row)
        self.assertFalse(self.s._format_events([event()], "2026-10-17")[0]["has_terrain"])

    def test_parser_error_dictionary_never_becomes_terrain(self):
        with mock.patch.object(self.s, "_parse_route_file", return_value={"error": "bad route"}):
            flags, rows, _ = self.run_routes()
        self.assertFalse(flags)
        self.assertNotIn("terrain_summary", rows[0])
        self.assertNotIn("analyzed_at", rows[0])

    def test_nested_error_dictionary_is_rejected(self):
        result = self.s._validated_route_result({"route_status": "ok", "terrain_summary": {"error": "bad"}})
        self.assertEqual(result["route_status"], "failed")
        self.assertNotIn("terrain_summary", result)

    def test_http_failure_then_recovery_retries_same_attachment(self):
        flags, rows, _ = self.run_routes(replies=[response(status=503)])
        self.assertFalse(flags)
        self.assertEqual(rows[0]["route_status"], "failed")
        self.assertIn("HTTP 503", rows[0]["route_error"])
        first_attempt = rows[0]["last_attempt_at"]
        self.assertEqual(first_attempt, FrozenClock.current.isoformat())
        self.persist()
        self.advance(899)
        rotated_url = "https://example.invalid/12.gpx?signature=rotated"
        rotated_event = event(attachments=[attachment(url=rotated_url)])
        # No request mock: the shared network guard must reject any accidental HTTP.
        self.assertEqual(self.s._generate_terrain([rotated_event]), set())
        self.assertEqual(self.s._routes_data["events"][0]["last_attempt_at"], first_attempt)
        self.persist()
        self.advance(1)
        flags, rows, get = self.run_routes([rotated_event])
        get.assert_called_once_with(rotated_url, timeout=30, allow_redirects=False, auth=mock.ANY)
        self.assertEqual(flags, {7})
        self.assertFalse(rows[0]["cache_hit"])
        self.assertNotEqual(rows[0]["last_attempt_at"], first_attempt)

    def test_repeated_failure_restarts_fifteen_minute_backoff(self):
        self.assertEqual(self.s.ROUTE_RETRY_BACKOFF_SECONDS, 900)
        self.run_routes(replies=[response(status=503)])
        self.persist()
        self.advance(900)
        _, failed, get = self.run_routes(replies=[response(status=503)])
        get.assert_called_once()
        self.persist()
        self.advance(899)
        self.s._generate_terrain([event()])  # network guard remains active
        self.assertEqual(self.s._routes_data["events"][0]["last_attempt_at"], failed[0]["last_attempt_at"])
        self.persist()
        self.advance(2)
        self.assertEqual(self.run_routes()[0], {7})

    def test_clock_regression_does_not_bypass_failure_backoff(self):
        self.run_routes(replies=[response(status=503)])
        self.persist()
        self.advance(-60)
        self.assertEqual(self.s._generate_terrain([event()]), set())

    def test_malformed_failure_timestamp_retries_and_records_new_attempt(self):
        self.run_routes(replies=[response(status=503)])
        self.s._routes_data["events"][0]["last_attempt_at"] = "invalid"
        self.persist()
        flags, rows, get = self.run_routes()
        get.assert_called_once()
        self.assertEqual(flags, {7})
        self.assertEqual(rows[0]["last_attempt_at"], FrozenClock.current.isoformat())

    def test_timeout_then_recovery(self):
        flags, rows, _ = self.run_routes(replies=[sync_mod.requests.exceptions.Timeout("synthetic")])
        self.assertFalse(flags)
        self.assertEqual(rows[0]["route_status"], "failed")
        self.persist()
        self.advance(900)
        self.assertEqual(self.run_routes()[0], {7})

    def test_cached_success_cannot_be_overwritten_by_download_failure(self):
        _, first, _ = self.run_routes()
        self.persist()
        self.advance(86400)
        flags, rows, get = self.run_routes(replies=[sync_mod.requests.exceptions.Timeout("must not run")])
        get.assert_not_called()
        self.assertEqual(flags, {7})
        self.assertEqual(rows[0]["terrain_summary"], first[0]["terrain_summary"])
        self.assertEqual(rows[0]["route_ref"], first[0]["route_ref"])

    def test_cache_hit_makes_no_request_and_keeps_analysis_time(self):
        _, first, _ = self.run_routes()
        self.persist()
        self.advance(60)
        with mock.patch.object(self.s, "_parse_route_file", side_effect=AssertionError("cached content was reparsed")):
            self.assertEqual(self.s._generate_terrain([event(name="Renamed", start_date_local="2026-10-19")]), {7})
        second = self.s._routes_data["events"]
        self.assertTrue(second[0]["cache_hit"])
        self.assertEqual(first[0]["analyzed_at"], second[0]["analyzed_at"])
        self.assertEqual(first[0]["checked_at"], second[0]["checked_at"])
        self.assertEqual(first[0]["last_attempt_at"], second[0]["last_attempt_at"])
        self.assertEqual(first[0]["route_ref"], second[0]["route_ref"])
        self.assertNotEqual(second[0]["analyzed_at"], self.s._routes_data["generated_at"])
        self.assertEqual(first[0]["terrain_summary"], second[0]["terrain_summary"])
        self.assertEqual(second[0]["event_name"], "Renamed")
        self.assertNotIn("start_time", second[0])
        self.assertEqual(second[0]["start_time_status"], "missing")

    def test_changed_attachment_id_downloads_and_records_reversed_revision(self):
        _, first, _ = self.run_routes()
        self.persist()
        reversed_content = route_bytes(track=list(reversed(points())))
        _, second, get = self.run_routes([event(attachments=[attachment(13)])], replies=[response(reversed_content)])
        get.assert_called_once()
        self.assertNotEqual(first[0]["route_ref"]["route_id"], second[0]["route_ref"]["route_id"])
        self.assertNotEqual(first[0]["route_ref"]["revision"], second[0]["route_ref"]["revision"])
        self.assertEqual(second[0]["route_ref"]["revision"], hashlib.sha256(reversed_content).hexdigest())
        self.assertFalse(second[0]["cache_hit"])
        self.assertNotEqual(first[0]["terrain_summary"]["start_coords"], second[0]["terrain_summary"]["start_coords"])

    def test_changed_filename_downloads_despite_same_attachment_id(self):
        _, first, _ = self.run_routes()
        self.persist()
        content = route_bytes(track=list(reversed(points())))
        _, rows, get = self.run_routes([event(attachments=[attachment(filename="replacement.gpx")])], [response(content)])
        get.assert_called_once()
        self.assertFalse(rows[0]["cache_hit"])
        self.assertNotEqual(rows[0]["attachment_source_hash"], first[0]["attachment_source_hash"])
        self.assertEqual(rows[0]["route_ref"]["revision"], hashlib.sha256(content).hexdigest())
        self.assertNotIn("https://", json.dumps(rows[0]))

    def test_rotated_url_reuses_terrain_or_geometry_without_http(self):
        gps_only = [{"lat": p["lat"], "lon": p["lon"]} for p in points()]
        for content in (route_bytes(), route_bytes(track=gps_only)):
            with self.subTest(gps_only=content == route_bytes(track=gps_only)):
                _, first, _ = self.run_routes(replies=[response(content)])
                self.persist()
                self.advance(60)
                # The active network guard proves a rotated URL cannot trigger HTTP.
                self.s._generate_terrain([event(attachments=[attachment(
                    url="https://example.invalid/12.gpx?signature=rotated")])])
                current = self.s._routes_data["events"][0]
                self.assertTrue(current["cache_hit"])
                for key in ("route_status", "route_ref", "attachment_source_hash",
                            "analyzed_at", "checked_at", "last_attempt_at"):
                    self.assertEqual(current[key], first[0][key])
                for key in ("terrain_summary", "route_geometry"):
                    self.assertEqual(current.get(key), first[0].get(key))
                self.assertNotIn("https://", json.dumps(current))
                # Start the second fixture with no earlier successful cache.
                (self.s.data_dir / self.s.ROUTES_FILE).unlink()

    def test_changed_attachment_bypasses_previous_failure_backoff(self):
        self.run_routes(replies=[response(status=503)])
        self.persist()
        self.advance(60)
        for att in (attachment(13), attachment(filename="replacement.gpx")):
            with self.subTest(attachment=att):
                self.assertEqual(self.run_routes([event(attachments=[att])])[0], {7})

    def test_changed_event_id_does_not_reuse_another_events_attachment(self):
        self.run_routes()
        self.persist()
        flags, _, get = self.run_routes([event(8)])
        get.assert_called_once()
        self.assertEqual(flags, {8})

    def test_unsupported_xml_is_not_requested_again_while_unchanged(self):
        _, first, _ = self.run_routes(replies=[response(b"<other/>")])
        self.persist()
        self.advance(86400)
        self.s._generate_terrain([event()])
        current = self.s._routes_data["events"][0]
        self.assertEqual(current["route_status"], "unsupported_format")
        self.assertEqual(current["last_attempt_at"], first[0]["last_attempt_at"])
        self.assertEqual(current["route_ref"], first[0]["route_ref"])

    def test_missing_identity_is_not_reconsidered_while_unchanged(self):
        for evt in (event(None), event(attachments=[attachment(None)])):
            with self.subTest(event=evt):
                self.s._generate_terrain([evt])
                first = self.s._routes_data["events"][0]
                self.persist()
                self.advance(86400)
                self.s._generate_terrain([evt])
                current = self.s._routes_data["events"][0]
                self.assertEqual(current["route_error"], "missing_identity")
                self.assertEqual(current["last_attempt_at"], first["last_attempt_at"])

    def test_old_error_cache_is_reparsed(self):
        self.s._routes_data = {"script_hash": self.s.script_hash, "events": [
            {"event_id": 7, "attachment_id": 12, "terrain_summary": {"error": "old failure"}}]}
        self.persist()
        self.assertEqual(self.run_routes()[0], {7})

    def test_malformed_cached_reference_is_reparsed(self):
        self.run_routes()
        self.s._routes_data["events"][0]["route_ref"] = "invalid reference"
        self.persist()
        _, rows, _ = self.run_routes()
        self.assertEqual(rows[0]["route_status"], "ok")
        self.assertFalse(rows[0]["cache_hit"])

    def test_invalid_success_cache_is_reparsed(self):
        self.run_routes()
        self.s._routes_data["events"][0]["terrain_summary"] = {"error": "bad cache"}
        self.persist()
        _, rows, _ = self.run_routes()
        self.assertEqual(rows[0]["route_status"], "ok")
        self.assertFalse(rows[0]["cache_hit"])

    def test_script_and_producer_changes_invalidate_analysis(self):
        for kind in ("script", "producer"):
            with self.subTest(kind=kind):
                self.run_routes()
                if kind == "script":
                    self.s._routes_data["script_hash"] = "old"
                else:
                    self.s._routes_data["events"][0]["route_ref"]["terrain_version"] = "old"
                self.persist()
                _, rows, _ = self.run_routes()
                self.assertFalse(rows[0]["cache_hit"])

    def test_gps_only_keeps_geometry_without_terrain_claims(self):
        track = [{"lat": p["lat"], "lon": p["lon"]} for p in points()]
        for fmt in ("gpx", "tcx"):
            with self.subTest(fmt=fmt):
                flags, rows, _ = self.run_routes(replies=[response(route_bytes(fmt, True, track))])
                row = rows[0]
                self.assertFalse(flags)
                self.assertEqual(row["route_status"], "no_elevation")
                self.assertNotIn("terrain_summary", row)
                geometry = row["route_geometry"]
                self.assertEqual(geometry["polyline"][0], [0.0, 55, 12])
                self.assertEqual(geometry["polyline"][-1], [11.1, 55.1, 12])
                for point in geometry["polyline"]:
                    self.assertEqual(len(point), 3)
                for key in ("total_elevation_m", "elevation_per_km", "course_character", "climbs", "descents"):
                    self.assertNotIn(key, geometry)

    def test_partial_invalid_and_nonfinite_elevation_are_unknown(self):
        for altitude in (None, "invalid", "nan", "inf"):
            for fmt in ("gpx", "tcx"):
                with self.subTest(altitude=altitude, fmt=fmt):
                    track = points()
                    track[50]["ele"] = altitude
                    result = self.s._parse_route_file(route_bytes(fmt, track=track), "x.gpx")
                    self.assertEqual(result["route_status"], "no_elevation")
                    self.assertNotIn("terrain_summary", result)

    def test_invalid_gps_is_not_valid_terrain(self):
        for coords in (("nan", 12), (91, 12), (55, 181), ("invalid", 12)):
            data = route_bytes(track=[{"lat": coords[0], "lon": coords[1], "ele": 10}] * 2)
            self.assertEqual(self.s._parse_route_file(data, "x.gpx")["route_status"], "no_gps")

    def test_short_route_analysis_failure_is_not_terrain(self):
        result = self.s._parse_route_file(route_bytes(track=points()[:1] * 2), "x.gpx")
        self.assertEqual(result["route_status"], "failed")

    def test_real_zero_ascent_is_valid_flat_terrain(self):
        result = self.s._parse_route_file(route_bytes(track=points("flat")), "x.gpx")
        self.assertEqual(result["route_status"], "ok")
        self.assertEqual(result["terrain_summary"]["total_elevation_m"], 0)
        self.assertEqual(result["terrain_summary"]["course_character"], "flat")

    def test_geometry_cache_refreshes_display_without_altitude(self):
        data = route_bytes(track=[{"lat": p["lat"], "lon": p["lon"]} for p in points()])
        self.run_routes(replies=[response(data)])
        self.persist()
        self.advance(60)
        self.s._generate_terrain([event()], {"distance": "imperial"})
        rows = self.s._routes_data["events"]
        self.assertTrue(rows[0]["cache_hit"])
        self.assertEqual(rows[0]["route_geometry"]["display"]["total_distance"]["unit"], "mi")
        self.assertEqual(set(rows[0]["route_geometry"]["display"]), {"total_distance"})

    def test_valid_cache_refreshes_display_but_preserves_canonical_values(self):
        _, first, _ = self.run_routes()
        self.persist()
        _, second, _ = self.run_routes(units={"distance": "imperial", "elevation": "feet"})
        self.assertTrue(second[0]["cache_hit"])
        self.assertEqual(second[0]["terrain_summary"]["display"]["total_distance"]["unit"], "mi")
        def canonical(value):
            if isinstance(value, dict):
                return {k: canonical(v) for k, v in value.items() if k != "display"}
            return [canonical(v) for v in value] if isinstance(value, list) else value
        self.assertEqual(canonical(first[0]["terrain_summary"]), canonical(second[0]["terrain_summary"]))

    def test_selection_is_order_independent_and_one_route_per_event(self):
        attachments = [attachment(1, "fit"), attachment(1, "tcx"), attachment(20), attachment(10)]
        for sequence in (attachments, list(reversed(attachments))):
            _, rows, get = self.run_routes([event(attachments=sequence)])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["attachment_id"], 10)
        get.assert_called_once_with("https://example.invalid/10.gpx", timeout=30, allow_redirects=False, auth=mock.ANY)

    def test_selected_failure_does_not_switch_routes(self):
        flags, rows, get = self.run_routes([event(attachments=[attachment(2), attachment(1)])], [response(status=503)])
        self.assertFalse(flags)
        self.assertEqual(rows[0]["attachment_id"], 1)
        self.assertEqual(get.call_count, 1)

    def test_absent_and_nonroute_attachments(self):
        for attachments in ([], [attachment(filename="notes.txt")]):
            self.s._generate_terrain([event(attachments=attachments)])
            self.assertEqual(self.s._routes_data["events"], [])
            self.assertEqual(self.s._planned_route_fields(event()), {"route_status": "absent", "has_terrain": False})

    def test_missing_url_or_identity_is_explicit_failure(self):
        for evt in (event(attachments=[attachment(url="")]), event(None), event(attachments=[attachment(None)])):
            self.s._generate_terrain([evt])
            row = self.s._routes_data["events"][0]
            self.assertEqual(row["route_status"], "failed")
            self.assertNotIn("terrain_summary", row)

    def test_event_ids_references_and_midnight_match_across_outputs(self):
        events = [event(), event("8", start_date_local="2026-10-19", attachments=[])]
        self.run_routes(events)
        planned = self.s._format_events(events, "2026-10-17")
        calendar = self.s._build_race_calendar(events, 50, 50, 0, [], "2026-10-17")
        for p, r in zip(planned, calendar["all_races"]):
            for key in ("id", "route_status", "has_terrain", "start_time_status"):
                self.assertEqual(p[key], r[key])
        self.assertEqual(planned[0]["id"], 7)
        self.assertEqual(planned[1]["id"], "8")
        route = self.s._routes_data["events"][0]
        self.assertEqual(planned[0]["route_ref"], route["route_ref"])
        self.assertEqual(calendar["next_race"]["route_ref"], route["route_ref"])
        for row in (planned[0], calendar["next_race"], route):
            self.assertNotIn("start_time", row)
            self.assertEqual(row["start_time_status"], "midnight_treated_as_unset")
        self.assertNotIn("start_time", planned[1])
        self.assertEqual(planned[1]["start_time_status"], "missing")

    def test_explicit_time_vs_missing_or_invalid_time(self):
        for raw in (None, "2026-10-18", "2026-10-18T99:00:00", "2026-10-18T"):
            self.assertEqual(self.s._event_start_fields(event(start_date_local=raw)), {"start_time_status": "missing"})
        self.assertEqual(self.s._event_start_fields(event(start_date_local="2026-10-18T14:30:00"))["start_time"], "14:30")

    def test_missing_ids_are_not_invented_from_list_order(self):
        evt = event(attachments=[])
        evt.pop("id")
        planned = self.s._format_events([evt], "2026-10-17")
        races = self.s._build_race_calendar([evt], 50, 50, 0, [], "2026-10-17")
        self.assertIsNone(planned[0]["id"])
        self.assertIsNone(races["next_race"]["id"])

    def test_attachment_removal_discards_previous_route(self):
        self.run_routes()
        self.persist()
        self.s._generate_terrain([event(attachments=[])])
        self.assertEqual(self.s._routes_data["events"], [])
        self.assertEqual(self.s._planned_route_fields(event())["route_status"], "absent")
