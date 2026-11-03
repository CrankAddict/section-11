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

import ast
import difflib
import hashlib
import html
import json
import os
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
    ('examples/json-auto-sync/DATA_REPO_README_TEMPLATE.md',
     'section11/examples/maintenance/UPDATING.md'),
    ('examples/json-auto-sync/DATA_REPO_README_TEMPLATE.md',
     'section11/examples/json-examples/README.md'),
    ('examples/json-auto-sync/DATA_REPO_README_TEMPLATE.md', 'section11/LICENSE'),
    ('dev/demo/templates/README.md', '../../actions/workflows/auto-sync.yml'),
    ('dev/demo/templates/README.md', 'demo/generate.py'),
    ('dev/demo/templates/README.md', '../../pulls'),
    ('dev/demo/templates/README.md', '../../actions'),
    ('dev/demo/templates/README.md',
     'section11/examples/maintenance/UPDATING.md#automatic-github-updates'),
    ('dev/demo/templates/SETUP_DEMO.md', 'section11/examples/maintenance/UPDATING.md'),
    ('dev/demo/templates/README.md', 'section11/examples/json-local-sync/SETUP.md'),
    ('dev/demo/templates/README.md', 'section11/examples/maintenance/UPDATING.md'),
    ('dev/demo/templates/README.md', 'custom/'),
    ('dev/demo/templates/README.md', 'LICENSE'),
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
    # Links and inline code may wrap across lines in one paragraph. Keep fence,
    # blank-line and definition boundaries so unrelated blocks cannot join.
    paragraphs, paragraph = [], []
    for number, raw in lines:
        if number in definition_lines or not raw.strip():
            if paragraph:
                paragraphs.append(paragraph)
                paragraph = []
            continue
        if paragraph and number != paragraph[-1][0] + 1:
            paragraphs.append(paragraph)
            paragraph = []
        paragraph.append((number, raw))
    if paragraph:
        paragraphs.append(paragraph)
    links = []
    for paragraph in paragraphs:
        number = paragraph[0][0]
        raw = '\n'.join(line for _number, line in paragraph)
        line = INLINE_CODE.sub(lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), raw)
        for match in re.finditer(r'<((?:https?://|mailto:)[^<>\s]+)>', line):
            links.append((number + line[:match.start()].count('\n'), html.unescape(match[1]), 'autolink'))
        consumed = set()
        for start, char in enumerate(line):
            if start in consumed or char != '[' or (len(line[:start]) - len(line[:start].rstrip('\\'))) % 2:
                continue
            end = closing(line, start, '[', ']')
            if end is None:
                continue
            label = line[start + 1:end]
            link_number = number + line[:start].count('\n')
            tail = end + 1
            if line[tail:tail + 1] == '(':
                stop = closing(line, tail, '(', ')')
                target = None if stop is None else destination(line[tail + 1:stop])
                links.append((link_number, target, 'inline'))
                if stop is not None:
                    consumed.update(range(tail, stop + 1))
            elif line[tail:tail + 1] == '[':
                stop = closing(line, tail, '[', ']')
                if stop is not None:
                    key = label_key(line[tail + 1:stop] or label)
                    if key in definitions:
                        links.append((link_number, definitions[key], 'reference'))
                        consumed.update(range(tail, stop + 1))
            elif label_key(label) in definitions:
                links.append((link_number, definitions[label_key(label)], 'reference'))
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


def headings(source):
    """Yield GitHub-style unique anchors, levels and source line numbers."""
    used = set()
    previous = ''
    previous_number = 0
    for number, line in visible_lines(source):
        match = ATX.match(line)
        title = None
        if match:
            title = re.sub(r'[ \t]+#+[ \t]*$', '', match[2] or '').strip()
            level, start = len(match[1]), number
        elif previous.strip() and number == previous_number + 1 and re.fullmatch(r' {0,3}(?:=+|-+)[ \t]*', line):
            title = previous.strip()
            level, start = (1 if line.strip().startswith('=') else 2), previous_number
        if title is not None:
            base = slug(heading_text(title))
            anchor = base
            count = 1
            while anchor in used:
                anchor = base + '-' + str(count)
                count += 1
            used.add(anchor)
            yield anchor, level, start
        previous, previous_number = line, number


def heading_ids(source):
    return {anchor for anchor, _level, _number in headings(source)}


def heading_section(source, anchor):
    outline = list(headings(source))
    for index, (identifier, level, start) in enumerate(outline):
        if identifier == anchor:
            end = next((number for _id, depth, number in outline[index + 1:]
                        if depth <= level), len(source.splitlines()) + 1)
            return '\n'.join(source.splitlines()[start:end - 1])
    raise AssertionError('missing heading: ' + anchor)


def markdown_fragment_target(source, target):
    """Resolve source and known installed Markdown paths, never bypass anchors."""
    url = urlsplit(target)
    if url.scheme or url.netloc or not url.fragment:
        return None
    path = unquote(url.path)
    if path and not path.lower().endswith('.md'):
        return None
    if path.startswith('/') or '\\' in path:
        raise AssertionError('unsupported fragment path: ' + target)
    if (source, target) in DEPLOYMENT_LINKS and path.startswith('section11/'):
        resolved = path.removeprefix('section11/')
    else:
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), path)) if path else source
    if resolved == '..' or resolved.startswith('../'):
        raise AssertionError('fragment path leaves source tree: ' + target)
    return resolved, unquote(url.fragment)


def markdown_fragment_issues(documents):
    issues = []
    for name, source in sorted(documents.items()):
        for line, target, _syntax in markdown_links(source):
            if target is None:
                continue  # The general link check reports malformed syntax.
            try:
                result = markdown_fragment_target(name, target)
                if result is None:
                    continue
                resolved, anchor = result
                if resolved not in documents:
                    raise AssertionError('missing Markdown target: ' + resolved)
                if anchor not in heading_ids(documents[resolved]):
                    raise AssertionError('missing heading: ' + resolved + '#' + anchor)
            except AssertionError as error:
                issues.append(f'{name}:{line}: {error}')
    return issues


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


# Digests keep the regression from publishing the private identifier it rejects.
PRIVATE_IDENTIFIER_DIGESTS = {(11, 'b8e53c35a5cb98fe9a96c62fb84b7706a93dadc9147630f9e136fca8009bf801')}
INTERNAL_CODE_TERMS = re.compile(
    r'\b(?:Coach|Astra|T3|workers?)\b|\b[Rr]ound[\s_-]+\d+\b'
    r'|pilot-workspace|(?:reference|working)/jobs/'
)
PUBLIC_CODE_TERMS = re.compile(r'\b(?:AI Coach|Coach (?:note|Guidance|Protocol)|T3 Code|service worker)\b')
# These existing producer comments describe the AI reader, not an operator.
PUBLIC_CODE_LINES = {
    'examples/sync.py': {
        "# Has GPS but no altitude. Coach can't reason about climbs/grade,",
        "climbs (and therefore don't appear in the climbs[] array). Coach",
    },
}
# Only policy definitions and explicit negative-test data may name these terms.
# The private-identifier check has no such exemption.
INTERNAL_TERM_TEST_SCOPES = {
    'dev/tests/test_demo_kit.py': {'INTERNAL_TERMS', 'test_public_templates_use_user_facing_terms'},
    'dev/tests/test_docs_contract.py': {
        'INTERNAL_CODE_TERMS', 'PUBLIC_CODE_TERMS', 'PUBLIC_CODE_LINES',
        'test_internal_code_term_controls',
    },
}

# Historical executable fixtures preserve the supplied public source verbatim.
# Only these exact byte identities are exempt from current-code wording rules;
# private-identifier scanning still covers every fixture.
HISTORICAL_EXECUTABLES = {
    'dev/fixtures/hosted/sync-0ab6e9d.py': 'c8d1b8eff4b66c512a789dad9cd54623849604d5c53392e2621f3381fa937b3d',
    'dev/fixtures/hosted/sync-2c8a813.py': '225d4308be9627bb882ef17a2f3c50afcdc672ba9b2207e93f9363612a96ffca',
    'dev/fixtures/hosted/sync-2d3980e.py': 'a60c2ee19b3469c2e34d51df9d075c6b5e8e1e9d81764f1f60c672ff440da152',
    'dev/fixtures/hosted/sync-fdde807.py': '75e927e95770356e5c9042280ac3fc1829763b15898aad397d246b8df9c1feb7',
    'dev/fixtures/b1-legacy/sync-0ab6e9d.py': 'c8d1b8eff4b66c512a789dad9cd54623849604d5c53392e2621f3381fa937b3d',
    'dev/fixtures/b1-legacy/sync-2c8a813.py': '225d4308be9627bb882ef17a2f3c50afcdc672ba9b2207e93f9363612a96ffca',
    'dev/fixtures/b1-legacy/sync-2d3980e.py': 'a60c2ee19b3469c2e34d51df9d075c6b5e8e1e9d81764f1f60c672ff440da152',
    'dev/fixtures/b1-legacy/sync-fdde807.py': '75e927e95770356e5c9042280ac3fc1829763b15898aad397d246b8df9c1feb7',
    'dev/fixtures/b1-legacy/sync-7db221d8.py': '0c49f8829426e3b5f0f912f49eead764463e2402cd313fcd6490e35af19a73e0',
}


def private_identifier_issues(name, content, forbidden=PRIVATE_IDENTIFIER_DIGESTS):
    for length, digest in forbidden:
        for token in re.findall(rb'[A-Za-z0-9-]{' + str(length).encode() + rb',}', content.lower()):
            if any(hashlib.sha256(token[i:i + length]).hexdigest() == digest
                   for i in range(len(token) - length + 1)):
                return [name + ': private account identifier']
    return []


def internal_code_issues(name, source, lines):
    if name in HISTORICAL_EXECUTABLES:
        if hashlib.sha256(source.encode()).hexdigest() != HISTORICAL_EXECUTABLES[name]:
            return [name + ': modified historical executable fixture']
        return []
    exempt = set()
    if name in INTERNAL_TERM_TEST_SCOPES:
        for node in ast.walk(ast.parse(source)):
            names = {node.name} if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else set()
            if isinstance(node, ast.Assign):
                names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if names & INTERNAL_TERM_TEST_SCOPES[name]:
                exempt.update(range(node.lineno, node.end_lineno + 1))
    issues = []
    for number, line in lines:
        # These are real product/protocol/report terms, not project operators.
        if line.strip() in PUBLIC_CODE_LINES.get(name, set()):
            continue
        text = PUBLIC_CODE_TERMS.sub('', line)
        if number not in exempt and INTERNAL_CODE_TERMS.search(text):
            issues.append(f'{name}:{number}: internal project wording')
    return issues


def release_review_inputs(root):
    manifest = os.environ.get('S11_RELEASE_CHANGED_FILES')
    baseline = os.environ.get('S11_RELEASE_BASELINE')
    if bool(manifest) != bool(baseline):
        raise AssertionError('supply both release changed-file list and baseline')
    if manifest:
        names = Path(manifest).read_text().splitlines()
        if not names or names != sorted(set(names)):
            raise AssertionError('release changed-file list must be sorted and unique')
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or not (root / name).is_file():
                raise AssertionError('invalid release source path: ' + name)
        return names, Path(baseline)
    # Standalone repository runs check every current file/line, with no skips.
    _documents, entries = repository_data(root)
    return sorted(name for name in entries if (root / name).is_file()), None


def release_added_lines(name, source, baseline):
    lines = source.splitlines()
    if baseline is None or not (baseline / name).exists():
        return list(enumerate(lines, 1))
    before = (baseline / name).read_text().splitlines()
    added = []
    for tag, _a, _b, start, end in difflib.SequenceMatcher(a=before, b=lines).get_opcodes():
        if tag in ('insert', 'replace'):
            added.extend((i + 1, lines[i]) for i in range(start, end))
    return added


# Relocated historical documents are frozen journey fixtures, not current guides.
# Exact hashes protect this exception; private-identifier checks still scan them.
HISTORICAL_DOCUMENTS = {
    'dev/fixtures/hosted/github-SETUP-0ab6e9d.md': '29795b7bfacae1e3071b26382637f79383243f6990044a698b83fdd776f58675',
    'dev/fixtures/hosted/github-SETUP-2c8a813.md': '4a6d6684ed46c21b5e15463683012e019d568afcfa1712fe7f77552af47daa65',
    'dev/fixtures/hosted/github-SETUP-2d3980e.md': '63e4e14a4f59daf3f6ed2056a54f912d6d675052a2d3ca168f7e0358e0595932',
    'dev/fixtures/hosted/github-SETUP-fdde807.md': 'a00e2cbe8c45ddf0102ae3a66d9d2240b5f91a768788cc36f424de19c6d1a8d8',
    'dev/fixtures/hosted/on-demand-2d3980e-SETUP.md': '8a4cf6b9f4406ee0c237f23ca26cbc423ecc4d97f0c81f79b0ac79df47a4d102',
    'dev/fixtures/hosted/on-demand-2c8a813-SETUP.md': '4452683bb7311a02d93d5473f8803dfd3e786ecc1f0bc1175728af105e860fef',
}


def historical_document(name, data):
    if name not in HISTORICAL_DOCUMENTS:
        return False
    if hashlib.sha256(data).hexdigest() != HISTORICAL_DOCUMENTS[name]:
        raise AssertionError('modified historical document: ' + name)
    return True


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
            if historical_document(relative.as_posix(), path.read_bytes()):
                continue
            documents[relative.as_posix()] = path.read_text(encoding='utf-8')
    return documents, entries


class TestDocsContract(unittest.TestCase):
    def test_historical_executable_fixture_integrity_and_changed_byte_control(self):
        for name, expected in HISTORICAL_EXECUTABLES.items():
            content = (ROOT / name).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), expected)
            self.assertEqual(internal_code_issues(name, content.decode(), []), [])
            self.assertTrue(internal_code_issues(name, content.decode() + '\n# edited\n', []))

    def test_historical_document_exact_bytes_and_changed_byte_control(self):
        for name in HISTORICAL_DOCUMENTS:
            data = (ROOT / name).read_bytes()
            self.assertTrue(historical_document(name, data))
            with self.assertRaises(AssertionError):
                historical_document(name, data + b'edited')
        self.assertFalse(historical_document('ordinary.md', b'ordinary'))

    def test_release_files_contain_no_private_account_identifiers(self):
        names, _baseline = release_review_inputs(ROOT)
        issues = [issue for name in names
                  for issue in private_identifier_issues(name, (ROOT / name).read_bytes())]
        self.assertEqual([], issues, '\n'.join(issues))

    def test_added_code_lines_contain_no_internal_project_wording(self):
        names, baseline = release_review_inputs(ROOT)
        issues = []
        for name in names:
            if name.endswith(('.md', '.txt')):
                continue
            try:
                source = (ROOT / name).read_text()
            except UnicodeDecodeError:
                continue
            issues.extend(internal_code_issues(name, source, release_added_lines(name, source, baseline)))
        self.assertEqual([], issues, '\n'.join(issues))

    def test_private_identifier_controls_do_not_embed_private_values(self):
        token = b'private-test-owner'
        forbidden = {(len(token), hashlib.sha256(token).hexdigest())}
        for content in (token, b'prefix' + token + b'suffix', token.upper(), b'https://example.invalid/' + token):
            self.assertTrue(private_identifier_issues('test.py', content, forbidden))
        self.assertEqual([], private_identifier_issues('test.py', b'example-owner', forbidden))

    def test_internal_code_term_controls(self):
        for text in ('Only Coach creates repositories', 'Astra review', 'worker checkout',
                     'Round 4', 'T3 job', 'reference/jobs/example', 'working/jobs/example'):
            source = 'print(' + repr(text) + ')\n'
            self.assertTrue(internal_code_issues('module.py', source, [(1, source)]))
        valid = 'print("AI Coach Guidance; Coach note:; T3 Code; test_update_round3.py; fixture-source; dev/prototype")'
        self.assertEqual([], internal_code_issues('module.py', valid, [(1, valid)]))
        self.assertEqual([], internal_code_issues('site.cjs', '', [(1, '// no service worker')]))
        for line in PUBLIC_CODE_LINES['examples/sync.py']:
            self.assertEqual([], internal_code_issues('examples/sync.py', '', [(1, line)]))
            self.assertTrue(internal_code_issues('examples/sync.py', '', [(1, line + ' Only Coach operates')]))
        # A new unrelated test cannot hide a project-operator string.
        source = 'def test_unrelated():\n    print("Only Coach creates repositories")\n'
        self.assertTrue(internal_code_issues('dev/tests/test_docs_contract.py', source,
                                            list(enumerate(source.splitlines(), 1))))
        # The diff selects inserted/replaced lines, never unchanged context.
        before = ['same', 'old', 'tail']
        after = ['same', 'new', 'added', 'tail']
        changed = [(i + 1, after[i]) for tag, _a, _b, start, end in
                   difflib.SequenceMatcher(a=before, b=after).get_opcodes()
                   if tag in ('insert', 'replace') for i in range(start, end)]
        self.assertEqual(changed, [(2, 'new'), (3, 'added')])

    def test_unrelated_guidance_survives_update_documentation(self):
        required = {
            'dev/README.md': (
                'A copy left by an older install can be\nignored entirely.',
                'compact snapshots after display additions.',
                'for offline validation, fallback, deletion and reset/retry restoration tests.',
            ),
            'examples/json-manual/SETUP.md': (
                'The legacy direct API publisher is not one of the four supported setup paths.',
            ),
            'examples/json-auto-sync/SETUP.md': (
                'Publication rules allow up to 128 ordinary JSON/PNG files, 64 MiB each, with relative paths up to 240 characters, no hidden components, traversal or symlinks.',
                'Paths that dropped from a valid prior declaration are the only deletion candidates; unrelated repository files remain.',
                'All companions are relative to the folder holding latest.json.',
                'Install, update and rollback refresh the standard README while retaining its sync timestamp; Sync changes only that timestamp between updates.',
                '**Keep your secrets.**',
                'Archive files written by either version can stay side by side.',
            ),
            'examples/json-on-demand/SETUP.md': (
                'Compact forecast snapshots stay bounded.',
                '## Updating an Existing Repository',
                'Use the On-demand template as supplied; do not add the scheduled',
            ),
            'examples/json-local-sync/SETUP.md': (
                'Where a planned event carries a route file, sync.py fetches that attachment from whatever host Intervals.icu records for it.',
                'it also calls `api.github.com` to read and write your repository using the token you supply.',
                'Confirmed local API publication uses the same daily release policy as file exports.',
                'It does not run the old separate changelog-Issue check; an uncertain publication holds maintenance.',
                'including failed attempts. They never advise from unpublished main content.',
            ),
        }
        for name, phrases in required.items():
            text = (ROOT / name).read_text()
            for phrase in phrases:
                with self.subTest(name=name, phrase=phrase):
                    self.assertIn(phrase, text)

    def test_repository_links(self):
        documents, entries = repository_data(ROOT)
        self.assertIn('SECTION_11.md', documents)
        issues, counts = link_issues(documents, entries)
        self.assertGreater(counts.get('local', 0), 0)
        self.assertGreater(counts.get('external', 0), 0)
        self.assertGreater(counts.get('deployment-relative', 0), 0)
        self.assertEqual([], issues, '\n'.join(issues))

    def test_all_repository_markdown_fragment_targets(self):
        # A superset of every Markdown file in the release changed-file list.
        # No external delivery manifest is needed to run the repository suite.
        documents, _entries = repository_data(ROOT)
        issues = markdown_fragment_issues(documents)
        self.assertEqual([], issues, '\n'.join(issues))

    def test_markdown_fragment_controls_include_installed_templates(self):
        documents = {
            'a.md': '# Start\n[local](#start) [other](sub/b.md#caf%C3%A9-1)',
            'sub/b.md': '# Café\n# Café\n',
            'dev/demo/templates/README.md':
                '[update](section11/examples/maintenance/UPDATING.md#automatic-github-updates)',
            'examples/maintenance/UPDATING.md': '# Automatic GitHub updates\n',
        }
        self.assertEqual([], markdown_fragment_issues(documents))
        for name, before, after in (
            ('a.md', '#start)', '#absent)'),
            ('a.md', '#caf%C3%A9-1)', '#caf%C3%A9-2)'),
            ('sub/b.md', '# Café\n# Café', '# Renamed\n# Renamed'),
            ('examples/maintenance/UPDATING.md', 'GitHub updates', 'GitHub review'),
        ):
            with self.subTest(name=name, after=after):
                broken = dict(documents)
                broken[name] = broken[name].replace(before, after)
                self.assertEqual(1, len(markdown_fragment_issues(broken)))

    def test_on_demand_migration_points_to_its_manual_only_editor_route(self):
        source = (ROOT / 'examples/json-on-demand/SETUP.md').read_text()
        section = heading_section(source, 'updating-an-existing-repository')
        self.assertIn('Replace the one sync workflow using Step 2', section)
        self.assertIn('do not add the scheduled', section)
        self.assertIn("template's cron", section)
        self.assertIn('replace both stubs in the same owner commit, before the first Sync', ' '.join(section.split()))
        sample = '# Guide\n## Wrong\nText.\n## Right\n2. **Choose a schedule**\n'
        self.assertNotIn('2.', heading_section(sample, 'wrong'))

    def test_multiline_fragment_links_and_ignored_code(self):
        source = ('# Start\n[local\nlabel](#start)\n'
                  '[other](\nsub/b.md#topic\n)\n'
                  '[reference\nlabel][target]\n\n[target]: sub/b.md#topic\n'
                  '`[code\nlabel](#missing)`\n\n'
                  '```md\n[hidden\nlabel](#missing)\n```\n')
        documents = {'a.md': source, 'sub/b.md': '# Topic\n'}
        self.assertEqual([(2, '#start', 'inline'),
                          (4, 'sub/b.md#topic', 'inline'),
                          (7, 'sub/b.md#topic', 'reference')], markdown_links(source))
        self.assertEqual([], markdown_fragment_issues(documents))
        documents['a.md'] = source.replace('sub/b.md#topic', 'sub/b.md#missing')
        self.assertEqual(2, len(markdown_fragment_issues(documents)))

    def test_restored_context_and_migration_links(self):
        auto = (ROOT / 'examples/json-auto-sync/SETUP.md').read_text()
        demand = (ROOT / 'examples/json-on-demand/SETUP.md').read_text()
        notifications = heading_section(auto, 'update-notifications')
        self.assertIn('owner-controlled copies outside `section11/`', notifications)
        self.assertIn('**`README.md`** is not comparable by template hash.', notifications)
        self.assertIn('[Owner-controlled workflow maintenance](#owner-controlled-workflow-maintenance)', notifications)
        self.assertIn('[migration steps](#updating-an-existing-repository)', auto)
        self.assertIn('[migration steps](#updating-an-existing-repository)', demand)
        overview = heading_section(demand, 'overview')
        self.assertEqual(1, overview.count('sync-declared JSON/PNG file list'))
        self.assertIn('#owner-controlled-workflow-maintenance)', overview)
        self.assertIn('future companion names/folders need only a script update.', overview)
        self.assertIn('Personal files, private request state and active workflows stay outside the managed release.', overview)

    def test_repository_release_prose(self):
        documents, _entries = repository_data(ROOT)
        issues = [issue for name, source in documents.items() for issue in version_issues(name, source)]
        self.assertEqual([], issues, '\n'.join(issues))

    def test_workflow_compatibility_and_history_are_explained(self):
        updating = (ROOT / 'examples/maintenance/UPDATING.md').read_text()
        section = ' '.join(heading_section(updating, 'workflow-compatibility').split())
        self.assertIn('`--wrapper-api` value on its `run:` line', section)
        self.assertIn('[`examples/maintenance/wrapper-api.json`](wrapper-api.json)', section)
        requirements = json.loads((ROOT / 'examples/maintenance/wrapper-api.json').read_text())
        for name, value in requirements.items():
            self.assertIn(f'`{name}` {value}', section)
        self.assertIn('A mismatch stops the updater with `owner wrapper update required`.', section)
        self.assertIn('bootstrap separately pins its trusted verifier', section)
        self.assertIn('unsealed pin stops', section)
        self.assertIn('no raw-main fallback', section)
        self.assertNotIn('### Opt-in automatic GitHub merging', updating)
        rollback = ' '.join(heading_section(updating, 'utc-timing-rejection-and-rollback').split())
        self.assertIn('claims the UTC day before latest-target discovery', rollback)
        self.assertIn('**Update** installs the selected date and clears its skip', rollback)
        self.assertIn('pre-adoption root-only setup requires owner workflow recovery', rollback)
        auto = (ROOT / 'examples/json-auto-sync/SETUP.md').read_text()
        notices = heading_section(auto, 'update-notifications')
        self.assertIn('../maintenance/UPDATING.md#workflow-compatibility', notices)
        self.assertNotIn('API 4', notices)
        local = next(p for p in notices.split('\n\n') if 'For local setups' in p)
        self.assertIn('its automatic toggle never enables automatic GitHub updates.', local)
        self.assertEqual(1, notices.count('../json-local-sync/SETUP.md#staying-up-to-date'))

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
        for owner, target in DEPLOYMENT_LINKS:
            self.assertEqual(('deployment-relative', None), classify_link(owner, target, docs, entries))
            self.assertIsNotNone(classify_link('wrong/' + owner, target, docs, entries)[1])
            self.assertIsNotNone(classify_link(owner, target + '-typo', docs, entries)[1])

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
