"""Offline relationships in synthetic session/weather report examples."""
from pathlib import Path
import re
import unittest

from test_docs_contract import REPORT_EXAMPLES, report_width_issues

REPORTS = Path(__file__).resolve().parents[2] / 'examples/reports'


def examples(stem):
    return (REPORTS / (stem + '_REPORT_EXAMPLES.md')).read_text(encoding='utf-8')


def blocks(source):
    return re.findall(r'^```(?:text)?\n(.*?)\n```', source, re.M | re.S)


def pre_order_issues(block):
    required = (r'^\*\*(?:Go|Modify|Skip)\*\*$', r'^Signals:', r'^Verdict:',
                r'^(?:\*\*Today:|Rest day:)', r'^\*\*Readiness\*\*$',
                r'^\*\*Load\*\*$', r'^\*\*Intensity', r'^\*\*Last 7 days\*\*$')
    matches = [re.search(pattern, block, re.M) for pattern in required]
    if any(match is None for match in matches):
        return ['missing required opening or supporting block']
    positions = [match.start() for match in matches]
    return [] if positions == sorted(positions) else ['wrong report order']


def session_ef_issues(block):
    """Only activity sections, never period EF means."""
    activity_text = block.split('**Last 7 days**', 1)[0]
    issues = []
    for activity in re.split(r'(?=^\*\*(?:Ride:|Walk:|Morning walk))', activity_text, flags=re.M):
        vi = re.search(r'^Variability Index: ([0-9.]+)', activity, re.M)
        if re.search(r'^EF: [0-9.]+$', activity, re.M):
            if vi is None or not 0 < float(vi[1]) <= 1.05:
                issues.append('session EF without valid VI')
    return issues


def short_home_issues(block, attached=False, rain=False):
    """Check the walk/hike display contract, not a weather formatter."""
    lines = block.splitlines()
    weather = [line for line in lines if line.startswith('Weather:')]
    wind = [line for line in lines if line.startswith('Wind:')]
    reasons = [line for line in lines if line.startswith('Route forecast:')]
    issues = []
    if len(weather) != 1 or len(wind) != int(rain):
        issues.append('wrong short weather line count')
    if len(reasons) != int(attached):
        issues.append('missing or extraneous route reason')
    if attached and reasons != ['Route forecast: rides only']:
        issues.append('unsupported route forecast')
    if not any(line.startswith('**Home (') for line in lines):
        issues.append('missing home source/window context')
    if any(line.startswith(('Place:', 'Time:', 'Temperature:', 'Rain:', 'Feels like:',
                            '**Weather at home**', '**Weather on the route**')) for line in lines):
        issues.append('full block or route forecast in short weather')
    if any(len(line) > 40 for line in weather + wind + reasons):
        issues.append('overwide short weather line')
    return issues


class SessionReportLayout(unittest.TestCase):
    def test_dry_walk_uses_short_home_line(self):
        source = examples('PRE_WORKOUT').split('## Example 6:', 1)[1].split('## Example 7:', 1)[0]
        walk, = blocks(source)
        self.assertEqual([], short_home_issues(walk))
        self.assertIn('Weather: dry, 13.0 °C, W 3.0 m/s', walk)
        self.assertIn('**Home (Lund, you said, 14:10–14:50)**', walk)
        self.assertIn('amount and probability are both zero', source)
        self.assertEqual(walk.splitlines()[-1], 'Weather data by Open-Meteo, CC BY 4.0.')

    def test_attached_hike_uses_home_rain_and_route_reason(self):
        source = examples('PRE_WORKOUT').split('## Example 7:', 1)[1]
        hike, = blocks(source)
        self.assertEqual([], short_home_issues(hike, attached=True, rain=True))
        self.assertIn('Weather: 0.6 mm/h 55%, 8.0 °C', hike)
        self.assertIn('Wind: NW 3.5 m/s, gusts 6.5 m/s', hike)
        self.assertIn('**Home (Lund, you said, 08:20–10:20)**', hike)
        self.assertIn('GPX attachment', source)
        self.assertIn('never conditions along the hiking route', source)

    def test_short_weather_direct_violations_and_nearby_valid(self):
        hike, = blocks(examples('PRE_WORKOUT').split('## Example 7:', 1)[1])
        for broken in (
            hike.replace('Route forecast: rides only\n', ''),
            hike.replace('Route forecast: rides only', '**Weather on the route**'),
            hike.replace('Weather: 0.6 mm/h 55%, 8.0 °C', 'Weather: ' + 'x' * 32),
            hike.replace('Wind: NW 3.5 m/s, gusts 6.5 m/s', 'Temperature: 8.0 °C'),
        ):
            self.assertTrue(short_home_issues(broken, attached=True, rain=True))
        trace = hike.replace('Weather: 0.6 mm/h 55%, 8.0 °C', 'Weather: <0.1 mm/h 5%, 9.0 °C')
        self.assertEqual([], short_home_issues(trace, attached=True, rain=True))
        self.assertEqual([], report_width_issues('trace', '```text\n' + trace + '\n```'))

    def test_run_full_block_and_indoor_walk_still_omit_weather(self):
        source = examples('PRE_WORKOUT').split('## Example 5:', 1)[1].split('## Example 6:', 1)[0]
        excerpt, = blocks(source)
        run, indoor = excerpt.split('**Today: Evening walk**', 1)
        self.assertIn('Outdoor run', run)
        for label in ('**Weather at home**', 'Place:', 'Time:', 'Temperature:', 'Wind:', 'Rain:'):
            self.assertIn(label, run)
        self.assertIn('Indoor walk', indoor)
        self.assertNotRegex(indoor, r'(?m)^(Weather:|Wind:|Route forecast:|\*\*Home)')
        template = (REPORTS / 'PRE_WORKOUT_REPORT_TEMPLATE.md').read_text()
        self.assertIn('Only outdoor rides have route forecasts', template)
        self.assertIn('same home-source order', template)
        self.assertIn('Positive rain probability', template)
        self.assertIn('single final linked weather attribution', template)

    def test_width_covers_all_six_files_and_later_fragments(self):
        self.assertEqual(len(REPORT_EXAMPLES), 6)
        for stem in ('PRE_WORKOUT', 'POST_WORKOUT', 'WEATHER'):
            name = 'examples/reports/' + stem + '_REPORT_EXAMPLES.md'
            self.assertIn(name, REPORT_EXAMPLES)
            self.assertEqual([], report_width_issues(name, examples(stem)))
            self.assertTrue(report_width_issues(name, examples(stem) +
                            '\n```text\nBand: ' + 'x' * 35 + '\n```'))

    def test_pre_verdict_session_support_order_and_mutation(self):
        full = [block for block in blocks(examples('PRE_WORKOUT'))
                if block.startswith('**Pre-workout:')]
        self.assertEqual(len(full), 4)
        for block in full:
            self.assertEqual([], pre_order_issues(block))
            verdict = re.search(r'^Verdict: (.+)$', block, re.M)[1]
            self.assertEqual(len(re.findall(r'[.!?](?: |$)', verdict)), 2)
            broken = block.replace('**Readiness**', '**Removed**')
            self.assertTrue(pre_order_issues(broken))
        block = full[1]
        moved = block.replace('**Readiness**', '') + '\n**Readiness**'
        self.assertTrue(pre_order_issues(moved))

    def test_outdoor_unrouted_and_indoor_weather_are_distinct(self):
        source = examples('PRE_WORKOUT')
        full = [b for b in blocks(source) if b.startswith('**Pre-workout:')]
        outdoor = full[1].split('**Today: Endurance**', 1)[1].split('**Readiness**')[0]
        self.assertIn('Outdoor ride', outdoor)
        self.assertIn('**Weather at home**', outdoor)
        self.assertNotIn('**Weather on the route**', outdoor)
        self.assertNotIn('Weather at home', full[2])
        self.assertIn('Indoor ride', full[2])
        template = (REPORTS / 'PRE_WORKOUT_REPORT_TEMPLATE.md').read_text()
        for preserved in ('P0 and P1 are not overridable', 'start-of-day',
                          'Same-Day Continuation Block', 'never home substitution',
                          'missing route', 'explicitly marked indoor'):
            self.assertIn(preserved, template)

    def test_post_ef_gate_and_nearby_valid_control(self):
        source = examples('POST_WORKOUT')
        for block in blocks(source):
            self.assertEqual([], session_ef_issues(block))
        for vi in ('0', '1.06'):
            self.assertTrue(session_ef_issues('**Ride: Test**\nVariability Index: ' + vi + '\nEF: 1.5'))
        self.assertTrue(session_ef_issues('**Ride: Test**\nEF: 1.5'))
        self.assertEqual([], session_ef_issues('**Ride: Test**\nVariability Index: 1.05\nEF: 1.5'))

    def test_post_retains_load_and_walks_without_planned_lines(self):
        full = [b for b in blocks(examples('POST_WORKOUT')) if b.startswith('**Post-workout:')]
        self.assertEqual(len(full), 8)
        walks = 0
        for block in full:
            self.assertIn('\nSummary: ', block)
            load = block.split('**Last 7 days**', 1)[1]
            for label in ('CTL:', 'ATL:', 'TSB:', 'Ramp rate:', 'Hours:', 'TSS:'):
                self.assertRegex(load, '(?m)^' + label)
            for match in re.finditer(r'^\*\*Walk:.*?\*\*\n(.*?)(?=^\*\*|\Z)', block, re.M | re.S):
                walks += 1
                self.assertNotIn('Planned:', match[1])
                self.assertIn('Moving time:', match[1])
        self.assertEqual(walks, 2)

    def test_post_three_bands_peaks_and_not_ridden_evidence(self):
        source = examples('POST_WORKOUT')
        for block in blocks(source):
            self.assertNotRegex(block, r'(?m)^(?:Grey Zone|Quality \(Z4\+\)|Power zones: Z1 |HR zones: Z1 )')
        self.assertIn('Power Z1+Z2/Z3/Z4+: 66/23/11%', source)
        self.assertIn('HR Z1+Z2/Z3/Z4+: 61/14/25%', source)
        self.assertIn('Peaks\n5 s: 390 W\n1 min: 230 W\n5 min: 190 W\n20 min: 160 W', source)
        fragment = blocks(source)[-1]
        self.assertIn('Set 2 (310 W): 3/5 ridden, 306 W avg', fragment)
        self.assertIn('Reason: set 2 bouts 4–5 below band', fragment)
        self.assertIn('Not ridden: set 2 bouts 6–8', fragment)
        self.assertNotIn('3/8', fragment)
        self.assertNotIn('%', fragment)

    def test_weather_summary_passed_start_band_blocks_and_attribution(self):
        source = examples('WEATHER')
        full = [b for b in blocks(source) if b.startswith('**Weather report:')]
        self.assertEqual(len(full), 7)
        for block in full:
            self.assertRegex(block, r'Period: next 5 days\n\nSummary: [^\n]+\n\n')
            self.assertNotIn('Comparison:', block)
            self.assertNotIn('[Matching map', block)
            lines = [line for line in block.splitlines() if line]
            credits = [line for line in lines if line.startswith('Weather data by')]
            if credits:
                self.assertEqual(len(credits), 1)
                self.assertEqual(credits[0], lines[-1])
        passed = full[3]
        self.assertIn('Start: 10:30 (assumed)\nPlanned 10:00 has passed.\nWhen are you leaving?', passed)
        partial = full[2]
        for band in 'ABCDEF':
            self.assertIn('**Band ' + band + ' (', partial)
        self.assertEqual(partial.count('Probability: unavailable'), 7)
        self.assertNotIn('Rain: dry', partial)
        self.assertIn('Missing map: River loop, page 2', source)
        self.assertIn('Rain: dry, 0%', source)
        self.assertIn('Rain: <0.1 mm/h, 10%', source)


if __name__ == '__main__':
    unittest.main()
