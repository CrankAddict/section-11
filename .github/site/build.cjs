'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const MarkdownIt = require('markdown-it');
const pages = require('./pages.json');
const REPOSITORY = 'https://github.com/CrankAddict/section-11';
const SITE = 'https://section11.net/';
// Committed in icons/ and copied to the site root; generate-icons.cjs regenerates them.
const ICONS = ['favicon.ico', 'favicon.svg', 'apple-touch-icon.png', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'site.webmanifest'];
const ICON_LINKS = [['icon', 'favicon.ico', ' sizes="16x16 32x32 48x48"'], ['icon', 'favicon.svg', ' type="image/svg+xml"'], ['apple-touch-icon', 'apple-touch-icon.png', ''], ['manifest', 'site.webmanifest', '']];
const md = new MarkdownIt({ html: false, linkify: false, typographer: false });
const escape = md.utils.escapeHtml;
const relative = (from, to) => path.posix.relative(path.posix.dirname(from), to);

// Heading IDs follow the punctuation/space rules used by these source documents.
// Work on Markdown tokens, never a second Markdown parser.
function headingText(token) {
  return (token.children || []).map(t => t.type === 'image' ? t.content :
    ['text', 'code_inline'].includes(t.type) ? t.content : '').join('');
}
function slug(text) {
  return text.toLowerCase().replace(/[^\p{L}\p{N}\p{M}_\-\s]/gu, '').replace(/\s/g, '-');
}
function parse(source) {
  const tokens = md.parse(source, {});
  const used = new Set();
  const headings = [];
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].type !== 'heading_open') continue;
    const text = headingText(tokens[i + 1]);
    const base = slug(text);
    let id = base;
    for (let n = 1; used.has(id); n++) id = `${base}-${n}`;
    used.add(id);
    tokens[i].attrSet('id', id);
    headings.push({ text, id, level: Number(tokens[i].tag.slice(1)), line: tokens[i].map[0] });
  }
  return { tokens, headings };
}

function ordinary(root, name, encoding = 'utf8') {
  if (!name || path.posix.isAbsolute(name) || name.split('/').some(p => !p || p === '..' || p === '.')) {
    throw new Error(`Unsafe source path: ${name}`);
  }
  let target = root;
  for (const part of name.split('/')) {
    target = path.join(target, part);
    if (fs.lstatSync(target).isSymbolicLink()) throw new Error(`Symlink input: ${name}`);
  }
  if (!fs.statSync(target).isFile()) throw new Error(`Not an ordinary file: ${name}`);
  return fs.readFileSync(target, encoding);
}

function select(source, page) {
  if (!page.section) return source;
  const headings = parse(source).headings;
  const matches = headings.filter(h => h.text === page.section);
  if (matches.length !== 1) throw new Error(`Expected one section: ${page.source} / ${page.section}`);
  const start = matches[0];
  const end = headings.find(h => h.line > start.line && h.level <= start.level);
  return source.split(/(?<=\n)/).slice(start.line, end ? end.line : undefined).join('');
}

function sourceURL(source, fragment = '') {
  return `${REPOSITORY}/blob/main/${source.split('/').map(encodeURIComponent).join('/')}${fragment}`;
}

function prepare(root) {
  const routes = new Set(['index.html']);
  return pages.map(page => {
    if (!/^(?:[a-z0-9-]+\/)*[a-z0-9-]+\.html$/.test(page.route) || routes.has(page.route)) {
      throw new Error(`Invalid or duplicate route: ${page.route}`);
    }
    if (!page.source.endsWith('.md') || page.source.split('/').some(p => p.startsWith('.'))) {
      throw new Error(`Not public Markdown: ${page.source}`);
    }
    routes.add(page.route);
    const original = ordinary(root, page.source);
    const selected = select(original, page);
    return { ...page, original, selected, ...parse(selected) };
  });
}

function linkURL(href, page, documents, root) {
  if (/^(https?:|mailto:)/i.test(href)) return href;
  if (/^(?:[a-z][a-z0-9+.-]*:|\/\/|\/)/i.test(href)) throw new Error(`Unsupported link: ${href}`);
  const [rawPath, rawFragment] = href.split('#');
  const fragment = rawFragment === undefined ? '' : `#${rawFragment}`;
  const target = rawPath ? path.posix.normalize(path.posix.join(path.posix.dirname(page.source), decodeURIComponent(rawPath))) : page.source;
  if (target.startsWith('../') || target.split('/').some(p => p.startsWith('.'))) throw new Error(`Unsafe link: ${href}`);
  const file = path.join(root, target);
  // Links to public directories stay on GitHub; nothing is recursively copied.
  if (fs.existsSync(file) && fs.lstatSync(file).isDirectory()) {
    return `${REPOSITORY}/tree/main/${target.replace(/\/$/, '')}${fragment}`;
  }
  const source = ordinary(root, target); // Missing local references fail the build.
  if (fragment && target.endsWith('.md') && !parse(source).headings.some(h => h.id === decodeURIComponent(rawFragment))) {
    throw new Error(`Missing source anchor: ${target}${fragment}`);
  }
  const local = documents.find(d => d.source === target && (!d.section ||
    (fragment && d.headings.some(h => h.id === decodeURIComponent(rawFragment)))));
  if (local) return `${relative(page.route, local.route)}${fragment}`;
  return sourceURL(target, fragment);
}

// Never embed remote images, scripts or raw HTML from repository Markdown.
md.renderer.rules.image = (tokens, i) => `<span class="image-description">${escape(tokens[i].content)}</span>`;
md.renderer.rules.table_open = () => '<div class="table-scroll" role="region" aria-label="Reference table" tabindex="0"><table>\n';
md.renderer.rules.table_close = () => '</table></div>\n';

function renderDocument(page, documents, root) {
  const tokens = parse(page.selected).tokens;
  const firstHeading = tokens.find(t => t.type === 'heading_open');
  const shift = Number(firstHeading.tag.slice(1)) - 1;
  for (const token of tokens) {
    if (['heading_open', 'heading_close'].includes(token.type)) token.tag = `h${Number(token.tag.slice(1)) - shift}`;
    for (const child of token.children || []) {
      if (child.type === 'link_open') child.attrSet('href', linkURL(child.attrGet('href'), page, documents, root));
    }
  }
  return md.renderer.render(tokens, md.options, {});
}

function shell(route, title, description, content, icons) {
  // Secondary links stay in every header; site.css hides them only at the mobile breakpoint.
  const nav = [ ['index.html', 'Overview', true], ['getting-started.html', 'Getting started'], ['reports.html', 'Reports', true] ];
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="${escape(description)}">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; img-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'none'">
<title>${escape(title)} | Section 11</title><link rel="canonical" href="${SITE}${route === 'index.html' ? '' : route}">
${ICON_LINKS.map(([rel, name, attributes]) => `<link rel="${rel}" href="${relative(route, name)}?v=${icons.get(name)}"${attributes}>`).join('\n')}
<link rel="stylesheet" href="${relative(route, 'assets/site.css')}"></head>
<body><a class="skip" href="#main">Skip to content</a>
<header class="site-header"><a class="wordmark" href="${relative(route, 'index.html')}" aria-label="Section 11 home">SECTION <span>11</span></a>
<nav aria-label="Main navigation">${nav.map(([url, label, secondary]) => `<a${secondary ? ' class="nav-secondary"' : ''} href="${relative(route, url)}"${url === route ? ' aria-current="page"' : ''}>${label}</a>`).join('')}<a href="${REPOSITORY}">Repository <span aria-hidden="true">↗</span></a></nav></header>
<main id="main">${content}</main>
<footer><span>Section 11 <span aria-hidden="true">/</span> by <a href="${REPOSITORY}">CrankAddict</a></span><span>Free and open source <span aria-hidden="true">·</span> <a href="${relative(route, 'LICENSE.txt')}">MIT license</a></span><span>Open protocol. Athlete-controlled data.</span></footer>
</body></html>\n`;
}

function landing() {
  return `<section class="hero"><p class="eyebrow">An open protocol for endurance coaching</p>
<h1>Your training data.<br>A clearer conversation.</h1>
<p class="lead">Give your AI coach a framework for working with your actual training data: what to read, how to interpret it, and when to ask for more.</p>
<div class="actions"><a class="button" href="getting-started.html">Getting started <span aria-hidden="true">→</span></a><a class="text-link hero-repo" href="${REPOSITORY}">View repository <span aria-hidden="true">↗</span></a></div>
<p class="hero-note">For endurance athletes using AI alongside their training, in AI chats or agentic setups.</p></section>
<section class="overview" aria-labelledby="how"><div><p class="eyebrow">How it fits together</p><h2 id="how">Data first.<br> Context alongside it.</h2></div>
<ol class="principles"><li><span class="number">01</span><div><h3>Your training data</h3><p>Sync your data from Intervals.icu, automatically or as a one-off export. Current metrics come from your data, with history loaded when the question needs it.</p></div></li>
<li><span class="number">02</span><div><h3>A shared set of rules</h3><p>The protocol defines coaching, planning and validation rules. Your optional private dossier adds goals, constraints and preferences.</p></div></li>
<li><span class="number">03</span><div><h3>A more useful review</h3><p>Use structured pre-workout briefings, session analysis and longer-term reviews to connect the data to your training questions.</p><a href="reports.html">Explore report examples <span aria-hidden="true">→</span></a></div></li></ol></section>
<section class="reading" aria-labelledby="explore"><div><p class="eyebrow">Read the project</p><h2 id="explore">Start with the essentials.</h2></div><div class="reading-links">
<a href="getting-started.html"><span>Getting started</span><span>Choose your setup <span aria-hidden="true">→</span></span></a>
<a href="${sourceURL('SECTION_11.md')}"><span>The protocol</span><span>Coaching rules and validation <span aria-hidden="true">↗</span></span></a>
<a href="${REPOSITORY}/tree/main/examples/workout-library"><span>Workout reference</span><span>Structured session templates <span aria-hidden="true">↗</span></span></a></div></section>
<section class="limits" aria-labelledby="limits"><h2 id="limits">Keep the limits in view.</h2><div><p>Section 11 is a protocol and a set of tools. You choose the AI and the services that handle your data; Section 11 operates no hosted backend. Keep your training exports and athlete dossier private.</p><p>AI can still make mistakes. This is not medical advice, a replacement for a human coach, or a guarantee of performance.</p><a href="${sourceURL('README.md', '#privacy--security')}">Privacy and data handling <span aria-hidden="true">↗</span></a></div></section>`;
}

function build(root, output) {
  root = path.resolve(root);
  output = path.resolve(output);
  if (fs.existsSync(output)) throw new Error('Output must be a new directory; inspect and remove old output separately.');
  const documents = prepare(root);
  const files = new Map();
  // Icon links carry a short content hash, so a changed icon is not served from an old favicon cache.
  const icons = new Map();
  for (const name of ICONS) {
    const data = ordinary(root, `.github/site/icons/${name}`, null);
    files.set(name, data);
    icons.set(name, crypto.createHash('sha256').update(data).digest('hex').slice(0, 8));
  }
  files.set('index.html', shell('index.html', 'AI coaching protocol', 'An open framework for AI-assisted endurance coaching, grounded in your training data.', landing(), icons));
  for (const page of documents) {
    const article = renderDocument(page, documents, root);
    const toc = page.headings.filter(h => h.level === (page.section ? 3 : 2));
    const sourceLink = sourceURL(page.source, page.section ? `#${slug(page.section)}` : '');
    const sidebar = `<aside class="guide-nav"><p class="eyebrow">Setup &amp; examples</p><nav aria-label="Guide navigation">${documents.map(d => `<a href="${relative(page.route, d.route)}"${d.route === page.route ? ' aria-current="page"' : ''}>${escape(d.title)}</a>`).join('')}</nav><a class="source-link" href="${sourceLink}">View Markdown source <span aria-hidden="true">↗</span></a></aside>`;
    const contents = `<details class="toc"><summary>On this page</summary><nav aria-label="On this page"><ul>${toc.map(h => `<li><a href="#${escape(h.id)}">${escape(h.text)}</a></li>`).join('')}</ul></nav></details>`;
    // Article first in reading and focus order; site.css keeps the guide column on the left on desktop.
    files.set(page.route, shell(page.route, page.title, page.description, `<div class="doc-layout"><div class="doc-content"><p class="eyebrow">${escape(page.title)}</p>${contents}<article class="prose">${article}</article></div>${sidebar}</div>`, icons));
  }
  files.set('assets/site.css', ordinary(root, '.github/site/site.css'));
  files.set('LICENSE.txt', ordinary(root, 'LICENSE'));
  // All rendering and link checks finish before any output is written.
  for (const [name, data] of files) {
    const target = path.join(output, name);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, data, { flag: 'wx' });
  }
  return [...files.keys()].sort();
}

module.exports = { build, prepare, select, parse, linkURL, renderDocument, pages, ICONS };
if (require.main === module) {
  const root = path.resolve(__dirname, '../..');
  const output = process.argv[2] || path.join(__dirname, '_site');
  console.log(JSON.stringify({ output: path.resolve(output), files: build(root, output) }, null, 2));
}
