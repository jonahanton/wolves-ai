import { type NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8080";
const BACKEND_ORIGIN = new URL(BACKEND_URL).origin;

const FORWARDED_REQUEST_HEADERS = ["content-type", "if-none-match", "if-modified-since"];
const FORWARDED_RESPONSE_HEADERS = ["content-type", "etag", "cache-control", "last-modified"];
const ADMIN_PREFIX = "admin";

function forwardedResponseHeaders(response: Response): Headers {
  const headers = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = response.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (!headers.has("content-type")) headers.set("content-type", "application/json");
  return headers;
}

interface RouteContext {
  params: Promise<{ slug: string[] }>;
}

async function proxyRequest(request: NextRequest, context: RouteContext): Promise<Response> {
  const { slug } = await context.params;
  const url = new URL(slug.map(encodeURIComponent).join("/"), BACKEND_URL);

  // Prevent SSRF: encoding blocks absolute or protocol-relative segments and the
  // origin pin is the last-resort guard should one ever resolve outside the backend.
  if (url.origin !== BACKEND_ORIGIN) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  request.nextUrl.searchParams.forEach((value, key) => url.searchParams.append(key, value));

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (slug[0] === ADMIN_PREFIX) {
    const value = request.headers.get("authorization");
    if (value) headers.set("authorization", value);
  }

  const options: RequestInit = {
    method: request.method,
    headers,
    signal: request.signal,
    cache: "no-store",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    const body = await request.arrayBuffer();
    if (body.byteLength > 0) options.body = body;
  }

  try {
    const response = await fetch(url, options);
    // 204 / 205 / 304 forbid a body; passing one throws under Next's runtime.
    if (response.status === 204 || response.status === 205) {
      return new Response(null, { status: response.status });
    }
    if (response.status === 304) {
      const etag = response.headers.get("etag");
      return new Response(null, { status: 304, headers: etag ? { etag } : undefined });
    }
    return new Response(response.body, {
      status: response.status,
      headers: forwardedResponseHeaders(response),
    });
  } catch (error) {
    if (request.signal.aborted || (error instanceof Error && error.name === "AbortError")) {
      return new Response(null, { status: 499, statusText: "Client Closed Request" });
    }
    console.error("Proxy error:", error);
    return NextResponse.json({ error: "failed to reach backend" }, { status: 502 });
  }
}

export const GET = proxyRequest;
export const HEAD = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
