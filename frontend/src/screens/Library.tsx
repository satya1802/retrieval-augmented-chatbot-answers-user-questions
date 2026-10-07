import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";
import {
  ApiError,
  deleteDocument,
  getUsage,
  listDocuments,
  renameDocument,
  type DocumentOut,
  type DocumentStatus,
  type UsageResponse,
} from "@/lib/api";

const { Button, Card, Input, Label, Table, THead, TBody, TR, TH, TD, Separator } = UI;
const { Search, FileText, Trash, Edit, CheckCircle, AlertCircle, Clock, X, ArrowRight, Check } =
  Icons;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const FILTERS: Array<{ id: "all" | DocumentStatus; label: string }> = [
  { id: "all", label: "All" },
  { id: "ready", label: "Ready" },
  { id: "processing", label: "Processing" },
  { id: "failed", label: "Failed" },
];

// How often to re-poll GET /documents while any document is still
// 'processing' (AC-026). Stops the moment none are.
const POLL_INTERVAL_MS = 4000;

type LoadState = "loading" | "ready" | "error";

function formatStamp(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${hh}:${mm}`;
}

function formatDateOnly(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

function StatusChip({ status }: { status: DocumentStatus }) {
  const map: Record<
    string,
    { label: string; Icon: typeof CheckCircle; style: React.CSSProperties }
  > = {
    ready: {
      label: "Ready",
      Icon: CheckCircle,
      style: { backgroundColor: "#E7F3EC", color: "#1B5E34", borderColor: "#BFDDCB" },
    },
    processing: {
      label: "Processing",
      Icon: Clock,
      style: { backgroundColor: "rgba(227,181,5,0.18)", color: "#6B5200", borderColor: "#D9C068" },
    },
    failed: {
      label: "Failed",
      Icon: AlertCircle,
      style: { backgroundColor: "#FBEAEA", color: "#8C1D18", borderColor: "#E4B6B3" },
    },
  };
  const conf = map[status] ?? map.processing;
  const Ico = conf.Icon;
  return (
    <span
      className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium whitespace-nowrap"
      style={conf.style}
    >
      <Ico className="h-3.5 w-3.5" aria-hidden="true" />
      {conf.label}
    </span>
  );
}

export default function Screen() {
  const navigate = useNavigate();

  const [documents, setDocuments] = React.useState<DocumentOut[]>([]);
  const [docState, setDocState] = React.useState<LoadState>("loading");
  const [docError, setDocError] = React.useState("");

  const [usage, setUsage] = React.useState<UsageResponse | null>(null);
  const [usageState, setUsageState] = React.useState<LoadState>("loading");
  const [usageError, setUsageError] = React.useState("");

  const [query, setQuery] = React.useState("");
  const [filter, setFilter] = React.useState<"all" | DocumentStatus>("all");
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [editing, setEditing] = React.useState(false);
  const [draftTitle, setDraftTitle] = React.useState("");
  const [renameError, setRenameError] = React.useState("");
  const [renaming, setRenaming] = React.useState(false);
  const [announcement, setAnnouncement] = React.useState("");
  const [deleteTarget, setDeleteTarget] = React.useState<DocumentOut | null>(null);
  const [deleting, setDeleting] = React.useState(false);
  const [deleteError, setDeleteError] = React.useState("");

  const confirmRef = React.useRef<HTMLButtonElement | null>(null);
  const returnFocusRef = React.useRef<HTMLElement | null>(null);

  const loadDocuments = React.useCallback(async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) setDocState("loading");
    try {
      const res = await listDocuments();
      setDocuments(res.documents);
      setDocState("ready");
      setDocError("");
    } catch (err) {
      setDocState("error");
      setDocError(
        err instanceof ApiError ? err.message : "Could not load your documents. Try again.",
      );
    }
  }, []);

  const loadUsage = React.useCallback(async () => {
    setUsageState("loading");
    try {
      const res = await getUsage();
      setUsage(res);
      setUsageState("ready");
      setUsageError("");
    } catch (err) {
      setUsageState("error");
      setUsageError(err instanceof ApiError ? err.message : "Could not load usage.");
    }
  }, []);

  React.useEffect(() => {
    void loadDocuments();
    void loadUsage();
  }, [loadDocuments, loadUsage]);

  // AC-026: a document whose status changes server-side (processing -> ready
  // or failed) updates here without a sign-out/sign-in cycle. Poll only
  // while something is still processing; stop the moment none are.
  React.useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === "processing");
    if (!hasProcessing) return undefined;
    const timer = setInterval(() => {
      void loadDocuments({ silent: true });
      void loadUsage();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [documents, loadDocuments, loadUsage]);

  React.useEffect(() => {
    if (!deleteTarget) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeDialog();
    };
    window.addEventListener("keydown", onKey);
    if (confirmRef.current) confirmRef.current.focus();
    return () => window.removeEventListener("keydown", onKey);
     
  }, [deleteTarget]);

  const counts = React.useMemo(
    () => ({
      all: documents.length,
      ready: documents.filter((d) => d.status === "ready").length,
      processing: documents.filter((d) => d.status === "processing").length,
      failed: documents.filter((d) => d.status === "failed").length,
    }),
    [documents],
  );

  const visible = documents.filter((d) => {
    const matchesFilter = filter === "all" || d.status === filter;
    const q = query.trim().toLowerCase();
    const matchesQuery =
      q === "" || d.title.toLowerCase().includes(q) || d.file_type.toLowerCase().includes(q);
    return matchesFilter && matchesQuery;
  });

  const selected = documents.find((d) => d.id === selectedId) || null;

  function selectDocument(id: string) {
    setSelectedId(id);
    setEditing(false);
    setRenameError("");
  }

  function startRename() {
    if (!selected) return;
    setDraftTitle(selected.title);
    setRenameError("");
    setEditing(true);
  }

  async function submitRename(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) return;
    // AC-030: an empty or whitespace-only title is rejected client-side,
    // no request is sent, the previous title is retained.
    const trimmed = draftTitle.trim();
    if (trimmed === "") {
      setRenameError("Enter a title. A blank title is not saved and the previous title is kept.");
      return;
    }
    setRenaming(true);
    setRenameError("");
    try {
      // AC-028, AC-029: save via PATCH and render only the API-returned
      // title -- no local title cache.
      const updated = await renameDocument(selected.id, trimmed);
      const previousTitle = selected.title;
      setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
      setEditing(false);
      setAnnouncement(`"${previousTitle}" renamed to "${updated.title}".`);
    } catch (err) {
      setRenameError(
        err instanceof ApiError ? err.message : "Could not save the title. Try again.",
      );
    } finally {
      setRenaming(false);
    }
  }

  function openDeleteDialog(doc: DocumentOut, event: React.MouseEvent<HTMLElement>) {
    returnFocusRef.current = event.currentTarget;
    setDeleteError("");
    setDeleteTarget(doc);
  }

  function closeDialog() {
    setDeleteTarget(null);
    setDeleteError("");
    if (returnFocusRef.current) returnFocusRef.current.focus();
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await deleteDocument(deleteTarget.id);
      const title = deleteTarget.title;
      setDocuments((prev) => prev.filter((d) => d.id !== deleteTarget.id));
      if (selectedId === deleteTarget.id) setSelectedId(null);
      setDeleteTarget(null);
      setAnnouncement(`"${title}" deleted. It can no longer be retrieved or cited.`);
      void loadUsage();
    } catch (err) {
      setDeleteError(
        err instanceof ApiError ? err.message : "Could not delete the document. Try again.",
      );
    } finally {
      setDeleting(false);
    }
  }

  const panelHeading = "text-[13px] font-semibold uppercase tracking-wide";

  return (
    <div
      className="mx-auto w-full max-w-[1200px] px-4 py-5"
      style={{ fontFamily: brand.fontBody, color: "#1B2430" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1
            className="text-xl font-semibold tracking-tight"
            style={{ fontFamily: brand.fontHeading, color: brand.primaryColor }}
          >
            My document library
          </h1>
          <p className="mt-1 max-w-2xl text-sm" style={{ color: brand.neutralColor }}>
            Only documents marked <strong className="font-semibold">Ready</strong> are searched when
            you ask a question.
          </p>
        </div>
        <Button
          onClick={() => navigate("chat")}
          className="shrink-0"
          style={{ backgroundColor: brand.primaryColor, color: "#FFFFFF" }}
        >
          Ask a question
          <ArrowRight className="ml-1.5 h-4 w-4" aria-hidden="true" />
        </Button>
      </div>

      <h2 className="sr-only">Account usage</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Card className="p-3">
          <p
            className="text-xs font-medium uppercase tracking-wide"
            style={{ color: brand.neutralColor }}
          >
            Documents stored
          </p>
          {usageState === "loading" ? (
            <p className="mt-1 text-sm" style={{ color: brand.neutralColor }}>
              Loading…
            </p>
          ) : usageState === "error" || !usage ? (
            <p role="alert" className="mt-1 text-sm" style={{ color: "#8C1D18" }}>
              {usageError || "Could not load usage."}
            </p>
          ) : (
            <>
              <p
                className="mt-1 text-2xl font-semibold tabular-nums"
                style={{ color: brand.primaryColor }}
              >
                {usage.document_count}
                <span className="text-base font-normal" style={{ color: brand.neutralColor }}>
                  {" "}
                  / {usage.documents_cap}
                </span>
              </p>
              <p className="mt-1 text-xs" style={{ color: brand.neutralColor }}>
                {Math.max(0, usage.documents_cap - usage.document_count)} slots free · deleting a
                document frees capacity
              </p>
            </>
          )}
        </Card>
        <Card className="p-3">
          <p
            className="text-xs font-medium uppercase tracking-wide"
            style={{ color: brand.neutralColor }}
          >
            Questions remaining this month
          </p>
          {usageState === "loading" ? (
            <p className="mt-1 text-sm" style={{ color: brand.neutralColor }}>
              Loading…
            </p>
          ) : usageState === "error" || !usage ? (
            <p role="alert" className="mt-1 text-sm" style={{ color: "#8C1D18" }}>
              {usageError || "Could not load usage."}
            </p>
          ) : (
            <>
              <p
                className="mt-1 text-2xl font-semibold tabular-nums"
                style={{ color: brand.primaryColor }}
              >
                {usage.remaining_questions}
              </p>
              <p className="mt-1 text-xs" style={{ color: brand.neutralColor }}>
                Resets {formatDateOnly(usage.reset_date)}
              </p>
            </>
          )}
        </Card>
      </div>

      <div className="mt-4 grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* ---------------- Library pane ---------------- */}
        <Card className="overflow-hidden">
          <div className="border-b border-slate-200 p-3">
            <h2 className={panelHeading} style={{ color: brand.primaryColor }}>
              Documents
            </h2>

            <div className="mt-3 flex flex-wrap items-end gap-3">
              <div className="min-w-[200px] flex-1">
                <Label htmlFor="doc-search" className="text-xs font-medium">
                  Search by title or type
                </Label>
                <div className="relative mt-1">
                  <Search
                    className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2"
                    aria-hidden="true"
                    style={{ color: brand.neutralColor }}
                  />
                  <Input
                    id="doc-search"
                    type="search"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="e.g. contract, pdf"
                    className="pl-8"
                  />
                </div>
              </div>
              <div
                role="group"
                aria-label="Filter documents by status"
                className="flex flex-wrap gap-1.5"
              >
                {FILTERS.map((f) => {
                  const active = filter === f.id;
                  return (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => setFilter(f.id)}
                      aria-pressed={active}
                      className="rounded-md border px-2.5 py-1.5 text-xs font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                      style={
                        active
                          ? {
                              backgroundColor: brand.primaryColor,
                              color: "#FFFFFF",
                              borderColor: brand.primaryColor,
                            }
                          : {
                              backgroundColor: "#FFFFFF",
                              color: brand.neutralColor,
                              borderColor: "#CBD5E1",
                            }
                      }
                    >
                      {f.label} ({counts[f.id as keyof typeof counts] ?? 0})
                    </button>
                  );
                })}
              </div>
            </div>

            <p
              role="status"
              aria-live="polite"
              className="mt-2 min-h-[1rem] text-xs"
              style={{ color: brand.primaryColor }}
            >
              {announcement}
            </p>
          </div>

          {docState === "loading" ? (
            <div className="p-10 text-center text-sm" style={{ color: brand.neutralColor }}>
              Loading your documents…
            </div>
          ) : docState === "error" ? (
            <div className="p-10 text-center">
              <AlertCircle
                className="mx-auto h-8 w-8"
                aria-hidden="true"
                style={{ color: "#8C1D18" }}
              />
              <p role="alert" className="mt-2 text-sm" style={{ color: "#8C1D18" }}>
                {docError}
              </p>
              <Button className="mt-3" onClick={() => void loadDocuments()}>
                Try again
              </Button>
            </div>
          ) : documents.length === 0 ? (
            <div className="p-10 text-center">
              <FileText
                className="mx-auto h-8 w-8"
                aria-hidden="true"
                style={{ color: brand.neutralColor }}
              />
              <h3 className="mt-2 text-sm font-semibold">Your library is empty</h3>
              <p className="mx-auto mt-1 max-w-sm text-sm" style={{ color: brand.neutralColor }}>
                Upload a PDF, Word, Markdown or plain-text file to start. Until a document is ready,
                the chatbot has nothing to answer from.
              </p>
            </div>
          ) : visible.length === 0 ? (
            <div className="p-10 text-center">
              <Search
                className="mx-auto h-8 w-8"
                aria-hidden="true"
                style={{ color: brand.neutralColor }}
              />
              <h3 className="mt-2 text-sm font-semibold">No documents match</h3>
              <p className="mt-1 text-sm" style={{ color: brand.neutralColor }}>
                No document matches "{query}" with the{" "}
                {FILTERS.find((f) => f.id === filter)?.label.toLowerCase()} filter.
              </p>
              <Button
                className="mt-3"
                onClick={() => {
                  setQuery("");
                  setFilter("all");
                }}
              >
                Clear search and filters
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <caption className="sr-only">
                  Your uploaded documents with file type, upload date and ingestion status
                </caption>
                <THead>
                  <TR>
                    <TH scope="col">Title</TH>
                    <TH scope="col">Type</TH>
                    <TH scope="col">Uploaded</TH>
                    <TH scope="col">Status</TH>
                    <TH scope="col" className="text-right">
                      Actions
                    </TH>
                  </TR>
                </THead>
                <TBody>
                  {visible.map((doc) => {
                    const isSelected = doc.id === selectedId;
                    return (
                      <TR
                        key={doc.id}
                        style={isSelected ? { backgroundColor: "#E8EEF4" } : undefined}
                      >
                        <TH scope="row" className="font-normal">
                          <button
                            type="button"
                            onClick={() => selectDocument(doc.id)}
                            aria-current={isSelected ? "true" : undefined}
                            className="flex max-w-[26rem] items-center gap-2 rounded text-left text-sm font-medium underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                            style={{ color: brand.primaryColor }}
                          >
                            <FileText className="h-4 w-4 shrink-0" aria-hidden="true" />
                            <span className="truncate">{doc.title}</span>
                          </button>
                        </TH>
                        <TD className="text-xs uppercase" style={{ color: brand.neutralColor }}>
                          {doc.file_type}
                        </TD>
                        <TD
                          className="whitespace-nowrap text-xs"
                          style={{ color: brand.neutralColor }}
                        >
                          {formatStamp(doc.uploaded_at)}
                        </TD>
                        <TD>
                          <StatusChip status={doc.status} />
                        </TD>
                        <TD className="text-right">
                          <div className="flex justify-end gap-1">
                            <button
                              type="button"
                              onClick={() => {
                                selectDocument(doc.id);
                                setDraftTitle(doc.title);
                                setEditing(true);
                              }}
                              aria-label={`Rename ${doc.title}`}
                              className="rounded border border-slate-300 bg-white p-1.5 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                              style={{ color: brand.neutralColor }}
                            >
                              <Edit className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => openDeleteDialog(doc, e)}
                              aria-label={`Delete ${doc.title}`}
                              className="rounded border border-slate-300 bg-white p-1.5 hover:bg-[#FBEAEA] focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                              style={{ color: "#8C1D18" }}
                            >
                              <Trash className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                          </div>
                        </TD>
                      </TR>
                    );
                  })}
                </TBody>
              </Table>
              <p
                className="border-t border-slate-200 px-3 py-2 text-xs"
                style={{ color: brand.neutralColor }}
              >
                Showing {visible.length} of {documents.length} documents. Documents that are
                processing or failed are excluded from retrieval and are never cited.
              </p>
            </div>
          )}
        </Card>

        {/* ---------------- Detail pane ---------------- */}
        <Card className="p-3 lg:sticky lg:top-4">
          <h2 className={panelHeading} style={{ color: brand.primaryColor }}>
            Document details
          </h2>
          <Separator className="my-2" />

          {!selected ? (
            <div className="py-10 text-center">
              <FileText
                className="mx-auto h-7 w-7"
                aria-hidden="true"
                style={{ color: brand.neutralColor }}
              />
              <p className="mt-2 text-sm" style={{ color: brand.neutralColor }}>
                Select a document title from the list to see its status, rename or delete it.
              </p>
            </div>
          ) : (
            <div>
              {editing ? (
                <form onSubmit={submitRename} noValidate>
                  <Label htmlFor="rename-input" className="text-xs font-medium">
                    Document title
                  </Label>
                  <Input
                    id="rename-input"
                    value={draftTitle}
                    onChange={(e) => setDraftTitle(e.target.value)}
                    aria-invalid={renameError ? "true" : undefined}
                    aria-describedby={renameError ? "rename-error" : "rename-hint"}
                    className="mt-1"
                  />
                  <p
                    id="rename-hint"
                    className="mt-1 text-xs"
                    style={{ color: brand.neutralColor }}
                  >
                    Sources in later answers will use this title.
                  </p>
                  {renameError ? (
                    <p
                      id="rename-error"
                      role="alert"
                      className="mt-1 text-xs font-medium"
                      style={{ color: "#8C1D18" }}
                    >
                      {renameError}
                    </p>
                  ) : null}
                  <div className="mt-2 flex gap-2">
                    <Button
                      type="submit"
                      disabled={renaming}
                      style={{ backgroundColor: brand.primaryColor, color: "#FFFFFF" }}
                    >
                      <Check className="mr-1 h-4 w-4" aria-hidden="true" />
                      {renaming ? "Saving…" : "Save title"}
                    </Button>
                    <Button
                      type="button"
                      onClick={() => {
                        setEditing(false);
                        setRenameError("");
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              ) : (
                <div>
                  <h3 className="text-sm font-semibold leading-snug">{selected.title}</h3>
                  <div className="mt-1.5">
                    <StatusChip status={selected.status} />
                  </div>
                </div>
              )}

              {selected.status === "failed" && selected.failure_reason ? (
                <div
                  className="mt-3 rounded border p-2"
                  style={{ backgroundColor: "#FBEAEA", borderColor: "#E4B6B3", color: "#8C1D18" }}
                >
                  <p className="flex items-center gap-1.5 text-xs font-semibold">
                    <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
                    Why ingestion failed
                  </p>
                  <p className="mt-1 text-xs leading-relaxed">{selected.failure_reason}</p>
                </div>
              ) : null}

              {selected.status === "processing" ? (
                <p
                  className="mt-3 rounded border p-2 text-xs leading-relaxed"
                  style={{
                    backgroundColor: "rgba(227,181,5,0.14)",
                    borderColor: "#D9C068",
                    color: "#6B5200",
                  }}
                >
                  Extracting text, chunking and embedding. This usually finishes within a couple of
                  minutes — you can leave this page. Until it is ready, this document is not used as
                  context.
                </p>
              ) : null}

              <dl className="mt-3 space-y-2 text-xs">
                <div className="flex justify-between gap-3">
                  <dt style={{ color: brand.neutralColor }}>File type</dt>
                  <dd className="font-medium uppercase">{selected.file_type}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt style={{ color: brand.neutralColor }}>Uploaded</dt>
                  <dd className="font-medium">{formatStamp(selected.uploaded_at)}</dd>
                </div>
                <div>
                  <dt style={{ color: brand.neutralColor }}>Document ID</dt>
                  <dd className="mt-0.5 break-all font-mono">{selected.id}</dd>
                </div>
              </dl>

              <Separator className="my-3" />

              <div className="flex flex-col gap-2">
                {!editing ? (
                  <Button type="button" onClick={startRename} className="w-full justify-center">
                    <Edit className="mr-1.5 h-4 w-4" aria-hidden="true" />
                    Rename document
                  </Button>
                ) : null}

                {selected.status === "ready" ? (
                  <Button
                    type="button"
                    onClick={() => navigate("chat")}
                    className="w-full justify-center"
                    style={{ backgroundColor: brand.primaryColor, color: "#FFFFFF" }}
                  >
                    Ask about this document
                    <ArrowRight className="ml-1.5 h-4 w-4" aria-hidden="true" />
                  </Button>
                ) : null}

                <button
                  type="button"
                  onClick={(e) => openDeleteDialog(selected, e)}
                  className="w-full rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-[#FBEAEA] focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                  style={{ borderColor: "#E4B6B3", color: "#8C1D18" }}
                >
                  <Trash className="mr-1.5 inline h-4 w-4 align-text-bottom" aria-hidden="true" />
                  Delete document
                </button>
              </div>
            </div>
          )}
        </Card>
      </div>

      {deleteTarget ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
            aria-describedby="delete-desc"
            className="w-full max-w-md rounded-lg bg-white p-4 shadow-xl"
            style={{ borderRadius: brand.radius }}
          >
            <div className="flex items-start justify-between gap-3">
              <h2
                id="delete-title"
                className="text-base font-semibold"
                style={{ color: brand.primaryColor }}
              >
                Delete "{deleteTarget.title}"?
              </h2>
              <button
                type="button"
                onClick={closeDialog}
                aria-label="Close dialog"
                className="rounded p-1 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                style={{ color: brand.neutralColor }}
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <p
              id="delete-desc"
              className="mt-2 text-sm leading-relaxed"
              style={{ color: brand.neutralColor }}
            >
              This removes the document record, the stored original file and all of its indexed
              content, so this material can never be retrieved or cited again. Past conversations
              that cited it will say the source is no longer available.{" "}
              <strong className="font-semibold" style={{ color: "#1B2430" }}>
                This action cannot be undone.
              </strong>
            </p>
            {deleteError ? (
              <p role="alert" className="mt-2 text-sm font-medium" style={{ color: "#8C1D18" }}>
                {deleteError}
              </p>
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <Button type="button" onClick={closeDialog} disabled={deleting}>
                Cancel
              </Button>
              <button
                type="button"
                ref={confirmRef}
                onClick={() => void confirmDelete()}
                disabled={deleting}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-60"
                style={{ backgroundColor: "#8C1D18", borderRadius: brand.radius }}
              >
                {deleting ? "Deleting…" : "Delete permanently"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
