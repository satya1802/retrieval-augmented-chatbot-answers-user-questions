import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SignIn from "./SignIn";
import { clearToken, getToken } from "@/lib/auth";

const mockNavigate = vi.fn();
vi.mock("@/lib/navigate", () => ({
  useNavigate: () => mockNavigate,
}));

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

function renderScreen() {
  return render(
    <MemoryRouter>
      <SignIn />
    </MemoryRouter>,
  );
}

async function registerWith(user: ReturnType<typeof userEvent.setup>, email: string) {
  await user.click(screen.getByRole("tab", { name: "Create account" }));
  await user.type(screen.getByLabelText("Email address"), email);
  await user.type(screen.getByLabelText("Password"), "Correct-Horse-9!");
  await user.type(screen.getByLabelText("Confirm password"), "Correct-Horse-9!");
  await user.click(screen.getByRole("button", { name: "Create account" }));
  return screen.findByRole("status");
}

describe("SignIn", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    clearToken();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("register: posts to /auth/register and shows the neutral check-your-email panel", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(202, { message: "accepted" }),
    );
    const user = userEvent.setup();
    renderScreen();

    const panel = await registerWith(user, "new.user@example.com");

    expect(screen.getByText("Check your email")).toBeInTheDocument();
    expect(panel).toHaveTextContent("new.user@example.com");
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/auth/register"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("register: an already-registered email renders the identical neutral panel copy", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(202, { message: "accepted" }),
    );
    const userA = userEvent.setup();
    const { unmount } = renderScreen();
    const freshPanel = await registerWith(userA, "fresh@example.com");
    const freshCopy = freshPanel.textContent?.replace("fresh@example.com", "EMAIL");
    unmount();

    const userB = userEvent.setup();
    renderScreen();
    const existingPanel = await registerWith(userB, "existing@example.com");
    const existingCopy = existingPanel.textContent?.replace("existing@example.com", "EMAIL");

    // Same wording, modulo the email itself -- nothing distinguishes a new
    // registration from one for an address already on file (AC-003).
    expect(existingCopy).toBe(freshCopy);
  });

  it("sign-in: a successful login stores the token and navigates to library", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(200, { access_token: "jwt-123" }),
    );
    const user = userEvent.setup();
    renderScreen();

    await user.type(screen.getByLabelText("Email address"), "verified@example.com");
    await user.type(screen.getByLabelText("Password"), "whatever-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("library"));
    expect(getToken()).toBe("jwt-123");
  });

  it("sign-in: a 401 renders only the generic invalid credentials message", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(401, { detail: "Incorrect password" }),
    );
    const user = userEvent.setup();
    renderScreen();

    await user.type(screen.getByLabelText("Email address"), "someone@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Invalid email or password.");
    expect(alert).not.toHaveTextContent("Incorrect password");
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("sign-in: a 403 renders the unverified notice with a working resend action", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/auth/login")) return jsonResponse(403, { detail: "Not verified" });
      return jsonResponse(202, { message: "accepted" });
    });
    const user = userEvent.setup();
    renderScreen();

    await user.type(screen.getByLabelText("Email address"), "unverified@example.com");
    await user.type(screen.getByLabelText("Password"), "Correct-Horse-9!");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText(/Account not verified\./)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Resend verification email" }));

    expect(await screen.findByText(/Verification email re-sent/)).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/auth/register"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("forgot password: always shows the neutral sent panel", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(202, { message: "accepted" }),
    );
    const user = userEvent.setup();
    renderScreen();

    await user.click(screen.getByRole("button", { name: "Forgot your password?" }));
    await user.type(screen.getByLabelText("Email address"), "someone@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByText(/password reset link has been sent/)).toBeInTheDocument();
  });
});
