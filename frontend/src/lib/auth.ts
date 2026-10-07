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

// Mirrors the server's password policy exactly (see
// backend/app/security.py's PASSWORD_MIN_LENGTH/PASSWORD_RULE and the
// register/password-reset/confirm handlers in backend/app/routers/auth.py,
// which are the only code that actually enforces this): at least 8
// characters, including at least one letter and at least one number. This
// list previously asserted a stricter rule (12 characters, mixed case, a
// symbol) that the server never enforced and that `/auth/register` would
// happily accept a password failing -- rejecting a password here that the
// API would accept is its own contract bug, not just a cosmetic one.
export const PASSWORD_RULES: PasswordRule[] = [
  { id: "len", label: "At least 8 characters", test: (v) => v.length >= 8 },
  { id: "letter", label: "At least one letter", test: (v) => /[A-Za-z]/.test(v) },
  { id: "num", label: "At least one number", test: (v) => /\d/.test(v) },
];

export function passwordMeetsRules(password: string): boolean {
  return PASSWORD_RULES.every((rule) => rule.test(password));
}
