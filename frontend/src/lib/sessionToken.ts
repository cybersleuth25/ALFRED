// The backend requires a per-launch token on every state-changing request
// (blocks drive-by CSRF from other websites). Patch fetch once so every
// existing `fetch('/api/...', { method: 'POST' })` call sends it automatically.

const TOKEN_HEADER = 'X-Alfred-Token';
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

let tokenPromise: Promise<string> | null = null;

function getToken(nativeFetch: typeof fetch): Promise<string> {
  if (!tokenPromise) {
    tokenPromise = nativeFetch('/api/session-token')
      .then((r) => r.json())
      .then((d: { token?: string }) => d.token ?? '')
      .catch(() => {
        tokenPromise = null; // retry on next request (backend may still be booting)
        return '';
      });
  }
  return tokenPromise;
}

function isSameOrigin(input: RequestInfo | URL): boolean {
  const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
  return new URL(url, window.location.href).origin === window.location.origin;
}

export function installSessionTokenFetch(): void {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase();
    if (SAFE_METHODS.has(method) || !isSameOrigin(input)) {
      return nativeFetch(input, init);
    }
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    headers.set(TOKEN_HEADER, await getToken(nativeFetch));
    return nativeFetch(input, { ...init, headers });
  };
}
