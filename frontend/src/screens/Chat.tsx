import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import {
  ApiError,
  createConversation,
  getChunk,
  getConversation,
  listConversations,
  listDocuments,
  streamAskQuestion,
  type AskQuestionResponse,
  type ChunkDetailResponse,
  type CitationOut,
  type ConversationOut,
  type DocumentOut,
  type MessageOut,
} from "@/lib/api";

const { Button, Textarea, Card, Separator, Checkbox, Label, Badge } = UI;
const { Plus, FileText, AlertCircle, ArrowRight, X, Check } = Icons;

const NOT_FOUND_EVIDENCE = "This source document is no longer available";
// AC-048, AC-070: the one message shown whenever the ask stream fails
// before any answer text arrived -- a 502 from the endpoint, a network
// failure, or a connection that closed with nothing read at all. Distinct
// from a *partial* answer (AC-070's other case), which is rendered and
// marked incomplete instead of replaced by this banner.
const GENERATION_FAILED_MESSAGE = "The answer could not be generated. Try again.";

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

// ------------------------------------------------------------- answer body --
// AC-056: a blank line separates paragraphs from bulleted lists. A block is
// treated as a list only when every one of its lines starts with "-" or
// "*" -- anything else, including a block that mixes prose and bullets,
// renders as a single paragraph rather than guessing at structure the
// backend did not send. This is formatting only: no answer text is
// invented or altered, only laid out.
type AnswerBlock = { type: "list"; items: string[] } | { type: "para"; text: string };

function parseAnswerBlocks(content: string): AnswerBlock[] {
  const blocks = content
    .split(/\n{2,}/)
    .map((b) => b.trim())
    .filter((b) => b.length > 0);
  if (blocks.length === 0) return [];
  return blocks.map((block) => {
    const lines = block
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 0);
    const isList = lines.length > 0 && lines.every((l) => /^[-*]\s+/.test(l));
    if (isList) {
      return { type: "list", items: lines.map((l) => l.replace(/^[-*]\s+/, "")) };
    }
    return { type: "para", text: block };
  });
}

// AC-053: inline citation markers -- "[1]", "[2]", ... -- reference the
// message's own `citations` array by position (1-indexed, matching how the
// markers read). A marker with no matching citation renders as plain text
// rather than a dead button.
function renderInlineText(
  text: string,
  citations: CitationOut[],
  onCite: (citation: CitationOut) => void,
): React.ReactNode[] {
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const citation = citations[Number(match[1]) - 1];
      if (citation) {
        return (
          <button
            key={i}
            type="button"
            onClick={() => onCite(citation)}
            className="mx-0.5 rounded px-0.5 text-xs font-semibold underline decoration-dotted hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
            style={{ color: brand.primaryColor }}
            aria-label={`View source ${match[1]}: ${citation.document_title_snapshot}`}
          >
            {part}
          </button>
        );
      }
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

function AnswerBody({
  content,
  citations,
  onCite,
}: {
  content: string;
  citations: CitationOut[];
  onCite: (citation: CitationOut) => void;
}) {
  const blocks = parseAnswerBlocks(content);
  return (
    <div className="space-y-2">
      {blocks.map((block, i) =>
        block.type === "list" ? (
          <ul key={i} className="ml-4 list-disc space-y-1">
            {block.items.map((item, j) => (
              <li key={j}>{renderInlineText(item, citations, onCite)}</li>
            ))}
          </ul>
        ) : (
          <p key={i} className="whitespace-pre-wrap">
            {renderInlineText(block.text, citations, onCite)}
          </p>
        ),
      )}
    </div>
  );
}

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

  // AC-068: the id of the assistant message currently receiving `delta`
  // events -- drives the in-progress indicator and withholds the Sources
  // section until the answer is actually done. AC-070: the id of a
  // message whose stream ended before `done`/`error` arrived -- rendered
  // with its partial text, visibly marked incomplete, and a Retry control.
  const [streamingId, setStreamingId] = React.useState<string | null>(null);
  const [truncatedId, setTruncatedId] = React.useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = React.useState("");

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
    setStreamingId(null);
    setTruncatedId(null);
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
    setStreamingId(null);
    setTruncatedId(null);
    setLastQuestion("");
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

  // AC-067 through AC-070: runs one ask -- creating the conversation if
  // needed, appending the user's question and an empty assistant draft,
  // then streaming the answer into that draft token by token. Shared by
  // the composer submit and the Retry control so a retry is exactly
  // "re-ask the same question" rather than a second code path.
  async function askFlow(trimmed: string) {
    setAsking(true);
    setAskError("");
    setTruncatedId(null);
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
      const draftId = `streaming-${Date.now()}`;
      const draftMessage: MessageOut = {
        id: draftId,
        role: "assistant",
        content: "",
        is_incomplete: false,
        created_at: new Date().toISOString(),
        citations: [],
      };
      setMessages((prev) => [...prev, optimisticUser, draftMessage]);
      setLastQuestion(trimmed);
      setStreamingId(draftId);

      let draftContent = "";
      let gotAnyDelta = false;

      const clearStreaming = () => setStreamingId((prev) => (prev === draftId ? null : prev));

      const handleCutShort = () => {
        if (!gotAnyDelta) {
          // AC-048/AC-070: nothing ever rendered for this turn -- remove
          // the empty draft bubble and show the banner instead.
          setMessages((prev) => prev.filter((m) => m.id !== draftId));
          setAskError(GENERATION_FAILED_MESSAGE);
        } else {
          // Partial text already arrived: keep it, mark it incomplete,
          // offer Retry -- do not discard it and do not show the banner.
          setMessages((prev) =>
            prev.map((m) =>
              m.id === draftId ? { ...m, content: draftContent, is_incomplete: true } : m,
            ),
          );
          setTruncatedId(draftId);
        }
      };

      await streamAskQuestion(conversationId, trimmed, {
        onDelta: (textDelta) => {
          gotAnyDelta = true;
          draftContent += textDelta;
          setMessages((prev) =>
            prev.map((m) => (m.id === draftId ? { ...m, content: draftContent } : m)),
          );
        },
        onDone: (result: AskQuestionResponse) => {
          clearStreaming();
          setMessages((prev) => prev.map((m) => (m.id === draftId ? result.message : m)));
        },
        onError: () => {
          clearStreaming();
          handleCutShort();
        },
        onStreamEnded: () => {
          // AC-070: the connection closed before `done` or `error` arrived.
          clearStreaming();
          handleCutShort();
        },
      });
    } catch (err) {
      setAskError(
        err instanceof ApiError ? err.message : "Could not send your question. Try again.",
      );
    } finally {
      setAsking(false);
    }
  }

  async function submitQuestion(e: React.FormEvent) {
    e.preventDefault();
    // AC-069: an empty or whitespace-only question sends nothing at all.
    const trimmed = question.trim();
    if (trimmed === "") return;
    setQuestion("");
    await askFlow(trimmed);
  }

  async function retryLastQuestion() {
    if (!lastQuestion || asking) return;
    setTruncatedId(null);
    await askFlow(lastQuestion);
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
                {messages.map((m) => {
                  const isStreaming = streamingId === m.id;
                  const isTruncated = truncatedId === m.id;
                  return (
                    <li key={m.id}>
                      <div
                        className="max-w-[90%] rounded-lg px-3 py-2 text-sm"
                        style={
                          m.role === "user"
                            ? { backgroundColor: "#E8EEF4", marginLeft: "auto" }
                            : { backgroundColor: "#F3F5F7" }
                        }
                      >
                        {m.role === "user" ? (
                          <p className="whitespace-pre-wrap">{m.content}</p>
                        ) : (
                          <div>
                            {/* AC-052: the Answer heading precedes the body
                                of every assistant message. */}
                            <h3
                              className="mb-1 text-[11px] font-semibold uppercase tracking-wide"
                              style={{ color: brand.primaryColor }}
                            >
                              Answer
                            </h3>
                            {isStreaming ? (
                              // AC-068: a visible in-progress indicator from
                              // submit until the answer completes.
                              <p
                                role="status"
                                className="mb-1 text-xs italic"
                                style={{ color: brand.neutralColor }}
                              >
                                Generating answer…
                              </p>
                            ) : null}
                            <AnswerBody
                              content={m.content}
                              citations={m.citations}
                              onCite={inspectCitation}
                            />
                            {isTruncated ? (
                              // AC-070: the partial answer is rendered and
                              // visibly marked incomplete, with a Retry
                              // control that re-asks the same question.
                              <div className="mt-2 flex flex-wrap items-center gap-2">
                                <Badge variant="warning">Incomplete</Badge>
                                <span className="text-xs" style={{ color: brand.neutralColor }}>
                                  The connection ended before the answer finished.
                                </span>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="secondary"
                                  disabled={asking}
                                  onClick={() => void retryLastQuestion()}
                                >
                                  Retry
                                </Button>
                              </div>
                            ) : null}
                          </div>
                        )}
                      </div>
                      {m.role !== "user" && !isStreaming && !isTruncated ? (
                        <div className="mt-1.5">
                          {/* AC-052: Sources follows Answer for every
                              completed assistant message, even when there
                              is nothing to list (AC-054, AC-050) -- no
                              placeholder or invented source is ever
                              rendered here. A message still streaming or
                              cut short never reaches this section at all. */}
                          <h4
                            className="mb-1 text-[11px] font-semibold uppercase tracking-wide"
                            style={{ color: brand.neutralColor }}
                          >
                            Sources
                          </h4>
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
                  );
                })}
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
