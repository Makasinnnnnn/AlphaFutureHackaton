const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const moduleUnderTest = { exports: {} };
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/documents.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(code, { module: moduleUnderTest, exports: moduleUnderTest.exports });
const { hasPendingAnalystRequest } = moduleUnderTest.exports;

test('analyst request stays blocked until a document outside its snapshot exists', () => {
  const app = { documents: [{ id: 1 }], missing_items: [{ code: 'ANALYST_REQUEST', document_ids_before_request: [1] }] };
  assert.equal(hasPendingAnalystRequest(app), true);
  assert.equal(hasPendingAnalystRequest({ ...app, documents: [{ id: 1 }, { id: 2 }] }), false);
  assert.equal(hasPendingAnalystRequest({ ...app, missing_items: [{ code: 'ANALYST_REQUEST', document_ids_before_request: [1, 2] }], documents: [{ id: 1 }, { id: 2 }] }), true);
});
test('legacy request without baseline fails closed; unrelated requests are unaffected', () => {
  assert.equal(hasPendingAnalystRequest({ documents: [{ id: 3 }], missing_items: [{ code: 'ANALYST_REQUEST' }] }), true);
  assert.equal(hasPendingAnalystRequest({ documents: [], missing_items: [{ code: 'STATEMENT' }] }), false);
});
