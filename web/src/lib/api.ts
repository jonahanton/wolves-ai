const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8080";

const TIMEOUT_MS = 8000;

const authHeaders: HeadersInit = process.env.BACKEND_KEY ? { "X-Wolves-Key": process.env.BACKEND_KEY } : {};

export type ApiErrorCategory = "offline" | "not_found" | "forbidden" | "upstream";

export interface ApiError {
  category: ApiErrorCategory;
  status?: number;
}

export type ApiResult<T> = { ok: true; data: T; stale?: boolean } | { ok: false; error: ApiError };

// Omit for the safe no-store default; revalidate: false caches forever, a number
// sets max staleness in seconds; retry re-attempts once on a transient failure.
export interface CachePolicy {
  revalidate?: number | false;
  retry?: boolean;
}

const RETRY_BACKOFF_MS = 300;

function categorise(status: number): ApiErrorCategory {
  if (status === 404) return "not_found";
  if (status === 401 || status === 403) return "forbidden";
  return "upstream";
}

// A 404/403 is a settled answer retrying cannot change.
function isTransient(error: ApiError): boolean {
  return error.category === "offline" || error.category === "upstream";
}

function fetchInit(policy?: CachePolicy): RequestInit {
  const base: RequestInit = { headers: authHeaders, signal: AbortSignal.timeout(TIMEOUT_MS) };
  if (policy && policy.revalidate !== undefined) {
    return { ...base, next: { revalidate: policy.revalidate } };
  }
  return { ...base, cache: "no-store" };
}

async function fetchOnce(path: string, policy?: CachePolicy): Promise<ApiResult<Response>> {
  try {
    const response = await fetch(new URL(path, BACKEND_URL), fetchInit(policy));
    if (!response.ok) {
      return { ok: false, error: { category: categorise(response.status), status: response.status } };
    }
    return { ok: true, data: response };
  } catch {
    return { ok: false, error: { category: "offline" } };
  }
}

async function fetchResponse(path: string, policy?: CachePolicy): Promise<ApiResult<Response>> {
  const first = await fetchOnce(path, policy);
  if (first.ok || !policy?.retry || !isTransient(first.error)) return first;
  await new Promise((resolve) => setTimeout(resolve, RETRY_BACKOFF_MS));
  return fetchOnce(path, policy);
}

export async function backendGet<T>(path: string, policy?: CachePolicy): Promise<ApiResult<T>> {
  const result = await fetchResponse(path, policy);
  if (!result.ok) return result;
  try {
    return { ok: true, data: (await result.data.json()) as T };
  } catch {
    return { ok: false, error: { category: "offline" } };
  }
}

export async function backendGetText(path: string, policy?: CachePolicy): Promise<ApiResult<string>> {
  const result = await fetchResponse(path, policy);
  if (!result.ok) return result;
  try {
    return { ok: true, data: await result.data.text() };
  } catch {
    return { ok: false, error: { category: "offline" } };
  }
}

export function orNull<T>(result: ApiResult<T>): T | null {
  return result.ok ? result.data : null;
}
