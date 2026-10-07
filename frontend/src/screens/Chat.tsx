import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import {
  ApiError,
  askQuestion,
  createConversation,
  getChunk,
  getConversation,
  listConversations,
  listDocuments,
  type ChunkDetailResponse,
  type CitationOut,
  type ConversationOut,
  type DocumentOut,
  type MessageOut,
} from "@/lib/api";

const { Button, Textarea, Card, Separator, Checkbox, Label } = UI;
const { Plus, FileText, AlertCircle, ArrowRight, X, Check } = Icons;

const NOT_FOUND_EVIDENCE = "This source document is no longer available";

type LoadState = "loading" | "ready" | "error";

function formatStamp(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type ChunkState = "idle" | "loading" | "ready" | "error";

export default function Screen() {
  // ------------------------------------------------------- conversations --
  const [conversations, setConversations] = React.useState<ConversationOut[]>([]);
  const [convState, setConvState] = React.useState<LoadState>("loading");
  const [convError, setConvError] = React.useState("");

  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [messages, setMessages] = React.useState<MessageOut[]>([]);
  const [threadState, setThreadState] = React.useState<LoadState>("ready");
  const [threadError, setThreadError] = React.useState("");

  // ------------------------------------------------------------ library --
  const [documents, setDocuments] = React.useState<DocumentOut[]>([]);
  const [docsState, setDocsState] = React.useState<LoadState>("loading");
  const [docsError, setDocsError] = React.useState("");

  // --------------------------------------------------------------- scope --
  const [scopeMode, setScopeMode] = React.useState<"all" | "custom">("all");
  const [customScopeIds, setCustomScopeIds] = React.useState<Set<string>>(new Set());

  // ------------------------------------------------------------ composer --
  const [question, setQuestion] = React.useState("");
  const [asking, setAsking] = React.useState(false);
  const [askError, setAskError] = React.useState("");

  // ------------------------------------------------------------ evidence --
  const [activeCitation, setActiveCitation] = React.useState<CitationOut | null>(null);
  const [chunk, setChunk] = React.useState<ChunkDetailResponse | null>(null);
  const [chunkState, setChunkState] = React.useState<ChunkState>("idle");
  const [chunkError, setChunkError] = React.useState("");

  const evidenceHeadingRef = React.useRef<HTMLHeadingElement | null>(null);

  const loadConversations = React.useCallback(async () => {
    setConvState("loading");
    try {
      const res = await listConversations();
      setConversations(res.conversations);
      setConvState("ready");
      setConvError("");
    } catch (err) {
      setConvState("error");
      setConvError(
        err instanceof ApiError ? err.message : "Could not load your conversations. Try again.",
      );
    }
  }, []);

  const loadDocuments = React.useCallback(async () => {
    setDocsState("loading");
    try {
      const res = await listDocuments();
      setDocuments(res.documents);
      setDocsState("ready");
      setDocsError("");
    } catch (err) {
      setDocsState("error");
      setDocsError(err instanceof ApiError ? err.message : "Could not load your documents.");
    }
  }, []);

  React.useEffect(() => {
    void loadConversations();
    void loadDocuments();
  }, [loadConversations, loadDocuments]);

  const readyDocuments = React.useMemo(
    () => documents.filter((d) => d.status === "ready"),
    [documents],
  );

  async function openConversation(id: string) {
    setActiveId(id);
    setThreadState("loading");
    setThreadError("");
    setActiveCitation(null);
    setChunk(null);
    setChunkState("idle");
    try {
      const detail = await getConversation(id);
      setMessages(detail.messages);
      setThreadState("ready");
    } catch (err) {
      setThreadState("error");
      setThreadError(
        err instanceof ApiError ? err.message : "Could not load this conversation. Try again.",
      );
    }
  }

  function startNewConversation() {
    setActiveId(null);
    setMessages([]);
    setThreadState("ready");
    setThreadError("");
    setScopeMode("all");
    setCustomScopeIds(new Set());
    setActiveCitation(null);
    setChunk(null);
    setChunkState("idle");
    setAskError("");
  }

  function toggleScopeDoc(id: string) {
    setScopeMode("custom");
    setCustomScopeIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function useAllReadyDocuments() {
    // AC-039, AC-040: clears any explicit scope selection.
    setScopeMode("all");
    setCustomScopeIds(new Set());
  }

  async function submitQuestion(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (trimmed === "") return;
    setAsking(true);
    setAskError("");
    try {
      let conversationId = activeId;
      if (!conversationId) {
        const scope_document_ids = scopeMode === "custom" ? Array.from(customScopeIds) : undefined;
        const created = await createConversation({ scope_document_ids });
        conversationId = created.conversation.id;
        setActiveId(conversationId);
        setConversations((prev) => [created.conversation, ...prev]);
      }
      const optimisticUser: MessageOut = {
        id: `pending-${Date.now()}`,
        role: "user",
        content: trimmed,
        is_incomplete: false,
        created_at: new Date().toISOString(),
        citations: [],
      };
      setMessages((prev) => [...prev, optimisticUser]);
      setQuestion("");
      const res = await askQuestion(conversationId, trimmed);
      setMessages((prev) => [...prev, res.message]);
    } catch (err) {
      setAskError(
        err instanceof ApiError ? err.message : "Could not send your question. Try again.",
      );
    } finally {
      setAsking(false);
    }
  }

  async function inspectCitation(citation: CitationOut) {
    setActiveCitation(citation);
    setChunk(null);
    if (!citation.chunk_id) {
      setChunkState("error");
      setChunkError(NOT_FOUND_EVIDENCE);
      if (evidenceHeadingRef.current) evidenceHeadingRef.current.focus();
      return;
    }
    setChunkState("loading");
    setChunkError("");
    try {
      const detail = await getChunk(citation.chunk_id);
      setChunk(detail);
      setChunkState("ready");
    } catch (err) {
      setChunkState("error");
      setChunkError(
        err instanceof ApiError && err.status === 404 ? NOT_FOUND_EVIDENCE : NOT_FOUND_EVIDENCE,
      );
    } finally {
      if (evidenceHeadingRef.current) evidenceHeadingRef.current.focus();
    }
  }

  const panelHeading = "text-[13px] font-semibold uppercase tracking-wide";

  return (
    <div
      className="mx-auto w-full max-w-[1280px] px-4 py-5"
      style={{ fontFamily: brand.fontBody, color: "#1B2430" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1
            className="text-xl font-semibold tracking-tight"
            style={{ fontFamily: brand.fontHeading, color: brand.primaryColor }}
          >
            Ask your documents
          </h1>
          <p className="mt-1 max-w-2xl text-sm" style={{ color: brand.neutralColor }}>
            Answers are grounded only in your ready documents, with sources you can inspect.
          </p>
        </div>
        <Button
          onClick={startNewConversation}
          className="shrink-0"
          style={{ backgroundColor: brand.primaryColor, color: "#FFFFFF" }}
        >
          <Plus className="mr-1.5 h-4 w-4" aria-hidden="true" />
          New conversation
        </Button>
      </div>

      <div className="mt-4 grid items-start gap-4 lg:grid-cols-[260px_minmax(0,1fr)_320px]">
        {/* ---------------- Conversations sidebar ---------------- */}
        <Card className="overflow-hidden">
          <div className="border-b border-slate-200 p-3">
            <h2 className={panelHeading} style={{ color: brand.primaryColor }}>
              Conversations
            </h2>
          </div>
          {convState === "loading" ? (
            <div className="p-4 text-sm" style={{ color: brand.neutralColor }}>
              Loading conversations…
            </div>
          ) : convState === "error" ? (
            <div className="p-4">
              <p role="alert" className="text-sm" style={{ color: "#8C1D18" }}>
                {convError}
              </p>
              <Button className="mt-2" size="sm" onClick={() => void loadConversations()}>
                Try again
              </Button>
            </div>
          ) : conversations.length === 0 ? (
            <p className="p-4 text-sm" style={{ color: brand.neutralColor }}>
              No conversations yet. Start one below.
            </p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {conversations.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => void openConversation(c.id)}
                    aria-current={activeId === c.id ? "true" : undefined}
                    className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                    style={activeId === c.id ? { backgroundColor: "#E8EEF4" } : undefined}
                  >
                    <span className="block truncate font-medium">
                      {c.title || "Untitled conversation"}
                    </span>
                    <span className="block text-xs" style={{ color: brand.neutralColor }}>
                      {formatStamp(c.created_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* ---------------- Thread + composer ---------------- */}
        <Card className="flex min-h-[520px] flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4">
            {threadState === "loading" ? (
              <p className="text-sm" style={{ color: brand.neutralColor }}>
                Loading conversation…
              </p>
            ) : threadState === "error" ? (
              <p role="alert" className="text-sm" style={{ color: "#8C1D18" }}>
                {threadError}
              </p>
            ) : messages.length === 0 ? (
              <p className="text-sm" style={{ color: brand.neutralColor }}>
                Ask a question below. Only your ready documents are used as context.
              </p>
            ) : (
              <ul className="space-y-4">
                {messages.map((m) => (
                  <li key={m.id}>
                    <div
                      className="max-w-[90%] rounded-lg px-3 py-2 text-sm"
                      style={
                        m.role === "user"
                          ? { backgroundColor: "#E8EEF4", marginLeft: "auto" }
                          : { backgroundColor: "#F3F5F7" }
                      }
                    >
                      <p className="whitespace-pre-wrap">{m.content}</p>
                    </div>
                    {m.role !== "user" ? (
                      <div className="mt-1.5">
                        {m.citations.length === 0 ? (
                          <p className="text-xs" style={{ color: brand.neutralColor }}>
                            No sources.
                          </p>
                        ) : (
                          <ul className="flex flex-wrap gap-1.5">
                            {m.citations.map((cit, idx) => (
                              <li key={`${m.id}-${idx}`}>
                                <button
                                  type="button"
                                  onClick={() => void inspectCitation(cit)}
                                  className="inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                                  style={{ borderColor: "#CBD5E1", color: brand.primaryColor }}
                                >
                                  <FileText className="h-3 w-3" aria-hidden="true" />
                                  {cit.document_title_snapshot}
                                </button>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <Separator />

          <form onSubmit={submitQuestion} className="p-3" noValidate>
            <Label htmlFor="chat-question" className="sr-only">
              Ask a question
            </Label>
            <Textarea
              id="chat-question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about your documents…"
              rows={2}
            />
            {askError ? (
              <p role="alert" className="mt-1 text-xs font-medium" style={{ color: "#8C1D18" }}>
                {askError}
              </p>
            ) : null}
            <div className="mt-2 flex justify-end">
              <Button
                type="submit"
                disabled={asking || question.trim() === ""}
                style={{ backgroundColor: brand.primaryColor, color: "#FFFFFF" }}
              >
                {asking ? "Asking…" : "Ask"}
                <ArrowRight className="ml-1.5 h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          </form>
        </Card>

        {/* ---------------- Scope + Evidence ---------------- */}
        <div className="flex flex-col gap-4">
          <Card className="p-3">
            <h2 className={panelHeading} style={{ color: brand.primaryColor }}>
              Scope
            </h2>
            <Separator className="my-2" />
            {activeId ? (
              <p className="text-xs" style={{ color: brand.neutralColor }}>
                This conversation was started with its scope fixed. Start a new conversation to
                change which documents are used.
              </p>
            ) : docsState === "loading" ? (
              <p className="text-sm" style={{ color: brand.neutralColor }}>
                Loading your documents…
              </p>
            ) : docsState === "error" ? (
              <p role="alert" className="text-sm" style={{ color: "#8C1D18" }}>
                {docsError}
              </p>
            ) : readyDocuments.length === 0 ? (
              <div className="py-2 text-center">
                <AlertCircle
                  className="mx-auto h-6 w-6"
                  aria-hidden="true"
                  style={{ color: brand.neutralColor }}
                />
                <p className="mt-2 text-sm" style={{ color: brand.neutralColor }}>
                  No ready documents yet. Upload documents and wait for them to finish processing
                  before asking questions.
                </p>
              </div>
            ) : (
              <>
                <button
                  type="button"
                  onClick={useAllReadyDocuments}
                  className="mb-2 flex w-full items-center justify-between rounded border px-2 py-1.5 text-xs font-medium hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                  style={
                    scopeMode === "all"
                      ? {
                          backgroundColor: brand.primaryColor,
                          color: "#FFFFFF",
                          borderColor: brand.primaryColor,
                        }
                      : { borderColor: "#CBD5E1", color: brand.neutralColor }
                  }
                >
                  Use all ready documents
                  {scopeMode === "all" ? (
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                  ) : null}
                </button>
                <ul className="max-h-64 space-y-1 overflow-y-auto">
                  {readyDocuments.map((doc) => (
                    <li key={doc.id} className="flex items-center gap-2">
                      <Checkbox
                        id={`scope-${doc.id}`}
                        checked={scopeMode === "custom" && customScopeIds.has(doc.id)}
                        onChange={() => toggleScopeDoc(doc.id)}
                      />
                      <label
                        htmlFor={`scope-${doc.id}`}
                        className="flex-1 truncate text-xs"
                        title={doc.title}
                      >
                        {doc.title}
                      </label>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Card>

          <Card className="p-3">
            <h2
              ref={evidenceHeadingRef}
              tabIndex={-1}
              className={panelHeading + " focus:outline-none"}
              style={{ color: brand.primaryColor }}
            >
              Evidence
            </h2>
            <Separator className="my-2" />
            {!activeCitation ? (
              <p className="text-sm" style={{ color: brand.neutralColor }}>
                Click a source under an answer to see the underlying text here.
              </p>
            ) : chunkState === "loading" ? (
              <p className="text-sm" style={{ color: brand.neutralColor }}>
                Loading source…
              </p>
            ) : chunkState === "error" ? (
              <p role="alert" className="text-sm font-medium" style={{ color: "#8C1D18" }}>
                {chunkError}
              </p>
            ) : chunkState === "ready" && chunk ? (
              <div>
                <p className="text-xs font-semibold" style={{ color: brand.primaryColor }}>
                  {chunk.document_title}
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">{chunk.text}</p>
                <button
                  type="button"
                  onClick={() => setActiveCitation(null)}
                  className="mt-2 inline-flex items-center gap-1 text-xs font-medium hover:underline"
                  style={{ color: brand.neutralColor }}
                >
                  <X className="h-3.5 w-3.5" aria-hidden="true" />
                  Close
                </button>
              </div>
            ) : null}
          </Card>
        </div>
      </div>
    </div>
  );
}
