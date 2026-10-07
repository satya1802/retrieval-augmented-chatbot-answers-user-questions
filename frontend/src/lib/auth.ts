/**
 * Single seam for reading, writing and clearing the JWT the backend issues
 * from `POST /auth/login`. `apiFetch` (lib/api.ts) reads the token from here
 * to attach the Authorization header; screens never touch localStorage
 * directly.
 */

const TOKEN_KEY = "evidence-bench.auth-token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Storage unavailable (private mode, disabled, quota) -- the session
    // simply won't persist; nothing to recover from here.
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing to remove, nothing to do.
  }
}

export type PasswordRule = {
  id: string;
  label: string;
  test: (value: string) => boolean;
};

// Mirrors the server's password policy exactly (see backend/app/security.py
// and the registration/reset handlers in backend/app/routers/auth.py): at
// least 12 characters, upper and lower case letters, a digit and a symbol.
export const PASSWORD_RULES: PasswordRule[] = [
  { id: "len", label: "At least 12 characters", test: (v) => v.length >= 12 },
  {
    id: "case",
    label: "Upper and lower case letters",
    test: (v) => /[a-z]/.test(v) && /[A-Z]/.test(v),
  },
  { id: "num", label: "At least one number", test: (v) => /\d/.test(v) },
  { id: "sym", label: "At least one symbol", test: (v) => /[^A-Za-z0-9]/.test(v) },
];

export function passwordMeetsRules(password: string): boolean {
  return PASSWORD_RULES.every((rule) => rule.test(password));
}
