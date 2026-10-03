'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { build, prepare, select, parse, linkURL, renderDocument, pages } = require('./build.cjs');
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
  assert.deepEqual(build(root, output), ['LICENSE.txt', 'assets/site.css', 'index.html', ...pages.map(p => p.route)].sort());
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
