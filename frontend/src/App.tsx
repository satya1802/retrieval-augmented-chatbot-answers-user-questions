import type { ReactNode } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import SignIn from "@/screens/SignIn";
import AccountAccess from "@/screens/AccountAccess";
import Library from "@/screens/Library";
import Chat from "@/screens/Chat";
import { clearToken, getToken } from "@/lib/auth";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  [
    "block rounded-[var(--brand-radius)] px-3 py-2 text-sm font-medium transition-colors",
    isActive ? "bg-[var(--brand-hover)] text-[var(--brand-fg)]" : "text-[var(--brand-fg-muted)]",
  ].join(" ");

/**
 * Guards a route behind a held token. Renders nothing but a redirect --
 * AC-010 requires /library, /chat and any other authenticated route to show
 * no content to a signed-out visitor, not even a flash of the screen before
 * it bounces away. The attempted path travels along as `?next=` so a future
 * sign-in can return the visitor to where they meant to go.
 */
function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (!getToken()) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/sign-in?next=${next}`} replace />;
  }
  return <>{children}</>;
}

export default function App() {
  // Subscribing to location here is what makes the sidebar and this guard
  // re-evaluate `getToken()` the moment sign-in or sign-out navigates --
  // there is no separate auth store to subscribe to instead (lib/auth.ts is
  // the only one, by design).
  useLocation();
  const isAuthed = Boolean(getToken());
  const navigate = useNavigate();

  const handleSignOut = () => {
    clearToken();
    navigate("/sign-in", { replace: true });
  };

  return (
    <div className="flex min-h-screen">
      <aside
        className="w-56 shrink-0 border-r p-4"
        style={{
          backgroundColor: "var(--brand-surface)",
          borderColor: "var(--brand-border)",
        }}
      >
        <p
          className="mb-4 px-3 text-sm font-semibold"
          style={{ fontFamily: "var(--brand-font-heading)" }}
        >
          {"Retrieval-augmented chatbot answers user questions"}
        </p>
        <nav className="flex flex-col gap-1">
          <NavLink to="/sign-in" className={navLinkClass}>
            {"Sign in or create account"}
          </NavLink>
          <NavLink to="/account-access" className={navLinkClass}>
            {"Email link landing"}
          </NavLink>
          {isAuthed ? (
            <>
              <NavLink to="/library" className={navLinkClass}>
                {"My document library"}
              </NavLink>
              <NavLink to="/chat" className={navLinkClass}>
                {"Chat"}
              </NavLink>
              <button
                type="button"
                onClick={handleSignOut}
                className="mt-2 block rounded-[var(--brand-radius)] px-3 py-2 text-left text-sm font-medium text-[var(--brand-fg-muted)] transition-colors hover:bg-[var(--brand-hover)]"
              >
                {"Sign out"}
              </button>
            </>
          ) : null}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/sign-in" element={<SignIn />} />
          <Route path="/account-access" element={<AccountAccess />} />
          <Route
            path="/library"
            element={
              <RequireAuth>
                <Library />
              </RequireAuth>
            }
          />
          <Route
            path="/chat"
            element={
              <RequireAuth>
                <Chat />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/sign-in" replace />} />
        </Routes>
      </main>
    </div>
  );
}
