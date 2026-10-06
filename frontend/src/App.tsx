import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import SignIn from "@/screens/SignIn";
import AccountAccess from "@/screens/AccountAccess";
import Library from "@/screens/Library";
import Chat from "@/screens/Chat";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  [
    "block rounded-[var(--brand-radius)] px-3 py-2 text-sm font-medium transition-colors",
    isActive ? "bg-[var(--brand-hover)] text-[var(--brand-fg)]" : "text-[var(--brand-fg-muted)]",
  ].join(" ");

export default function App() {
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
          <NavLink to="/library" className={navLinkClass}>
            {"My document library"}
          </NavLink>
          <NavLink to="/chat" className={navLinkClass}>
            {"Chat"}
          </NavLink>
        </nav>
      </aside>
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/sign-in" element={<SignIn />} />
          <Route path="/account-access" element={<AccountAccess />} />
          <Route path="/library" element={<Library />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="*" element={<Navigate to="/sign-in" replace />} />
        </Routes>
      </main>
    </div>
  );
}
