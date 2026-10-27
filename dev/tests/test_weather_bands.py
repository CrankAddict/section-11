"""Offline single-source forecast bands and compact-report contract checks."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_route_weather_map import fixture, mod, Map, NOW
from test_weather_map_design import many_bands
from _harness import install_verb_guard, restore_verb_guard

Weather = mod.RouteWeather


def setUpModule():
    global originals
    originals = install_verb_guard(mod.requests)


def tearDownModule():
    restore_verb_guard(mod.requests, originals)


class WeatherBandTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sync = mod.IntervalsSync.__new__(mod.IntervalsSync)
        self.sync.data_dir = Path(tmp.name)
        self.sync.athlete_id = 'synthetic-bands'
        self.sync.debug = False
        self.sync.route_weather_enabled = True
        self.row, self.evt = fixture(self.sync, athlete={'timezone':'Europe/Copenhagen'})
        self.brief = self.row['route_weather']

    def test_producer_computes_once_before_binding_and_map_returns_exact_array(self):
        with mock.patch.object(Weather, 'forecast_bands', wraps=Weather.forecast_bands) as build:
            row, _ = fixture(self.sync)
        build.assert_called_once()
        brief = row['route_weather']
        self.assertIs(Map.bands(brief), brief['bands'])
        bound = copy.deepcopy(brief)
        identity = bound.pop('brief_id')
        self.assertEqual(identity, Weather.digest(bound))
        self.assertEqual(len(brief['bands']), len(brief['sampling']['points']))

    def test_map_rows_render_supplied_band_values_without_aggregation(self):
        band = self.brief['bands'][0]
        band['display'].update(wind='6.0–6.4 m/s from E · gusts 8',
                               temperature='8.6–9.0 °C', rain='0.3 mm/h · 40%')
        # Geometry and whole-ride cards still use sections. Row aggregation must not.
        original_range = Map.display_range
        def whole_ride_only(sections, key):
            self.assertIs(sections, self.brief['sections'])
            return original_range(sections, key)
        with mock.patch.object(Weather, 'forecast_bands', side_effect=AssertionError('recomputed')), \
             mock.patch.object(Map, 'display_range', side_effect=whole_ride_only):
            scene = Map.scene(self.row)
        labels = [op[3] for op in scene if op[0] == 'text']
        for key in ('distance', 'time', 'wind_class', 'wind', 'temperature', 'rain'):
            self.assertIn(band['display'][key], labels)
        del self.brief['bands']
        with self.assertRaisesRegex(ValueError, 'map_bands_missing_or_invalid'):
            Map.scene(self.row)

    def test_outlook_has_no_bands_and_never_calls_producer(self):
        with mock.patch.object(Weather, 'forecast_bands', side_effect=AssertionError('outlook bands')):
            row, _ = fixture(self.sync, outlook=True)
        self.assertNotIn('bands', row['route_weather'])
        self.assertEqual(Map.bands(row['route_weather']), [])
        self.assertEqual(len(Map.scenes(row)), 1)

    def test_band_extrema_windows_and_membership_match_existing_sections(self):
        for point, band in zip(self.brief['sampling']['points'], self.brief['bands']):
            group = [s for s in self.brief['sections'] if s['point_id'] == point['point_id']]
            self.assertEqual(band['section_count'], len(group))
            self.assertEqual([band['start_km'], band['end_km']], [group[0]['start_km'], group[-1]['end_km']])
            self.assertEqual(band['wind_class'], Map.dominant(group))
            self.assertEqual(band['wind_from'], Map.direction(group))
            for field, source in (('wind_speed','wind_speed_range_mps'),
                                  ('temperature','temperature_range_c'),
                                  ('feels_like','apparent_temperature_range_c')):
                values = [v for s in group for v in s['weather']['display'][source]['value']]
                self.assertEqual(band[field]['value'], [min(values), max(values)])
            self.assertEqual(band['gust_max']['value'], max(s['weather']['display']['gust_max_mps']['value'] for s in group))
            for field, source in (('arrival_window_local',group[0]['arrival_window_utc']),
                                  ('end_window_local',group[-1]['end_window_utc'])):
                self.assertEqual(band[field], [Map.local_time(t,self.brief['display_time']) for t in source])
                self.assertTrue(all('CEST+0200' in label for label in band[field]))
        self.assertEqual(sum(b['section_count'] for b in self.brief['bands']), len(self.brief['sections']))

    def test_rain_keeps_native_period_and_separate_probability_maximum(self):
        group = [s for s in self.brief['sections'] if s['point_id'] == 0]
        original = copy.deepcopy(group[0]['weather']['precipitation_intervals'][0])
        wet = dict(original, amount_mm=3, display_amount={'value':3,'unit':'mm'}, period_hours=6, probability_pct=20)
        likely = dict(original, amount_mm=.2, display_amount={'value':.2,'unit':'mm'}, period_hours=1, probability_pct=90)
        for s in group:
            s['weather']['precipitation_intervals'] = [wet, likely]
        band = Weather.forecast_bands(self.brief)[0]
        self.assertEqual(band['rain']['max_amount'], {'value':3,'unit':'mm'})
        self.assertEqual(band['rain']['period_hours'], 6)
        self.assertEqual(band['rain']['max_probability_pct'], 90)
        self.assertEqual(band['display']['rain'], '3.0 mm/6h · 90%')
        self.assertEqual(band['rain']['wettest_window_local'], [Map.local_time(wet[k],self.brief['display_time']) for k in ('from_utc','to_utc')])

    def test_missing_and_partial_rain_are_never_dry(self):
        group = [s for s in self.brief['sections'] if s['point_id'] == 0]
        for s in group:
            s['weather']['coverage']['precipitation'] = False
            for p in s['weather']['precipitation_intervals']:
                p.update(amount_mm=0, display_amount={'value':0,'unit':'mm'}, probability_pct=0)
        band = Weather.forecast_bands(self.brief)[0]
        self.assertFalse(band['coverage']['precipitation'])
        self.assertEqual(band['display']['rain'], 'Rain incomplete · 0%')
        for s in group:
            s['weather']['precipitation_intervals'] = []
            s['weather']['display']['apparent_temperature_range_c'] = None
        band = Weather.forecast_bands(self.brief)[0]
        self.assertIn('Rain unknown', band['display']['rain'])
        self.assertIsNone(band['rain']['max_amount'])
        self.assertEqual(band['rain']['wettest_window_local'], [])
        self.assertIsNone(band['feels_like'])
        self.assertEqual(band['display']['feels_like'], 'UNKNOWN')

    def test_size_bound_accepts_32_bands_and_rejects_oversized_array(self):
        from test_route_snapshots import hundred_km_row
        row, _ = fixture(self.sync, terrain=hundred_km_row(self.row)['terrain_summary'])
        row = many_bands(row, 32)
        packed = json.dumps(row['route_weather']['bands'],separators=(',',':')).encode()
        self.assertLessEqual(len(packed), Weather.MAX_BANDS_BYTES)
        self.assertEqual(len(Map.bands(row['route_weather'])), 32)
        with mock.patch.object(Weather, 'MAX_BANDS_BYTES', len(packed)-1):
            with self.assertRaisesRegex(ValueError, 'forecast_bands_too_large'):
                Weather.forecast_bands(row['route_weather'])
            with self.assertRaisesRegex(ValueError, 'forecast_bands_too_large'):
                Map.bands(row['route_weather'])
        row['route_weather']['bands'][0]['letter'] = 'Z'
        with self.assertRaisesRegex(ValueError, 'map_band_count_or_identity'):
            Map.bands(row['route_weather'])

    def test_no_bands_duplicated_in_latest_summary_or_overview(self):
        self.sync._routes_data = {'events':[self.row]}
        self.sync._overview_events = [self.evt]
        self.sync._overview_athlete = {'timezone':'Europe/Copenhagen'}
        overview = mod.DataOverview.build(self.sync, {}, now=NOW)
        self.assertNotIn('"bands"', json.dumps(overview))
        self.sync._planned_routes = {self.evt['id']:self.row}
        self.assertNotIn('"bands"', json.dumps(self.sync._planned_route_fields(self.evt)))

    def test_consistent_decimal_places_equal_endpoints_and_units(self):
        cases = [([6,6.4],'m/s','6.0–6.4 m/s'), ([8.6,9],'C','8.6–9.0 °C'),
                 ([6.0,6],'mph','6.0 mph'), ([-2,-1.5],'F','-2.0–-1.5 °F'),
                 ([4.01,4.04],'C','4.0 °C')]
        for values, unit, expected in cases:
            self.assertEqual(Map.display_label({'value':[round(v,1) for v in values],'unit':unit}), expected)


class CompactReportContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        reports = self.root / 'examples/reports'
        self.template = (reports/'WEATHER_REPORT_TEMPLATE.md').read_text()
        self.examples = (reports/'WEATHER_REPORT_EXAMPLES.md').read_text()

    def test_templates_and_examples_retain_compact_and_fallback_contracts(self):
        root = Path(__file__).resolve().parents[2] / 'examples/reports'
        for filename in ('WEATHER_REPORT_TEMPLATE.md','WEATHER_REPORT_EXAMPLES.md',
                         'PRE_WORKOUT_REPORT_TEMPLATE.md','PRE_WORKOUT_REPORT_EXAMPLES.md'):
            text = (root/filename).read_text()
            for required in ('bands','expiry','CC BY 4.0'):
                self.assertIn(required,text,filename)
            self.assertIn('assumed',text.lower(),filename)
            self.assertIn('raw',text,filename)
            self.assertNotIn('·',text,filename)
            self.assertNotIn('summarized by Section 11',text,filename)
            self.assertNotIn('Riding:',text,filename)
        template = (root/'WEATHER_REPORT_TEMPLATE.md').read_text()
        for required in ('Start:','Moving time:','Total time:','Wind:','Gusts:',
                         'Strongest gusts at:','[Dominant wind effect]:','Rain:',
                         'Temperature:','Feels like:','moving','elapsed','outlook',
                         'safety','confirmation'):
            self.assertIn(required,template)
        pre = (root/'PRE_WORKOUT_REPORT_TEMPLATE.md').read_text()
        body = pre.split('```', 2)[1]
        order = ('**[Go / Modify / Skip]**', 'Signals:', 'Verdict:',
                 '**Today:', '**Readiness**', '**Load**', '**Intensity',
                 '**Last 7 days**')
        positions = [body.index(label) for label in order]
        self.assertEqual(positions, sorted(positions))
        for field in ('Phase:', 'RHR:', 'HRV:', 'Sleep:', 'Sleep Quality:',
                      'Sleep context:', 'TSB:', 'CTL:', 'ATL:', 'ACWR:',
                      'Recovery Index:', 'Ramp Rate:', 'Load/Recovery:',
                      'Durability (cycling):', 'EF:', 'Monotony (',
                      'Hard days this week:', 'Hours:', 'Activities:', 'TSS:'):
            self.assertIn(field, body)
        for required in ('**Pre-workout: [Weekday D Month]**',
                         'Data updated: [local date time + zone',
                         '**Today: [session name]**','**Weather on the route**',
                         '**Weather at home**','**[Go / Modify / Skip]**',
                         'Only a session explicitly marked indoor skips weather',
                         'omitting Main set', 'without a missing-structure line'):
            self.assertIn(required,pre)
        self.assertNotIn('**Interpretation**',pre)
        hierarchy = (root/'REPORT_HIERARCHY.md').read_text()
        self.assertIn('One fact per labelled line',hierarchy)
        self.assertNotIn('12-18 lines per ride',hierarchy)
        fallback = ('Weather data by [MET Norway](https://api.met.no/), '
                    '[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).')
        self.assertIn(fallback,template)
        self.assertEqual(self.examples.count('Weather data by MET Norway, CC BY 4.0.'),2)
        self.assertIn('Never credit Open-Meteo for MET-only data',template)

    def test_no_route_output_and_situation_table_share_capability_gates(self):
        branch = self.template.split('## No planned ride has a usable route within 120 h\n',1)[1]
        branch = branch.split('## No-map and partial paths',1)[0]
        for required in ('No planned rides with a route.',
                         'Rides without a route:', 'Attach a GPX/TCX',
                         'actual, permitted weather-fetch capability',
                         'current official dossier', 'explicit current-chat athlete statement',
                         'Open-Meteo first, MET Norway fallback',
                         '../agentic/EXTERNAL_APIS.md', 'Weather data by Open-Meteo, CC BY 4.0.',
                         'Never use completed-activity `weather_summary` or old snapshots',
                         'No wind classes, strongest-gust km locations, sections, bands, maps, ETA or route claims',
                         'never a substitute inside a ride block',
                         'separate labelled set of facts for each day with a planned ride',
                         'at its planned time where known'):
            self.assertIn(required,branch)
        for row in ('| No planned ride with a usable route within 120 h |',
                    '| No planned rides within 120 h |',
                    '| Stale, expired, missing or unavailable |',
                    '| Disabled |'):
            self.assertIn(row,self.template)
        self.assertIn('an omitted or capped overview is not enough',branch)
        self.assertIn('The disabled rule takes precedence',branch)
        self.assertNotIn('Do not infer flatness or substitute home weather.',self.examples)

    def test_home_example_has_labelled_facts_per_planned_day_and_no_route_claims(self):
        example = self.examples.split('### Fetch-capable setup with known home\n',1)[1]
        example = example.split('### Setup without weather-fetch capability',1)[0]
        home = example.split('**Weather at home**',1)[1]
        home, attribution = home.split('Weather data by ',1)
        lines = [line.strip() for line in home.splitlines() if line.strip()]
        self.assertEqual(lines[0],'Place: Roskilde (from Intervals.icu)')
        days = home.split('Date: ')[1:]
        self.assertEqual(len(days),3)
        self.assertEqual([day[:3] for day in days],['Wed','Thu','Fri'])
        for day in days:
            self.assertRegex(day,r'^\w{3} \d{2} Jun')
            for label in ('Time: ','Wind: ','Gusts: ','Rain: ','Temperature: ','Feels like: '):
                self.assertEqual(day.count(label),1,day)
            self.assertRegex(day,r'Time: \d{2}:\d{2}–\d{2}:\d{2}\s*\n')
            self.assertRegex(day,r'Wind: [WN/]+ \d+\.\d–\d+\.\d m/s')
            self.assertRegex(day,r'Temperature: \d+\.\d–\d+\.\d °C')
            self.assertNotIn('CEST',day)
            for forbidden in ('Headwind','Crosswind','Tailwind','ETA','Moving time:','Total time:',
                              'Section ','Band ','Map ',' km'):
                self.assertNotIn(forbidden,day)
        self.assertEqual(attribution.splitlines()[0],
                         'Open-Meteo, CC BY 4.0.')
        self.assertNotIn('summarized by Section 11',attribution)
        self.assertNotIn('Location data based on [GeoNames]',example)

    def test_no_fetch_and_unknown_location_examples_do_not_supply_forecasts(self):
        no_fetch = self.examples.split('### Setup without weather-fetch capability\n',1)[1]
        no_fetch = no_fetch.split('### Unknown home or failed fetch',1)[0]
        report = no_fetch.split('**Weather report:',1)[1].split('\nNo Home block,',1)[0]
        for required in ('No planned rides with a route.',
                         'Rides without a route:', 'Attach a GPX/TCX',
                         "A home forecast isn't available in this setup."):
            self.assertIn(required,report)
        for forbidden in ('**Weather at home**','m/s','°C','Weather data by','CC BY','weather_summary'):
            self.assertNotIn(forbidden,report)
        unknown = self.examples.split('### Unknown home or failed fetch\n',1)[1]
        unknown = unknown.split('### No planned rides at all',1)[0]
        self.assertIn("A home forecast isn't available: no home location. Add your city/country "
                      "to your Intervals.icu athlete profile, or a Home region in your dossier.",unknown)
        self.assertIn('Omit the Home block',unknown)
        self.assertIn('actual unavailability reason without values',unknown)
        self.assertNotIn('m/s',unknown)

    def test_no_rides_and_nearby_routed_cases_remain_distinct(self):
        empty = self.examples.split('### No planned rides at all\n',1)[1]
        empty, nearby = empty.split('### Nearby cases that do not use this branch',1)
        report = empty.split('**Weather report:',1)[1].split('\nIn a setup',1)[0]
        self.assertEqual([line for line in report.splitlines()[1:] if line.strip() and line != '```'],
                         ['Period: next 5 days',
                          'Summary: No planned ride-day conditions to report.',
                          'No planned rides in the next 5 days.'])
        self.assertIn('optional Home block',empty)
        self.assertIn('same capability, location and planned-day gates',empty)
        for required in ('expired brief gets its ride/reason line',
                         'missing map uses supported band text',
                         'at least one usable route retains the normal ride blocks',
                         'Disabled weather still prints only'):
            self.assertIn(required,nearby)

    def test_no_route_policy_is_mirrored_in_protocol_and_report_pointers(self):
        for filename in ('SECTION_11.md','examples/agentic/README.md',
                         'examples/reports/README.md','examples/reports/REPORT_HIERARCHY.md'):
            with self.subTest(filename=filename):
                text = (self.root/filename).read_text()
                for required in ('Weather at home','Place','Time',
                                 'inside a ride block', '120 h',
                                 "A home forecast isn't available in this setup.",
                                 'optional'):
                    self.assertIn(required,text)

    def test_shared_point_location_order_route_precedence_and_travel_scope(self):
        protocol = (self.root/'SECTION_11.md').read_text()
        shared = protocol.split('##### Point-weather location\n',1)[1].split('##### Route-weather operation',1)[0]
        pre = (self.root/'examples/reports/PRE_WORKOUT_REPORT_TEMPLATE.md').read_text()
        pre_rule = next(line for line in pre.splitlines() if line.startswith('| Weather |'))
        agentic = (self.root/'examples/agentic/README.md').read_text().split('For an on-request report',1)[1]
        report_readme = (self.root/'examples/reports/README.md').read_text().split('- **Weather:**',1)[1]
        for text in (shared,self.template,pre_rule,agentic,report_readme):
            with self.subTest(text=text[:80]):
                lower = text.lower()
                positions = [lower.index(term) for term in
                             ('current-chat','athlete_profile.location','home region')]
                self.assertEqual(positions,sorted(positions))
                for required in ('null/empty','(you said)','(from Intervals.icu)',
                                 '(from dossier)','takes precedence','omit weather or ask',
                                 'earlier chats'):
                    self.assertIn(required,text)
        self.assertIn('valid only for that conversation',shared.lower())
        self.assertIn('must not persist into another conversation or a later automated run',shared)
        self.assertIn('nonempty but ambiguous or unusable Intervals location is not permission',shared)
        for text in (self.template,pre_rule,agentic,report_readme):
            self.assertIn('#point-weather-location',text)

    def test_point_examples_show_sources_and_keep_fallback_and_override_distinct(self):
        pre = (self.root/'examples/reports/PRE_WORKOUT_REPORT_EXAMPLES.md').read_text()
        lines = [line for line in pre.splitlines() if line.startswith('Place:')]
        self.assertEqual(len(lines),3)
        for line, source in zip(lines,('from Intervals.icu','you said','from dossier')):
            self.assertEqual(line,'Place: Klampenborg ('+source+')')
        self.assertNotIn('Weather (Klampenborg):',pre)
        cases = self.examples.split('### Location source and ambiguity examples\n',1)[1]
        cases = cases.split('### No planned rides at all',1)[0]
        rows = [line for line in cases.splitlines() if line.startswith('| ')][1:]
        self.assertEqual(len(rows),6)
        self.assertIn('Bergen (you said)',rows[0])
        self.assertIn('Roskilde (from Intervals.icu)',rows[1])
        self.assertIn('null/empty',rows[2])
        self.assertIn('Klampenborg (from dossier)',rows[2])
        self.assertIn('unavailable: geocoding ambiguous. Do not switch to the dossier',rows[3])
        self.assertIn('old chat override has expired',rows[4])
        self.assertIn('Omit weather or ask where; do not silently use home',rows[5])
        self.assertNotIn('Location data based on [GeoNames]',self.examples)
        self.assertNotIn('Location data based on [GeoNames]',pre)

    def test_heartbeat_location_removed_without_removing_other_settings(self):
        heartbeat = (self.root/'examples/agentic/openclaw/HEARTBEAT_TEMPLATE.md').read_text()
        self.assertNotIn('| Location |',heartbeat)
        for setting in ('Timezone','Notification hours','Notification channel','Notification ID'):
            self.assertIn('| '+setting+' |',heartbeat)
        self.assertIn('#point-weather-location',heartbeat)
        self.assertIn('Do not store or read a weather location in heartbeat configuration',heartbeat)
        skill = (self.root/'SKILL.md').read_text()
        self.assertIn('specific values (timezone, riding hours, weather thresholds, notification hours)',skill)
        for path in self.root.rglob('*.md'):
            text = path.read_text()
            for obsolete in ('configured heartbeat `Location`',
                             'specific values (location, timezone',
                             'home/base location is unknown.'):
                self.assertNotIn(obsolete,text,str(path.relative_to(self.root)))

    def test_geocoding_contract_matches_reference_and_rejects_unresolved_choices(self):
        api = (self.root/'examples/agentic/EXTERNAL_APIS.md').read_text()
        geo = api.split('### Geocoding for point weather\n',1)[1].split('## 4. Intervals.icu',1)[0]
        for required in ('https://geocoding-api.open-meteo.com/v1/search?',
                         'https://open-meteo.com/en/docs/geocoding-api',
                         '| `name` |','| `countryCode` |','| `count` |',
                         '| `language` |','| `format` |','Default 10, maximum 100',
                         '`results[]`','`country_code`','empty fields are omitted',
                         'only the text between the first and second comma',
                         'countryCode=DK','57.048','9.9187','142937','Aalborg SØ','Aalborg SV',
                         'Location data based on [GeoNames](https://www.geonames.org/)'):
            self.assertIn(required,geo)
        selection = geo.split('**Deterministic selection:**',1)[1].split('The supplied Aalborg',1)[0]
        positions = [selection.index(term) for term in
                     ('Filter by `countryCode`','Prefer an exact name match','uniquely highest population')]
        self.assertEqual(positions,sorted(positions))
        for required in ('tie','missing population','result limit','no candidate matches',
                         'Never choose the first result','lower-priority location',
                         'Empty results, malformed responses and failed requests'):
            self.assertIn(required,selection)
        self.assertIn('non-commercial use',geo)
        self.assertIn('Pre-workout and weather reports omit a separate GeoNames line',geo)
        self.assertIn("their Place line names the athlete's location source",geo)

    def test_dossier_readme_and_platform_contracts_preserve_location_labels(self):
        dossier = (self.root/'DOSSIER_TEMPLATE.md').read_text()
        row = next(line for line in dossier.splitlines() if line.startswith('| Home region |'))
        for required in ('fallback only','athlete_profile.location','null/empty','current-chat','(from dossier)'):
            self.assertIn(required,row)
        readme = (self.root/'README.md').read_text()
        weather = readme.split('### Route Weather\n',1)[1].split('### Saved Workouts Mirror\n',1)[0]
        self.assertIn('Without a usable route, a fetch-capable AI can give a home forecast.',weather)
        self.assertIn('[SECTION_11](SECTION_11.md#weather-data-source)',weather)
        protocol = (self.root/'SECTION_11.md').read_text()
        location = protocol.split('##### Point-weather location\n',1)[1].split('##### Route-weather operation\n',1)[0]
        sources = ('1. **Explicit current-chat athlete statement**',
                   '2. **`athlete_profile.location` in the current `latest.json`**',
                   "3. **The current official dossier's Home region**")
        positions = [location.index(source) for source in sources]
        self.assertEqual(positions,sorted(positions))
        for required in ('(you said)','Intervals.icu city/region/country','(from Intervals.icu)',
                         'only when `athlete_profile.location` is null/empty','(from dossier)',
                         'Show the selected place and source every time',
                         'unusable Intervals location is not permission to fall back to the dossier'):
            self.assertIn(required,location)
        for filename in ('PROJECT_INSTRUCTIONS_AGENTIC.md','PROJECT_INSTRUCTIONS_WEB.md'):
            text = (self.root/filename).read_text()
            exception = next(line for line in text.splitlines() if line.startswith('Exception: displayed forecast'))
            for required in ('source label','you said / from Intervals.icu / from dossier','GeoNames attribution'):
                self.assertIn(required,exception)


if __name__ == '__main__':
    unittest.main()
