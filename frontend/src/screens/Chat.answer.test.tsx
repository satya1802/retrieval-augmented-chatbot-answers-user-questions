import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Chat from "./Chat";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

const READY_DOC = {
  id: "doc-1",
  title: "Supplier Agreement",
  file_type: "PDF",
  status: "ready",
  failure_reason: null,
  uploaded_at: "2026-09-28T10:00:00Z",
};

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

describe("Chat screen -- answer, sources and errors (US-014-3)", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("AC-052: renders an Answer heading followed by a Sources section listing citations", async () => {
    const createdConversation = {
      id: "conv-1",
      title: null,
      scope_document_ids: [],
      created_at: "2026-10-07T10:00:00Z",
    };
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
        "POST /conversations": () => jsonResponse(201, { conversation: createdConversation }),
        "POST /conversations/:id/messages": () =>
          jsonResponse(200, {
            message: {
              id: "msg-1",
              role: "assistant",
              content: "The agreement renews annually [1].",
              is_incomplete: false,
              created_at: "2026-10-07T10:01:00Z",
              citations: [
                {
                  chunk_id: "chunk-1",
                  document_title_snapshot: "Supplier Agreement",
                  chunk_position: 2,
                },
              ],
            },
            citations: [],
          }),
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByText("Supplier Agreement");
    await askQuestionFlow(user, "When does it renew?");

    expect(await screen.findByText("Answer")).toBeInTheDocument();
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Supplier Agreement" })).toBeInTheDocument();
  });

  it("AC-053: an inline citation marker in the body is clickable and opens the Evidence panel", async () => {
    const createdConversation = {
      id: "conv-1",
      title: null,
      scope_document_ids: [],
      created_at: "2026-10-07T10:00:00Z",
    };
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
        "POST /conversations": () => jsonResponse(201, { conversation: createdConversation }),
        "POST /conversations/:id/messages": () =>
          jsonResponse(200, {
            message: {
              id: "msg-1",
              role: "assistant",
              content: "The agreement renews annually [1].",
              is_incomplete: false,
              created_at: "2026-10-07T10:01:00Z",
              citations: [
                {
                  chunk_id: "chunk-1",
                  document_title_snapshot: "Supplier Agreement",
                  chunk_position: 2,
                },
              ],
            },
            citations: [],
          }),
        "GET /chunks/:id": () =>
          jsonResponse(200, {
            text: "Renewal term is automatic, annually.",
            document_title: "Supplier Agreement",
            position: 2,
          }),
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByText("Supplier Agreement");
    await askQuestionFlow(user, "When does it renew?");
    await screen.findByText("Answer");

    const marker = screen.getByRole("button", { name: /View source 1: Supplier Agreement/ });
    await user.click(marker);

    expect(await screen.findByText("Renewal term is automatic, annually.")).toBeInTheDocument();
  });

  it("AC-054: no citations means Sources shows no references and nothing invented", async () => {
    const createdConversation = {
      id: "conv-2",
      title: null,
      scope_document_ids: [],
      created_at: "2026-10-07T10:00:00Z",
    };
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
        "POST /conversations": () => jsonResponse(201, { conversation: createdConversation }),
        "POST /conversations/:id/messages": () =>
          jsonResponse(200, {
            message: {
              id: "msg-2",
              role: "assistant",
              content: "Here is the answer with no backing sources.",
              is_incomplete: false,
              created_at: "2026-10-07T10:01:00Z",
              citations: [],
            },
            citations: [],
          }),
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByText("Supplier Agreement");
    await askQuestionFlow(user, "Anything on file?");

    await screen.findByText("Sources");
    expect(screen.getByText("No sources.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /View source/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Supplier Agreement" })).not.toBeInTheDocument();
  });

  it("AC-056: bulleted content renders as a list, paragraph content renders as a paragraph", async () => {
    const createdConversation = {
      id: "conv-3",
      title: null,
      scope_document_ids: [],
      created_at: "2026-10-07T10:00:00Z",
    };
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
        "POST /conversations": () => jsonResponse(201, { conversation: createdConversation }),
        "POST /conversations/:id/messages": () =>
          jsonResponse(200, {
            message: {
              id: "msg-3",
              role: "assistant",
              content: "Here is a summary.\n\n- First point\n- Second point",
              is_incomplete: false,
              created_at: "2026-10-07T10:01:00Z",
              citations: [],
            },
            citations: [],
          }),
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByText("Supplier Agreement");
    await askQuestionFlow(user, "Summarize it");

    const paragraph = await screen.findByText("Here is a summary.");
    expect(paragraph.tagName).toBe("P");
    const list = screen.getByText("First point").closest("ul");
    expect(list).not.toBeNull();
    expect(within(list as HTMLElement).getByText("Second point")).toBeInTheDocument();
  });

  it("AC-050: the insufficient-context answer renders alone with no Sources entries", async () => {
    const createdConversation = {
      id: "conv-4",
      title: null,
      scope_document_ids: [],
      created_at: "2026-10-07T10:00:00Z",
    };
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
        "POST /conversations": () => jsonResponse(201, { conversation: createdConversation }),
        "POST /conversations/:id/messages": () =>
          jsonResponse(200, {
            message: {
              id: "msg-4",
              role: "assistant",
              content:
                "I don't have enough information in the selected documents to answer that question.",
              is_incomplete: true,
              created_at: "2026-10-07T10:01:00Z",
              citations: [],
            },
            citations: [],
          }),
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);
    await screen.findByText("Supplier Agreement");
    await askQuestionFlow(user, "What is the capital of France?");

    expect(
      await screen.findByText(
        "I don't have enough information in the selected documents to answer that question.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("No sources.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /View source/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Supplier Agreement" })).not.toBeInTheDocument();
  });

  it("AC-048: a 502 from the ask endpoint shows a generation-failure error and leaves no partial assistant bubble", async () => {
    const createdConversation = {
      id: "conv-5",
      title: null,
      scope_document_ids: [],
      created_at: "2026-10-07T10:00:00Z",
    };
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
        "POST /conversations": () => jsonResponse(201, { conversation: createdConversation }),
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
});
