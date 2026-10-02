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
