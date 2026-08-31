// Minimal typed fetch client.
// In dev, Vite proxies /api to the backend. In Electron/production the backend
// URL can be injected via window.__API_BASE__.

declare global {
  interface Window {
    __API_BASE__?: string;
  }
}

const BASE =
  (typeof window !== "undefined" && window.__API_BASE__) ||
  import.meta.env.VITE_API_BASE ||
  ""; // same-origin (dev proxy)

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body: unknown) =>
    request<T>(p, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(p: string, body: unknown) =>
    request<T>(p, { method: "PUT", body: JSON.stringify(body) }),
  del: (p: string) => request<void>(p, { method: "DELETE" }),
};
