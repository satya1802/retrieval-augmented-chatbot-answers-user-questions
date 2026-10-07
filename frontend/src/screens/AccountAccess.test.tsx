import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AccountAccess from "./AccountAccess";

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

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/account-access" element={<AccountAccess />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AccountAccess", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("verify: posts the URL token to /auth/verify and offers continue to sign in on success", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(200, { verified: true }),
    );
    const user = userEvent.setup();
    renderAt("/account-access?token=tok_abc123&purpose=verify");

    await user.click(screen.getByRole("button", { name: /Confirm my email address/ }));

    expect(await screen.findByText("Email address verified")).toBeInTheDocument();
    const continueBtn = screen.getByRole("button", { name: /Continue to sign in/ });
    expect(continueBtn).toBeInTheDocument();

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/auth/verify"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ token: "tok_abc123" }),
      }),
    );

    await user.click(continueBtn);
    expect(mockNavigate).toHaveBeenCalledWith("sign-in");
  });

  it("verify: a failed verification shows a clear expired/used state", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(410, { detail: "Token expired" }),
    );
    const user = userEvent.setup();
    renderAt("/account-access?token=tok_expired&purpose=verify");

    await user.click(screen.getByRole("button", { name: /Confirm my email address/ }));

    expect(await screen.findByText("This link can’t be used")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/no longer valid/);
  });

  it("password reset: posts the new password to /auth/password-reset/confirm and succeeds", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(200, { message: "ok" }),
    );
    const user = userEvent.setup();
    renderAt("/account-access?token=tok_reset1&purpose=reset");

    await user.type(screen.getByLabelText("New password"), "Correct-Horse-9!");
    await user.type(screen.getByLabelText("Re-type new password"), "Correct-Horse-9!");
    await user.click(screen.getByRole("button", { name: /Save new password/ }));

    expect(await screen.findByText("Password updated")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/auth/password-reset/confirm"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ token: "tok_reset1", new_password: "Correct-Horse-9!" }),
      }),
    );
  });

  it("password reset: reuse of a consumed link is reported as an error", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(410, { detail: "Token already used" }),
    );
    const user = userEvent.setup();
    renderAt("/account-access?token=tok_used&purpose=reset");

    await user.type(screen.getByLabelText("New password"), "Correct-Horse-9!");
    await user.type(screen.getByLabelText("Re-type new password"), "Correct-Horse-9!");
    await user.click(screen.getByRole("button", { name: /Save new password/ }));

    expect(await screen.findByText("This link can’t be used")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/already been used to set a password/);
  });

  it("shows a missing-token error state when no token is present in the URL", () => {
    renderAt("/account-access");

    expect(screen.getByText("This link can’t be used")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
});
