// API client: same backend endpoints, friendly errors, no alert() ever.
export class ApiError extends Error {
  status: number;
  constructor(status: number, msg: string) {
    super(msg);
    this.status = status;
  }
}

export function friendly(e: unknown): string {
  const m = e instanceof Error ? e.message : String(e);
  if (/Failed to fetch|NetworkError|Load failed/i.test(m)) return 'server unreachable (restarting?)';
  if (/server 429/.test(m)) return 'too many requests — backing off, retrying…';
  if (/login required/i.test(m)) return 'session expired — log in again';
  return m;
}

export async function api<T>(path: string, opts: RequestInit = {}, retries = 0): Promise<T> {
  let last: unknown = null;
  for (let a = 0; a <= retries; a++) {
    try {
      const res = await fetch(path, opts);
      if (res.status === 401) {
        if (!path.includes('/login')) location.href = '/login';
        throw new Error('login required');
      }
      const txt = await res.text();
      if (txt.trimStart().startsWith('<')) throw new Error('auth session expired — log in again');
      let data: unknown = null;
      try { data = txt ? JSON.parse(txt) : null; } catch { throw new Error('bad response (not JSON)'); }
      if (!res.ok) {
        const d = data as { error?: string } | null;
        throw new ApiError(res.status, `server ${res.status}${d?.error ? ': ' + d.error : ''}`);
      }
      return data as T;
    } catch (e) {
      last = e;
      const msg = e instanceof Error ? e.message : String(e);
      const retryable = e instanceof TypeError || /^(server 5|server 429)/.test(msg);
      if (retryable && a < retries) await new Promise((r) => setTimeout(r, 1500 * (a + 1)));
      else throw e;
    }
  }
  throw last;
}

export function safeUrl(u: string): string {
  try {
    const p = new URL(String(u || ''), location.href);
    return p.protocol === 'http:' || p.protocol === 'https:' ? p.href : '';
  } catch { return ''; }
}

export const esc = (s: unknown): string => String(s ?? '');
