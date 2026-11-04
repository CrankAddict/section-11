'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { build, prepare, select, parse, linkURL, renderDocument, pages, ICONS, shell, headTitle } = require('./build.cjs');
const icons = require('./generate-icons.cjs');
const root = path.resolve(__dirname, '../..');
// The one permitted <script>: an inert JSON-LD data block with no "<" inside. Everything else stays script-free.
const DATA_BLOCK = /<script type="application\/ld\+json">([^<]*)<\/script>/;
const withoutDataBlock = html => html.replace(DATA_BLOCK, '');

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

test('published update guide describes direct updates and sealed release templates', t => {
  const output = path.join(scratch(t), 'public');
  build(root, output);
  const updating = fs.readFileSync(path.join(root, 'examples/maintenance/UPDATING.md'), 'utf8');
  assert.match(updating, /SECTION11_AUTO_UPDATE/);
  assert.match(updating, /blob-pinned source reads/);
  assert.match(updating, /daily allowance limits automatic discovery/);
  assert.doesNotMatch(updating, /review GitHub update PRs/);
  for (const [route, asset] of [['github-sync.html', 'auto-sync.yml'], ['on-demand.html', 'on-demand.yml']]) {
    const guide = fs.readFileSync(route === 'github-sync.html' ? path.join(root, 'examples/json-auto-sync/SETUP.md') : path.join(output, 'guides', route), 'utf8');
    assert.ok(guide.includes('section11-YYYY.MM.DD-' + asset));
    assert.match(guide, /UNSEALED/);
    assert.match(guide, /releases\/latest/);
  }
  const contents = html => [...html.match(/<nav aria-label="On this page"><ul>(.*?)<\/ul><\/nav>/)[1].matchAll(/<a href="#([^"]+)">(.*?)<\/a>/g)].map(m => [m[1], m[2]]);
  for (const [route, id, title, sections] of [
    ['guides/updating.html', 'updating-section-11', 'Updating Section 11', ['Before you update', 'Update on your computer', 'Update on GitHub', 'Automatic updates and undo']],
    ['guides/local-sync.html', 'local-sync-setup-guide', 'Local Sync Setup Guide', ['Get help from your AI', 'Set it up yourself', 'After setup']],
    ['guides/github-sync.html', 'github-sync-setup-guide', 'GitHub Sync Setup Guide', ['Get help from your AI', 'Set up a new repository', 'Already set up?']],
    ['guides/on-demand.html', 'on-demand-sync', 'On-Demand Sync', ['Get help from your AI', 'Set up once', 'Refresh and use your data']],
    ['guides/manual-export.html', 'manual-json-export', 'Manual JSON Export', ['Get help from your AI', 'Install and export', 'Give the files to your AI']],
    ['reports.html', 'report-examples', 'Report Examples', ['Choose a report', 'Ask your AI']],
  ]) {
    const html = fs.readFileSync(path.join(output, route), 'utf8');
    assert.deepEqual(html.match(/<h1\b[^>]*>.*?<\/h1>/g), [`<h1 id="${id}">${title}</h1>`], route);
    assert.doesNotMatch(html, /Start here/, route);
    const headings = [...html.matchAll(/<h2 id="([^"]+)">(.*?)<\/h2>/g)].map(m => [m[1], m[2]]);
    assert.deepEqual(headings.map(h => h[1]), sections, route);
    assert.deepEqual(contents(html), headings, route);
  }
  const start = fs.readFileSync(path.join(output, 'getting-started.html'), 'utf8');
  assert.deepEqual(contents(start), [
    ['1-create-your-dossier-your-stable-private-context', '1. Create Your Dossier: your stable private context'],
    ['2-set-up-your-data-sync', '2. Set Up Your Data Sync'],
    ['3-configure-your-ai-platform', '3. Configure Your AI Platform'],
    ['4-make-files-available-to-your-ai', '4. Make Files Available to Your AI'],
    ['having-trouble', 'Having trouble?'],
  ]);
  assert.ok([['local-sync', 'local-sync-setup-guide', 'Local sync'], ['github-sync', 'github-sync-setup-guide', 'GitHub sync'], ['on-demand', 'on-demand-sync', 'On-demand sync'], ['manual-export', 'manual-json-export', 'Manual export']].every(([name, id, label]) => start.includes(`<a href="guides/${name}.html#${id}">${label}</a>`)));
});

test('build emits only the explicit public inventory', t => {
  const output = path.join(scratch(t), 'public');
  assert.deepEqual(build(root, output), ['LICENSE.txt', 'assets/site.css', 'index.html', 'robots.txt', 'sitemap.xml', ...ICONS, ...pages.map(p => p.route)].sort());
  const index = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
  assert.match(index, /href="getting-started.html"/);
  assert.match(index, /Data first\.<br> Context alongside it\./);
  assert.match(index, /https:\/\/section11\.net\//);
  assert.doesNotMatch(withoutDataBlock(index), /<script|<form|<iframe|<img/i);
  for (const route of ['index.html', ...pages.map(p => p.route)]) {
    const footer = fs.readFileSync(path.join(output, route), 'utf8').match(/<footer>.*<\/footer>/)[0];
    const license = route.includes('/') ? '../LICENSE.txt' : 'LICENSE.txt';
    assert.ok(footer.includes(`<span>Free and open source <span aria-hidden="true">·</span> <a href="${license}">MIT license</a></span>`), route);
    assert.ok(footer.includes('<a href="https://forum.intervals.icu/t/section-11-open-protocol-for-ai-endurance-coaching-chatgpt-claude-grok-mistral/120602">Community discussion</a>'), route);
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

test('OpenCode leaves Quick Start; its full entry and T3 Code stay in Agentic Setup', () => {
  const docs = prepare(root);
  const start = docs.find(p => p.route === 'getting-started.html');
  const readme = start.original;
  const titles = parse(readme).headings.filter(h => h.level === 3).map(h => h.text);
  assert.deepEqual(titles.slice(titles.indexOf('Hermes Agent'), titles.indexOf('Agentic Tools') + 1), ['Hermes Agent', 'OpenCode', 'Agentic Tools']);
  const entry = readme.slice(readme.indexOf('\n### OpenCode\n'), readme.indexOf('\n### Agentic Tools\n'));
  assert.equal(entry, '\n### OpenCode\n\nAn open-source coding agent for the terminal, IDE and desktop.\n\n**Control interfaces.** T3 Code provides an interface for supported agents such as Claude Code, ChatGPT Codex and OpenCode. Section 11 access depends on the underlying agent\'s configured filesystem and tool permissions; T3 Code is not a separate coaching runtime.\n');
  assert.match(entry, /An open-source coding agent for the terminal, IDE and desktop\.\n\n\*\*Control interfaces\.\*\* T3 Code provides an interface for supported agents[^\n]*T3 Code is not a separate coaching runtime\.\n$/);
  assert.equal(readme.split('T3 Code').length, 3);
  assert.ok(start.selected.includes("\n- **Agentic:** open [PROJECT_INSTRUCTIONS_AGENTIC.md](PROJECT_INSTRUCTIONS_AGENTIC.md), copy the text in its grey box (GitHub shows a copy button at the top right) and add it to your agent's persistent configuration. See [Agentic Platforms](#agentic-setup) for your platform (OpenClaw, Claude Code, ChatGPT Codex, Grok Bot, Hermes Agent, etc.).\n- **Web chat:** open [PROJECT_INSTRUCTIONS_WEB.md](PROJECT_INSTRUCTIONS_WEB.md), copy the text in its grey box and paste it into your Project, Space, Gem or custom instructions. See [Web Chat Platforms](#web-chat-setup) for your platform (ChatGPT, Claude, Gemini, Grok, Mistral Vibe, etc.) and [Platform Setup](#platform-setup) for connection details.\n\n### 4. Make Files Available to Your AI\n"));
  assert.doesNotMatch(start.selected, /OpenCode/);
  assert.equal(linkURL('#agentic-setup', start, docs, root), 'https://github.com/CrankAddict/section-11/blob/main/README.md#agentic-setup');
  const html = renderDocument(start, docs, root);
  assert.ok(html.includes('(OpenClaw, Claude Code, ChatGPT Codex, Grok Bot, Hermes Agent, etc.).</li>'));
  assert.doesNotMatch(html, /OpenCode/);
  assert.doesNotMatch(start.selected + html, /T3 Code|t3\.codes|optional control interface/);
  assert.doesNotMatch(readme + html, /open-weight/i);
});

test('local sync Connect Your Agent ends with open-weight options, control interfaces, then Project instructions', () => {
  const docs = prepare(root);
  const local = docs.find(p => p.route === 'guides/local-sync.html');
  const paragraph = 'Open-weight setups are another option, for example, GLM with ZCode, Qwen with Qwen Code, or DeepSeek through a compatible agent. These are examples, not fixed pairings: choose the models and tools that fit your needs.';
  const note = '[T3 Code](https://t3.codes/) is an optional control interface for supported agents, not a separate coaching runtime.';
  const instructions = '### Project instructions\n\nYour coach\'s instructions live in one canonical contract, not in this guide. Which one you use depends on whether the AI has a runtime filesystem at all, not on which sync method you chose, and not on the platform\'s name. If it has one, whether that is this machine or a provider-hosted computer, it is an agentic session: copy the block between the fences in [`PROJECT_INSTRUCTIONS_AGENTIC.md`](../../PROJECT_INSTRUCTIONS_AGENTIC.md) into the agent\'s project settings. That holds even when the data itself arrives through a connector.\n\nThat contract names the Workout Reference Library and report templates. Verify that the agent can read the required files at `section11/examples/workout-library/WORKOUT_REFERENCE.md` and `section11/examples/reports/`; a path on your machine does not establish access from another runtime.\n';
  const titles = parse(local.original).headings.filter(h => h.level <= 3).map(h => h.text);
  assert.deepEqual(titles.slice(titles.indexOf('Connect Your Agent'), titles.indexOf('Using with Web Chat Platforms') + 1), ['Connect Your Agent', 'OpenClaw', 'Claude Code', 'Claude Cowork', 'ChatGPT Codex CLI', 'Gemini CLI', 'OpenCode', 'Hermes Agent', 'Grok Bot (experimental)', 'Open-weight options', 'Control interfaces', 'Project instructions', 'Using with Web Chat Platforms']);
  const opencode = '[OpenCode](https://opencode.ai/docs/) supports multiple model providers. Start it from `~/training-data/` and use the agentic contract under [Project instructions](#project-instructions) below.';
  assert.ok(local.original.includes(`Verify that Gemini CLI can read the required files in the working directory; write and execution access are separate capabilities.\n\n### OpenCode\n\n${opencode}\n\n### Hermes Agent\n`));
  assert.equal(local.original.split('### OpenCode\n').length, 2);
  assert.ok(local.original.includes(`medication or health context.\n\n### Open-weight options\n\n${paragraph}\n\n### Control interfaces\n\n${note}\n\n${instructions}\n---\n\n## Using with Web Chat Platforms\n`));
  assert.equal(local.original.split(/open-weight/i).length, 3);
  assert.equal(local.original.split('T3 Code').length, 2);
  const html = renderDocument({ ...local, selected: local.original }, docs, root);
  assert.ok(html.includes('<h3 id="opencode">OpenCode</h3>\n<p><a href="https://opencode.ai/docs/">OpenCode</a> supports multiple model providers. Start it from <code>~/training-data/</code> and use the agentic contract under <a href="https://github.com/CrankAddict/section-11/blob/main/examples/json-local-sync/SETUP.md#project-instructions">Project instructions</a> below.</p>\n<h3 id="hermes-agent">'));
  const rendered = '<p><a href="https://t3.codes/">T3 Code</a> is an optional control interface for supported agents, not a separate coaching runtime.</p>';
  assert.ok(html.includes(`<h3 id="open-weight-options">Open-weight options</h3>\n<p>${paragraph}</p>\n<h3 id="control-interfaces">Control interfaces</h3>\n${rendered}\n<h3 id="project-instructions">Project instructions</h3>\n<p>Your coach's instructions live in one canonical contract`));
  assert.match(html, /Verify that the agent can read the required files at <code>section11\/examples\/workout-library\/WORKOUT_REFERENCE\.md<\/code> and <code>section11\/examples\/reports\/<\/code>; a path on your machine does not establish access from another runtime\.<\/p>\n<hr>\n<h2 id="using-with-web-chat-platforms">/);
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
    assert.doesNotMatch(route === 'index.html' ? withoutDataBlock(html) : html, /serviceWorker|<script/i, route);
  }
});

test('search metadata, home structured data and sitemap change only the head and add one file', t => {
  const output = path.join(scratch(t), 'public');
  build(root, output);
  const home = { route: 'index.html', searchTitle: 'AI endurance coaching protocol | Section 11',
    description: 'Use ChatGPT, Claude, OpenClaw and other AI tools as your AI coach. Section 11 is a free, open-source protocol built around your data. No hosted backend.' };
  const expected = [home,
    { route: 'getting-started.html', title: 'Getting started', searchTitle: 'Getting started: data sync and AI setup | Section 11', description: 'Set up Section 11 in four steps: write an optional dossier, sync your Intervals.icu training data, choose your AI platform and give it the protocol files.' },
    { route: 'guides/local-sync.html', title: 'Local sync', searchTitle: 'Local sync setup guide for Intervals.icu data | Section 11', description: 'Run sync.py on a machine you control to refresh your Intervals.icu training data on a timer for your AI coach to read. No GitHub needed.' },
    { route: 'guides/github-sync.html', title: 'GitHub sync', searchTitle: 'GitHub sync setup guide for Intervals.icu data | Section 11', description: 'Use GitHub Actions to mirror your Intervals.icu training data to a private repository as JSON, on a schedule or on request, for your AI coach to read.' },
    { route: 'guides/on-demand.html', title: 'On-demand sync', searchTitle: 'On-demand Intervals.icu sync from your browser | Section 11', description: 'Run a fresh Intervals.icu sync from your phone or browser, then connect your AI to your repository or download it as a ZIP. No schedule, no local Python.' },
    { route: 'guides/manual-export.html', title: 'Manual export', searchTitle: 'Manual JSON export of Intervals.icu data | Section 11', description: 'Export Intervals.icu training data as JSON for your AI. Setup includes automatic sync by default; use --no-timer to run exports by hand.' },
    { route: 'reports.html', title: 'Report examples', searchTitle: 'AI coaching report templates and examples | Section 11', description: 'Templates and annotated examples for Section 11 AI coaching reports: pre-workout, post-workout, 7-day, 28-day and season.' },
    { route: 'guides/updating.html', title: 'Updates and rollback', searchTitle: 'Section 11 updates, automatic updates and rollback | Section 11', description: 'Install verified Section 11 releases locally or on GitHub, choose automatic updates, and restore a previous installation when needed.' },
  ];
  // pages.json keeps its routes and UI labels; searchTitle and description feed the head only.
  assert.deepEqual(pages.map(({ route, title, searchTitle, description }) => ({ route, title, searchTitle, description })), expected.slice(1));
  assert.equal(new Set(expected.map(p => p.searchTitle)).size, 8);
  assert.equal(new Set(expected.map(p => p.description)).size, 8);
  assert.equal(headTitle({ title: 'Local sync' }), 'Local sync | Section 11');
  assert.equal(headTitle({ title: 'Local sync', searchTitle: 'Complete | Section 11' }), 'Complete | Section 11');
  const html = {};
  for (const page of expected) {
    const text = html[page.route] = fs.readFileSync(path.join(output, page.route), 'utf8'), up = page.route.includes('/') ? '../' : '';
    assert.ok(text.includes(`<meta name="description" content="${page.description}">\n<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; img-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'none'">\n<title>${page.searchTitle}</title><link rel="canonical" href="https://section11.net/${page.route === 'index.html' ? '' : page.route}">\n`), page.route);
    assert.equal(page.searchTitle.split(' | Section 11').length, 2, page.route);
    assert.equal(text.split('<title>').length, 2, page.route);
    if (page === home) continue;
    // Labels and headings still come from title; no search title leaks into the body.
    assert.ok(text.includes(`<p class="eyebrow">${page.title}</p>`), page.route);
    for (const other of expected.slice(1)) assert.ok(text.includes(`"${other.route === page.route ? ' aria-current="page"' : ''}>${other.title}</a>`), `${page.route}: ${other.title}`);
    assert.ok(text.endsWith(`<link rel="stylesheet" href="${up}assets/site.css"></head>\n` + text.slice(text.indexOf('<body>'))), page.route);
    assert.doesNotMatch(text, /<script/i, page.route);
    for (const leak of expected) assert.ok(!text.slice(text.indexOf('<body>')).includes(leak.searchTitle), `${page.route}: ${leak.searchTitle}`);
  }
  // Home only: exactly one data block, directly before </head>, holding exactly the approved graph.
  const index = html['index.html'];
  assert.equal(index.split(/<script/i).length, 2);
  assert.equal(index.split(/<\/script>/i).length, 2);
  const block = index.match(DATA_BLOCK);
  assert.ok(index.includes(`<link rel="stylesheet" href="assets/site.css">\n${block[0]}</head>\n<body>`));
  const license = 'https://section11.net/LICENSE.txt', website = { '@id': 'https://section11.net/#website' }, project = { '@id': 'https://section11.net/#project' };
  assert.deepEqual(JSON.parse(block[1]), { '@context': 'https://schema.org', '@graph': [
    { '@type': 'WebSite', ...website, url: 'https://section11.net/', name: 'Section 11', description: home.description, inLanguage: 'en', license, about: project },
    { '@type': 'WebPage', '@id': 'https://section11.net/#webpage', url: 'https://section11.net/', name: home.searchTitle, description: home.description, inLanguage: 'en', isPartOf: website, about: project },
    { '@type': 'SoftwareSourceCode', ...project, name: 'Section 11', description: 'An open protocol for deterministic, auditable AI-powered endurance coaching.', url: 'https://section11.net/',
      codeRepository: 'https://github.com/CrankAddict/section-11', license, programmingLanguage: 'Python', isAccessibleForFree: true },
  ] });
  // A hostile value cannot end the data block or add a tag: it stays data and round-trips.
  const hostile = { note: '</script><script>alert(1)</script><!-- <img src=x onerror=alert(1)> & "quoted"' };
  const page = shell('index.html', 'T', 'D', '<p>body</p>', new Map(ICONS.map(name => [name, '0'])), hostile);
  assert.equal(page.split(/<script/i).length, 2);
  assert.equal(page.split(/<\/script>/i).length, 2);
  assert.doesNotMatch(page, /<img|<!--|alert\(1\)</);
  assert.doesNotMatch(page.match(DATA_BLOCK)[1], /</);
  assert.deepEqual(JSON.parse(page.match(DATA_BLOCK)[1]), hostile);
  assert.doesNotMatch(shell('index.html', 'T', 'D', '<p>body</p>', new Map(ICONS.map(name => [name, '0']))), /<script/i);
  // Sitemap: the eight canonical addresses, nothing else, no dates or hints.
  const canonicals = expected.map(p => html[p.route].match(/<link rel="canonical" href="([^"]*)">/)[1]);
  assert.equal(fs.readFileSync(path.join(output, 'sitemap.xml'), 'utf8'),
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${canonicals.map(url => `<url><loc>${url}</loc></url>\n`).join('')}</urlset>\n`);
  assert.deepEqual(canonicals, ['https://section11.net/', ...pages.map(p => `https://section11.net/${p.route}`)]);
  // robots.txt: allow-all plus the sitemap address, nothing else.
  assert.equal(fs.readFileSync(path.join(output, 'robots.txt'), 'utf8'),
    'User-agent: *\nAllow: /\n\nSitemap: https://section11.net/sitemap.xml\n');
});

test('Getting started step 3 supplies the instructions through the existing eight-page navigation', t => {
  const docs = prepare(root);
  const start = docs.find(p => p.route === 'getting-started.html');
  const expected = "### 3. Configure Your AI Platform\n\nAgentic: you use an AI agent such as OpenClaw, usually running on a computer or server that is on a lot or always. Web chat: you use a chat app such as ChatGPT, Claude or Gemini.\n\n- **Agentic:** open [PROJECT_INSTRUCTIONS_AGENTIC.md](PROJECT_INSTRUCTIONS_AGENTIC.md), copy the text in its grey box (GitHub shows a copy button at the top right) and add it to your agent's persistent configuration. See [Agentic Platforms](#agentic-setup) for your platform (OpenClaw, Claude Code, ChatGPT Codex, Grok Bot, Hermes Agent, etc.).\n- **Web chat:** open [PROJECT_INSTRUCTIONS_WEB.md](PROJECT_INSTRUCTIONS_WEB.md), copy the text in its grey box and paste it into your Project, Space, Gem or custom instructions. See [Web Chat Platforms](#web-chat-setup) for your platform (ChatGPT, Claude, Gemini, Grok, Mistral Vibe, etc.) and [Platform Setup](#platform-setup) for connection details.\n\n";
  assert.equal(select(start.original, { source: 'README.md', section: '3. Configure Your AI Platform' }), expected);
  const typeLine = 'Agentic: you use an AI agent such as OpenClaw, usually running on a computer or server that is on a lot or always. Web chat: you use a chat app such as ChatGPT, Claude or Gemini.';
  assert.equal(start.selected.split(typeLine).length, 2);
  assert.doesNotMatch(start.original, /## Connect your AI|#connect-your-ai|#3-give-it-the-files/);
  assert.doesNotMatch(JSON.stringify(pages), /connect-ai|connect-your-ai/);
  const output = path.join(scratch(t), 'public');
  const files = build(root, output);
  assert.equal(files.filter(name => name.endsWith('.html')).length, 8);
  assert.ok(!files.includes('guides/connect-ai.html'));
  for (const name of files.filter(name => name.endsWith('.html') || name === 'sitemap.xml')) {
    assert.doesNotMatch(fs.readFileSync(path.join(output, name), 'utf8'), /connect-ai\.html|#connect-your-ai|#3-give-it-the-files|>Connect your AI</, name);
  }
  const html = fs.readFileSync(path.join(output, start.route), 'utf8');
  const step3 = html.slice(html.indexOf('<h2 id="3-configure-your-ai-platform">'), html.indexOf('<h2 id="4-make-files-available-to-your-ai">'));
  const github = 'https://github.com/CrankAddict/section-11/blob/main/';
  assert.deepEqual([...step3.matchAll(/href="([^"]+)"/g)].map(m => m[1]), [
    github + 'PROJECT_INSTRUCTIONS_AGENTIC.md', github + 'README.md#agentic-setup',
    github + 'PROJECT_INSTRUCTIONS_WEB.md', github + 'README.md#web-chat-setup',
    github + 'README.md#platform-setup',
  ]);
  assert.ok(step3.includes('<p>' + typeLine + '</p>'));
  for (const route of ['guides/local-sync.html', 'guides/github-sync.html', 'guides/on-demand.html', 'guides/manual-export.html']) {
    const article = fs.readFileSync(path.join(output, route), 'utf8').match(/<article class="prose">(.*?)<\/article>/s)[1];
    assert.ok(article.includes('<a href="../getting-started.html#3-configure-your-ai-platform">Section 11\'s project instructions</a>'), route);
  }
});

test('Getting started step 4 preserves the complete access, ZIP, privacy, freshness and check text', () => {
  const start = prepare(root).find(p => p.route === 'getting-started.html');
  const expected = "### 4. Make Files Available to Your AI\n\nIf your AI agent can read your data folder directly, give it access to the installed `section11/` folder and current exported data. For web chat:\n\n- **Local sync:** use a supported cloud connector and check it can read your current data\n  and the installed `section11/` folder. Without working connector access, use the Manual\n  export upload steps below.\n- **GitHub sync or On-demand:** use a connector or a link to your own repository first.\n  If the chat can use neither, open your repository's **Code > Download ZIP** and\n  give that ZIP to the chat or project. It includes the installed protocol and templates.\n- **Manual export:** upload the exported data files, `DOSSIER.md` if used, and a ZIP of the `section11/`\n  folder only. Never zip the whole data folder, which can contain credentials and rollback state.\n\nAn uploaded ZIP is a snapshot. Re-upload for fresh data and after updates, replacing\nthe previous upload. Keep the optional dossier as `DOSSIER.md` at the top of your data folder or repository; replace uploaded copies when it changes. Keep any repository containing it private; Git keeps old versions.\nConnectors may need refresh or re-import; check [Platform Setup](#platform-setup).\n\n**Check it works.** Ask your AI:\n\n> Read my latest.json. When was it generated, and what is my most recent activity? Can you open the Section 11 protocol and the report templates? If a file is missing, tell me which.\n\nCheck that the date is recent and the activity is your latest one in Intervals.icu.\n\n";
  assert.equal(select(start.original, { source: 'README.md', section: '4. Make Files Available to Your AI' }), expected);
});

test('instruction files and setup anchors are required; Manual retains its companion-list link', t => {
  for (const name of ['PROJECT_INSTRUCTIONS_AGENTIC.md', 'PROJECT_INSTRUCTIONS_WEB.md']) {
    const source = fixture(t);
    fs.unlinkSync(path.join(source, name));
    const output = path.join(scratch(t), 'public');
    assert.throws(() => build(source, output), /ENOENT/, name);
    assert.equal(fs.existsSync(output), false, name);
  }
  const docs = prepare(root);
  const start = docs.find(p => p.route === 'getting-started.html');
  const github = 'https://github.com/CrankAddict/section-11/blob/main/';
  assert.throws(() => linkURL('PROJECT_INSTRUCTIONS_WEB.md#missing-instructions', start, docs, root), /Missing source anchor/);
  assert.equal(linkURL('PROJECT_INSTRUCTIONS_WEB.md', start, docs, root), github + 'PROJECT_INSTRUCTIONS_WEB.md');
  assert.ok(start.selected.includes('#platform-setup)'));
  assert.throws(() => renderDocument({ ...start, selected: start.selected.replace('#platform-setup)', '#missing-platform-setup)') }, docs, root), /Missing source anchor/);
  assert.ok(renderDocument(start, docs, root).includes('href="' + github + 'README.md#platform-setup"'));
  const manual = docs.find(p => p.route === 'guides/manual-export.html');
  assert.ok(manual.selected.includes('#use-with-ai)'));
  assert.throws(() => renderDocument({ ...manual, selected: manual.selected.replace('#use-with-ai)', '#missing-companion-list)') }, docs, root), /Missing source anchor/);
  assert.ok(renderDocument(manual, docs, root).includes('href="' + github + 'examples/json-manual/SETUP.md#use-with-ai"'));
});

test('new-repository setup ends with the minutes paragraph and dossier step 1 keeps its heading', t => {
  const output = path.join(scratch(t), 'public');
  build(root, output);
  const github = fs.readFileSync(path.join(output, 'guides/github-sync.html'), 'utf8');
  const minutes = '<p>A private repository uses your GitHub Actions minutes. The default schedule needs about 1,500 a month, more if runs take longer than a minute; GitHub Free includes 2,000. See <a href="https://github.com/CrankAddict/section-11/blob/main/examples/json-auto-sync/SETUP.md#github-actions-minutes">GitHub Actions minutes</a>.</p>';
  assert.equal(github.split('A private repository uses your GitHub Actions minutes.').length, 2);
  assert.ok(github.includes('<p>Set up your AI with <a href="../getting-started.html#3-configure-your-ai-platform">Section 11\'s project instructions</a>.</p>\n' + minutes + '\n<h2 id="already-set-up">Already set up?</h2>'));
  const start = fs.readFileSync(path.join(output, 'getting-started.html'), 'utf8');
  assert.ok(start.includes('<h2 id="1-create-your-dossier-your-stable-private-context">1. Create Your Dossier: your stable private context</h2>\n<p>Create <code>DOSSIER.md</code> at the top of your data folder (or of your repository on GitHub) from the <a href="https://github.com/CrankAddict/section-11/blob/main/DOSSIER_TEMPLATE.md">dossier template</a>'));
  const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
  const step1 = select(readme, { source: 'README.md', section: '1. Create Your Dossier: your stable private context' });
  assert.ok(step1.startsWith("### 1. Create Your Dossier: your stable private context\n\nCreate `DOSSIER.md` at the top of your data folder (or of your repository on GitHub) from the [dossier template](DOSSIER_TEMPLATE.md)"));
  assert.ok(readme.includes("Root `DOSSIER.md` in the data-folder root (repository root on GitHub) is authoritative."));
});

test('Local and Manual step 3 show the same terminal-in-folder sentence', t => {
  const output = path.join(scratch(t), 'public');
  build(root, output);
  const sentence = 'To get there: on Mac, type <code>cd </code> (with a space) in Terminal, drag the folder into the window and press Return; on Windows, open the folder in File Explorer, click the address bar, type <code>powershell</code> and press Enter.';
  for (const route of ['guides/local-sync.html', 'guides/manual-export.html']) {
    const html = fs.readFileSync(path.join(output, route), 'utf8');
    const steps = [...html.match(/<ol>(.*?)<\/ol>/s)[1].matchAll(/<li>(.*?)<\/li>/gs)].map(m => m[1]);
    assert.ok(steps[2].endsWith(sentence), route);
    assert.equal(html.split(sentence).length, 2, route);
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
  assert.equal(linkURL('../json-auto-sync/SETUP.md#ftp-history-tracking', manual, docs, root), 'https://github.com/CrankAddict/section-11/blob/main/examples/json-auto-sync/SETUP.md#ftp-history-tracking');
  assert.equal(linkURL('../maintenance/UPDATING.md#github-update-review', manual, docs, root), 'https://github.com/CrankAddict/section-11/blob/main/examples/maintenance/UPDATING.md#github-update-review');
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
