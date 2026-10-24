const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const flush = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); };

function harness() {
  const slots = []; let cursor = 0, pending = [], load, deps, result;
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
  vm.runInNewContext(output, { module: mod, exports: mod.exports, require: n => n === 'react' ? react : { ApiError }, window: { setTimeout, clearTimeout } });
  const render = (nextLoad = load, nextDeps = deps) => {
    load = nextLoad; deps = nextDeps; cursor = 0; pending = [];
    result = mod.exports.useResource(load, deps);
    pending.forEach(effect => effect());
    return result;
  };
  return { render, unmount: () => slots.forEach(slot => slot?.cleanup?.()) };
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
