const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const flush = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); };

function harness() {
  const slots = []; let cursor = 0, pending = [], load, deps, result, poll, timerId = 0;
  const timers = new Map();
  const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
  const react = {
    useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = initial; return [slots[i], value => { slots[i] = typeof value === 'function' ? value(slots[i]) : value; }]; },
    useRef(initial) { const i = cursor++; return slots[i] ??= { current: initial }; },
    useCallback(fn, ds) { const i = cursor++; if (!same(slots[i]?.deps, ds)) slots[i] = { deps: ds, fn }; return slots[i].fn; },
    useEffect(fn, ds) { const i = cursor++; if (!same(slots[i]?.deps, ds)) pending.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps: ds, cleanup: fn() }; }); },
  };
  class ApiError extends Error { constructor(status, code, message) { super(message); this.status = status; this.code = code; } }
  const mod = { exports: {} };
  const output = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/hooks.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  vm.runInNewContext(output, { module: mod, exports: mod.exports, require: n => n === 'react' ? react : { ApiError }, window: {
    setTimeout: fn => { timers.set(++timerId, fn); return timerId; },
    clearTimeout: id => timers.delete(id),
  } });
  const render = (nextLoad = load, nextDeps = deps, nextPoll = poll) => {
    load = nextLoad; deps = nextDeps; poll = nextPoll; cursor = 0; pending = [];
    result = mod.exports.useResource(load, deps, poll);
    pending.forEach(effect => effect());
    return result;
  };
  return { render, timers, tick: async () => { const [id, fn] = timers.entries().next().value; timers.delete(id); await fn(); await flush(); }, unmount: () => slots.forEach(slot => slot?.cleanup?.()) };
}

test('late response for previous application cannot replace current application', async () => {
  const h = harness(), a = deferred(), b = deferred();
  h.render(() => a.promise, [1]);
  h.render(() => b.promise, [2]);
  b.resolve('application-2'); await flush();
  assert.equal(h.render().data, 'application-2');
  a.resolve('application-1'); await flush();
  assert.equal(h.render().data, 'application-2');
  h.unmount();
});

test('submitting a saved draft starts polling and a final decision stops it', async () => {
  const h = harness(); let calls = 0;
  h.render(async () => { calls++; return { status: calls === 1 ? 'DRAFT' : 'APPROVED' }; }, [1],
    value => value?.status === 'SUBMITTED' ? 1200 : null);
  await flush();
  assert.equal(h.timers.size, 0);
  h.render().setData({ status: 'SUBMITTED' });
  assert.equal(h.timers.size, 1);
  await h.tick();
  assert.equal(h.render().data.status, 'APPROVED');
  assert.equal(h.timers.size, 0);
  h.unmount();
});

test('transient poll failure keeps the last status and retries automatically', async () => {
  const h = harness(); let calls = 0;
  h.render(async () => { calls++; if (calls === 2) throw new Error('network'); return { status: calls >= 3 ? 'APPROVED' : 'SUBMITTED' }; }, [1],
    value => value?.status === 'SUBMITTED' ? 1200 : null);
  await flush();
  await h.tick();
  assert.equal(h.render().data.status, 'SUBMITTED');
  assert.ok(h.render().error);
  assert.equal(h.timers.size, 1);
  await h.tick();
  assert.equal(h.render().data.status, 'APPROVED');
  assert.equal(h.render().error, null);
  h.unmount();
  assert.equal(h.timers.size, 0);
});
test('changing application clears old data even if new request fails', async () => {
  const h = harness(); h.render(async () => 'application-1', [1]); await flush();
  assert.equal(h.render().data, 'application-1');
  h.render(async () => { throw new Error('404'); }, [2]); await flush();
  assert.equal(h.render().data, undefined);
  assert.ok(h.render().error);
  h.unmount();
});
test('action result cannot be overwritten by a poll that started earlier', async () => {
  const h = harness(), poll = deferred();
  h.render(() => poll.promise, [1]);
  h.render().setData('after-action');
  poll.resolve('before-action'); await flush();
  assert.equal(h.render().data, 'after-action');
  h.unmount();
});
