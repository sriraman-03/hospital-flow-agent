const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const API_ROOT = `${BASE}/api/v1`;
export const WS_ROOT = API_ROOT.replace(/^http/, "ws");

const TOKEN_KEY = "hfa-token";
export const tokenStore = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set: (t: string) => { try { localStorage.setItem(TOKEN_KEY, t); } catch { /* ignore */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ } },
};

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) { super(message); }
}

let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn; };

type Params = Record<string, string | number | boolean | null | undefined>;

export async function api<T>(path: string, opts: { method?: string; body?: unknown; params?: Params } = {}): Promise<T> {
  const url = new URL(API_ROOT + path);
  Object.entries(opts.params ?? {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v)); });
  const token = tokenStore.get();
  let res: Response;
  try {
    res = await fetch(url, {
      method: opts.method ?? "GET",
      headers: { ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the server. Check that the backend is running.");
  }
  if (res.status === 401 && token && !path.startsWith("/auth/login")) { tokenStore.clear(); onUnauthorized?.(); }
  if (!res.ok) {
    let body: any = null;
    try { body = await res.json(); } catch { /* non-JSON error */ }
    const err = body?.error;
    const detail = Array.isArray(err?.details) && err.details.length ? `: ${err.details.map((d: any) => `${d.field} ${d.message}`).join("; ")}` : "";
    throw new ApiError(res.status, err?.code ?? "error", (err?.message ?? `Request failed (${res.status})`) + detail, err?.details);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const get = <T,>(path: string, params?: Params) => api<T>(path, { params });
export const post = <T,>(path: string, body?: unknown) => api<T>(path, { method: "POST", body: body ?? {} });
export const patch = <T,>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body });
export const put = <T,>(path: string, body: unknown) => api<T>(path, { method: "PUT", body });
