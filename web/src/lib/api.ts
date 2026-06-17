const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8080";

const TIMEOUT_MS = 8000;

export type ApiErrorCategory = "offline" | "not_found" | "forbidden" | "upstream";

export interface ApiError {
  category: ApiErrorCategory;
  status?: number;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

function categorise(status: number): ApiErrorCategory {
  if (status === 404) return "not_found";
  if (status === 401 || status === 403) return "forbidden";
  return "upstream";
}

export async function backendGet<T>(path: string): Promise<ApiResult<T>> {
  try {
    const response = await fetch(new URL(path, BACKEND_URL), {
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!response.ok) {
      return { ok: false, error: { category: categorise(response.status), status: response.status } };
    }
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return { ok: false, error: { category: "offline" } };
  }
}

export async function backendGetText(path: string): Promise<ApiResult<string>> {
  try {
    const response = await fetch(new URL(path, BACKEND_URL), {
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
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
