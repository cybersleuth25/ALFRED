// Compute a stable hash for a photo file so it can be re-attached when reloading a saved space.
// We hash the first 64 KB of the file plus its size and name — sufficient to disambiguate
// typical photo libraries without reading the whole file.

const HASH_PREFIX_BYTES = 64 * 1024;

export async function photoContentHash(file: File): Promise<string> {
  const slice = file.slice(0, HASH_PREFIX_BYTES);
  const buf = await slice.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buf);
  const hex = Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
  return `${hex}-${file.size}-${file.name}`;
}
