/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck
import React from "react";
import { useSearchParams } from "react-router-dom";

import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";
import { ApiError, confirmPasswordReset, verifyAccount } from "@/lib/api";
import { PASSWORD_RULES } from "@/lib/auth";

const EXPIRED_OR_USED_VERIFY =
  "This verification link is no longer valid. It may have expired or already been used.";
const EXPIRED_OR_USED_RESET =
  "This reset link is no longer valid. It may have expired, or it may have already been used to set a password.";
const GENERIC_ERROR = "Something went wrong. Try again in a moment.";

export default function Screen() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = (searchParams.get("token") || "").trim();
  const purpose = searchParams.get("purpose") === "reset" ? "reset" : "verify";

  // idle: waiting for the user to act; verifying/submitting: request in
  // flight; verified/password_set: success; error: the link could not be
  // used (expired, already used, or missing from the URL).
  const [status, setStatus] = React.useState(token ? "idle" : "error");
  const [errorMessage, setErrorMessage] = React.useState(
    token ? "" : "This link is missing its token. Open the link from your email again.",
  );
  const [password, setPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [formError, setFormError] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  const headingRef = React.useRef(null);
  const firstRender = React.useRef(true);

  React.useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    if (headingRef.current) headingRef.current.focus();
  }, [status]);

  const panelClass = "border bg-white shadow-sm";
  const panelStyle = { borderColor: "#D5DCE4", borderRadius: brand.radius };
  const focusRing =
    "focus:outline-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#1F4E79]";

  const primaryBtn =
    "inline-flex items-center justify-center gap-2 px-3.5 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-60 " +
    focusRing;
  const secondaryBtn =
    "inline-flex items-center justify-center gap-2 border px-3.5 py-2 text-sm font-semibold transition-colors hover:bg-[#E6EEF6] " +
    focusRing;

  const handleVerify = async () => {
    setSubmitting(true);
    setErrorMessage("");
    try {
      const result = await verifyAccount(token);
      if (result.verified) {
        setStatus("verified");
      } else {
        setStatus("error");
        setErrorMessage(EXPIRED_OR_USED_VERIFY);
      }
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof ApiError ? EXPIRED_OR_USED_VERIFY : GENERIC_ERROR);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSetPassword = async (event) => {
    event.preventDefault();
    setFormError("");
    const unmet = PASSWORD_RULES.filter((r) => !r.test(password));
    if (password.trim() === "") {
      setFormError("Enter a new password.");
      return;
    }
    if (unmet.length > 0) {
      setFormError("Your password does not meet all of the password rules listed below.");
      return;
    }
    if (password !== confirmPassword) {
      setFormError("The two passwords do not match. Re-type them and try again.");
      return;
    }
    setSubmitting(true);
    try {
      await confirmPasswordReset(token, password);
      setStatus("password_set");
    } catch (err) {
      // AC-007: re-using an already-consumed reset link is reported as an
      // error here, not silently accepted.
      setStatus("error");
      setErrorMessage(err instanceof ApiError ? EXPIRED_OR_USED_RESET : GENERIC_ERROR);
    } finally {
      setSubmitting(false);
    }
  };

  const Heading = ({ icon: Icon, children, tone }) => (
    <h2
      ref={headingRef}
      tabIndex={-1}
      className="flex items-start gap-2 text-lg font-semibold tracking-tight focus:outline-none"
      style={{ color: tone || brand.primaryColor, fontFamily: brand.fontHeading }}
    >
      {Icon ? <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" /> : null}
      <span>{children}</span>
    </h2>
  );

  const renderMain = () => {
    if (status === "verified") {
      return (
        <div className="space-y-4">
          <Heading icon={Icons.CheckCircle}>Email address verified</Heading>
          <p className="text-sm leading-6" style={{ color: "#2C3540" }}>
            Your account is now verified. You can sign in and start uploading documents to your
            private library.
          </p>
          <ul className="space-y-1.5 text-sm" style={{ color: brand.neutralColor }}>
            <li className="flex items-start gap-2">
              <Icons.Check className="mt-1 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>This link is now marked used and cannot be opened a second time.</span>
            </li>
          </ul>
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              className={primaryBtn}
              style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
              onClick={() => navigate("sign-in")}
            >
              Continue to sign in
              <Icons.ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      );
    }

    if (status === "password_set") {
      return (
        <div className="space-y-4">
          <Heading icon={Icons.CheckCircle}>Password updated</Heading>
          <p className="text-sm leading-6" style={{ color: "#2C3540" }}>
            Your password has been changed. Sign in with your new password to reach your library and
            conversations.
          </p>
          <ul className="space-y-1.5 text-sm" style={{ color: brand.neutralColor }}>
            <li className="flex items-start gap-2">
              <Icons.Check className="mt-1 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>This reset link has been consumed and cannot be reused.</span>
            </li>
          </ul>
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              className={primaryBtn}
              style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
              onClick={() => navigate("sign-in")}
            >
              Sign in with your new password
              <Icons.ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      );
    }

    if (status === "error") {
      return (
        <div className="space-y-4">
          <Heading icon={Icons.AlertCircle} tone="#8A6A00">
            This link can&rsquo;t be used
          </Heading>
          <div
            role="alert"
            className="border-l-4 p-3 text-sm leading-6"
            style={{
              borderColor: brand.accentColor,
              backgroundColor: "#FBF6E3",
              color: "#4A3B00",
              borderRadius: brand.radius,
            }}
          >
            {errorMessage}
          </div>
          <p className="text-sm leading-6" style={{ color: "#2C3540" }}>
            Nothing has changed on your account. Request a fresh link from the sign-in page.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              className={secondaryBtn}
              style={{
                borderColor: "#9FBAD2",
                color: brand.primaryColor,
                borderRadius: brand.radius,
              }}
              onClick={() => navigate("sign-in")}
            >
              <Icons.ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back to sign in
            </button>
          </div>
        </div>
      );
    }

    if (purpose === "verify") {
      return (
        <div className="space-y-4">
          <Heading icon={Icons.FileText}>Confirm your email address</Heading>
          <p className="text-sm leading-6" style={{ color: "#2C3540" }}>
            Confirming marks your account as verified so you can sign in. Until then, sign-in is
            refused and your library stays empty and private.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              className={primaryBtn}
              style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
              onClick={handleVerify}
              disabled={submitting}
            >
              <Icons.Check className="h-4 w-4" aria-hidden="true" />
              {submitting ? "Confirming…" : "Confirm my email address"}
            </button>
          </div>
        </div>
      );
    }

    return (
      <form className="space-y-5" onSubmit={handleSetPassword} noValidate>
        <div className="space-y-2">
          <Heading icon={Icons.Settings}>Set a new password</Heading>
          <p className="text-sm leading-6" style={{ color: "#2C3540" }}>
            Choose a new password for your account. This link can only be used once and stops
            working as soon as the password is saved.
          </p>
        </div>

        {formError ? (
          <div
            role="alert"
            className="flex items-start gap-2 border-l-4 p-3 text-sm leading-6"
            style={{
              borderColor: "#B3261E",
              backgroundColor: "#FBEAE9",
              color: "#7A1A15",
              borderRadius: brand.radius,
            }}
          >
            <Icons.AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{formError}</span>
          </div>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label
              htmlFor="new-password"
              className="block text-sm font-semibold"
              style={{ color: "#2C3540" }}
            >
              New password
            </label>
            <input
              id="new-password"
              name="new-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-describedby="password-rules"
              aria-invalid={formError ? "true" : "false"}
              className={
                "w-full border px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 " +
                focusRing
              }
              style={{ borderColor: "#B9C3CE", borderRadius: brand.radius }}
            />
          </div>
          <div className="space-y-1.5">
            <label
              htmlFor="confirm-password"
              className="block text-sm font-semibold"
              style={{ color: "#2C3540" }}
            >
              Re-type new password
            </label>
            <input
              id="confirm-password"
              name="confirm-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              aria-invalid={formError ? "true" : "false"}
              className={
                "w-full border px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 " +
                focusRing
              }
              style={{ borderColor: "#B9C3CE", borderRadius: brand.radius }}
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            id="show-password"
            type="checkbox"
            checked={showPassword}
            onChange={(e) => setShowPassword(e.target.checked)}
            className={"h-4 w-4 border-slate-400 " + focusRing}
            style={{ accentColor: brand.primaryColor }}
          />
          <label htmlFor="show-password" className="text-sm" style={{ color: "#2C3540" }}>
            Show passwords
          </label>
        </div>

        <div
          id="password-rules"
          className="border p-3"
          style={{ borderColor: "#D5DCE4", backgroundColor: "#F7F9FB", borderRadius: brand.radius }}
        >
          <h3
            className="text-xs font-semibold uppercase tracking-wide"
            style={{ color: brand.neutralColor }}
          >
            Password rules
          </h3>
          <ul className="mt-2 space-y-1.5 text-sm">
            {PASSWORD_RULES.map((rule) => {
              const met = rule.test(password);
              const Icon = met ? Icons.CheckCircle : Icons.X;
              return (
                <li key={rule.id} className="flex items-center gap-2" style={{ color: "#2C3540" }}>
                  <Icon
                    className="h-3.5 w-3.5 shrink-0"
                    style={{ color: met ? brand.primaryColor : brand.neutralColor }}
                    aria-hidden="true"
                  />
                  <span>{rule.label}</span>
                  <span className="sr-only">{met ? " — met" : " — not met"}</span>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            className={primaryBtn}
            disabled={submitting}
            style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
          >
            <Icons.Check className="h-4 w-4" aria-hidden="true" />
            {submitting ? "Saving…" : "Save new password"}
          </button>
          <button
            type="button"
            className={secondaryBtn}
            style={{
              borderColor: "#9FBAD2",
              color: brand.primaryColor,
              borderRadius: brand.radius,
            }}
            onClick={() => navigate("sign-in")}
          >
            <Icons.ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Back to sign in
          </button>
        </div>
      </form>
    );
  };

  return (
    <div
      className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6"
      style={{ fontFamily: brand.fontBody, color: "#2C3540" }}
    >
      <header className="max-w-2xl">
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.14em]"
          style={{ color: brand.neutralColor }}
        >
          Evidence Bench · Account access
        </p>
        <h1
          className="mt-1 text-2xl font-semibold tracking-tight"
          style={{ color: brand.primaryColor, fontFamily: brand.fontHeading }}
        >
          Finish the link you opened from your email
        </h1>
        <p className="mt-2 text-sm leading-6" style={{ color: brand.neutralColor }}>
          What the link does and what happens next is shown below.
        </p>
      </header>

      <div className="mt-4 grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_19rem]">
        <section className={panelClass + " p-5"} style={panelStyle}>
          {renderMain()}
        </section>

        <aside className="space-y-4">
          <section
            className={panelClass + " p-4"}
            style={panelStyle}
            aria-labelledby="help-heading"
          >
            <h2
              id="help-heading"
              className="text-sm font-semibold"
              style={{ color: brand.primaryColor, fontFamily: brand.fontHeading }}
            >
              Didn&rsquo;t request this?
            </h2>
            <p className="mt-2 text-[12px] leading-5" style={{ color: brand.neutralColor }}>
              Ignore the email — nothing changes until a link is opened and confirmed. Your
              documents and conversations stay private to this account and are never shared.
            </p>
            <button
              type="button"
              onClick={() => navigate("sign-in")}
              className={
                "mt-3 inline-flex items-center gap-1.5 text-[13px] font-semibold underline underline-offset-2 " +
                focusRing
              }
              style={{ color: brand.primaryColor, borderRadius: brand.radius }}
            >
              Go to sign in
              <Icons.ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </section>
        </aside>
      </div>
    </div>
  );
}
