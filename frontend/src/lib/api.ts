/// <reference types="vite/client" />
// Without the reference above, `import.meta.env` is not typed and `tsc --noEmit` fails --
// which `vite build` does not catch, because it tree-shakes this module out when no screen
// imports it yet.
//
// Where the generated API lives.
//
// Set at build time: the platform bakes the deployed API URL into the frontend build. The
// fallback is the local backend so a bare `npm run dev` still points somewhere real.
import { clearToken, getToken } from "@/lib/auth";

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** Raised for any non-2xx response. `status` lets callers branch on the
 * HTTP code (e.g. 403 unverified vs 401 bad credentials) without parsing
 * the message text. */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readDetail(response: Response): Promise<string | undefined> {
  try {
    const body = (await response.clone().json()) as { detail?: unknown };
    return typeof body?.detail === "string" ? body.detail : undefined;
  } catch {
    return undefined;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    // AC-010: a 401 on a call that *carried* a token means the token expired
    // or was revoked server-side -- clear it and send the visitor back to
    // sign-in once, here, rather than duplicating this check in every
    // screen that calls apiFetch. A 401 with no token held (e.g. a failed
    // login attempt, which never attaches one) is just a normal credential
    // error and is left for the caller to render.
    if (response.status === 401 && token) {
      clearToken();
      if (typeof window !== "undefined") {
        const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
        window.location.assign(`/sign-in?next=${next}`);
      }
    }
    const detail = await readDetail(response);
    throw new ApiError(
      response.status,
      detail ?? `${init?.method ?? "GET"} ${path} failed: ${response.status}`,
    );
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export type MessageResponse = { message: string };
export type LoginResponse = { access_token: string };
export type VerifyResponse = { verified: boolean };

export function registerAccount(email: string, password: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function verifyAccount(token: string): Promise<VerifyResponse> {
  return apiFetch<VerifyResponse>("/auth/verify", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function requestPasswordReset(email: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/password-reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function confirmPasswordReset(token: string, newPassword: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/password-reset/confirm", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

// -------------------------------------------------------------- library --

/** Mirrors `app.schemas.DocumentOut`. `status` is server-owned: the backend
 * is free to introduce values beyond these three, so the screen renders
 * whatever string it gets back rather than asserting a closed set. */
export type DocumentStatus = "processing" | "ready" | "failed";

export type DocumentOut = {
  id: string;
  title: string;
  file_type: string;
  status: DocumentStatus;
  failure_reason: string | null;
  uploaded_at: string;
};

export type DocumentListResponse = { documents: DocumentOut[] };

/** Mirrors `app.schemas.UsageResponse` (GET /me/usage). */
export type UsageResponse = {
  document_count: number;
  documents_cap: number;
  remaining_questions: number;
  reset_date: string;
};

export function listDocuments(): Promise<DocumentListResponse> {
  return apiFetch<DocumentListResponse>("/documents");
}

export function renameDocument(id: string, title: string): Promise<DocumentOut> {
  return apiFetch<DocumentOut>(`/documents/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function deleteDocument(id: string): Promise<void> {
  return apiFetch<void>(`/documents/${id}`, { method: "DELETE" });
}

export function getUsage(): Promise<UsageResponse> {
  return apiFetch<UsageResponse>("/me/usage");
}

// --------------------------------------------------------- conversations --

/** Mirrors `app.schemas.ConversationOut`. An empty `scope_document_ids`
 * means "all of the caller's ready documents" (AC-039, AC-040) -- the
 * backend never materialises the full id list for that case. */
export type ConversationOut = {
  id: string;
  title: string | null;
  scope_document_ids: string[];
  created_at: string;
};

export type ConversationListResponse = { conversations: ConversationOut[] };

export type ConversationCreateRequest = {
  title?: string | null;
  scope_document_ids?: string[] | null;
};

export type ConversationCreateResponse = { conversation: ConversationOut };

/** Mirrors `app.schemas.CitationOut`. `chunk_id` is null when the source
 * document was deleted after the citation was recorded -- there is no
 * chunk left to fetch, so callers should not attempt `getChunk` for it. */
export type CitationOut = {
  chunk_id: string | null;
  document_title_snapshot: string;
  chunk_position: number;
};

export type MessageOut = {
  id: string;
  role: string;
  content: string;
  is_incomplete: boolean;
  created_at: string;
  citations: CitationOut[];
};

export type ConversationDetailResponse = {
  conversation: ConversationOut;
  messages: MessageOut[];
};

export type AskQuestionResponse = {
  message: MessageOut;
  citations: CitationOut[];
};

export type ChunkDetailResponse = {
  text: string;
  document_title: string;
  position: number;
};

export function listConversations(): Promise<ConversationListResponse> {
  return apiFetch<ConversationListResponse>("/conversations");
}

export function createConversation(
  body: ConversationCreateRequest,
): Promise<ConversationCreateResponse> {
  return apiFetch<ConversationCreateResponse>("/conversations", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getConversation(id: string): Promise<ConversationDetailResponse> {
  return apiFetch<ConversationDetailResponse>(`/conversations/${id}`);
}

export function askQuestion(
  conversationId: string,
  question: string,
): Promise<AskQuestionResponse> {
  return apiFetch<AskQuestionResponse>(`/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

// ------------------------------------------------------- streaming ask --

/** Callbacks for `streamAskQuestion` (US-020-1's SSE contract: `delta`,
 * `done`, `error` events over `POST /conversations/:id/messages`).
 * `onError` and `onStreamEnded` are both "this turn did not finish
 * cleanly" signals -- `onError` fires when the server sent an explicit
 * `error` event (or the request failed before any event arrived at all),
 * `onStreamEnded` fires when the connection simply closed without a
 * `done` or `error` ever being seen. Callers (Chat.tsx) treat both the
 * same way: AC-070 if any text had already streamed in, AC-048's
 * generation-failed message otherwise. */
export type AskStreamHandlers = {
  onDelta: (textDelta: string) => void;
  onDone: (result: AskQuestionResponse) => void;
  onError: (message?: string) => void;
  onStreamEnded: () => void;
};

function parseSseEvent(raw: string): { event: string; data: string } {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }
  return { event, data: dataLines.join("\n") };
}

/**
 * Streams an answer for `question` in `conversationId`, invoking
 * `handlers` as `delta`/`done`/`error` events arrive on the SSE response.
 *
 * Screens never call `fetch` directly (per constraint) -- this is the one
 * seam that does, alongside `apiFetch`. It is a separate function rather
 * than a mode of `apiFetch` because the two have incompatible response
 * handling: `apiFetch` always awaits one JSON body, this reads an
 * event-stream incrementally and can also fall back to a single JSON body
 * when the response has no readable stream (a plain non-streaming mock or
 * backend), so callers written against the contract keep working either
 * way.
 */
export async function streamAskQuestion(
  conversationId: string,
  question: string,
  handlers: AskStreamHandlers,
): Promise<void> {
  const token = getToken();
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ question }),
    });
  } catch {
    // Network failure before any token arrived (AC-048's second case).
    handlers.onError();
    return;
  }

  if (!response.ok) {
    if (response.status === 401 && token) {
      clearToken();
      if (typeof window !== "undefined") {
        const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
        window.location.assign(`/sign-in?next=${next}`);
      }
    }
    const detail = await readDetail(response);
    handlers.onError(detail);
    return;
  }

  const body = response.body as ReadableStream<Uint8Array> | null | undefined;
  if (!body || typeof body.getReader !== "function") {
    // No readable stream on this response -- either a backend that still
    // answers with one JSON body, or a test double. Treat the whole body
    // as the final `done` payload rather than attempting to parse it as
    // SSE framing.
    try {
      const result = (await response.json()) as AskQuestionResponse;
      handlers.onDone(result);
    } catch {
      handlers.onError();
    }
    return;
  }

  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let settled = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sepIndex = buffer.indexOf("\n\n");
      while (sepIndex !== -1) {
        const rawEvent = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        const { event, data } = parseSseEvent(rawEvent);
        if (data.length > 0) {
          if (event === "delta") {
            try {
              // The SSE contract's delta payload carries the text chunk as
              // `content`; `text` is accepted too in case a future
              // revision of the contract renames the field.
              const parsed = JSON.parse(data) as { content?: string; text?: string };
              const chunk = parsed.content ?? parsed.text;
              if (typeof chunk === "string" && chunk.length > 0) {
                handlers.onDelta(chunk);
              }
            } catch {
              // Malformed delta frame -- skip rather than throw mid-stream.
            }
          } else if (event === "done") {
            settled = true;
            try {
              const parsed = JSON.parse(data) as AskQuestionResponse;
              handlers.onDone(parsed);
            } catch {
              handlers.onError();
            }
          } else if (event === "error") {
            settled = true;
            let message: string | undefined;
            try {
              const parsed = JSON.parse(data) as { detail?: string; message?: string };
              message = parsed.detail ?? parsed.message;
            } catch {
              message = undefined;
            }
            handlers.onError(message);
          }
        }
        sepIndex = buffer.indexOf("\n\n");
      }
    }
  } catch {
    // The connection dropped mid-read.
    if (!settled) handlers.onStreamEnded();
    return;
  }

  if (!settled) {
    // AC-070: the stream closed without a `done` or `error` event.
    handlers.onStreamEnded();
  }
}

export function getChunk(chunkId: string): Promise<ChunkDetailResponse> {
  return apiFetch<ChunkDetailResponse>(`/chunks/${chunkId}`);
}
