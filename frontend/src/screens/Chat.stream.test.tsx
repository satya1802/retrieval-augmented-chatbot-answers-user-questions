import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Chat from "./Chat";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    clone() {
      return this;
    },
  } as unknown as Response);
}

const READY_DOC = {
  id: "doc-1",
  title: "Supplier Agreement",
  file_type: "PDF",
  status: "ready",
  failure_reason: null,
  uploaded_at: "2026-09-28T10:00:00Z",
};

function sseEvent(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/** A controllable SSE body: the test pushes encoded chunks and ends the
 * stream on its own schedule, so it can assert on state *between* chunks
 * (AC-068's "progressively", not just the eventual end state). */
function createControllableReader() {
  type ReadResult = { done: boolean; value?: Uint8Array };
  const queue: ReadResult[] = [];
  const waiting: Array<(x: ReadResult) => void> = [];
  return {
    push(text: string) {
      const value = new TextEncoder().encode(text);
      const item: ReadResult = { done: false, value };
      const resolver = waiting.shift();
      if (resolver) resolver(item);
      else queue.push(item);
    },
    end() {
      const item: ReadResult = { done: true };
      const resolver = waiting.shift();
      if (resolver) resolver(item);
      else queue.push(item);
    },
    read(): Promise<ReadResult> {
      const next = queue.shift();
      if (next) return Promise.resolve(next);
      return new Promise((resolve) => waiting.push(resolve));
    },
  };
}

function streamResponse(reader: ReturnType<typeof createControllableReader>) {
  return Promise.resolve({
    ok: true,
    status: 200,
    body: { getReader: () => reader },
    json: () => Promise.resolve({}),
    clone() {
      return this;
    },
  } as unknown as Response);
}

function mockFetchRouter(handlers: Record<string, (init?: RequestInit) => Promise<Response>>) {
  return vi.fn((url: string, init?: RequestInit) => {
    const path = url.replace("http://localhost:8000", "");
    const reqMethod = init?.method ?? "GET";
    for (const [key, handler] of Object.entries(handlers)) {
      const [method, pattern] = key.split(" ");
      const re = new RegExp("^" + pattern.replace(/:id/g, "[^/]+").replace(/\//g, "\\/") + "$");
      if (reqMethod === method && re.test(path)) {
        return handler(init);
      }
    }
    return jsonResponse(404, { detail: "not found" });
  });
}

async function askQuestionFlow(user: ReturnType<typeof userEvent.setup>, text: string) {
  const textarea = screen.getByLabelText("Ask a question");
  await user.type(textarea, text);
  await user.click(screen.getByRole("button", { name: /^Ask/ }));
}

type FetchCall = [string, RequestInit | undefined];

const CREATED_CONVERSATION = {
  id: "conv-1",
  title: null,
  scope_document_ids: [],
  created_at: "2026-10-07T10:00:00Z",
};

describe("Chat screen -- streaming ask (US-020-2)", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("AC-068: renders answer text progressively and shows an in-progress indicator until done", async () => {
    const reader = createControllableReader();
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
        "POST /conversations": () => jsonResponse(201, { conversation: CREATED_CONVERSATION }),
        "POST /conversations/:id/messages": () => streamResponse(reader),
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByText("Supplier Agreement");
    await askQuestionFlow(user, "When does it renew?");

    expect(await screen.findByRole("status")).toHaveTextContent(/Generating answer/i);

    reader.push(sseEvent("delta", { content: "The agreement" }));
    expect(await screen.findByText("The agreement")).toBeInTheDocument();
    expect(screen.queryByText("Sources")).not.toBeInTheDocument();

    reader.push(sseEvent("delta", { content: " renews annually." }));
    expect(await screen.findByText("The agreement renews annually.")).toBeInTheDocument();

    reader.push(
      sseEvent("done", {
        message: {
          id: "msg-1",
          role: "assistant",
          content: "The agreement renews annually.",
          is_incomplete: false,
          created_at: "2026-10-07T10:01:00Z",
          citations: [],
        },
        citations: [],
      }),
    );
    reader.end();

    expect(await screen.findByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("No sources.")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("AC-070: a stream that ends unexpectedly after partial text is marked incomplete, with no Sources, and Retry re-asks the same question", async () => {
    const reader = createControllableReader();
    let secondCallReader: ReturnType<typeof createControllableReader> | null = null;
    let callCount = 0;
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
        "POST /conversations": () => jsonResponse(201, { conversation: CREATED_CONVERSATION }),
        "POST /conversations/:id/messages": () => {
          callCount += 1;
          if (callCount === 1) return streamResponse(reader);
          secondCallReader = createControllableReader();
          return streamResponse(secondCallReader);
        },
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByText("Supplier Agreement");
    await askQuestionFlow(user, "What is the notice period?");

    reader.push(sseEvent("delta", { content: "Thirty days" }));
    await screen.findByText("Thirty days");
    // the connection drops: no `done`, no `error`, body just ends.
    reader.end();

    expect(await screen.findByText("Incomplete")).toBeInTheDocument();
    expect(
      screen.getByText("The connection ended before the answer finished."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Sources")).not.toBeInTheDocument();
    const retryButton = await screen.findByRole("button", { name: "Retry" });

    await user.click(retryButton);
    expect(await screen.findByText(/Generating answer/i)).toBeInTheDocument();
    expect(secondCallReader).not.toBeNull();
    secondCallReader!.push(
      sseEvent("done", {
        message: {
          id: "msg-2",
          role: "assistant",
          content: "The notice period is thirty days.",
          is_incomplete: false,
          created_at: "2026-10-07T10:02:00Z",
          citations: [],
        },
        citations: [],
      }),
    );
    secondCallReader!.end();

    expect(await screen.findByText("The notice period is thirty days.")).toBeInTheDocument();

    // the request body of the retried call carried the same question text.
    const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls as FetchCall[];
    const secondCall = calls.find(
      (call) =>
        call[0].includes("/messages") &&
        JSON.parse((call[1]?.body as string) ?? "{}").question === "What is the notice period?",
    );
    expect(secondCall).toBeTruthy();
  });

  it("AC-070 (error variant): an `error` event after partial text also marks the answer incomplete rather than showing the generic banner", async () => {
    const reader = createControllableReader();
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
        "POST /conversations": () => jsonResponse(201, { conversation: CREATED_CONVERSATION }),
        "POST /conversations/:id/messages": () => streamResponse(reader),
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByText("Supplier Agreement");
    await askQuestionFlow(user, "Anything on file?");

    reader.push(sseEvent("delta", { content: "Partial answer" }));
    await screen.findByText("Partial answer");
    reader.push(sseEvent("error", { detail: "provider timed out" }));
    reader.end();

    expect(await screen.findByText("Incomplete")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("AC-048/AC-070: a 502 before any token arrives shows the generation-failed banner, not an empty assistant bubble", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
        "POST /conversations": () => jsonResponse(201, { conversation: CREATED_CONVERSATION }),
        "POST /conversations/:id/messages": () =>
          jsonResponse(502, { detail: "generation failed" }),
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByText("Supplier Agreement");
    await askQuestionFlow(user, "Will this fail?");

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be generated/i);
    expect(screen.queryByText("Answer")).not.toBeInTheDocument();
  });

  it("AC-069: a network failure before any token arrives shows the generation-failed banner, not an empty assistant bubble", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
        "POST /conversations": () => jsonResponse(201, { conversation: CREATED_CONVERSATION }),
        "POST /conversations/:id/messages": () => Promise.reject(new TypeError("network error")),
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByText("Supplier Agreement");
    await askQuestionFlow(user, "Is the network up?");

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be generated/i);
    expect(screen.queryByText("Answer")).not.toBeInTheDocument();
  });

  it("AC-069: submitting an empty or whitespace-only question sends nothing and makes no API call", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByText("Supplier Agreement");

    const textarea = screen.getByLabelText("Ask a question");
    await user.type(textarea, "   ");
    const askButton = screen.getByRole("button", { name: /^Ask/ });
    expect(askButton).toBeDisabled();

    const callsBefore = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.length;
    const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls as FetchCall[];
    expect(calls.some((call) => call[0].includes("/messages"))).toBe(false);
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.length).toBe(callsBefore);
  });
});
