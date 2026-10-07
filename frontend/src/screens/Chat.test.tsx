import { render, screen } from "@testing-library/react";
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

describe("Chat screen", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads conversations and documents with no seeded sample data", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
      }),
    );

    render(<Chat />);

    expect(await screen.findByText("No conversations yet. Start one below.")).toBeInTheDocument();
    expect(await screen.findByText("Supplier Agreement")).toBeInTheDocument();
    expect(screen.queryByText(/Northwind Logistics/)).not.toBeInTheDocument();
  });

  it("shows the empty-library message in the scope panel when there are no ready documents", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [] }),
      }),
    );

    render(<Chat />);

    expect(
      await screen.findByText(/No ready documents yet\. Upload documents/),
    ).toBeInTheDocument();
  });

  it("'Use all ready documents' clears an explicit scope selection", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      mockFetchRouter({
        "GET /conversations": () => jsonResponse(200, { conversations: [] }),
        "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
      }),
    );
    const user = userEvent.setup();
    render(<Chat />);

    const checkbox = await screen.findByLabelText("Supplier Agreement");
    await user.click(checkbox);
    expect(checkbox).toBeChecked();

    await user.click(screen.getByRole("button", { name: /Use all ready documents/ }));
    expect(checkbox).not.toBeChecked();
  });

  it("submits a question via POST /conversations then /messages, persisting the scope, and renders the answer with citations", async () => {
    const createdConversation = {
      id: "conv-1",
      title: null,
      scope_document_ids: ["doc-1"],
      created_at: "2026-10-07T10:00:00Z",
    };
    const fetchMock = mockFetchRouter({
      "GET /conversations": () => jsonResponse(200, { conversations: [] }),
      "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
      "POST /conversations": () => jsonResponse(201, { conversation: createdConversation }),
      "POST /conversations/:id/messages": () =>
        jsonResponse(200, {
          message: {
            id: "msg-1",
            role: "assistant",
            content: "The supplier agreement renews annually.",
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
    });
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(fetchMock);
    const user = userEvent.setup();
    render(<Chat />);

    await screen.findByText("Supplier Agreement");
    await user.click(screen.getByLabelText("Supplier Agreement"));

    const textarea = screen.getByLabelText("Ask a question");
    await user.type(textarea, "When does it renew?");
    await user.click(screen.getByRole("button", { name: /^Ask/ }));

    expect(await screen.findByText("The supplier agreement renews annually.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Supplier Agreement/ })).toBeInTheDocument();

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/conversations"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ scope_document_ids: ["doc-1"] }),
      }),
    );
  });

  it("renders the insufficient-context reply with zero sources", async () => {
    const createdConversation = {
      id: "conv-2",
      title: null,
      scope_document_ids: [],
      created_at: "2026-10-07T10:00:00Z",
    };
    const fetchMock = mockFetchRouter({
      "GET /conversations": () => jsonResponse(200, { conversations: [] }),
      "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
      "POST /conversations": () => jsonResponse(201, { conversation: createdConversation }),
      "POST /conversations/:id/messages": () =>
        jsonResponse(200, {
          message: {
            id: "msg-2",
            role: "assistant",
            content:
              "I don't have enough information in the provided context to answer that accurately.",
            is_incomplete: true,
            created_at: "2026-10-07T10:01:00Z",
            citations: [],
          },
          citations: [],
        }),
    });
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(fetchMock);
    const user = userEvent.setup();
    render(<Chat />);

    await screen.findByText("Supplier Agreement");
    const textarea = screen.getByLabelText("Ask a question");
    await user.type(textarea, "What is the capital of France?");
    await user.click(screen.getByRole("button", { name: /^Ask/ }));

    expect(
      await screen.findByText(
        "I don't have enough information in the provided context to answer that accurately.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("No sources.")).toBeInTheDocument();
  });

  it("clicking a citation calls GET /chunks/{id} and shows the chunk text", async () => {
    const conversation = {
      id: "conv-3",
      title: "Prior conversation",
      scope_document_ids: [],
      created_at: "2026-10-01T10:00:00Z",
    };
    const fetchMock = mockFetchRouter({
      "GET /conversations": () => jsonResponse(200, { conversations: [conversation] }),
      "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
      "GET /conversations/:id": () =>
        jsonResponse(200, {
          conversation,
          messages: [
            {
              id: "msg-3",
              role: "assistant",
              content: "The notice period is 30 days.",
              is_incomplete: false,
              created_at: "2026-10-01T10:01:00Z",
              citations: [
                {
                  chunk_id: "chunk-9",
                  document_title_snapshot: "Supplier Agreement",
                  chunk_position: 4,
                },
              ],
            },
          ],
        }),
      "GET /chunks/:id": () =>
        jsonResponse(200, {
          text: "Either party may terminate with 30 days written notice.",
          document_title: "Supplier Agreement",
          position: 4,
        }),
    });
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(fetchMock);
    const user = userEvent.setup();
    render(<Chat />);

    await user.click(await screen.findByText("Prior conversation"));
    await screen.findByText("The notice period is 30 days.");
    await user.click(screen.getByRole("button", { name: /Supplier Agreement/ }));

    expect(
      await screen.findByText("Either party may terminate with 30 days written notice."),
    ).toBeInTheDocument();
  });

  it("shows the evidence-unavailable message, not chunk text, on a 404", async () => {
    const conversation = {
      id: "conv-4",
      title: "Old conversation",
      scope_document_ids: [],
      created_at: "2026-09-01T10:00:00Z",
    };
    const fetchMock = mockFetchRouter({
      "GET /conversations": () => jsonResponse(200, { conversations: [conversation] }),
      "GET /documents": () => jsonResponse(200, { documents: [READY_DOC] }),
      "GET /conversations/:id": () =>
        jsonResponse(200, {
          conversation,
          messages: [
            {
              id: "msg-4",
              role: "assistant",
              content: "Deleted doc answer.",
              is_incomplete: false,
              created_at: "2026-09-01T10:01:00Z",
              citations: [
                {
                  chunk_id: "chunk-gone",
                  document_title_snapshot: "Deleted Document",
                  chunk_position: 1,
                },
              ],
            },
          ],
        }),
      "GET /chunks/:id": () =>
        jsonResponse(404, { detail: "source document is no longer available" }),
    });
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(fetchMock);
    const user = userEvent.setup();
    render(<Chat />);

    await user.click(await screen.findByText("Old conversation"));
    await screen.findByText("Deleted doc answer.");
    await user.click(screen.getByRole("button", { name: /Deleted Document/ }));

    expect(
      await screen.findByText("This source document is no longer available"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/terminate/)).not.toBeInTheDocument();
  });
});
