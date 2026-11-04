/** A tiny wrapper around fetch for talking to the Flask API. */

export type FieldErrors = Record<string, string>;

export interface ApiResult<T> {
  ok: boolean;
  status: number;
  data: T & { error?: string; errors?: FieldErrors; message?: string; code?: string };
}

export interface User {
  id: number;
  name: string;
  email: string;
  role: "user" | "admin";
  experience: string;
  is_verified: boolean;
  is_banned: boolean;
  bio: string;
  timezone: string;
  avatar_url: string | null;
  notify_email: boolean;
  notify_party: boolean;
  created_at: string;
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

async function request<T>(method: Method, url: string, body?: unknown): Promise<ApiResult<T>> {
  // The custom header is our CSRF protection: other websites can't add it to a request.
  const headers: Record<string, string> = { "X-Requested-With": "fetch" };
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  try {
    const res = await fetch(url, { method, headers, body: payload, credentials: "same-origin" });
    const data = res.headers.get("content-type")?.includes("json") ? await res.json() : {};
    return { ok: res.ok, status: res.status, data };
  } catch {
    return {
      ok: false,
      status: 0,
      data: { error: "Couldn't reach the server. Check your connection and try again." } as ApiResult<T>["data"],
    };
  }
}

export const api = {
  get: <T>(url: string) => request<T>("GET", url),
  post: <T>(url: string, body: unknown = {}) => request<T>("POST", url, body),
  patch: <T>(url: string, body: unknown) => request<T>("PATCH", url, body),
  delete: <T>(url: string, body?: unknown) => request<T>("DELETE", url, body),
};
