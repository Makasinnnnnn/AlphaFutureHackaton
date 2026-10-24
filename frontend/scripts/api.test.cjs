const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function harness() {
  let resolve, token = 'previous-session', logouts = 0;
  const pending = new Promise(r => { resolve = r; });
  const mod = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/api.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  vm.runInNewContext(code, { module: mod, exports: mod.exports, Headers,
    sessionStorage: { getItem: () => token, setItem: (_, v) => { token = v; }, removeItem: () => { token = null; } },
    fetch: () => pending,
  });
  mod.exports.setUnauthorizedHandler(() => { logouts++; });
  return { api: mod.exports, rejectAuth: () => resolve({ status: 401, ok: false, json: async () => ({}) }), logouts: () => logouts };
}
test('late 401 from previous session cannot log out a newly signed-in user', async () => {
  const h = harness(), pending = h.api.request('/api/auth/me');
  h.api.session.token = 'new-session';
  h.rejectAuth(); await assert.rejects(pending);
  assert.equal(h.logouts(), 0);
});
test('401 for current session still triggers logout', async () => {
  const h = harness(), pending = h.api.request('/api/auth/me');
  h.rejectAuth(); await assert.rejects(pending);
  assert.equal(h.logouts(), 1);
});
