'use strict';

// Regenerates the committed favicon set in icons/ from one vector mark, using Node built-ins only.
// Run `node .github/site/generate-icons.cjs` to rewrite icons/, or add `--check` to verify it.
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');

const PAPER = [0xfa, 0xfa, 0xfa];
const ACCENT = [0x96, 0x3a, 0x21];
const hex = c => `#${c.map(v => v.toString(16).padStart(2, '0')).join('')}`;

// The mark: a bold "11" on a 64-unit tile. Each digit is a stem with a flag, so it cannot read as two plain bars.
const VIEW = 64;
const TILE_RADIUS = 12;
const digit = x => [[x, 12], [x + 12, 12], [x + 12, 52], [x, 52], [x, 20], [x - 8, 28], [x - 8, 20]];
const GLYPH = [digit(16), digit(44)];
const SAFE_RADIUS = 0.4; // Maskable icons keep the mark inside a centred circle of this share of the width.
const VARIANTS = {
  tile: { background: 'rounded', scale: 1, alpha: true },      // favicon.svg, favicon.ico, icon-192, icon-512
  touch: { background: 'full', scale: 0.86, alpha: false },    // apple-touch-icon: opaque, the system rounds it
  maskable: { background: 'full', scale: 0.78, alpha: false }, // icon-maskable-512: opaque, mark inside the safe zone
};

function inPolygon(points, x, y) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [xi, yi] = points[i], [xj, yj] = points[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function inTile(x, y) {
  if (x < 0 || y < 0 || x > VIEW || y > VIEW) return false;
  const dx = Math.max(TILE_RADIUS - x, x - (VIEW - TILE_RADIUS), 0), dy = Math.max(TILE_RADIUS - y, y - (VIEW - TILE_RADIUS), 0);
  return dx * dx + dy * dy <= TILE_RADIUS * TILE_RADIUS;
}

// Supersampled coverage; arithmetic only, so the pixels are identical on every platform.
function raster(size, { background, scale, alpha }) {
  const SAMPLES = 8, channels = alpha ? 4 : 3, half = VIEW / 2;
  const pixels = Buffer.alloc(size * size * channels);
  for (let py = 0; py < size; py++) for (let px = 0; px < size; px++) {
    const sum = [0, 0, 0]; let covered = 0;
    for (let sy = 0; sy < SAMPLES; sy++) for (let sx = 0; sx < SAMPLES; sx++) {
      const x = (px + (sx + 0.5) / SAMPLES) * VIEW / size, y = (py + (sy + 0.5) / SAMPLES) * VIEW / size;
      const gx = (x - half) / scale + half, gy = (y - half) / scale + half;
      const colour = GLYPH.some(points => inPolygon(points, gx, gy)) ? PAPER : background === 'full' || inTile(x, y) ? ACCENT : null;
      if (!colour) continue;
      covered++;
      for (let c = 0; c < 3; c++) sum[c] += colour[c];
    }
    const at = (py * size + px) * channels;
    for (let c = 0; c < 3; c++) pixels[at + c] = covered ? Math.round(sum[c] / covered) : 0;
    if (alpha) pixels[at + 3] = Math.round(255 * covered / (SAMPLES * SAMPLES));
  }
  return { size, channels, pixels };
}

function chunk(type, data) {
  const body = Buffer.concat([Buffer.from(type, 'latin1'), data]);
  const out = Buffer.alloc(body.length + 8);
  out.writeUInt32BE(data.length, 0);
  body.copy(out, 4);
  out.writeUInt32BE(zlib.crc32(body), body.length + 4);
  return out;
}
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
function encodePng({ size, channels, pixels }) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header.set([8, channels === 4 ? 6 : 2, 0, 0, 0], 8);
  const row = size * channels, lines = Buffer.alloc((row + 1) * size); // Filter type 0 on every scanline.
  for (let y = 0; y < size; y++) pixels.copy(lines, y * (row + 1) + 1, y * row, (y + 1) * row);
  return Buffer.concat([PNG_SIGNATURE, chunk('IHDR', header), chunk('IDAT', zlib.deflateSync(lines, { level: 9 })), chunk('IEND', Buffer.alloc(0))]);
}
// Reads the PNGs written above (8-bit RGB or RGBA, filter 0), so checks compare pixels rather than compressed bytes.
function decodePng(file) {
  if (!file.subarray(0, 8).equals(PNG_SIGNATURE)) throw new Error('Not a PNG');
  const data = []; let header;
  for (let at = 8; at < file.length;) {
    const length = file.readUInt32BE(at), type = file.toString('latin1', at + 4, at + 8), body = file.subarray(at + 8, at + 8 + length);
    if (zlib.crc32(file.subarray(at + 4, at + 8 + length)) !== file.readUInt32BE(at + 8 + length)) throw new Error(`Bad CRC: ${type}`);
    if (type === 'IHDR') header = body; else if (type === 'IDAT') data.push(body);
    at += length + 12;
  }
  const width = header.readUInt32BE(0), height = header.readUInt32BE(4), channels = { 2: 3, 6: 4 }[header[9]];
  if (width !== height || header[8] !== 8 || !channels || header[12] !== 0) throw new Error('Unsupported PNG');
  const lines = zlib.inflateSync(Buffer.concat(data)), row = width * channels, pixels = Buffer.alloc(row * height);
  if (lines.length !== (row + 1) * height) throw new Error('Unexpected PNG data length');
  for (let y = 0; y < height; y++) {
    if (lines[y * (row + 1)] !== 0) throw new Error('Unsupported PNG filter');
    lines.copy(pixels, y * row, y * (row + 1) + 1, (y + 1) * (row + 1));
  }
  return { size: width, channels, pixels };
}

const ICO_SIZES = [16, 32, 48];
function encodeIco(frames) {
  const header = Buffer.alloc(6 + 16 * frames.length);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(frames.length, 4);
  let offset = header.length;
  frames.forEach(({ size, png }, i) => {
    const at = 6 + 16 * i;
    header.set([size, size, 0, 0], at);
    header.writeUInt16LE(1, at + 4);
    header.writeUInt16LE(32, at + 6);
    header.writeUInt32LE(png.length, at + 8);
    header.writeUInt32LE(offset, at + 12);
    offset += png.length;
  });
  return Buffer.concat([header, ...frames.map(f => f.png)]);
}
function decodeIco(file) {
  if (file.readUInt16LE(0) !== 0 || file.readUInt16LE(2) !== 1) throw new Error('Not an ICO');
  return Array.from({ length: file.readUInt16LE(4) }, (_, i) => {
    const at = 6 + 16 * i, length = file.readUInt32LE(at + 8), offset = file.readUInt32LE(at + 12);
    return { size: file[at], png: file.subarray(offset, offset + length) };
  });
}

function svg() {
  const d = GLYPH.map(points => `M${points.map(p => p.join(' ')).join('L')}Z`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${VIEW} ${VIEW}"><rect width="${VIEW}" height="${VIEW}" rx="${TILE_RADIUS}" fill="${hex(ACCENT)}"/><path fill="${hex(PAPER)}" d="${d}"/></svg>\n`;
}
// Icon metadata only: browser display, no service worker, no install or offline behaviour.
function webmanifest() {
  const icon = (src, size, purpose) => ({ src, sizes: `${size}x${size}`, type: 'image/png', purpose });
  return `${JSON.stringify({
    name: 'Section 11', short_name: 'Section 11',
    icons: [icon('icon-192.png', 192, 'any'), icon('icon-512.png', 512, 'any'), icon('icon-maskable-512.png', 512, 'maskable')],
    theme_color: hex(PAPER), background_color: hex(PAPER), display: 'browser',
  }, null, 2)}\n`;
}

function generate() {
  const png = (size, variant) => encodePng(raster(size, VARIANTS[variant]));
  return new Map([
    ['favicon.svg', Buffer.from(svg())],
    ['favicon.ico', encodeIco(ICO_SIZES.map(size => ({ size, png: png(size, 'tile') })))],
    ['apple-touch-icon.png', png(180, 'touch')],
    ['icon-192.png', png(192, 'tile')],
    ['icon-512.png', png(512, 'tile')],
    ['icon-maskable-512.png', png(512, 'maskable')],
    ['site.webmanifest', Buffer.from(webmanifest())],
  ]);
}

// True when a committed file carries the same content as a fresh render: pixels for images, bytes for text.
function same(name, committed, fresh) {
  const pixels = (a, b) => { const x = decodePng(a), y = decodePng(b); return x.size === y.size && x.channels === y.channels && x.pixels.equals(y.pixels); };
  if (name.endsWith('.png')) return pixels(committed, fresh);
  if (!name.endsWith('.ico')) return committed.equals(fresh);
  const a = decodeIco(committed), b = decodeIco(fresh);
  return a.length === b.length && a.every((frame, i) => frame.size === b[i].size && pixels(frame.png, b[i].png));
}

module.exports = { generate, same, raster, encodePng, decodePng, encodeIco, decodeIco, svg, webmanifest, VARIANTS, ICO_SIZES, SAFE_RADIUS, PAPER, ACCENT };
if (require.main === module) {
  const directory = path.join(__dirname, 'icons');
  const check = process.argv.includes('--check');
  if (!check) fs.mkdirSync(directory, { recursive: true });
  const stale = [];
  for (const [name, data] of generate()) {
    const target = path.join(directory, name);
    if (!check) fs.writeFileSync(target, data);
    else if (!fs.existsSync(target) || !same(name, fs.readFileSync(target), data)) stale.push(name);
  }
  if (stale.length) throw new Error(`icons/ does not match the generator: ${stale.join(', ')}`);
  console.log(check ? 'icons/ matches the generator.' : `Wrote ${directory}`);
}
