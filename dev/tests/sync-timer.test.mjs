// Maintainer-only, offline: node --test dev/tests/sync-timer.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('../../examples/json-auto-sync/sync-timer/sync-timer.js', import.meta.url), 'utf8');
// Import the unchanged .js bytes as an ES module without adding package bindings.
const moduleURL = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const secret = 'github_pat_SYNTHETIC_SECRET_SENTINEL';
const repository = 'timer-owner/private.training-data';
const env = { GITHUB_TOKEN: secret, GITHUB_REPOSITORY: repository };
const epoch = Date.parse('2026-11-07T12:00:00Z');

async function harness(t, replies) {
  const requests = [], logs = [], waits = [], signals = [], pending = new Map();
  let now = epoch;
  let nextId = 0;
  t.mock.method(Date, 'now', () => now);
  t.mock.method(globalThis, 'setTimeout', (callback, delay) => {
    const id = ++nextId;
    pending.set(id, { callback, delay });
    if (delay !== 10_000) {
      waits.push(delay);
      queueMicrotask(() => {
        if (pending.delete(id)) { now += delay; callback(); }
      });
    }
    return id;
  });
  t.mock.method(globalThis, 'clearTimeout', id => pending.delete(id));
  for (const method of ['log', 'info', 'warn', 'error', 'debug']) {
    t.mock.method(console, method, (...args) => logs.push(args));
  }
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    requests.push({ url, options });
    signals.push(options.signal);
    const reply = replies[requests.length - 1];
    assert.ok(reply, 'unexpected additional POST');
    if (reply.network) throw new Error(`${secret} ${repository} ${url} Authorization: Bearer ${secret}`);
    if (reply.timeout) {
      queueMicrotask(() => {
        const entry = [...pending].find(([, timer]) => timer.delay === 10_000);
        assert.ok(entry, 'request must have a deadline');
        const [id, timer] = entry;
        pending.delete(id);
        now += timer.delay;
        timer.callback();
      });
      return new Promise(() => {}); // Also prove the deadline bounds a stuck fetch.
    }
    now += reply.latency || 0;
    return {
      status: reply.status,
      headers: new Headers(reply.headers),
      body: { cancel: async () => {} },
      text() { throw new Error(`must not read body: ${secret}`); },
      json() { throw new Error(`must not read body: ${secret}`); },
    };
  });
  const timer = (await import(moduleURL)).default;
  return {
    timer, requests, logs, waits, signals, pending,
    elapsed: () => now - epoch,
    async tick(settings = env) {
      let error;
      try { await timer.scheduled({}, settings, {}); } catch (failure) { error = failure; }
      const output = JSON.stringify(logs) + (error ? String(error) : '');
      for (const value of [secret, repository, 'api.github.com', 'Bearer', 'Authorization']) {
        assert.ok(!output.includes(value), 'logs/errors must not disclose request details');
      }
      assert.ok(logs.every(args => args.length === 1 && Number.isInteger(args[0])), 'log status codes only');
      assert.equal(pending.size, 0, 'all timers must be cleared');
      assert.ok(requests.length <= 3, 'POST cap');
      assert.ok(waits.every(delay => delay <= 5000), 'wait cap');
      assert.ok(now - epoch <= 40_000, 'tick duration cap');
      return error;
    },
  };
}

test('exact fixed dispatch URL, body, headers and default ref', async t => {
  const h = await harness(t, [{ status: 204 }]);
  assert.equal(await h.tick(), undefined);
  assert.equal(h.requests.length, 1);
  const { url, options } = h.requests[0];
  assert.equal(url, 'https://api.github.com/repos/timer-owner/private.training-data/actions/workflows/auto-sync.yml/dispatches');
  assert.equal(options.method, 'POST');
  assert.equal(options.redirect, 'manual');
  assert.equal(options.body, '{"ref":"main","inputs":{"operation":"Sync timer"}}');
  assert.deepEqual(options.headers, {
    Authorization: `Bearer ${secret}`,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'section11-sync-timer',
    'Content-Type': 'application/json',
  });
  assert.ok(options.signal instanceof AbortSignal);
  assert.deepEqual(h.logs, [[204]]);
  assert.deepEqual(h.waits, []);
});

for (const ref of ['master', 'release/2026.11', 'main-2', 'feature_1', 'branche-é']) {
  test(`accepts a valid configured ref: ${ref}`, async t => {
    const h = await harness(t, [{ status: 204 }]);
    assert.equal(await h.tick({ ...env, GITHUB_REF: ref }), undefined);
    assert.deepEqual(JSON.parse(h.requests[0].options.body), { ref, inputs: { operation: 'Sync timer' } });
  });
}

for (const [key, values] of Object.entries({
  GITHUB_TOKEN: [undefined, null, 42, '', ' ', `${secret}\n`, `${secret}\r`, `${secret}\t`, 'tok en', 'tök', '\0'],
  GITHUB_REPOSITORY: [undefined, null, 42, '', 'owner', '/name', 'owner/', 'a/b/c', 'a/..', 'a/.', '../repo',
    'https://github.com/a/b', 'a/b?x=y', 'a/b#hash', 'a%2fb/c', ' a/b', 'a/b\n', 'a/b\u2028', 'a/b\\c',
    `${'a'.repeat(40)}/repo`, `a/${'b'.repeat(101)}`],
  GITHUB_REF: [null, 42, '', ' ', 'main\n', 'a b', '..', 'a..b', '@', 'a@{b', 'a:b', 'a?b', 'a*b', 'a[b',
    'a\\b', 'a~b', 'a^b', '/main', 'main/', 'a//b', '.main', 'a/.b', 'main.', 'a.lock', 'a.lock/b', 'a\0b', 'a'.repeat(1025)],
})) {
  values.forEach((value, index) => {
    test(`invalid ${key} case ${index + 1} fails before fetch without echoing values`, async t => {
      const h = await harness(t, []);
      const error = await h.tick({ ...env, [key]: value });
      assert.ok(error instanceof Error);
      assert.ok(error.message.startsWith(`Sync timer: invalid ${key} (`));
      assert.equal(h.requests.length, 0);
      assert.deepEqual(h.waits, []);
      assert.deepEqual(h.logs, []);
    });
  });
}

test('absent environment fails safely', async t => {
  const h = await harness(t, []);
  const error = await h.tick(null);
  assert.match(error.message, /invalid GITHUB_TOKEN/);
  assert.equal(h.requests.length, 0);
});

for (const status of [200, 201, 202, 204, 206, 299]) {
  test(`never retries successful HTTP ${status}, even with rate headers`, async t => {
    const h = await harness(t, [{ status, headers: { 'Retry-After': '500', 'X-RateLimit-Remaining': '0' } }]);
    assert.equal(await h.tick(), undefined);
    assert.equal(h.requests.length, 1);
    assert.deepEqual(h.waits, []);
  });
}

for (const status of [0, 301, 302, 307, 308, 400, 401, 403, 404, 408, 422, 429, 499]) {
  test(`stops on HTTP ${status} without following redirects or retrying`, async t => {
    const h = await harness(t, [{ status, headers: { Location: 'https://untrusted.invalid/' } }]);
    assert.equal((await h.tick()).message, `Sync timer: HTTP ${status}`);
    assert.equal(h.requests.length, 1);
    assert.deepEqual(h.waits, []);
  });
}

for (const status of [403, 429]) {
  test(`rate-limited HTTP ${status} ends the tick even with a short Retry-After`, async t => {
    const h = await harness(t, [{ status, headers: { 'Retry-After': '1', 'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': String(epoch / 1000 + 1) } }]);
    assert.equal((await h.tick()).message, `Sync timer: HTTP ${status}`);
    assert.equal(h.requests.length, 1);
    assert.deepEqual(h.waits, []);
  });
}

for (const status of [500, 502, 503, 504, 599]) {
  test(`retries HTTP ${status} then stops at successful acceptance`, async t => {
    const h = await harness(t, [{ status }, { status: 204 }]);
    assert.equal(await h.tick(), undefined);
    assert.equal(h.requests.length, 2);
    assert.deepEqual(h.waits, [1000]);
  });
}

test('persistent 5xx uses exactly three POSTs and throws the last status', async t => {
  const h = await harness(t, [{ status: 500 }, { status: 502 }, { status: 503 }]);
  assert.equal((await h.tick()).message, 'Sync timer: HTTP 503');
  assert.equal(h.requests.length, 3);
  assert.deepEqual(h.waits, [1000, 2000]);
});

test('network errors retry but never expose original exceptions', async t => {
  const h = await harness(t, [{ network: true }, { network: true }, { network: true }]);
  assert.equal((await h.tick()).message, 'Sync timer: network error');
  assert.equal(h.requests.length, 3);
  assert.deepEqual(h.waits, [1000, 2000]);
  assert.deepEqual(h.logs, []);
});

test('network error then acceptance does not retry again', async t => {
  const h = await harness(t, [{ network: true }, { status: 204 }]);
  assert.equal(await h.tick(), undefined);
  assert.equal(h.requests.length, 2);
});

test('a terminal status after a transient error stops immediately', async t => {
  const h = await harness(t, [{ status: 503 }, { status: 401 }]);
  assert.equal((await h.tick()).message, 'Sync timer: HTTP 401');
  assert.equal(h.requests.length, 2);
  assert.deepEqual(h.waits, [1000]);
});

test('timeouts abort each request and are bounded even when fetch never settles', async t => {
  const h = await harness(t, [{ timeout: true }, { timeout: true }, { timeout: true }]);
  assert.equal((await h.tick()).message, 'Sync timer: request timeout');
  assert.equal(h.elapsed(), 33_000);
  assert.ok(h.signals.every(signal => signal.aborted));
});

test('timeout followed by acceptance is not retried again', async t => {
  const h = await harness(t, [{ timeout: true }, { status: 204 }]);
  assert.equal(await h.tick(), undefined);
  assert.equal(h.requests.length, 2);
  assert.equal(h.signals[0].aborted, true);
});

const dateAt = seconds => new Date(epoch + seconds * 1000).toUTCString();
for (const [label, headers, wait] of [
  ['seconds', { 'Retry-After': '3' }, 3000],
  ['zero uses backoff', { 'Retry-After': '0' }, 1000],
  ['HTTP date', { 'Retry-After': dateAt(4) }, 4000],
  ['past HTTP date', { 'Retry-After': dateAt(-5) }, 1000],
  ['exact cap', { 'Retry-After': '5' }, 5000],
  ['primary reset', { 'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': String(epoch / 1000 + 3) }, 3000],
  ['past reset', { 'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': String(epoch / 1000 - 5) }, 1000],
  ['both signals use longer wait', { 'Retry-After': '2', 'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': String(epoch / 1000 + 4) }, 4000],
  ['nonempty budget ignores reset', { 'X-RateLimit-Remaining': '20', 'X-RateLimit-Reset': String(epoch / 1000 + 100) }, 1000],
]) {
  test(`5xx honors bounded rate wait: ${label}`, async t => {
    const h = await harness(t, [{ status: 503, headers }, { status: 204 }]);
    assert.equal(await h.tick(), undefined);
    assert.deepEqual(h.waits, [wait]);
  });
}

for (const [label, headers] of [
  ['over cap', { 'Retry-After': '6' }],
  ['long date', { 'Retry-After': dateAt(60) }],
  ['unreadable Retry-After', { 'Retry-After': secret }],
  ['negative Retry-After', { 'Retry-After': '-1' }],
  ['non-integer Retry-After', { 'Retry-After': '0.5' }],
  ['empty Retry-After', { 'Retry-After': '' }],
  ['overflow Retry-After', { 'Retry-After': '9'.repeat(400) }],
  ['invalid date', { 'Retry-After': 'Sat, 99 Nov 2026 12:00:00 GMT' }],
  ['long primary reset', { 'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': String(epoch / 1000 + 6) }],
  ['missing reset', { 'X-RateLimit-Remaining': '0' }],
  ['invalid reset', { 'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': secret }],
  ['overflow reset', { 'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': '9'.repeat(400) }],
  ['short Retry-After cannot override reset', { 'Retry-After': '1', 'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': String(epoch / 1000 + 60) }],
]) {
  test(`5xx gives up this tick: ${label}`, async t => {
    const h = await harness(t, [{ status: 503, headers }]);
    assert.equal((await h.tick()).message, 'Sync timer: HTTP 503');
    assert.equal(h.requests.length, 1);
    assert.deepEqual(h.waits, []);
  });
}

test('two maximum waits then a timed-out final request remain bounded', async t => {
  const h = await harness(t, [
    { status: 503, latency: 9999, headers: { 'Retry-After': '5' } },
    { status: 503, latency: 9999, headers: { 'Retry-After': '5' } },
    { timeout: true },
  ]);
  assert.equal((await h.tick()).message, 'Sync timer: request timeout');
  assert.deepEqual(h.waits, [5000, 5000]);
  assert.equal(h.elapsed(), 39_998);
});

test('ticks do not retain retry state', async t => {
  const h = await harness(t, [{ status: 401 }, { status: 204 }]);
  assert.equal((await h.tick()).message, 'Sync timer: HTTP 401');
  assert.equal(await h.tick(), undefined);
  assert.equal(h.requests.length, 2);
});

test('all HTTP methods and paths return 404 without dispatch or configuration', async t => {
  const h = await harness(t, []);
  for (const method of ['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']) {
    for (const path of ['/', '/dispatch', '/?operation=Rollback', '/secret']) {
      const response = await h.timer.fetch(new Request(`https://timer.invalid${path}`, { method }), null, {});
      assert.equal(response.status, 404);
      assert.equal(await response.text(), 'Not found');
    }
  }
  assert.equal(h.requests.length, 0);
  assert.deepEqual(h.logs, []);
  assert.equal(h.pending.size, 0);
});
