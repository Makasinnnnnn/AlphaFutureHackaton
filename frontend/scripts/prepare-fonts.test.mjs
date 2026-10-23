import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { prepareFonts } from './prepare-fonts.mjs';
async function directory(t) {
  const path = await mkdtemp(join(tmpdir(), 'conveyor-fonts-'));
  t.after(() => rm(path, { recursive: true, force: true }));
  return pathToFileURL(`${path}/`);
}
const font = Buffer.concat([Buffer.from('wOF2'), Buffer.alloc(1100)]);
const quiet = () => {};
test('normal build succeeds offline without attempting a network connection', async (t) => {
  let requests = 0;
  const result = await prepareFonts({ target: await directory(t), log: quiet, fetchFont: async () => {
    requests++;
    throw new Error('ERR_SSL_TLSV1_ALERT_INTERNAL_ERROR');
  } });
  assert.equal(requests, 0);
  assert.equal(result.missing.length, 3);
});
test('cached fonts are reused without network access', async (t) => {
  const target = await directory(t);
  for (const weight of ['regular', 'medium', 'bold']) await writeFile(new URL(`styrene-ui_${weight}.woff2`, target), font);
  const result = await prepareFonts({ target, log: quiet, download: true, fetchFont: () => assert.fail('unexpected download') });
  assert.deepEqual(result.missing, []);
});
test('explicit download reports TLS errors without disabling verification', async (t) => {
  await assert.rejects(prepareFonts({ target: await directory(t), log: quiet, download: true, fetchFont: async () => {
    throw new Error('ERR_SSL_TLSV1_ALERT_INTERNAL_ERROR');
  } }), /ERR_SSL_TLSV1_ALERT_INTERNAL_ERROR/);
});
test('HTML error pages cannot be saved as font files', async (t) => {
  const target = await directory(t);
  await assert.rejects(prepareFonts({ target, log: quiet, download: true, fetchFont: async () => new Response('<html>error</html>') }), /Invalid WOFF2/);
  await assert.rejects(readFile(new URL('styrene-ui_regular.woff2', target)), { code: 'ENOENT' });
});
test('explicit successful download writes three local font files', async (t) => {
  const target = await directory(t);
  const result = await prepareFonts({ target, log: quiet, download: true, fetchFont: async () => new Response(font) });
  assert.deepEqual(result.missing, []);
  for (const weight of ['regular', 'medium', 'bold']) assert.deepEqual(await readFile(new URL(`styrene-ui_${weight}.woff2`, target)), font);
});
