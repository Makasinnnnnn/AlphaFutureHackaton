import { mkdir, readFile, writeFile, rename } from 'node:fs/promises';

// URLs published in Alfa Laboratory's core-components typography documentation.
// Download at build time: the running application never contacts the font CDN.
const target = new URL('../public/fonts/', import.meta.url);
await mkdir(target, { recursive: true });
for (const weight of ['regular', 'medium', 'bold']) {
  const name = `styrene-ui_${weight}.woff2`;
  const destination = new URL(name, target);
  const valid = (bytes) => bytes.length > 1024 && bytes.subarray(0, 4).toString() === 'wOF2';
  try {
    if (valid(await readFile(destination))) continue;
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  const response = await fetch(`https://alfabank.gcdn.co/media/fonts/styrene-ui/${name}`, {
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`Cannot download ${name}: HTTP ${response.status}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (!valid(bytes)) throw new Error(`Invalid WOFF2 font: ${name}`);
  const temporary = new URL(`${name}.tmp`, target);
  await writeFile(temporary, bytes);
  await rename(temporary, destination);
  console.log(`Prepared ${name} (${bytes.length} bytes)`);
}
