/* eslint-disable @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment, react-hooks/rules-of-hooks */
// @ts-nocheck
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Label } = UI;
const { Check, X, Bell, Home, Clock, ArrowLeft, ArrowRight, AlertCircle, CheckCircle } = Icons;

const PROTOTYPE_ACCOUNTS = [
  {
    email: "maya.okonjo@ferrisloop.com",
    password: "Harbour-7781",
    is_verified: true,
    note: "Verified · 34 documents",
  },
  {
    email: "devi.raman@northquay.org",
    password: "Lantern-4420",
    is_verified: true,
    note: "Verified · 9 documents",
  },
  {
    email: "t.beaumont@ferrisloop.com",
    password: "Cornice-9003",
    is_verified: false,
    note: "Awaiting email verification",
  },
];

const PASSWORD_RULES = [
  { id: "len", label: "At least 10 characters", test: (v) => v.length >= 10 },
  { id: "num", label: "Contains a number", test: (v) => /\d/.test(v) },
  {
    id: "case",
    label: "Contains upper and lower case letters",
    test: (v) => /[a-z]/.test(v) && /[A-Z]/.test(v),
  },
];

const PRINCIPLES = [
  {
    title: "Answer, then Sources — every time",
    body:
      "Each reply names the chunks it drew on, or says plainly that the library does not contain enough information.",
  },
  {
    title: "Owned by one account",
    body:
      "Documents, chunks and conversations are retrievable only by the account that uploaded them. Nothing is shared.",
  },
  {
    title: "Digital text only",
    body:
      "PDF, Word, Markdown and plain text. Scanned pages are rejected at ingestion with the reason shown in your library.",
  },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export default function Screen() {
  const navigate = useNavigate();
  const [mode, setMode] = React.useState("signin");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [keepSignedIn, setKeepSignedIn] = React.useState(true);

  const [errors, setErrors] = React.useState({});
  const [formError, setFormError] = React.useState(null);
  const [unverified, setUnverified] = React.useState(null);
  const [resendCount, setResendCount] = React.useState(0);
  const [panel, setPanel] = React.useState(null); // {kind, email}

  const tabRefs = React.useRef({});

  const resetMessages = () => {
    setErrors({});
    setFormError(null);
    setUnverified(null);
    setResendCount(0);
  };

  const switchMode = (next) => {
    setMode(next);
    setPanel(null);
    resetMessages();
    setPassword("");
    setConfirm("");
  };

  const onTabKeyDown = (event) => {
    const order = ["signin", "register"];
    const index = order.indexOf(mode);
    let nextIndex = null;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % order.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + order.length) % order.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = order.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const next = order[nextIndex];
    switchMode(next);
    const node = tabRefs.current[next];
    if (node && node.focus) node.focus();
  };

  const handleSignIn = (event) => {
    event.preventDefault();
    resetMessages();
    const nextErrors = {};
    if (!email.trim()) nextErrors.email = "Enter the email address on your account.";
    else if (!EMAIL_RE.test(email.trim())) nextErrors.email = "That does not look like an email address.";
    if (!password) nextErrors.password = "Enter your password.";
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }
    const account = PROTOTYPE_ACCOUNTS.find(
      (a) => a.email.toLowerCase() === email.trim().toLowerCase()
    );
    if (!account || account.password !== password) {
      setFormError("Invalid email or password.");
      return;
    }
    if (!account.is_verified) {
      setUnverified(account.email);
      return;
    }
    navigate("library");
  };

  const handleRegister = (event) => {
    event.preventDefault();
    resetMessages();
    const nextErrors = {};
    const trimmed = email.trim();
    if (!trimmed) nextErrors.email = "Enter an email address.";
    else if (!EMAIL_RE.test(trimmed)) nextErrors.email = "That does not look like an email address.";
    const unmet = PASSWORD_RULES.filter((r) => !r.test(password));
    if (!password) nextErrors.password = "Choose a password.";
    else if (unmet.length) nextErrors.password = "Your password does not meet all of the rules below.";
    if (!confirm) nextErrors.confirm = "Re-enter your password.";
    else if (confirm !== password) nextErrors.confirm = "The two passwords do not match.";
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }
    setPanel({ kind: "verify-sent", email: trimmed });
  };

  const handleReset = (event) => {
    event.preventDefault();
    resetMessages();
    const trimmed = email.trim();
    if (!trimmed) {
      setErrors({ email: "Enter the email address on your account." });
      return;
    }
    if (!EMAIL_RE.test(trimmed)) {
      setErrors({ email: "That does not look like an email address." });
      return;
    }
    setPanel({ kind: "reset-sent", email: trimmed });
  };

  const useAccount = (account) => {
    switchMode("signin");
    setEmail(account.email);
    setPassword(account.password);
  };

  const fieldClass =
    "w-full rounded-md border px-3 py-2 text-sm bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-offset-1";
  const focusRing = {
    borderColor: "#CBD5E1",
    boxShadow: "none",
  };

  const describedBy = (field, extra) => {
    const ids = [];
    if (errors[field]) ids.push(`${field}-error`);
    if (extra) ids.push(extra);
    return ids.length ? ids.join(" ") : undefined;
  };

  const FieldError = ({ field }) =>
    errors[field] ? (
      <p id={`${field}-error`} className="mt-1 flex items-start gap-1.5 text-xs text-red-700">
        <Icons.AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span>{errors[field]}</span>
      </p>
    ) : null;

  const tabButton = (value, label) => {
    const selected = mode === value;
    return (
      <button
        type="button"
        role="tab"
        id={`tab-${value}`}
        aria-selected={selected}
        aria-controls="account-panel"
        tabIndex={selected ? 0 : -1}
        ref={(node) => {
          tabRefs.current[value] = node;
        }}
        onClick={() => switchMode(value)}
        className="relative -mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 rounded-t"
        style={{
          borderBottomColor: selected ? brand.primaryColor : "transparent",
          color: selected ? brand.primaryColor : brand.neutralColor,
        }}
      >
        {label}
      </button>
    );
  };

  return (
    <div
      className="mx-auto w-full max-w-5xl px-4 py-8"
      style={{ fontFamily: brand.fontBody, color: "#1B2430" }}
    >
      <header className="mb-6">
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.14em]"
          style={{ color: brand.neutralColor }}
        >
          Evidence Bench
        </p>
        <h1
          className="mt-1 text-2xl font-semibold tracking-tight"
          style={{ fontFamily: brand.fontHeading, color: "#15202B" }}
        >
          Sign in or create an account
        </h1>
        <p className="mt-1.5 max-w-2xl text-sm" style={{ color: brand.neutralColor }}>
          Your library, your chunks, your conversations. Access is per account — there is no
          anonymous or shared view of anyone&rsquo;s documents.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.05fr] lg:items-start">
        {/* Left: product framing */}
        <section
          aria-labelledby="why-heading"
          className="rounded-lg p-6 text-white"
          style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
        >
          <h2 id="why-heading" className="text-base font-semibold" style={{ fontFamily: brand.fontHeading }}>
            Every answer sits beside its evidence
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/80">
            Retrieval runs only over chunks you own. The retrieved text stays on screen next to the
            answer, so you can defend each claim without opening anything.
          </p>

          <ul className="mt-5 space-y-4">
            {PRINCIPLES.map((item) => (
              <li key={item.title} className="flex gap-3">
                <Icons.CheckCircle
                  className="mt-0.5 h-4 w-4 shrink-0"
                  style={{ color: brand.accentColor }}
                  aria-hidden="true"
                />
                <div>
                  <h3 className="text-sm font-semibold text-white">{item.title}</h3>
                  <p className="mt-0.5 text-sm leading-relaxed text-white/75">{item.body}</p>
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-6 border-t border-white/20 pt-4">
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/70">
              Prototype accounts
            </h3>
            <ul className="mt-2 space-y-2">
              {PROTOTYPE_ACCOUNTS.map((account) => (
                <li
                  key={account.email}
                  className="flex items-center justify-between gap-3 rounded border border-white/15 bg-white/5 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate font-mono text-xs text-white">{account.email}</p>
                    <p className="truncate font-mono text-[11px] text-white/60">
                      {account.password} · {account.note}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => useAccount(account)}
                    className="shrink-0 rounded border border-white/40 px-2 py-1 text-xs font-medium text-white hover:bg-white/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2"
                    style={{ outlineColor: "#fff" }}
                    aria-label={`Fill the sign-in form with ${account.email}`}
                  >
                    Use
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs leading-relaxed text-white/60">
              Free while in preview. Each account may store 50 documents and ask 200 questions a
              month.
            </p>
          </div>
        </section>

        {/* Right: the form */}
        <section aria-labelledby="form-heading">
          <div
            className="overflow-hidden border bg-white shadow-sm"
            style={{ borderRadius: brand.radius, borderColor: "#D7DEE6" }}
          >
            <div style={{ height: "3px", backgroundColor: brand.accentColor }} aria-hidden="true" />

            {panel ? (
              <div className="p-6">
                <h2
                  id="form-heading"
                  className="flex items-center gap-2 text-base font-semibold"
                  style={{ fontFamily: brand.fontHeading, color: "#15202B" }}
                >
                  <Icons.Bell className="h-4 w-4" style={{ color: brand.primaryColor }} aria-hidden="true" />
                  Check your email
                </h2>
                <div
                  role="status"
                  className="mt-3 rounded border p-3 text-sm leading-relaxed"
                  style={{ borderColor: "#D7DEE6", backgroundColor: "#F6F8FA" }}
                >
                  {panel.kind === "verify-sent" ? (
                    <p>
                      If <span className="font-medium">{panel.email}</span> can be registered, a
                      verification link is on its way to it. Follow the link to verify the account,
                      then sign in. We don&rsquo;t say whether an address is already in use.
                    </p>
                  ) : (
                    <p>
                      If an account exists for <span className="font-medium">{panel.email}</span>, a
                      password reset link has been sent. The link works once and expires in 60
                      minutes.
                    </p>
                  )}
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <dt style={{ color: brand.neutralColor }}>Link expires</dt>
                    <dd className="mt-0.5 font-medium">
                      {panel.kind === "verify-sent" ? "In 24 hours" : "In 60 minutes"}
                    </dd>
                  </div>
                  <div>
                    <dt style={{ color: brand.neutralColor }}>Sent</dt>
                    <dd className="mt-0.5 font-medium">6 Oct 2026, 09:14</dd>
                  </div>
                </dl>
                <div className="mt-5 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => navigate("account-access")}
                    className="rounded px-3 py-2 text-sm font-medium text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                    style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
                  >
                    I have the link — open it
                  </button>
                  <button
                    type="button"
                    onClick={() => switchMode("signin")}
                    className="inline-flex items-center gap-1.5 rounded border px-3 py-2 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                    style={{ borderColor: "#D7DEE6", color: brand.primaryColor, borderRadius: brand.radius }}
                  >
                    <Icons.ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
                    Back to sign in
                  </button>
                </div>
              </div>
            ) : mode === "reset" ? (
              <div className="p-6">
                <h2
                  id="form-heading"
                  className="text-base font-semibold"
                  style={{ fontFamily: brand.fontHeading, color: "#15202B" }}
                >
                  Reset your password
                </h2>
                <p className="mt-1.5 text-sm" style={{ color: brand.neutralColor }}>
                  We&rsquo;ll email a single-use link. Setting a new password signs you out of
                  nothing else — there are no other sessions in this version.
                </p>
                <form className="mt-5 space-y-4" onSubmit={handleReset} noValidate>
                  <div>
                    <Label htmlFor="reset-email" className="text-sm font-medium">
                      Email address
                    </Label>
                    <input
                      id="reset-email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      aria-invalid={errors.email ? "true" : undefined}
                      aria-describedby={describedBy("email")}
                      className={`${fieldClass} mt-1`}
                      style={focusRing}
                    />
                    <FieldError field="email" />
                  </div>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <button
                      type="submit"
                      className="rounded px-3 py-2 text-sm font-medium text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                      style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
                    >
                      Send reset link
                    </button>
                    <button
                      type="button"
                      onClick={() => switchMode("signin")}
                      className="inline-flex items-center gap-1.5 rounded px-3 py-2 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                      style={{ color: brand.primaryColor }}
                    >
                      <Icons.ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
                      Back to sign in
                    </button>
                  </div>
                </form>
              </div>
            ) : (
              <div>
                <h2 id="form-heading" className="sr-only">
                  {mode === "signin" ? "Sign in to your account" : "Create an account"}
                </h2>
                <div
                  role="tablist"
                  aria-label="Account access"
                  onKeyDown={onTabKeyDown}
                  className="flex gap-1 border-b px-5 pt-3"
                  style={{ borderColor: "#D7DEE6" }}
                >
                  {tabButton("signin", "Sign in")}
                  {tabButton("register", "Create account")}
                </div>

                <div
                  id="account-panel"
                  role="tabpanel"
                  aria-labelledby={`tab-${mode}`}
                  tabIndex={-1}
                  className="p-6"
                >
                  {mode === "signin" ? (
                    <form className="space-y-4" onSubmit={handleSignIn} noValidate>
                      {formError && (
                        <div
                          role="alert"
                          className="flex items-start gap-2 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800"
                        >
                          <Icons.AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                          <p>
                            <span className="font-semibold">Sign-in failed.</span> {formError} Check
                            the address and try again.
                          </p>
                        </div>
                      )}

                      {unverified && (
                        <div
                          role="alert"
                          className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
                        >
                          <p className="flex items-start gap-2">
                            <Icons.Clock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                            <span>
                              <span className="font-semibold">Account not verified.</span> We
                              can&rsquo;t sign you in until {unverified} is confirmed.
                            </span>
                          </p>
                          {resendCount > 0 ? (
                            <p className="mt-2 pl-6 text-amber-900">
                              Verification email re-sent to {unverified}. The link expires in 24
                              hours.{" "}
                              <button
                                type="button"
                                onClick={() => navigate("account-access")}
                                className="font-medium underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                              >
                                Open the link
                              </button>
                            </p>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setResendCount((c) => c + 1)}
                              className="ml-6 mt-2 rounded border border-amber-400 bg-white px-2.5 py-1.5 text-xs font-medium text-amber-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                            >
                              Resend verification email
                            </button>
                          )}
                        </div>
                      )}

                      <div>
                        <Label htmlFor="signin-email" className="text-sm font-medium">
                          Email address
                        </Label>
                        <input
                          id="signin-email"
                          name="email"
                          type="email"
                          autoComplete="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          aria-invalid={errors.email ? "true" : undefined}
                          aria-describedby={describedBy("email")}
                          className={`${fieldClass} mt-1`}
                          style={focusRing}
                        />
                        <FieldError field="email" />
                      </div>

                      <div>
                        <div className="flex items-baseline justify-between gap-3">
                          <Label htmlFor="signin-password" className="text-sm font-medium">
                            Password
                          </Label>
                          <button
                            type="button"
                            onClick={() => switchMode("reset")}
                            className="rounded text-xs font-medium underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                            style={{ color: brand.primaryColor }}
                          >
                            Forgot your password?
                          </button>
                        </div>
                        <input
                          id="signin-password"
                          name="password"
                          type="password"
                          autoComplete="current-password"
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          aria-invalid={errors.password ? "true" : undefined}
                          aria-describedby={describedBy("password")}
                          className={`${fieldClass} mt-1`}
                          style={focusRing}
                        />
                        <FieldError field="password" />
                      </div>

                      <div className="flex items-center gap-2">
                        <input
                          id="keep-signed-in"
                          type="checkbox"
                          checked={keepSignedIn}
                          onChange={(e) => setKeepSignedIn(e.target.checked)}
                          className="h-4 w-4 rounded border-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                          style={{ accentColor: brand.primaryColor }}
                        />
                        <Label htmlFor="keep-signed-in" className="text-sm">
                          Keep me signed in on this device
                        </Label>
                      </div>

                      <button
                        type="submit"
                        className="w-full rounded px-3 py-2.5 text-sm font-semibold text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                        style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
                      >
                        Sign in
                      </button>

                      <p className="text-xs leading-relaxed" style={{ color: brand.neutralColor }}>
                        Signing in takes you to your document library. Unverified accounts cannot
                        sign in.
                      </p>
                    </form>
                  ) : (
                    <form className="space-y-4" onSubmit={handleRegister} noValidate>
                      <p className="text-sm" style={{ color: brand.neutralColor }}>
                        Registration is free. We send a verification link before the account can
                        sign in.
                      </p>

                      <div>
                        <Label htmlFor="register-email" className="text-sm font-medium">
                          Email address
                        </Label>
                        <input
                          id="register-email"
                          name="email"
                          type="email"
                          autoComplete="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          aria-invalid={errors.email ? "true" : undefined}
                          aria-describedby={describedBy("email", "register-email-hint")}
                          className={`${fieldClass} mt-1`}
                          style={focusRing}
                        />
                        <p id="register-email-hint" className="mt-1 text-xs" style={{ color: brand.neutralColor }}>
                          Used for verification, password reset and nothing else.
                        </p>
                        <FieldError field="email" />
                      </div>

                      <div>
                        <Label htmlFor="register-password" className="text-sm font-medium">
                          Password
                        </Label>
                        <input
                          id="register-password"
                          name="new-password"
                          type="password"
                          autoComplete="new-password"
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          aria-invalid={errors.password ? "true" : undefined}
                          aria-describedby={describedBy("password", "password-rules")}
                          className={`${fieldClass} mt-1`}
                          style={focusRing}
                        />
                        <FieldError field="password" />
                        <ul id="password-rules" className="mt-2 space-y-1">
                          {PASSWORD_RULES.map((rule) => {
                            const met = rule.test(password);
                            return (
                              <li key={rule.id} className="flex items-center gap-2 text-xs">
                                {met ? (
                                  <Icons.Check className="h-3.5 w-3.5 text-emerald-700" aria-hidden="true" />
                                ) : (
                                  <Icons.X className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                                )}
                                <span style={{ color: met ? "#15803D" : brand.neutralColor }}>
                                  {rule.label}
                                </span>
                                <span className="sr-only">{met ? "— met" : "— not yet met"}</span>
                              </li>
                            );
                          })}
                        </ul>
                      </div>

                      <div>
                        <Label htmlFor="register-confirm" className="text-sm font-medium">
                          Confirm password
                        </Label>
                        <input
                          id="register-confirm"
                          name="confirm-password"
                          type="password"
                          autoComplete="new-password"
                          value={confirm}
                          onChange={(e) => setConfirm(e.target.value)}
                          aria-invalid={errors.confirm ? "true" : undefined}
                          aria-describedby={describedBy("confirm")}
                          className={`${fieldClass} mt-1`}
                          style={focusRing}
                        />
                        <FieldError field="confirm" />
                      </div>

                      <button
                        type="submit"
                        className="w-full rounded px-3 py-2.5 text-sm font-semibold text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                        style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
                      >
                        Create account
                      </button>
                    </form>
                  )}
                </div>
              </div>
            )}
          </div>

          <div
            className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded border bg-white px-4 py-3 text-xs"
            style={{ borderColor: "#D7DEE6", borderRadius: brand.radius, color: brand.neutralColor }}
          >
            <p>
              Already have a verification or reset link?{" "}
              <button
                type="button"
                onClick={() => navigate("account-access")}
                className="rounded font-medium underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                style={{ color: brand.primaryColor }}
              >
                Open it here
              </button>
            </p>
            <p className="flex items-center gap-1.5">
              <Icons.CheckCircle className="h-3.5 w-3.5 text-emerald-700" aria-hidden="true" />
              Retrieval and embedding services operational
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
