import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch, ApiError } from "@/lib/api";
import { clearToken, getToken, setToken } from "@/lib/auth";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

describe("apiFetch 401 handling", () => {
  let assignSpy: ReturnType<typeof vi.fn>;
  let originalLocation: Location;

  beforeEach(() => {
    clearToken();
    vi.stubGlobal("fetch", vi.fn());
    assignSpy = vi.fn();
    originalLocation = window.location;
    // jsdom's real location throws "not implemented" on navigation; stub it
    // so the redirect call is observable instead.
    delete (window as unknown as { location?: Location }).location;
    (window as unknown as { location: Location }).location = {
      ...originalLocation,
      pathname: "/library",
      search: "",
      assign: assignSpy,
    } as unknown as Location;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    (window as unknown as { location: Location }).location = originalLocation;
    clearToken();
  });

  it("does not clear the token or redirect on a 401 with no token held (e.g. a failed login)", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(401, { detail: "Incorrect password" }),
    );

    await expect(apiFetch("/auth/login", { method: "POST" })).rejects.toBeInstanceOf(ApiError);

    expect(assignSpy).not.toHaveBeenCalled();
  });

  it("clears the token and redirects to sign-in, preserving the attempted path, on a 401 with a token held", async () => {
    setToken("expired-jwt");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(401, { detail: "Token expired" }),
    );

    await expect(apiFetch("/library/documents")).rejects.toBeInstanceOf(ApiError);

    expect(getToken()).toBeNull();
    expect(assignSpy).toHaveBeenCalledWith("/sign-in?next=%2Flibrary");
  });

  it("does not redirect on other error statuses", async () => {
    setToken("valid-jwt");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(() =>
      jsonResponse(500, { detail: "Server error" }),
    );

    await expect(apiFetch("/library/documents")).rejects.toBeInstanceOf(ApiError);

    expect(assignSpy).not.toHaveBeenCalled();
    expect(getToken()).toBe("valid-jwt");
  });
});
