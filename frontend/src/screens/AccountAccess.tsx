/* eslint-disable @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment, react-hooks/rules-of-hooks */
// @ts-nocheck
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Select } = UI;
const { Check, X, ChevronRight, Settings, Bell, FileText, ArrowLeft, ArrowRight, AlertCircle, CheckCircle } = Icons;

const ACCOUNT_EMAIL = 'sai.kiron@quorq.ai';

const PURPOSE_LABEL = {
  verify: 'Email verification',
  password_reset: 'Password reset',
};

const STATUS_STYLE = {
  active: { label: 'Active', bg: '#E6EEF6', fg: '#1A3F61', border: '#9FBAD2' },
  expired: { label: 'Expired', bg: '#FAF2D4', fg: '#5A4600', border: '#E3B505' },
  used: { label: 'Used', bg: '#E8EBEF', fg: '#434E5B', border: '#AFB8C2' },
};

const INITIAL_LINKS = [
  {
    id: 'tok_7f3a91',
    purpose: 'verify',
    status: 'active',
    requested: '6 Oct 2026, 08:52',
    expires: '7 Oct 2026, 08:52',
    usedAt: null,
    origin: 'Firefox 142 on Windows · 203.0.113.42',
  },
  {
    id: 'tok_2b8d04',
    purpose: 'password_reset',
    status: 'active',
    requested: '6 Oct 2026, 09:31',
    expires: '6 Oct 2026, 10:31',
    usedAt: null,
    origin: 'Firefox 142 on Windows · 203.0.113.42',
  },
  {
    id: 'tok_51c7e0',
    purpose: 'password_reset',
    status: 'expired',
    requested: '5 Oct 2026, 19:04',
    expires: '5 Oct 2026, 20:04',
    usedAt: null,
    origin: 'Safari on iPhone · 198.51.100.7',
  },
  {
    id: 'tok_c09a2f',
    purpose: 'verify',
    status: 'expired',
    requested: '28 Sep 2026, 08:47',
    expires: '29 Sep 2026, 08:47',
    usedAt: null,
    origin: 'Firefox 142 on Windows · 203.0.113.42',
  },
  {
    id: 'tok_a4e118',
    purpose: 'password_reset',
    status: 'used',
    requested: '14 Aug 2026, 11:20',
    expires: '14 Aug 2026, 12:20',
    usedAt: '14 Aug 2026, 11:26',
    origin: 'Chrome on macOS · 203.0.113.42',
  },
];

const PASSWORD_RULES = [
  { id: 'len', label: 'At least 12 characters', test: (v) => v.length >= 12 },
  {
    id: 'case',
    label: 'Upper and lower case letters',
    test: (v) => /[a-z]/.test(v) && /[A-Z]/.test(v),
  },
  { id: 'num', label: 'At least one number', test: (v) => /\d/.test(v) },
  { id: 'sym', label: 'At least one symbol', test: (v) => /[^A-Za-z0-9]/.test(v) },
];

const StatusPill = ({ status }) => {
  const s = STATUS_STYLE[status] || STATUS_STYLE.used;
  const Icon =
    status === 'active' ? Icons.CheckCircle : status === 'expired' ? Icons.AlertCircle : Icons.Check;
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-[1px] text-[11px] font-semibold leading-5"
      style={{ backgroundColor: s.bg, color: s.fg, borderColor: s.border }}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {s.label}
    </span>
  );
};

export default function Screen() {
  const navigate = useNavigate();
  const [links, setLinks] = React.useState(INITIAL_LINKS);
  const [activeId, setActiveId] = React.useState(INITIAL_LINKS[0].id);
  const [results, setResults] = React.useState({});
  const [password, setPassword] = React.useState('');
  const [confirmPassword, setConfirmPassword] = React.useState('');
  const [showPassword, setShowPassword] = React.useState(false);
  const [formError, setFormError] = React.useState('');
  const [notice, setNotice] = React.useState('');

  const headingRef = React.useRef(null);
  const firstRender = React.useRef(true);

  const link = links.find((l) => l.id === activeId) || links[0];
  const result = results[activeId];
  const isVerify = link.purpose === 'verify';

  React.useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    if (headingRef.current) headingRef.current.focus();
  }, [activeId, result]);

  const panelClass = 'border bg-white shadow-sm';
  const panelStyle = { borderColor: '#D5DCE4', borderRadius: brand.radius };
  const focusRing =
    'focus:outline-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#1F4E79]';

  const primaryBtn =
    'inline-flex items-center justify-center gap-2 px-3.5 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 ' +
    focusRing;
  const secondaryBtn =
    'inline-flex items-center justify-center gap-2 border px-3.5 py-2 text-sm font-semibold transition-colors hover:bg-[#E6EEF6] ' +
    focusRing;

  const selectLink = (id) => {
    setActiveId(id);
    setFormError('');
    setPassword('');
    setConfirmPassword('');
    setNotice('');
  };

  const markUsed = (id) =>
    setLinks((prev) =>
      prev.map((l) => (l.id === id ? { ...l, status: 'used', usedAt: 'Just now' } : l))
    );

  const handleVerify = () => {
    markUsed(link.id);
    setResults((prev) => ({ ...prev, [link.id]: 'verified' }));
    setNotice('');
  };

  const handleSetPassword = (event) => {
    event.preventDefault();
    const unmet = PASSWORD_RULES.filter((r) => !r.test(password));
    if (password.trim() === '') {
      setFormError('Enter a new password.');
      return;
    }
    if (unmet.length > 0) {
      setFormError('Your password does not meet all of the password rules listed below.');
      return;
    }
    if (password !== confirmPassword) {
      setFormError('The two passwords do not match. Re-type them and try again.');
      return;
    }
    setFormError('');
    markUsed(link.id);
    setResults((prev) => ({ ...prev, [link.id]: 'password_set' }));
  };

  const handleResend = (purpose) => {
    const verify = purpose === 'verify';
    const newLink = {
      id: 'tok_' + Math.random().toString(16).slice(2, 8),
      purpose,
      status: 'active',
      requested: 'Just now',
      expires: verify ? 'In 24 hours' : 'In 60 minutes',
      usedAt: null,
      origin: 'Firefox 142 on Windows · 203.0.113.42',
    };
    setLinks((prev) => [
      newLink,
      ...prev.map((l) =>
        l.purpose === purpose && l.status === 'active' ? { ...l, status: 'expired' } : l
      ),
    ]);
    setActiveId(newLink.id);
    setPassword('');
    setConfirmPassword('');
    setFormError('');
    setNotice(
      'A new ' +
        (verify ? 'verification' : 'password reset') +
        ' email was sent to ' +
        ACCOUNT_EMAIL +
        '. Any earlier ' +
        (verify ? 'verification' : 'password reset') +
        ' link has been cancelled.'
    );
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
    if (result === 'verified') {
      return (
        <div className="space-y-4">
          <Heading icon={Icons.CheckCircle}>Email address verified</Heading>
          <p className="text-sm leading-6" style={{ color: '#2C3540' }}>
            <span className="font-semibold">{ACCOUNT_EMAIL}</span> is now a verified account. You can
            sign in and start uploading documents to your private library.
          </p>
          <ul className="space-y-1.5 text-sm" style={{ color: brand.neutralColor }}>
            <li className="flex items-start gap-2">
              <Icons.Check className="mt-1 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>Verification recorded against token {link.id} at {link.usedAt}.</span>
            </li>
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
              onClick={() => navigate('sign-in')}
            >
              Continue to sign in
              <Icons.ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      );
    }

    if (result === 'password_set') {
      return (
        <div className="space-y-4">
          <Heading icon={Icons.CheckCircle}>Password updated</Heading>
          <p className="text-sm leading-6" style={{ color: '#2C3540' }}>
            The password for <span className="font-semibold">{ACCOUNT_EMAIL}</span> has been changed.
            Sign in with your new password to reach your library and conversations.
          </p>
          <ul className="space-y-1.5 text-sm" style={{ color: brand.neutralColor }}>
            <li className="flex items-start gap-2">
              <Icons.Check className="mt-1 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>Reset token {link.id} consumed at {link.usedAt} — it cannot be reused.</span>
            </li>
            <li className="flex items-start gap-2">
              <Icons.Check className="mt-1 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>Any other outstanding reset link for this address was cancelled.</span>
            </li>
          </ul>
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              className={primaryBtn}
              style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
              onClick={() => navigate('sign-in')}
            >
              Sign in with your new password
              <Icons.ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      );
    }

    if (link.status !== 'active') {
      const expired = link.status === 'expired';
      return (
        <div className="space-y-4">
          <Heading icon={Icons.AlertCircle} tone="#8A6A00">
            {expired ? 'This link has expired' : 'This link has already been used'}
          </Heading>
          <div
            className="border-l-4 p-3 text-sm leading-6"
            style={{
              borderColor: brand.accentColor,
              backgroundColor: '#FBF6E3',
              color: '#4A3B00',
              borderRadius: brand.radius,
            }}
          >
            {expired ? (
              <span>
                The {PURPOSE_LABEL[link.purpose].toLowerCase()} link {link.id} expired on{' '}
                <span className="font-semibold">{link.expires}</span>. Verification links last 24
                hours and password reset links last 60 minutes.
              </span>
            ) : (
              <span>
                The {PURPOSE_LABEL[link.purpose].toLowerCase()} link {link.id} was used on{' '}
                <span className="font-semibold">{link.usedAt}</span>. Each link works exactly once.
              </span>
            )}
          </div>
          <p className="text-sm leading-6" style={{ color: '#2C3540' }}>
            Nothing has changed on your account. Request a fresh link below and we will email it to{' '}
            <span className="font-semibold">{ACCOUNT_EMAIL}</span>.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              className={primaryBtn}
              style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
              onClick={() => handleResend(link.purpose)}
            >
              <Icons.Bell className="h-4 w-4" aria-hidden="true" />
              {isVerify ? 'Email me a new verification link' : 'Email me a new reset link'}
            </button>
            <button
              type="button"
              className={secondaryBtn}
              style={{
                borderColor: '#9FBAD2',
                color: brand.primaryColor,
                borderRadius: brand.radius,
              }}
              onClick={() => navigate('sign-in')}
            >
              <Icons.ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back to sign in
            </button>
          </div>
        </div>
      );
    }

    if (isVerify) {
      return (
        <div className="space-y-4">
          <Heading icon={Icons.FileText}>Confirm your email address</Heading>
          <p className="text-sm leading-6" style={{ color: '#2C3540' }}>
            Confirming marks <span className="font-semibold">{ACCOUNT_EMAIL}</span> as verified so you
            can sign in. Until then, sign-in is refused and your library stays empty and private.
          </p>
          <dl className="grid grid-cols-[9rem_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
            <dt className="font-medium" style={{ color: brand.neutralColor }}>
              Account
            </dt>
            <dd style={{ color: '#2C3540' }}>{ACCOUNT_EMAIL}</dd>
            <dt className="font-medium" style={{ color: brand.neutralColor }}>
              Link valid until
            </dt>
            <dd style={{ color: '#2C3540' }}>{link.expires}</dd>
          </dl>
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              className={primaryBtn}
              style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
              onClick={handleVerify}
            >
              <Icons.Check className="h-4 w-4" aria-hidden="true" />
              Confirm my email address
            </button>
            <button
              type="button"
              className={secondaryBtn}
              style={{
                borderColor: '#9FBAD2',
                color: brand.primaryColor,
                borderRadius: brand.radius,
              }}
              onClick={() => handleResend('verify')}
            >
              Send a fresh link instead
            </button>
          </div>
        </div>
      );
    }

    return (
      <form className="space-y-5" onSubmit={handleSetPassword} noValidate>
        <div className="space-y-2">
          <Heading icon={Icons.Settings}>Set a new password</Heading>
          <p className="text-sm leading-6" style={{ color: '#2C3540' }}>
            Choose a new password for <span className="font-semibold">{ACCOUNT_EMAIL}</span>. This
            link can only be used once and stops working as soon as the password is saved.
          </p>
        </div>

        {formError ? (
          <div
            role="alert"
            className="flex items-start gap-2 border-l-4 p-3 text-sm leading-6"
            style={{
              borderColor: '#B3261E',
              backgroundColor: '#FBEAE9',
              color: '#7A1A15',
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
              style={{ color: '#2C3540' }}
            >
              New password
            </label>
            <input
              id="new-password"
              name="new-password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-describedby="password-rules"
              aria-invalid={formError ? 'true' : 'false'}
              className={
                'w-full border px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 ' + focusRing
              }
              style={{ borderColor: '#B9C3CE', borderRadius: brand.radius }}
            />
          </div>
          <div className="space-y-1.5">
            <label
              htmlFor="confirm-password"
              className="block text-sm font-semibold"
              style={{ color: '#2C3540' }}
            >
              Re-type new password
            </label>
            <input
              id="confirm-password"
              name="confirm-password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              aria-invalid={formError ? 'true' : 'false'}
              className={
                'w-full border px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 ' + focusRing
              }
              style={{ borderColor: '#B9C3CE', borderRadius: brand.radius }}
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            id="show-password"
            type="checkbox"
            checked={showPassword}
            onChange={(e) => setShowPassword(e.target.checked)}
            className={'h-4 w-4 border-slate-400 ' + focusRing}
            style={{ accentColor: brand.primaryColor }}
          />
          <label htmlFor="show-password" className="text-sm" style={{ color: '#2C3540' }}>
            Show passwords
          </label>
        </div>

        <div
          id="password-rules"
          className="border p-3"
          style={{ borderColor: '#D5DCE4', backgroundColor: '#F7F9FB', borderRadius: brand.radius }}
        >
          <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: brand.neutralColor }}>
            Password rules
          </h3>
          <ul className="mt-2 space-y-1.5 text-sm">
            {PASSWORD_RULES.map((rule) => {
              const met = rule.test(password);
              const Icon = met ? Icons.CheckCircle : Icons.X;
              return (
                <li key={rule.id} className="flex items-center gap-2" style={{ color: '#2C3540' }}>
                  <Icon
                    className="h-3.5 w-3.5 shrink-0"
                    style={{ color: met ? brand.primaryColor : brand.neutralColor }}
                    aria-hidden="true"
                  />
                  <span>{rule.label}</span>
                  <span className="sr-only">{met ? ' — met' : ' — not met'}</span>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            className={primaryBtn}
            style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
          >
            <Icons.Check className="h-4 w-4" aria-hidden="true" />
            Save new password
          </button>
          <button
            type="button"
            className={secondaryBtn}
            style={{ borderColor: '#9FBAD2', color: brand.primaryColor, borderRadius: brand.radius }}
            onClick={() => navigate('sign-in')}
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
      style={{ fontFamily: brand.fontBody, color: '#2C3540' }}
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
          You arrived from an email sent to{' '}
          <span className="font-semibold" style={{ color: '#2C3540' }}>
            {ACCOUNT_EMAIL}
          </span>
          . Everything about that link — what it does, when it expires and where it was requested from —
          is shown beside the action.
        </p>
      </header>

      <div role="status" aria-live="polite" className="mt-4">
        {notice ? (
          <div
            className="flex items-start gap-2 border-l-4 p-3 text-sm leading-6"
            style={{
              borderColor: brand.primaryColor,
              backgroundColor: '#E9F0F7',
              color: '#1A3F61',
              borderRadius: brand.radius,
            }}
          >
            <Icons.Bell className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{notice}</span>
          </div>
        ) : null}
      </div>

      <div className="mt-4 grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_19rem]">
        <section aria-labelledby={null} className={panelClass + ' p-5'} style={panelStyle}>
          {renderMain()}
        </section>

        <aside className="space-y-4">
          <section className={panelClass + ' p-4'} style={panelStyle} aria-labelledby="link-details-heading">
            <h2
              id="link-details-heading"
              className="text-sm font-semibold"
              style={{ color: brand.primaryColor, fontFamily: brand.fontHeading }}
            >
              Link details
            </h2>
            <dl className="mt-3 space-y-2.5 text-[13px]">
              <div className="flex items-start justify-between gap-3">
                <dt className="font-medium" style={{ color: brand.neutralColor }}>
                  Purpose
                </dt>
                <dd className="text-right">{PURPOSE_LABEL[link.purpose]}</dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="font-medium" style={{ color: brand.neutralColor }}>
                  Status
                </dt>
                <dd>
                  <StatusPill status={link.status} />
                </dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="font-medium" style={{ color: brand.neutralColor }}>
                  Token
                </dt>
                <dd className="font-mono text-[12px]">{link.id}</dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="font-medium" style={{ color: brand.neutralColor }}>
                  Requested
                </dt>
                <dd className="text-right">{link.requested}</dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="font-medium" style={{ color: brand.neutralColor }}>
                  Expires
                </dt>
                <dd className="text-right">{link.expires}</dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="font-medium" style={{ color: brand.neutralColor }}>
                  Used
                </dt>
                <dd className="text-right">{link.usedAt || 'Not yet used'}</dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="font-medium" style={{ color: brand.neutralColor }}>
                  Requested from
                </dt>
                <dd className="max-w-[10.5rem] text-right">{link.origin}</dd>
              </div>
            </dl>
          </section>

          <section className={panelClass + ' p-4'} style={panelStyle} aria-labelledby="link-history-heading">
            <h2
              id="link-history-heading"
              className="text-sm font-semibold"
              style={{ color: brand.primaryColor, fontFamily: brand.fontHeading }}
            >
              Links sent to this address
            </h2>
            <p className="mt-1 text-[12px] leading-5" style={{ color: brand.neutralColor }}>
              Only the newest link of each kind stays valid. Select one to see what it does.
            </p>
            <ul className="mt-3 space-y-1.5">
              {links.map((item) => {
                const selected = item.id === activeId;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => selectLink(item.id)}
                      aria-current={selected ? 'true' : undefined}
                      className={
                        'flex w-full items-start justify-between gap-2 border px-2.5 py-2 text-left transition-colors hover:bg-[#EEF3F8] ' +
                        focusRing
                      }
                      style={{
                        borderColor: selected ? brand.primaryColor : '#DCE2E9',
                        backgroundColor: selected ? '#EEF3F8' : '#FFFFFF',
                        borderRadius: brand.radius,
                        boxShadow: selected ? 'inset 3px 0 0 0 ' + brand.accentColor : 'none',
                      }}
                    >
                      <span className="min-w-0">
                        <span className="block text-[13px] font-semibold" style={{ color: '#2C3540' }}>
                          {PURPOSE_LABEL[item.purpose]}
                          {selected ? (
                            <span className="sr-only"> — the link you opened</span>
                          ) : null}
                        </span>
                        <span className="mt-0.5 block text-[12px]" style={{ color: brand.neutralColor }}>
                          {item.requested}
                        </span>
                      </span>
                      <StatusPill status={item.status} />
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>

          <section className={panelClass + ' p-4'} style={panelStyle} aria-labelledby="help-heading">
            <h2
              id="help-heading"
              className="text-sm font-semibold"
              style={{ color: brand.primaryColor, fontFamily: brand.fontHeading }}
            >
              Didn't request this?
            </h2>
            <p className="mt-2 text-[12px] leading-5" style={{ color: brand.neutralColor }}>
              Ignore the email — nothing changes until a link is opened and confirmed. Your documents and
              conversations stay private to this account and are never shared.
            </p>
            <button
              type="button"
              onClick={() => navigate('sign-in')}
              className={
                'mt-3 inline-flex items-center gap-1.5 text-[13px] font-semibold underline underline-offset-2 ' +
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
