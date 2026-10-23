import { mkdir, readFile, writeFile, rename } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const weights = ['regular', 'medium', 'bold'];
const valid = (bytes) => bytes.length > 1024 && bytes.subarray(0, 4).toString() === 'wOF2';

// A normal build only checks local files. CDN availability must not block the UI.
// Explicit downloads use the URLs published by Alfa Laboratory and verify TLS.
export async function prepareFonts({
  target = new URL('../public/fonts/', import.meta.url),
  download = false,
  fetchFont = globalThis.fetch,
  log = console.log,
} = {}) {
  const missing = [];
  for (const weight of weights) {
    const name = `styrene-ui_${weight}.woff2`;
    const destination = new URL(name, target);
    try {
      if (valid(await readFile(destination))) continue;
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    if (!download) {
      missing.push(name);
      continue;
    }
    const response = await fetchFont(`https://alfabank.gcdn.co/media/fonts/styrene-ui/${name}`, {
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) throw new Error(`Cannot download ${name}: HTTP ${response.status}`);
    const bytes = Buffer.from(await response.arrayBuffer());
    if (!valid(bytes)) throw new Error(`Invalid WOFF2 font: ${name}`);
    await mkdir(target, { recursive: true });
    const temporary = new URL(`${name}.tmp`, target);
    await writeFile(temporary, bytes);
    await rename(temporary, destination);
    log(`Prepared ${name} (${bytes.length} bytes)`);
  }
  if (missing.length) log('Styrene UI is not fully available locally; using bundled Onest fallback. To install Styrene UI, run npm run download:fonts on a host with access to the official CDN, then rebuild.');
  return { missing };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    await prepareFonts({ download: process.argv.includes('--download') });
  } catch (error) {
    console.error(`Font preparation failed: ${error.cause?.code ?? error.message}`);
    process.exitCode = 1;
  }
}
