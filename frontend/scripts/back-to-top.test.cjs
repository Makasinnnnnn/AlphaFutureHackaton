const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

test('floating navigation never covers an actively edited field and cleans up listeners', () => {
  let visible = false, cleanup, mounted = false, editing = false;
  const events = new Map();
  const target = {
    addEventListener: (name, callback) => events.set(name, callback),
    removeEventListener: name => events.delete(name),
  };
  const window = { ...target, scrollY: 800, scrollTo: () => {} };
  const document = { ...target, activeElement: { matches: () => editing } };
  const exports = {};
  const react = {
    useState: () => [visible, value => { visible = value; }],
    useEffect: effect => { if (!mounted) { mounted = true; cleanup = effect(); } },
  };
  const output = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/components/BackToTop.tsx'), 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  vm.runInNewContext(output, { exports, window, document,
    require: name => name === 'react' ? react : { jsx: (type, props) => ({ type, props }) } });
  const render = () => exports.BackToTop();
  render();
  assert.equal(render().props['aria-label'], 'Вернуться наверх');
  editing = true; events.get('focusin')();
  assert.equal(render(), null);
  events.get('scroll')();
  assert.equal(render(), null);
  editing = false; events.get('focusout')();
  assert.ok(render());
  window.scrollY = 100; events.get('scroll')();
  assert.equal(render(), null);
  cleanup();
  assert.equal(events.size, 0);
});
