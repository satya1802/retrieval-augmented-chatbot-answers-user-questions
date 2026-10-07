/// <reference types="vite/client" />
// Without the reference above, `import.meta.env` is not typed and `tsc --noEmit` fails --
// which `vite build` does not catch, because it tree-shakes this module out when no screen
// imports it yet.
//
// Where the generated API lives.
//
// Set at build time: the platform bakes the deployed API URL into the frontend build. The
// fallback is the local backend so a bare `npm run dev` still points somewhere real.
import { clearToken, getToken } from "@/lib/auth";

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** Raised for any non-2xx response. `status` lets callers branch on the
 * HTTP code (e.g. 403 unverified vs 401 bad credentials) without parsing
 * the message text. */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readDetail(response: Response): Promise<string | undefined> {
  try {
    const body = (await response.clone().json()) as { detail?: unknown };
    return typeof body?.detail === "string" ? body.detail : undefined;
  } catch {
    return undefined;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    // AC-010: a 401 on a call that *carried* a token means the token expired
    // or was revoked server-side -- clear it and send the visitor back to
    // sign-in once, here, rather than duplicating this check in every
    // screen that calls apiFetch. A 401 with no token held (e.g. a failed
    // login attempt, which never attaches one) is just a normal credential
    // error and is left for the caller to render.
    if (response.status === 401 && token) {
      clearToken();
      if (typeof window !== "undefined") {
        const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
        window.location.assign(`/sign-in?next=${next}`);
      }
    }
    const detail = await readDetail(response);
    throw new ApiError(
      response.status,
      detail ?? `${init?.method ?? "GET"} ${path} failed: ${response.status}`,
    );
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export type MessageResponse = { message: string };
export type LoginResponse = { access_token: string };
export type VerifyResponse = { verified: boolean };

export function registerAccount(email: string, password: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function verifyAccount(token: string): Promise<VerifyResponse> {
  return apiFetch<VerifyResponse>("/auth/verify", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function requestPasswordReset(email: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/password-reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function confirmPasswordReset(token: string, newPassword: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/password-reset/confirm", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}
