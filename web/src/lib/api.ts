const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8080";

const TIMEOUT_MS = 8000;

const authHeaders: HeadersInit = process.env.BACKEND_KEY ? { "X-Wolves-Key": process.env.BACKEND_KEY } : {};

export type ApiErrorCategory = "offline" | "not_found" | "forbidden" | "upstream";

export interface ApiError {
  category: ApiErrorCategory;
  status?: number;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

// Cache policy per call. Omit for the safe default (no-store): live and per-request
// sim endpoints must never be cached. revalidate: false caches an immutable run-id
// URL forever; a number sets the max staleness in seconds for a moving pointer.
export interface CachePolicy {
  revalidate?: number | false;
}

function categorise(status: number): ApiErrorCategory {
  if (status === 404) return "not_found";
  if (status === 401 || status === 403) return "forbidden";
  return "upstream";
}

function fetchInit(policy?: CachePolicy): RequestInit {
  const base: RequestInit = { headers: authHeaders, signal: AbortSignal.timeout(TIMEOUT_MS) };
  if (policy && policy.revalidate !== undefined) {
    return { ...base, next: { revalidate: policy.revalidate } };
  }
  return { ...base, cache: "no-store" };
}

export async function backendGet<T>(path: string, policy?: CachePolicy): Promise<ApiResult<T>> {
  try {
    const response = await fetch(new URL(path, BACKEND_URL), fetchInit(policy));
    if (!response.ok) {
      return { ok: false, error: { category: categorise(response.status), status: response.status } };
    }
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return { ok: false, error: { category: "offline" } };
  }
}

export async function backendGetText(path: string, policy?: CachePolicy): Promise<ApiResult<string>> {
  try {
    const response = await fetch(new URL(path, BACKEND_URL), fetchInit(policy));
    if (!response.ok) {
      return { ok: false, error: { category: categorise(response.status), status: response.status } };
    }
    return { ok: true, data: await response.text() };
  } catch {
    return { ok: false, error: { category: "offline" } };
  }
}

export function orNull<T>(result: ApiResult<T>): T | null {
  return result.ok ? result.data : null;
}
