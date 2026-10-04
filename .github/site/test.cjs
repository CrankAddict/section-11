'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { build, prepare, select, parse, linkURL, renderDocument, pages, ICONS } = require('./build.cjs');
const icons = require('./generate-icons.cjs');
const root = path.resolve(__dirname, '../..');

function scratch(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'section11-site-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  return directory;
}
function fixture(t) {
  const directory = path.join(scratch(t), 'source');
  fs.cpSync(root, directory, { recursive: true, filter: name =>
    !['node_modules', '_site'].includes(path.basename(name)) });
  return directory;
}

test('build emits only the explicit public inventory', t => {
  const output = path.join(scratch(t), 'public');
  assert.deepEqual(build(root, output), ['LICENSE.txt', 'assets/site.css', 'index.html', ...ICONS, ...pages.map(p => p.route)].sort());
  const index = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
  assert.match(index, /href="getting-started.html"/);
  assert.match(index, /Data first\.<br> Context alongside it\./);
  assert.match(index, /https:\/\/section11\.net\//);
  assert.doesNotMatch(index, /<script|<form|<iframe|<img/i);
  for (const route of ['index.html', ...pages.map(p => p.route)]) {
    const footer = fs.readFileSync(path.join(output, route), 'utf8').match(/<footer>.*<\/footer>/)[0];
    const license = route.includes('/') ? '../LICENSE.txt' : 'LICENSE.txt';
    assert.ok(footer.includes(`<span>Free and open source <span aria-hidden="true">·</span> <a href="${license}">MIT license</a></span>`), route);
  }
});

test('arrows are decorative: up-right leaves the site, right stays on it', t => {
  const output = path.join(scratch(t), 'public');
  build(root, output);
  for (const route of ['index.html', ...pages.map(p => p.route)]) {
    const html = fs.readFileSync(path.join(output, route), 'utf8');
    assert.doesNotMatch(html, /(?<!<span aria-hidden="true">)↗/, route);
    for (const [, href, label] of html.matchAll(/<a [^>]*href="([^"]*)"[^>]*>(.*?)<\/a>/gs)) {
      if (label.includes('<span aria-hidden="true">↗</span>')) assert.match(href, /^https:\/\//, `${route}: ${href}`);
      if (label.includes('<span aria-hidden="true">→</span>')) assert.doesNotMatch(href, /^[a-z]+:/i, `${route}: ${href}`);
    }
    if (route === 'index.html') continue;
    assert.doesNotMatch(html, /class="source-note"/, route);
    assert.match(html, /<a class="source-link" href="https:\/\/github\.com\/CrankAddict\/section-11\/blob\/main\/[^"]+">View Markdown source /, route);
  }
});

test('mobile header keeps Getting started and the repository; the article precedes the guides', t => {
  const output = path.join(scratch(t), 'public');
  build(root, output);
  for (const route of ['index.html', ...pages.map(p => p.route)]) {
    const html = fs.readFileSync(path.join(output, route), 'utf8');
    const header = html.match(/<nav aria-label="Main navigation">(.*?)<\/nav>/)[1];
    const links = [...header.matchAll(/<a(?: class="([^"]*)")? href="[^"]*"[^>]*>(.*?)<\/a>/g)].map(m => [m[1] || '', m[2].replace(/<[^>]*>/g, '').trim()]);
    assert.deepEqual(links, [['nav-secondary', 'Overview'], ['', 'Getting started'], ['nav-secondary', 'Reports'], ['', 'Repository ↗']], route);
    assert.match(header, /<a href="https:\/\/github\.com\/CrankAddict\/section-11">Repository <span aria-hidden="true">↗<\/span><\/a>$/, route);
    assert.equal(html.split('hero-repo').length, route === 'index.html' ? 2 : 1, route);
    if (route === 'index.html') {
      assert.match(html, /<div class="actions"><a class="button" href="getting-started\.html">Getting started <span aria-hidden="true">→<\/span><\/a><a class="text-link hero-repo" href="https:\/\/github\.com\/CrankAddict\/section-11">View repository <span aria-hidden="true">↗<\/span><\/a><\/div>/);
      continue;
    }
    const content = html.indexOf('<div class="doc-content">'), guide = html.indexOf('<aside class="guide-nav">');
    assert.ok(content > 0 && guide > content && guide > html.indexOf('</article>'), route);
    const aside = html.slice(guide, html.indexOf('</aside>', guide));
    for (const p of pages) assert.match(aside, new RegExp(`>${p.title}</a>`), `${route}: ${p.title}`);
    assert.match(aside, /class="source-link"/, route);
  }
  const css = fs.readFileSync(path.join(output, 'assets/site.css'), 'utf8');
  const mobile = css.slice(css.indexOf('@media (max-width: 800px) {'), css.indexOf('@media print'));
  for (const name of ['.nav-secondary', '.hero-repo']) assert.equal(css.split(name).length, 2, name);
  assert.match(mobile, /\.nav-secondary, \.hero-repo \{ display: none; \}/);
  assert.doesNotMatch(css, /nav-repo|nav-full|::before|\.button[^{]*\{[^}]*display: none/);
  assert.match(mobile, /\.site-header \{ flex-wrap: wrap;/);
  assert.match(mobile, /\.site-header nav \{[^}]*margin-left: auto; \}/);
  assert.match(css, /\.doc-layout \{[^}]*grid-template-areas: "guide content";/);
  assert.match(mobile, /\.doc-layout \{[^}]*grid-template-areas: "content" "guide";/);
  assert.match(css, /\.wordmark \{ font-size: 1\.3rem; font-weight: 600; letter-spacing: \.07em;/);
  assert.match(css, /\.wordmark span \{ color: var\(--accent\); font-size: 1\.7rem; font-weight: 750; letter-spacing: -\.08em; margin-left: -\.15rem; \}/);
  // Phone header: tighter gaps and a header-only inset; body and footer keep the shared margin, wrapping stays the fallback.
  assert.match(mobile, /\.site-header, main, footer \{ width: calc\(100% - 2\.5rem\); \}\n  \.site-header \{ flex-wrap: wrap; gap: \.25rem; min-height: 4\.5rem; padding-block: \.9rem; width: calc\(100% - 1rem\); \}\n  \.site-header nav \{ gap: \.45rem \.5rem; margin-left: auto; \}/);
  assert.equal(mobile.split(' width: ').length, 3);
  assert.doesNotMatch(mobile, /nowrap|overflow|font-size|font-weight|footer \{ (?!width: calc\(100% - 2\.5rem\))/);
  assert.match(css, /\.site-header, main, footer \{ width: min\(1160px, calc\(100% - 5rem\)\); margin-inline: auto; \}/);
  assert.match(css, /\.site-header \{ display: flex; justify-content: space-between; align-items: center; gap: 2rem; min-height: 6\.5rem; border-bottom: 1px solid var\(--line\); \}/);
  assert.match(css, /\.site-header nav \{ display: flex; gap: 1\.75rem; flex-wrap: wrap; font-size: \.9375rem; \}/);
  assert.match(css, /\nfooter \{ display: flex; justify-content: space-between; flex-wrap: wrap; gap: 1rem 2rem; border-top: 1px solid var\(--line\); padding-block: 2rem; font-size: \.875rem; color: var\(--muted\); \}/);
});

test('OpenCode stays a Quick Start example; the T3 Code entry stays in Agentic Setup, not Quick Start', () => {
  const docs = prepare(root);
  const start = docs.find(p => p.route === 'getting-started.html');
  const readme = start.original;
  const titles = parse(readme).headings.filter(h => h.level === 3).map(h => h.text);
  assert.deepEqual(titles.slice(titles.indexOf('Hermes Agent'), titles.indexOf('Agentic Tools') + 1), ['Hermes Agent', 'OpenCode', 'Agentic Tools']);
  const entry = readme.slice(readme.indexOf('\n### OpenCode\n'), readme.indexOf('\n### Agentic Tools\n'));
  assert.match(entry, /has not been validated end to end on this runtime\.\n\n\*\*Control interfaces\.\*\* T3 Code provides an interface for supported agents[^\n]*T3 Code is not a separate coaching runtime\.\n$/);
  assert.equal(readme.split('T3 Code').length, 3);
  assert.ok(start.selected.includes('\nChoose your path:\n\n- **[Agentic Platforms](#agentic-setup)**: OpenClaw, Claude Code, ChatGPT Codex, OpenCode, Grok Bot, and Hermes Agent, etc.\n- **[Web Chat Platforms](#web-chat-setup)**: ChatGPT, Claude, Gemini, Grok, Mistral Vibe, etc.\n\n### 4. Make Files Available to Your AI\n'));
  assert.equal(start.selected.split('OpenCode').length, 2);
  assert.equal(linkURL('#agentic-setup', start, docs, root), 'https://github.com/CrankAddict/section-11/blob/main/README.md#agentic-setup');
  const html = renderDocument(start, docs, root);
  assert.ok(html.includes('OpenClaw, Claude Code, ChatGPT Codex, OpenCode, Grok Bot, and Hermes Agent, etc.</li>'));
  assert.doesNotMatch(start.selected + html, /T3 Code|t3\.codes|optional control interface/);
  assert.doesNotMatch(readme + html, /open-weight/i);
});

test('local sync Connect Your Agent ends with open-weight options, control interfaces, then Project instructions', () => {
  const docs = prepare(root);
  const local = docs.find(p => p.route === 'guides/local-sync.html');
  const paragraph = 'Open-weight setups are another option, for example, GLM with ZCode, Qwen with Qwen Code, or DeepSeek through a compatible agent. These are examples, not fixed pairings: choose the models and tools that fit your needs.';
  const note = '[T3 Code](https://t3.codes/) is an optional control interface for supported agents, not a separate coaching runtime.';
  const instructions = '### Project instructions\n\nYour coach\'s instructions live in one canonical contract, not in this guide. Which one you use depends on whether the AI has a runtime filesystem at all, not on which sync method you chose, and not on the platform\'s name. If it has one, whether that is this machine or a provider-hosted computer, it is an agentic session: copy the block between the fences in [`PROJECT_INSTRUCTIONS_AGENTIC.md`](../../PROJECT_INSTRUCTIONS_AGENTIC.md) into the agent\'s project settings. That holds even when the data itself arrives through a connector.\n\nThat contract names the Workout Reference Library (`section11/examples/workout-library/WORKOUT_REFERENCE.md`, with a fetch fallback) but not the report templates. Where the agent can actually reach them (a provider-hosted computer often cannot), point it at `section11/examples/reports/` as well.\n';
  const titles = parse(local.original).headings.filter(h => h.level <= 3).map(h => h.text);
  assert.deepEqual(titles.slice(titles.indexOf('Connect Your Agent'), titles.indexOf('Using with Web Chat Platforms') + 1), ['Connect Your Agent', 'OpenClaw', 'Claude Code', 'Claude Cowork', 'ChatGPT Codex CLI', 'Gemini CLI', 'Hermes Agent', 'Grok Bot (experimental)', 'Open-weight options', 'Control interfaces', 'Project instructions', 'Using with Web Chat Platforms']);
  assert.ok(local.original.includes(`medication or health context.\n\n### Open-weight options\n\n${paragraph}\n\n### Control interfaces\n\n${note}\n\n${instructions}\n---\n\n## Using with Web Chat Platforms\n`));
  assert.equal(local.original.split(/open-weight/i).length, 3);
  assert.equal(local.original.split('T3 Code').length, 2);
  const html = renderDocument(local, docs, root);
  const rendered = '<p><a href="https://t3.codes/">T3 Code</a> is an optional control interface for supported agents, not a separate coaching runtime.</p>';
  assert.ok(html.includes(`<h3 id="open-weight-options">Open-weight options</h3>\n<p>${paragraph}</p>\n<h3 id="control-interfaces">Control interfaces</h3>\n${rendered}\n<h3 id="project-instructions">Project instructions</h3>\n<p>Your coach's instructions live in one canonical contract`));
  assert.match(html, /<code>section11\/examples\/reports\/<\/code> as well\.<\/p>\n<hr>\n<h2 id="using-with-web-chat-platforms">/);
  assert.equal(html.split(paragraph).length, 2);
  assert.equal(html.split(rendered).length, 2);
  for (const page of docs) if (page !== local) assert.doesNotMatch(page.selected, /open-weight|optional control interface|t3\.codes/i, page.route);
});

test('favicon set is generated from one mark, copied to the site root and linked from every page', t => {
  const output = path.join(scratch(t), 'public');
  build(root, output);
  const fresh = icons.generate();
  assert.deepEqual([...fresh.keys()].sort(), [...ICONS].sort());
  assert.deepEqual(fs.readdirSync(path.join(__dirname, 'icons')).sort(), [...ICONS].sort());
  const file = {}, version = {};
  for (const name of ICONS) {
    file[name] = fs.readFileSync(path.join(__dirname, 'icons', name));
    assert.ok(icons.same(name, file[name], fresh.get(name)), `${name} matches generate-icons.cjs`);
    assert.ok(file[name].equals(fs.readFileSync(path.join(output, name))), `${name} copied unchanged`);
    version[name] = crypto.createHash('sha256').update(file[name]).digest('hex').slice(0, 8);
  }
  // Rasters: real dimensions, tile icons keep transparent corners, touch and maskable icons are opaque.
  for (const [name, size, channels] of [['apple-touch-icon.png', 180, 3], ['icon-192.png', 192, 4], ['icon-512.png', 512, 4], ['icon-maskable-512.png', 512, 3]]) {
    const png = icons.decodePng(file[name]);
    assert.deepEqual([png.size, png.channels], [size, channels], name);
  }
  const frames = icons.decodeIco(file['favicon.ico']);
  assert.deepEqual(frames.map(f => f.size), [16, 32, 48]);
  for (const frame of frames) {
    const png = icons.decodePng(frame.png);
    assert.deepEqual([png.size, png.channels], [frame.size, 4]);
    assert.ok(png.pixels[3] < 32, 'rounded corner is transparent');
    const centre = (png.size * (png.size >> 1) + (png.size >> 1)) * 4;
    assert.deepEqual([...png.pixels.subarray(centre, centre + 4)], [...icons.ACCENT, 255]);
  }
  // Maskable: everything that is not background lies inside the centred safe circle.
  const maskable = icons.decodePng(file['icon-maskable-512.png']);
  let marked = 0;
  for (let y = 0; y < 512; y++) for (let x = 0; x < 512; x++) {
    const at = (y * 512 + x) * 3;
    if (icons.ACCENT.every((v, c) => maskable.pixels[at + c] === v)) continue;
    marked++;
    assert.ok(Math.hypot(x + 0.5 - 256, y + 0.5 - 256) <= icons.SAFE_RADIUS * 512, `maskable mark outside the safe zone at ${x},${y}`);
  }
  assert.ok(marked > 20000);
  // One geometry: the SVG is paths in the site palette, with no text, fonts, scripts or external references.
  const svg = file['favicon.svg'].toString();
  assert.match(svg, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#963a21"\/><path fill="#fafafa" d="[MLZ0-9 ]+"\/><\/svg>\n$/);
  const manifest = JSON.parse(file['site.webmanifest'].toString());
  assert.deepEqual(manifest, { name: 'Section 11', short_name: 'Section 11', icons: [
    { src: 'icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
    { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
    { src: 'icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
  ], theme_color: '#fafafa', background_color: '#fafafa', display: 'browser' });
  for (const icon of manifest.icons) assert.ok(fs.existsSync(path.join(output, icon.src)), icon.src);
  assert.equal(fs.existsSync(path.join(output, 'manifest.json')), false);
  for (const route of ['index.html', ...pages.map(p => p.route)]) {
    const html = fs.readFileSync(path.join(output, route), 'utf8'), up = route.includes('/') ? '../' : '';
    assert.ok(html.includes(`<link rel="icon" href="${up}favicon.ico?v=${version['favicon.ico']}" sizes="16x16 32x32 48x48">\n<link rel="icon" href="${up}favicon.svg?v=${version['favicon.svg']}" type="image/svg+xml">\n<link rel="apple-touch-icon" href="${up}apple-touch-icon.png?v=${version['apple-touch-icon.png']}">\n<link rel="manifest" href="${up}site.webmanifest?v=${version['site.webmanifest']}">\n<link rel="stylesheet"`), route);
    assert.equal(html.split('<link rel="icon"').length, 3, route);
    assert.match(html, /img-src 'self'; manifest-src 'self';/, route);
    assert.doesNotMatch(html, /serviceWorker|<script/i, route);
  }
});

test('Quick Start is an exact source section, excluding adjacent sections', () => {
  const source = '# Root\n\n## Before\nNo\n\n## Quick Start\nYes\n\n### Detail\nAlso yes\n\n## After\nNo\n';
  assert.equal(select(source, { source: 'README.md', section: 'Quick Start' }), '## Quick Start\nYes\n\n### Detail\nAlso yes\n\n');
  assert.throws(() => select(source, { source: 'README.md', section: 'Absent' }), /Expected one section/);
  assert.throws(() => select(source + '\n## Quick Start\nDuplicate', { source: 'README.md', section: 'Quick Start' }), /Expected one section/);
});

test('missing selected Markdown fails before output exists', t => {
  const source = fixture(t);
  fs.unlinkSync(path.join(source, pages[1].source));
  const output = path.join(scratch(t), 'public');
  assert.throws(() => build(source, output), /ENOENT/);
  assert.equal(fs.existsSync(output), false);
});

test('unselected Markdown and data never enter output', t => {
  const source = fixture(t);
  fs.writeFileSync(path.join(source, 'UNSELECTED.md'), '# MUST_NOT_SHIP_PRIVATE_SENTINEL');
  fs.writeFileSync(path.join(source, 'latest.json'), '{"private":"MUST_NOT_SHIP_PRIVATE_SENTINEL"}');
  fs.writeFileSync(path.join(source, '.env'), 'MUST_NOT_SHIP_PRIVATE_SENTINEL');
  const output = path.join(scratch(t), 'public');
  const files = build(source, output);
  for (const file of files) assert.ok(!fs.readFileSync(path.join(output, file), 'utf8').includes('MUST_NOT_SHIP_PRIVATE_SENTINEL'));
  assert.ok(!files.includes('latest.json'));
});

test('local, unselected and partial-document links preserve their destination', () => {
  const docs = prepare(root);
  const manual = docs.find(p => p.title === 'Manual export');
  assert.equal(linkURL('../json-auto-sync/SETUP.md#ftp-history-tracking', manual, docs, root), 'github-sync.html#ftp-history-tracking');
  assert.equal(linkURL('../../README.md#quick-start', manual, docs, root), '../getting-started.html#quick-start');
  assert.equal(linkURL('../../README.md#platform-setup', manual, docs, root), 'https://github.com/CrankAddict/section-11/blob/main/README.md#platform-setup');
  assert.equal(linkURL('../../SETUP_ASSISTANT.md', manual, docs, root), 'https://github.com/CrankAddict/section-11/blob/main/SETUP_ASSISTANT.md');
  assert.equal(linkURL('https://intervals.icu', manual, docs, root), 'https://intervals.icu');
});

test('missing links, wrong anchors and traversal fail', () => {
  const docs = prepare(root);
  const page = docs[0];
  assert.throws(() => linkURL('MISSING.md', page, docs, root), /ENOENT/);
  assert.throws(() => linkURL('#wrong-anchor', page, docs, root), /Missing source anchor/);
  assert.throws(() => linkURL('../private.md', page, docs, root), /Unsafe link/);
  assert.throws(() => linkURL('file:///private', page, docs, root), /Unsupported link/);
});

test('source changes flow through and markup cannot load remote resources', () => {
  const docs = prepare(root);
  const page = { ...docs[0], selected: '# Fresh title\nNew source text.\n\n<script>bad()</script>\n\n![Example](https://example.com/tracker.png)\n\n[bad](javascript:alert(1))' };
  const html = renderDocument(page, docs, root);
  assert.match(html, /New source text/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script|<img|href="javascript:/);
});

test('heading IDs include formatting, duplicates and punctuation', () => {
  assert.deepEqual(parse('# Privacy & Security\n## **Repeat**\n## Repeat\n## Repeat-1\n').headings.map(h => h.id), ['privacy--security', 'repeat', 'repeat-1', 'repeat-1-1']);
});

test('stale output is rejected and its bytes are preserved', t => {
  const output = scratch(t);
  const file = path.join(output, 'stale.txt');
  fs.writeFileSync(file, 'preserve');
  assert.throws(() => build(root, output), /Output must be a new directory/);
  assert.equal(fs.readFileSync(file, 'utf8'), 'preserve');
});
