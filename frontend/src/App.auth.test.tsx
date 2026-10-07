import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { clearToken, setToken } from "@/lib/auth";

vi.mock("@/screens/Library", () => ({ default: () => <div>Library Screen</div> }));
vi.mock("@/screens/Chat", () => ({ default: () => <div>Chat Screen</div> }));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("App route guard, nav visibility and sign-out", () => {
  beforeEach(() => {
    clearToken();
  });

  afterEach(() => {
    clearToken();
  });

  it("redirects /library to sign-in and renders no library content when no token is held", () => {
    renderAt("/library");

    expect(screen.queryByText("Library Screen")).not.toBeInTheDocument();
    expect(screen.getByText("Sign in or create account")).toBeInTheDocument();
  });

  it("redirects /chat to sign-in and renders no chat content when no token is held", () => {
    renderAt("/chat");

    expect(screen.queryByText("Chat Screen")).not.toBeInTheDocument();
    expect(screen.getByText("Sign in or create account")).toBeInTheDocument();
  });

  it("renders the guarded screen once a valid token is held", () => {
    setToken("jwt-abc");
    renderAt("/library");

    expect(screen.getByText("Library Screen")).toBeInTheDocument();
  });

  it("does not expose library or chat links to a signed-out visitor", () => {
    renderAt("/sign-in");

    expect(screen.queryByText("My document library")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Chat" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
  });

  it("shows library, chat and sign-out once signed in", () => {
    setToken("jwt-abc");
    renderAt("/library");

    expect(screen.getByText("My document library")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Chat" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("signing out clears the token and lands on sign-in; returning to /library redirects again", async () => {
    setToken("jwt-abc");
    const user = userEvent.setup();
    renderAt("/library");

    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(screen.getByText("Sign in or create account")).toBeInTheDocument();
    expect(localStorage.getItem("evidence-bench.auth-token")).toBeNull();

    // Simulating the back button: the same guarded route, re-rendered fresh,
    // must not show the cached authenticated screen once the token is gone.
    renderAt("/library");
    expect(screen.queryByText("Library Screen")).not.toBeInTheDocument();
  });
});
