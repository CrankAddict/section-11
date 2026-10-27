"""Offline source-document checks; source files are data, never imported.

The link parser covers inline/image/reference links, autolinks, ATX/setext
headings and fenced code. It is a bounded source check, not a renderer. Heading
IDs use build.cjs's Unicode slug and collision rules. External links are only
classified. Runtime files and the data-repository action link have explicit
classes, so absence from the source tree does not imply a broken source link.

Only Markdown prose is scanned for release churn. JSON version fields, script
constants/docstrings, test fixtures and other code are not prose inputs. Inline
code remains visible to the version check, since prose often quotes filenames.
Plain fences in the two copyable instruction files contain prose, not code.
"""

import html
from pathlib import Path, PurePosixPath
import posixpath
import re
import unicodedata
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
INSTRUCTION_PROSE = {'PROJECT_INSTRUCTIONS_AGENTIC.md', 'PROJECT_INSTRUCTIONS_WEB.md'}
JS_SPACE = '\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
ATX = re.compile(r'^ {0,3}(#{1,6})(?:[ \t]+(.*)|$)')
DEFINITION = re.compile(r'^ {0,3}\[([^]\n]+)\]:\s*(<[^>\n]+>|\S+)(?:\s+[\"\'(].*)?\s*$')
INLINE_CODE = re.compile(r'(`+)(?!`)(.*?)(?<!`)\1(?!`)', re.DOTALL)

# Exact filenames with an installed/generated/private role in the protocol.
# Misspellings and arbitrary .json/.md paths are not exempted.
RUNTIME_FILES = {
    'latest.json', 'history.json', 'intervals.json', 'routes.json',
    'saved_workouts.json', 'ftp_history.json', 'route_eta_history.json',
    'DOSSIER.md', 'HEARTBEAT.md',
}
DEPLOYMENT_LINKS = {
    ('examples/json-auto-sync/DATA_REPO_README_TEMPLATE.md',
     '../../actions/workflows/auto-sync.yml'),
}


def visible_lines(source, prose_fences=False):
    """Keep original line numbers; remove code fences and their contents."""
    active = None
    for number, line in enumerate(source.splitlines(), 1):
        match = FENCE.match(line)
        if active:
            marker, length, keep = active
            if re.fullmatch(r' {0,3}' + re.escape(marker) + '{' + str(length) + r',}[ \t]*', line):
                active = None
            elif keep:
                yield number, line
            continue
        if match:
            fence, info = match.groups()
            active = (fence[0], len(fence), prose_fences and not info.strip())
        elif not line.startswith(('    ', '\t')):
            yield number, line


def label_key(label):
    return ' '.join(label.split()).casefold()


def closing(text, start, opening, end):
    depth = 0
    i = start
    while i < len(text):
        if text[i] == '\\':
            i += 2
            continue
        if text[i] == opening:
            depth += 1
        elif text[i] == end:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def destination(body):
    """Drop an optional quoted title without splitting balanced URL parens."""
    body = body.strip()
    if body.startswith('<'):
        end = body.find('>')
        if end < 0:
            return None
        target, rest = body[1:end], body[end + 1:].strip()
    else:
        depth = 0
        end = len(body)
        escaped = False
        for index, char in enumerate(body):
            if escaped:
                escaped = False
                continue
            if char == '\\':
                escaped = True
            elif char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char.isspace() and depth == 0:
                end = index
                break
        target, rest = body[:end], body[end:].strip()
    if rest and not ((rest[0], rest[-1]) in {('"', '"'), ("'", "'"), ('(', ')')}):
        return None
    return html.unescape(re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\]^_`{|}~\\])', r'\1', target))


def markdown_links(source):
    """Return (line, target, syntax) records; undefined references are prose."""
    lines = list(visible_lines(source))
    definitions = {}
    definition_lines = set()
    for number, line in lines:
        match = DEFINITION.match(line)
        if match:
            label, target = match.groups()
            definitions.setdefault(label_key(label), destination(target))
            definition_lines.add(number)
    links = []
    for number, raw in lines:
        if number in definition_lines:
            continue
        line = INLINE_CODE.sub(lambda m: ' ' * len(m[0]), raw)
        for match in re.finditer(r'<((?:https?://|mailto:)[^<>\s]+)>', line):
            links.append((number, html.unescape(match[1]), 'autolink'))
        consumed = set()
        for start, char in enumerate(line):
            if start in consumed or char != '[' or (len(line[:start]) - len(line[:start].rstrip('\\'))) % 2:
                continue
            end = closing(line, start, '[', ']')
            if end is None:
                continue
            label = line[start + 1:end]
            tail = end + 1
            if line[tail:tail + 1] == '(':
                stop = closing(line, tail, '(', ')')
                target = None if stop is None else destination(line[tail + 1:stop])
                links.append((number, target, 'inline'))
                if stop is not None:
                    consumed.update(range(tail, stop + 1))
            elif line[tail:tail + 1] == '[':
                stop = closing(line, tail, '[', ']')
                if stop is not None:
                    key = label_key(line[tail + 1:stop] or label)
                    if key in definitions:
                        links.append((number, definitions[key], 'reference'))
                        consumed.update(range(tail, stop + 1))
            elif label_key(label) in definitions:
                links.append((number, definitions[label_key(label)], 'reference'))
    return links


def heading_text(text):
    # Keep inline-code text intact while removing prose emphasis delimiters.
    code = []
    def save(match):
        code.append(match[2].replace('\n', ' '))
        return '\x00' + str(len(code) - 1) + '\x00'
    text = INLINE_CODE.sub(save, text)
    text = re.sub(r'!?\[([^]\n]*)\]\([^\n]*?\)', r'\1', text)
    text = re.sub(r'!?\[([^]\n]*)\]\[[^]\n]*\]', r'\1', text)
    text = re.sub(r'(\*\*|__|~~)(.+?)\1', r'\2', text)
    text = re.sub(r'(?<!\w)([*_])(.+?)\1(?!\w)', r'\2', text)
    text = re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\]^_`{|}~\\])', r'\1', text)
    text = html.unescape(text)
    return re.sub(r'\x00(\d+)\x00', lambda m: code[int(m[1])], text)


def slug(text):
    # build.cjs: lowercase; keep L/N/M, underscore, hyphen, JS whitespace;
    # replace each whitespace separately, without normalization or collapsing.
    return ''.join('-' if char in JS_SPACE else char for char in text.lower()
                   if unicodedata.category(char)[0] in 'LNM' or char in '_-' + JS_SPACE)


def heading_ids(source):
    used = set()
    previous = ''
    previous_number = 0
    for number, line in visible_lines(source):
        match = ATX.match(line)
        title = None
        if match:
            title = re.sub(r'[ \t]+#+[ \t]*$', '', match[2] or '').strip()
        elif previous.strip() and number == previous_number + 1 and re.fullmatch(r' {0,3}(?:=+|-+)[ \t]*', line):
            title = previous.strip()
        if title is not None:
            base = slug(heading_text(title))
            anchor = base
            count = 1
            while anchor in used:
                anchor = base + '-' + str(count)
                count += 1
            used.add(anchor)
        previous, previous_number = line, number
    return used


def classify_link(source, target, documents, entries):
    if target is None:
        return 'invalid', 'malformed link or unresolved reference'
    if (source, target) in DEPLOYMENT_LINKS:
        return 'deployment-relative', None
    url = urlsplit(target)
    if url.scheme or url.netloc or target.startswith('//'):
        return 'external', None
    path = unquote(url.path)
    if path.startswith('/') or '\\' in path:
        return 'invalid', 'unsupported absolute or backslash path'
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), path)) if path else source
    if resolved == '..' or resolved.startswith('../'):
        return 'invalid', 'path leaves the source tree'
    if resolved not in entries:
        # An explicit bare runtime filename, not any path with the same suffix.
        if path in RUNTIME_FILES:
            return 'generated/private', None
        return 'local', 'missing file: ' + resolved
    if url.fragment and resolved in documents and unquote(url.fragment) not in heading_ids(documents[resolved]):
        return 'local', 'missing heading: ' + resolved + '#' + unquote(url.fragment)
    return 'local', None


def link_issues(documents, entries):
    issues, counts = [], {}
    for name, source in sorted(documents.items()):
        for line, target, syntax in markdown_links(source):
            kind, error = classify_link(name, target, documents, entries)
            counts[kind] = counts.get(kind, 0) + 1
            if error:
                issues.append(f'{name}:{line}: {error} ({syntax}: {target})')
    return issues, counts


# Stable labels, provenance and upgrade notes are allowed. The owner explicitly
# retained the baseline fixture history, including this one historical sentence
# that happens to match the release-news syntax. No other line is exempted.
HISTORICAL_FIXTURE_LINE = (
    'path. v3.136 adds repeat semantics (a nested repeat is shown as a repeat or marked,'
)
SKILL_PROTOCOL_RELEASE = re.compile(
    r'\bv11\.\d+(?:\.\d+)*\+?'
    r'|\b(?:Section 11(?: version)?|protocol(?: version)?|current version)'
    r'[\s:*()]+v?11\.\d+(?:\.\d+)*\+?',
    re.IGNORECASE,
)
SKILL_CURRENT_VERSION = re.compile(r'^\s*\*{0,2}current version\*{0,2}\s*:', re.IGNORECASE)
RELEASE_NEWS = re.compile(
    r'\bUpdated exports add\b|\bnew in v(?=\d|X\b)|\bthis release adds\b'
    r'|\bv(?:\d+(?:\.\d+)+|X)\s+adds\b', re.IGNORECASE,
)


def version_issues(name, source):
    issues = []
    changelog = False
    for number, line in visible_lines(source, name in INSTRUCTION_PROSE):
        heading = ATX.match(line)
        if name == 'SECTION_11.md':
            if heading and (heading[2] or '').strip() == 'Changelog':
                changelog = True
                continue
            if heading and len(heading[1]) <= 3:
                changelog = False
            if changelog:
                continue
        if name == 'dev/README.md' and line == HISTORICAL_FIXTURE_LINE:
            continue
        # Dependency/source URLs are not release prose.
        line = re.sub(r'(?:https?://|mailto:)\S+', '', line)
        skill_version = name == 'SKILL.md' and (
            SKILL_PROTOCOL_RELEASE.search(line) or SKILL_CURRENT_VERSION.search(line)
        )
        if skill_version or RELEASE_NEWS.search(line):
            issues.append(f'{name}:{number}: {line}')
    return issues


def report_rule_issues(name, source):
    if name in {'SECTION_11.md', 'examples/json-examples/README.md'}:
        return []
    return [f'{name}:{number}: {line}'
            for number, line in enumerate(source.splitlines(), 1)
            if re.search(r'\b(?:endurance_10_50_week_guard|report_sport_identity|report_sport_longest)_v\d+\b', line)]


# These two documents own literal report data-format versions.
REPORT_FORMAT_OWNERS = {'SECTION_11.md', 'examples/json-examples/README.md'}
REPORT_EXAMPLES = tuple('examples/reports/' + stem + '_REPORT_EXAMPLES.md'
                        for stem in ('7_DAY', '28_DAY', 'SEASON',
                                     'PRE_WORKOUT', 'POST_WORKOUT', 'WEATHER'))
RUNNING_TEXT = re.compile(
    r'^(?:Summary|Load|Quality|Watch|Next|Year on year|Shift|Verdict|Coach note): \S'
)


def report_format_issues(name, source):
    if name in REPORT_FORMAT_OWNERS:
        return []
    # A function/count suffix such as mean(2) is not the standalone literal.
    return [f'{name}:{number}: {line}'
            for number, line in enumerate(source.splitlines(), 1)
            if re.search(r'(?<![\w])\(2\)(?!\w)', line)]


def report_width_issues(name, source):
    """All fenced report examples/fragments: 40 Unicode code points per data line.

    Blank lines and standalone bold headings are structural. Only the explicit
    RUNNING_TEXT labels mark narrative paragraphs; those stay on one source line
    and wrap in the reader. No exemption based on punctuation, length or lack of
    a colon: unlabelled fact continuations and marker-first session lines count.
    All fence info strings are checked, so changing text to md cannot evade it.
    """
    issues, active, blocks = [], None, 0
    paragraph = False
    for number, line in enumerate(source.splitlines(), 1):
        match = FENCE.match(line)
        if active:
            marker, length = active
            if re.fullmatch(r' {0,3}' + re.escape(marker) + '{' + str(length) + r',}[ \t]*', line):
                active = None
                paragraph = False
                continue
            if paragraph and line.strip():
                issues.append(f'{name}:{number}: narrative paragraph needs a blank separator')
            paragraph = bool(RUNNING_TEXT.match(line))
            if not line.strip() or re.fullmatch(r'\*\*[^\n]+\*\*', line) or paragraph:
                continue
            if len(line) > 40:
                issues.append(f'{name}:{number}: {len(line)} characters: {line}')
            if line.startswith((' ', '\t')):
                issues.append(f'{name}:{number}: indented report line')
        elif match:
            fence, _info = match.groups()
            active = (fence[0], len(fence))
            blocks += 1
    if active:
        issues.append(f'{name}: unclosed report fence')
    if not blocks:
        issues.append(f'{name}: no report examples found')
    return issues


def repository_data(root):
    documents, entries = {}, set()
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        # Generated/dependency trees are not repository source documents.
        if any(part in {'.git', '.venv', 'node_modules', '__pycache__'} for part in relative.parts):
            continue
        if relative.parts[:3] == ('.github', 'site', 'dist'):
            continue
        if path.is_symlink():
            raise AssertionError('source input is a symlink: ' + relative.as_posix())
        entries.add(relative.as_posix())
        if path.is_file() and path.suffix == '.md':
            documents[relative.as_posix()] = path.read_text(encoding='utf-8')
    return documents, entries


class TestDocsContract(unittest.TestCase):
    def test_repository_links(self):
        documents, entries = repository_data(ROOT)
        self.assertIn('SECTION_11.md', documents)
        issues, counts = link_issues(documents, entries)
        self.assertGreater(counts.get('local', 0), 0)
        self.assertGreater(counts.get('external', 0), 0)
        self.assertGreater(counts.get('deployment-relative', 0), 0)
        self.assertEqual([], issues, '\n'.join(issues))

    def test_repository_release_prose(self):
        documents, _entries = repository_data(ROOT)
        issues = [issue for name, source in documents.items() for issue in version_issues(name, source)]
        self.assertEqual([], issues, '\n'.join(issues))

    def test_repository_report_rule_owners(self):
        documents, _entries = repository_data(ROOT)
        issues = [issue for name, source in documents.items() for issue in report_rule_issues(name, source)]
        self.assertEqual([], issues, '\n'.join(issues))

    def test_report_rule_owner_violation_and_nearby_valid(self):
        for rule in ('endurance_10_50_week_guard_v2', 'endurance_10_50_week_guard_v99',
                     'report_sport_identity_v2', 'report_sport_identity_v99',
                     'report_sport_longest_v1', 'report_sport_longest_v99'):
            for source in (f'Require {rule}.', f'Use `{rule}`.', f'```json\n{{"rule_version": "{rule}"}}\n```'):
                for name in ('guide.md', 'PROJECT_INSTRUCTIONS_AGENTIC.md', 'sub/SECTION_11.md'):
                    with self.subTest(name=name, source=source):
                        self.assertEqual(1, len(report_rule_issues(name, source)))
                for name in ('SECTION_11.md', 'examples/json-examples/README.md'):
                    self.assertEqual([], report_rule_issues(name, source))
        self.assertEqual([], report_rule_issues('guide.md',
            'Use report_intensity blocks matching the same file report_intensity_schema.rule_version; schema_version: 2. '
            'Require the sport_identity_rule marker; decode history.longest_session_schema columns.'))

    def test_repository_report_format_owners(self):
        documents, _entries = repository_data(ROOT)
        issues = [issue for name, source in documents.items()
                  for issue in report_format_issues(name, source)]
        self.assertEqual([], issues, '\n'.join(issues))

    def test_report_format_violation_and_nearby_valid(self):
        for source in ('report_intensity_schema (2)', '`report_intensity_schema` (2)',
                       '~~~text\nFormat: (2)\n~~~', 'Schema\n(2)'):
            for name in ('guide.md', 'PROJECT_INSTRUCTIONS_AGENTIC.md',
                         'sub/SECTION_11.md', 'examples/reports/PRE_WORKOUT_REPORT_TEMPLATE.md'):
                with self.subTest(name=name, source=source):
                    self.assertEqual(1, len(report_format_issues(name, source)))
            for name in REPORT_FORMAT_OWNERS:
                self.assertEqual([], report_format_issues(name, source))
        self.assertEqual([], report_format_issues('guide.md',
                         'HRRc: 7d mean(2); avg(2); report_intensity_schema.'))

    def test_all_report_example_data_width(self):
        for name in REPORT_EXAMPLES:
            with self.subTest(name=name):
                issues = report_width_issues(name, (ROOT / name).read_text(encoding='utf-8'))
                self.assertEqual([], issues, '\n'.join(issues))

    def test_report_width_boundary_narrative_and_fragment_controls(self):
        def block(line, fence='text'):
            return '```' + fence + '\n' + line + '\n```\n'
        self.assertEqual([], report_width_issues('fixture', block('Data: ' + 'x' * 34)))
        for line in ('Data: ' + 'x' * 35, '⚠️ ' + 'x' * 38,
                     'x' * 41, '  short continuation'):
            for fence in ('', 'text', 'md'):
                with self.subTest(line=line, fence=fence):
                    self.assertTrue(report_width_issues('fixture', block(line, fence)))
        for label in ('Summary', 'Load', 'Quality', 'Watch', 'Next', 'Year on year',
                      'Shift', 'Verdict', 'Coach note'):
            self.assertEqual([], report_width_issues('fixture', block(
                label + ': This labelled paragraph wraps naturally on a phone and fills a wide screen.')))
        self.assertTrue(report_width_issues('fixture', block('Note: ' + 'x' * 41)))
        self.assertTrue(report_width_issues('fixture', block('Summary: One paragraph.\ncontinued text')))
        self.assertEqual([], report_width_issues('fixture', block(
            '**Intensity (cycling, power, 4/4 weeks, 14/14 rides)**\nZ3: 7%\n\n'
            'Summary: One paragraph.\n\nTSS: 10')))
        self.assertEqual([], report_width_issues('fixture', 'Outside prose ' + 'x' * 100 + '\n' + block('TSS: 1')))
        self.assertTrue(report_width_issues('fixture', 'No fenced examples'))
        self.assertTrue(report_width_issues('fixture', '```text\nTSS: 1'))
        # A short complete block must not hide a long line in a later fragment.
        self.assertTrue(report_width_issues('fixture', block('TSS: 1') + block('x' * 41)))

    def test_slug_rules_and_collisions(self):
        self.assertEqual('å-2--é-e\u0301-字-ⅱ-a_b', slug('Å 2 & É e\u0301 字 Ⅱ A_B'))
        self.assertEqual('a-b', slug('A\ufeffB'))
        source = '# Same\n# Same-1\n# Same\n# **Bold** `a_b` & [link](file.md)\nTitle\n=====\n~~~md\n# Hidden\n~~~\n'
        self.assertEqual({'same', 'same-1', 'same-2', 'bold-a_b--link', 'title'}, heading_ids(source))
        builder = (ROOT / '.github/site/build.cjs').read_text(encoding='utf-8')
        self.assertIn("text.toLowerCase().replace(/[^\\p{L}\\p{N}\\p{M}_\\-\\s]/gu, '').replace(/\\s/g, '-')", builder)
        self.assertIn('for (let n = 1; used.has(id); n++) id = `${base}-${n}`;', builder)

    def test_link_violation_and_nearby_valid(self):
        documents = {'a.md': '# Start\n', 'sub/target.md': '# Café\n# Café\n'}
        entries = set(documents) | {'sub', 'sub/image(1).png'}
        good = '[ok](sub/target.md#caf%C3%A9-1) ![map](sub/image(1).png "caption") [same](#start)'
        documents['a.md'] += good
        self.assertEqual([], link_issues(documents, entries)[0])
        for target in ('sub/missing.md', 'sub/target.md#missing', '../outside.md', 'sub/target.md#cafe'):
            with self.subTest(target=target):
                broken = dict(documents, **{'a.md': '# Start\n[bad](' + target + ')'})
                self.assertEqual(1, len(link_issues(broken, entries)[0]))

    def test_reference_images_fences_and_inline_code(self):
        source = ('[go][target] ![picture][image]\n[target]: other.md#topic\n'
                  '[image]: <image.png> "caption"\n[collapsed][] [shortcut]\n'
                  '[collapsed]: other.md\n[shortcut]: other.md\n'
                  '```md\n[bad](missing.md)\n````\n'
                  '~~~\n[bad](missing-again.md)\n~~~\n'
                  '`[bad](inline-missing.md)` \\[escaped](not-a-link.md)\n')
        docs = {'a.md': source, 'other.md': '# Topic'}
        self.assertEqual([], link_issues(docs, set(docs) | {'image.png'})[0])
        self.assertEqual(4, len(markdown_links(source)))
        self.assertEqual([], markdown_links('tid[sport][mapping] and [plain][undefined]'))
        self.assertEqual(1, len(link_issues({'a.md': '[bad][target]\n[target]: missing.md'}, {'a.md'})[0]))
        self.assertEqual(1, len(link_issues({'a.md': '[bad](unclosed'}, {'a.md'})[0]))

    def test_link_classes_are_narrow(self):
        source = 'examples/json-auto-sync/DATA_REPO_README_TEMPLATE.md'
        entries = {source}
        docs = {source: '# Source'}
        for target, kind in [('https://invalid.example/x', 'external'),
                             ('mailto:someone@example.invalid', 'external'),
                             ('../../actions/workflows/auto-sync.yml', 'deployment-relative'),
                             ('latest.json', 'generated/private'), ('DOSSIER.md', 'generated/private')]:
            self.assertEqual((kind, None), classify_link(source, target, docs, entries))
        for target in ('latset.json', 'missing/DOSSIER.md', '../../actions/workflows/typo.yml'):
            self.assertIsNotNone(classify_link(source, target, docs, entries)[1])
        self.assertIsNotNone(classify_link('README.md', '../../actions/workflows/auto-sync.yml', docs, entries)[1])

    def test_release_news_violations(self):
        for text in ('Updated exports add fields.', 'New in v2.1',
                     'This release adds fields.', 'v11.99 adds fields.',
                     'v3.136 adds fields.', 'vX adds fields.'):
            with self.subTest(text=text):
                for name in ('guide.md', 'SKILL.md', 'SECTION_11.md'):
                    self.assertEqual(1, len(version_issues(name, text)))

    def test_skill_protocol_release_numbers(self):
        for text in ('description: Coaching protocol (v11.95).',
                     '**Current version:** 11.95', 'Section 11 11.95',
                     'Protocol version: 11.95', 'Use Section 11 v11.99.',
                     '**Current version:** upcoming'):
            with self.subTest(text=text):
                self.assertEqual(1, len(version_issues('SKILL.md', text)))
                self.assertEqual([], version_issues('guide.md', text))
        self.assertEqual([], version_issues('SKILL.md', 'Use push.py v0.8 and updated sync.py.'))
        self.assertEqual([], version_issues('SKILL.md', '11.95 W; -11.40 TSB; schema version 2.'))

    def test_stable_labels_provenance_and_technical_versions(self):
        text = ('### Report intensity (sync 3.147)\n'
                '### Report schema (sync.py v3.152)\n'
                '### Readiness Decision (v11.13)\n'
                '# Renamed in v11.84\n'
                'Originated with sync.py v3.86 / Section 11 v11.17.\n'
                'Regenerated by hand at sync.py v3.121 / Section 11 v11.53.\n'
                'Upgrading from before 11.80; For 11.80 / sync 3.146, replace files.\n'
                'Use push.py v0.8; v11.30+; removed in v11.52; outcomes (v0.6).\n'
                'Update the script if the field is absent; use updated sync.py.\n'
                'schema_version: 2; structure version 6; calculation v4.\n'
                '3.5 h; -11.40 TSB; 3.147 W; 0.8; Python 3.8+; Node 24.20.0.\n'
                'CC BY 4.0; licence 1.1; font 2.1.5.\n'
                'https://example.invalid/v3.999/source\n'
                '\x60\x60\x60json\n{"version": "11.99"}\n\x60\x60\x60\n')
        for name in ('guide.md', 'dev/README.md', 'SECTION_11.md'):
            self.assertEqual([], version_issues(name, text))
        self.assertEqual([], version_issues('guide.md', '### Feature (sync 3.147)'))
        self.assertEqual([], version_issues('examples/json-local-sync/SETUP.md', '\x60\x60\x60\nsync.py 3.75 -> 3.76\nSECTION_11.md 11.13 -> 11.14\n\x60\x60\x60'))

    def test_only_changelog_allows_release_news(self):
        text = '**Protocol Version:** 11.99\n### Changelog\nv11.99 adds fields.\n## Overview\nNew in v11.99\n'
        self.assertEqual(1, len(version_issues('SECTION_11.md', text)))
        self.assertEqual(2, len(version_issues('guide.md', text)))
        for name in INSTRUCTION_PROSE:
            self.assertEqual(1, len(version_issues(name, '\x60\x60\x60\nThis release adds fields.\n\x60\x60\x60')))
            self.assertEqual([], version_issues(name, '\x60\x60\x60\nUse push.py v0.8.\n\x60\x60\x60'))

    def test_historical_fixture_exception_is_exact(self):
        self.assertEqual([], version_issues('dev/README.md', HISTORICAL_FIXTURE_LINE))
        self.assertEqual(1, len(version_issues('guide.md', HISTORICAL_FIXTURE_LINE)))
        self.assertEqual(1, len(version_issues('dev/README.md', HISTORICAL_FIXTURE_LINE + ' This release adds fields.')))
        self.assertEqual(1, len(version_issues('dev/README.md', HISTORICAL_FIXTURE_LINE.replace('v3.136', 'v3.999'))))


if __name__ == '__main__':
    unittest.main()
