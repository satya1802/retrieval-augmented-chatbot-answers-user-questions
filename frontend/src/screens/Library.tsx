/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Button, Card, Input, Label, Select, Table, THead, TBody, TR, TH, TD, Separator } = UI;
const { Plus, Search, Check, X, FileText, Clock, Trash, Edit, Filter, Upload, ArrowRight, AlertCircle, CheckCircle } = Icons;

const { Button, Card, Input, Label, Table, THead, TBody, TR, TH, TD, Separator } = UI;
const {
  Upload, Search, FileText, Trash, Edit, CheckCircle, AlertCircle, Clock, X, ArrowRight, Plus,
} = Icons;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const SUPPORTED = ["pdf", "docx", "doc", "md", "txt"];
const DOCUMENT_CAP = 25;
const QUESTION_CAP = 200;
const QUESTIONS_USED = 63;
const WINDOW_RESETS = "1 Nov 2026";

const INITIAL_DOCUMENTS = [
  {
    id: "doc_8f21",
    owner_id: "usr_01",
    title: "Vendor Master Services Agreement 2026",
    file_type: "pdf",
    storage_key: "u01/2026/09/msa-2026-final.pdf",
    status: "ready",
    failure_reason: null,
    uploaded_at: "2026-09-28T09:14:00Z",
    chunk_count: 184,
  },
  {
    id: "doc_7c04",
    owner_id: "usr_01",
    title: "Q3 Financial Controls Review",
    file_type: "docx",
    storage_key: "u01/2026/09/q3-controls-review.docx",
    status: "ready",
    failure_reason: null,
    uploaded_at: "2026-09-29T16:02:00Z",
    chunk_count: 97,
  },
  {
    id: "doc_6b55",
    owner_id: "usr_01",
    title: "Incident Postmortem — Payments Outage, 14 Sep",
    file_type: "md",
    storage_key: "u01/2026/09/postmortem-payments.md",
    status: "ready",
    failure_reason: null,
    uploaded_at: "2026-09-30T11:48:00Z",
    chunk_count: 42,
  },
  {
    id: "doc_5a18",
    owner_id: "usr_01",
    title: "SOC 2 Type II Report (FY25)",
    file_type: "pdf",
    storage_key: "u01/2026/10/soc2-fy25-signed.pdf",
    status: "failed",
    failure_reason:
      "No readable text was found. This PDF contains scanned page images only, and documents requiring OCR are not supported in this version.",
    uploaded_at: "2026-10-01T08:21:00Z",
    chunk_count: 0,
  },
  {
    id: "doc_4e72",
    owner_id: "usr_01",
    title: "Employee Handbook v4.2",
    file_type: "pdf",
    storage_key: "u01/2026/10/handbook-v4-2.pdf",
    status: "ready",
    failure_reason: null,
    uploaded_at: "2026-10-01T14:35:00Z",
    chunk_count: 310,
  },
  {
    id: "doc_3d90",
    owner_id: "usr_01",
    title: "Data Processing Addendum — Northwind",
    file_type: "docx",
    storage_key: "u01/2026/10/dpa-northwind.docx",
    status: "ready",
    failure_reason: null,
    uploaded_at: "2026-10-02T10:07:00Z",
    chunk_count: 58,
  },
  {
    id: "doc_2f33",
    owner_id: "usr_01",
    title: "Board Minutes 2026-09-24",
    file_type: "txt",
    storage_key: "u01/2026/10/board-minutes-0924.txt",
    status: "ready",
    failure_reason: null,
    uploaded_at: "2026-10-02T17:55:00Z",
    chunk_count: 21,
  },
  {
    id: "doc_1a47",
    owner_id: "usr_01",
    title: "Insurance Policy — Cyber Liability",
    file_type: "pdf",
    storage_key: "u01/2026/10/cyber-liability-policy.pdf",
    status: "failed",
    failure_reason:
      "Text extraction failed: the file is password-protected and could not be opened. No partial chunks remain in the search index.",
    uploaded_at: "2026-10-03T09:12:00Z",
    chunk_count: 0,
  },
  {
    id: "doc_9b61",
    owner_id: "usr_01",
    title: "Records Retention Schedule 2026",
    file_type: "txt",
    storage_key: "u01/2026/10/retention-schedule.txt",
    status: "ready",
    failure_reason: null,
    uploaded_at: "2026-10-04T13:26:00Z",
    chunk_count: 33,
  },
  {
    id: "doc_0c28",
    owner_id: "usr_01",
    title: "Procurement Policy (Rev C)",
    file_type: "docx",
    storage_key: "u01/2026/10/procurement-rev-c.docx",
    status: "ready",
    failure_reason: null,
    uploaded_at: "2026-10-05T08:44:00Z",
    chunk_count: 76,
  },
  {
    id: "doc_ab19",
    owner_id: "usr_01",
    title: "Customer Contract — Halden Group",
    file_type: "pdf",
    storage_key: "u01/2026/10/halden-contract.pdf",
    status: "ready",
    failure_reason: null,
    uploaded_at: "2026-10-05T15:03:00Z",
    chunk_count: 142,
  },
  {
    id: "doc_cd77",
    owner_id: "usr_01",
    title: "Supplier Risk Register — working notes",
    file_type: "md",
    storage_key: "u01/2026/10/supplier-risk-notes.md",
    status: "processing",
    failure_reason: null,
    uploaded_at: "2026-10-06T07:58:00Z",
    chunk_count: 0,
  },
];

const FILTERS = [
  { id: "all", label: "All" },
  { id: "ready", label: "Ready" },
  { id: "processing", label: "Processing" },
  { id: "failed", label: "Failed" },
];

function formatStamp(iso) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${hh}:${mm}`;
}

function extensionOf(name) {
  const parts = String(name).split(".");
  return parts.length > 1 ? parts.pop().toLowerCase() : "";
}

function estimateChunks(title) {
  let h = 0;
  for (let i = 0; i < title.length; i++) h = (h * 31 + title.charCodeAt(i)) % 997;
  return 24 + (h % 160);
}

function StatusChip({ status }) {
  const map = {
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
  const conf = map[status] || map.processing;
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
  const [documents, setDocuments] = React.useState(INITIAL_DOCUMENTS);
  const [query, setQuery] = React.useState("");
  const [filter, setFilter] = React.useState("all");
  const [selectedId, setSelectedId] = React.useState("doc_5a18");
  const [editing, setEditing] = React.useState(false);
  const [draftTitle, setDraftTitle] = React.useState("");
  const [renameError, setRenameError] = React.useState("");
  const [uploadError, setUploadError] = React.useState("");
  const [announcement, setAnnouncement] = React.useState("");
  const [deleteTarget, setDeleteTarget] = React.useState(null);

  const confirmRef = React.useRef(null);
  const returnFocusRef = React.useRef(null);
  const searchRef = React.useRef(null);

  // Ingestion: newly uploaded / retried documents move from processing to ready
  // while the user is on the screen (no sign-out required).
  React.useEffect(() => {
    const pending = documents.filter((d) => d.status === "processing" && d.ingesting);
    if (pending.length === 0) return undefined;
    const timer = setTimeout(() => {
      setDocuments((prev) =>
        prev.map((d) =>
          d.ingesting && d.status === "processing"
            ? { ...d, status: "ready", ingesting: false, chunk_count: estimateChunks(d.title) }
            : d
        )
      );
      setAnnouncement(
        pending.length === 1
          ? `“${pending[0].title}” finished ingesting and is now ready for retrieval.`
          : `${pending.length} documents finished ingesting and are now ready for retrieval.`
      );
    }, 2800);
    return () => clearTimeout(timer);
  }, [documents]);

  React.useEffect(() => {
    if (!deleteTarget) return undefined;
    const onKey = (e) => {
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
    [documents]
  );

  const indexedChunks = documents.reduce((sum, d) => sum + (d.chunk_count || 0), 0);
  const remainingQuestions = QUESTION_CAP - QUESTIONS_USED;

  const visible = documents.filter((d) => {
    const matchesFilter = filter === "all" || d.status === filter;
    const q = query.trim().toLowerCase();
    const matchesQuery =
      q === "" || d.title.toLowerCase().includes(q) || d.file_type.toLowerCase().includes(q);
    return matchesFilter && matchesQuery;
  });

  const selected = documents.find((d) => d.id === selectedId) || null;

  function selectDocument(id) {
    setSelectedId(id);
    setEditing(false);
    setRenameError("");
  }

  function handleUpload(event) {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    if (files.length === 0) return;

    const accepted = [];
    const rejected = [];
    files.forEach((f) => {
      const ext = extensionOf(f.name);
      if (SUPPORTED.includes(ext)) accepted.push({ file: f, ext });
      else rejected.push(f.name);
    });

    const capacity = DOCUMENT_CAP - documents.length;
    if (capacity <= 0) {
      setUploadError(
        `You have reached the ${DOCUMENT_CAP}-document limit for this account. Delete a document to free capacity before uploading another.`
      );
      return;
    }

    const takeable = accepted.slice(0, capacity);
    const overflow = accepted.length - takeable.length;

    const created = takeable.map((item, i) => {
      const baseTitle = item.file.name.replace(/\.[^.]+$/, "");
      return {
        id: `doc_new_${Date.now()}_${i}`,
        owner_id: "usr_01",
        title: baseTitle,
        file_type: item.ext === "doc" ? "docx" : item.ext,
        storage_key: `u01/2026/10/${item.file.name}`,
        status: "processing",
        failure_reason: null,
        uploaded_at: new Date().toISOString(),
        chunk_count: 0,
        ingesting: true,
      };
    });

    const messages = [];
    if (created.length > 0) {
      setDocuments((prev) => [...created, ...prev]);
      setSelectedId(created[0].id);
      setEditing(false);
      setAnnouncement(
        created.length === 1
          ? `“${created[0].title}” uploaded. Extraction and embedding are running.`
          : `${created.length} documents uploaded. Each is being ingested independently.`
      );
    }
    if (rejected.length > 0) {
      messages.push(
        `${rejected.join(", ")} was not uploaded — unsupported file type. Supported types are PDF, Word (.docx), Markdown (.md) and plain text (.txt).`
      );
    }
    if (overflow > 0) {
      messages.push(
        `${overflow} file(s) exceeded the ${DOCUMENT_CAP}-document limit. Delete a document to free capacity.`
      );
    }
    setUploadError(messages.join(" "));
  }

  function startRename() {
    if (!selected) return;
    setDraftTitle(selected.title);
    setRenameError("");
    setEditing(true);
  }

  function submitRename(e) {
    e.preventDefault();
    if (draftTitle.trim() === "") {
      setRenameError("Enter a title. A blank title is not saved and the previous title is kept.");
      return;
    }
    const previous = selected.title;
    const next = draftTitle.trim();
    setDocuments((prev) => prev.map((d) => (d.id === selected.id ? { ...d, title: next } : d)));
    setEditing(false);
    setRenameError("");
    setAnnouncement(`“${previous}” renamed to “${next}”. Future answers will cite the new title.`);
  }

  function retryIngestion(doc) {
    setDocuments((prev) =>
      prev.map((d) =>
        d.id === doc.id
          ? { ...d, status: "processing", failure_reason: null, ingesting: true, chunk_count: 0 }
          : d
      )
    );
    setAnnouncement(`Retrying ingestion for “${doc.title}”.`);
  }

  function openDeleteDialog(doc, event) {
    returnFocusRef.current = event && event.currentTarget ? event.currentTarget : null;
    setDeleteTarget(doc);
  }

  function closeDialog() {
    setDeleteTarget(null);
    if (returnFocusRef.current && returnFocusRef.current.focus) {
      returnFocusRef.current.focus();
    }
  }

  function confirmDelete() {
    const doc = deleteTarget;
    setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    if (selectedId === doc.id) setSelectedId(null);
    setDeleteTarget(null);
    setAnnouncement(
      `“${doc.title}” deleted. Its ${doc.chunk_count} chunks were removed from the search index and can no longer be retrieved or cited.`
    );
    if (searchRef.current) searchRef.current.focus();
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
            Everything here is private to sai.kiron@quorq.ai. Only documents marked{" "}
            <strong className="font-semibold">Ready</strong> are searched when you ask a question.
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
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Card className="p-3">
          <p className="text-xs font-medium uppercase tracking-wide" style={{ color: brand.neutralColor }}>
            Documents stored
          </p>
          <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: brand.primaryColor }}>
            {documents.length}
            <span className="text-base font-normal" style={{ color: brand.neutralColor }}>
              {" "}
              / {DOCUMENT_CAP}
            </span>
          </p>
          <p className="mt-1 text-xs" style={{ color: brand.neutralColor }}>
            {DOCUMENT_CAP - documents.length} slots free · deleting a document frees capacity
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-xs font-medium uppercase tracking-wide" style={{ color: brand.neutralColor }}>
            Questions remaining this month
          </p>
          <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: brand.primaryColor }}>
            {remainingQuestions}
            <span className="text-base font-normal" style={{ color: brand.neutralColor }}>
              {" "}
              / {QUESTION_CAP}
            </span>
          </p>
          <p className="mt-1 text-xs" style={{ color: brand.neutralColor }}>
            {QUESTIONS_USED} used · resets {WINDOW_RESETS}
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-xs font-medium uppercase tracking-wide" style={{ color: brand.neutralColor }}>
            Chunks in your index
          </p>
          <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: brand.primaryColor }}>
            {indexedChunks.toLocaleString()}
          </p>
          <p className="mt-1 text-xs" style={{ color: brand.neutralColor }}>
            Across {counts.ready} ready document{counts.ready === 1 ? "" : "s"} · 800-token chunks, 120 overlap
          </p>
        </Card>
      </div>

      <div className="mt-4 grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* ---------------- Library pane ---------------- */}
        <Card className="overflow-hidden">
          <div className="border-b border-slate-200 p-3">
            <h2 className={panelHeading} style={{ color: brand.primaryColor }}>
              Documents
            </h2>

            <div className="mt-3 rounded-md border border-dashed border-slate-300 bg-slate-50 p-3">
              <Label htmlFor="file-upload" className="text-sm font-medium">
                Upload documents
              </Label>
              <p id="upload-hint" className="mt-0.5 text-xs" style={{ color: brand.neutralColor }}>
                PDF, Word (.docx), Markdown (.md) or plain text (.txt). Digital text only — scanned pages
                are not supported. Select several files to ingest each one separately.
              </p>
              <input
                id="file-upload"
                type="file"
                multiple
                accept=".pdf,.docx,.doc,.md,.txt"
                onChange={handleUpload}
                aria-describedby="upload-hint"
                className="mt-2 block w-full cursor-pointer rounded-md border border-slate-300 bg-white p-1.5 text-sm file:mr-3 file:cursor-pointer file:rounded file:border-0 file:bg-[#1F4E79] file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                style={{ outlineColor: brand.primaryColor }}
              />
              {uploadError ? (
                <p
                  role="alert"
                  className="mt-2 flex items-start gap-1.5 rounded border border-[#E4B6B3] bg-[#FBEAEA] p-2 text-xs"
                  style={{ color: "#8C1D18" }}
                >
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <span>{uploadError}</span>
                </p>
              ) : null}
            </div>

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
                    ref={searchRef}
                    type="search"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="e.g. contract, pdf"
                    className="pl-8"
                  />
                </div>
              </div>
              <div role="group" aria-label="Filter documents by status" className="flex flex-wrap gap-1.5">
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
                          ? { backgroundColor: brand.primaryColor, color: "#FFFFFF", borderColor: brand.primaryColor }
                          : { backgroundColor: "#FFFFFF", color: brand.neutralColor, borderColor: "#CBD5E1" }
                      }
                    >
                      {f.label} ({counts[f.id]})
                    </button>
                  );
                })}
              </div>
            </div>

            <p role="status" aria-live="polite" className="mt-2 min-h-[1rem] text-xs" style={{ color: brand.primaryColor }}>
              {announcement}
            </p>
          </div>

          {documents.length === 0 ? (
            <div className="p-10 text-center">
              <FileText className="mx-auto h-8 w-8" aria-hidden="true" style={{ color: brand.neutralColor }} />
              <h3 className="mt-2 text-sm font-semibold">Your library is empty</h3>
              <p className="mx-auto mt-1 max-w-sm text-sm" style={{ color: brand.neutralColor }}>
                Upload a PDF, Word, Markdown or plain-text file to start. Until a document is ready, the
                chatbot has nothing to answer from.
              </p>
            </div>
          ) : visible.length === 0 ? (
            <div className="p-10 text-center">
              <Search className="mx-auto h-8 w-8" aria-hidden="true" style={{ color: brand.neutralColor }} />
              <h3 className="mt-2 text-sm font-semibold">No documents match</h3>
              <p className="mt-1 text-sm" style={{ color: brand.neutralColor }}>
                No document matches “{query}” with the {FILTERS.find((f) => f.id === filter).label.toLowerCase()} filter.
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
                  Your uploaded documents with file type, upload date, ingestion status and indexed chunk count
                </caption>
                <THead>
                  <TR>
                    <TH scope="col">Title</TH>
                    <TH scope="col">Type</TH>
                    <TH scope="col">Uploaded</TH>
                    <TH scope="col">Status</TH>
                    <TH scope="col" className="text-right">Chunks</TH>
                    <TH scope="col" className="text-right">Actions</TH>
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
                        <TD className="whitespace-nowrap text-xs" style={{ color: brand.neutralColor }}>
                          {formatStamp(doc.uploaded_at)}
                        </TD>
                        <TD>
                          <StatusChip status={doc.status} />
                        </TD>
                        <TD className="text-right text-xs tabular-nums" style={{ color: brand.neutralColor }}>
                          {doc.status === "ready" ? doc.chunk_count : "—"}
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
              <p className="border-t border-slate-200 px-3 py-2 text-xs" style={{ color: brand.neutralColor }}>
                Showing {visible.length} of {documents.length} documents. Documents that are processing or
                failed are excluded from retrieval and are never cited.
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
              <FileText className="mx-auto h-7 w-7" aria-hidden="true" style={{ color: brand.neutralColor }} />
              <p className="mt-2 text-sm" style={{ color: brand.neutralColor }}>
                Select a document title from the list to see its ingestion status, storage key and
                rename or delete it.
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
                  <p id="rename-hint" className="mt-1 text-xs" style={{ color: brand.neutralColor }}>
                    Sources in later answers will use this title.
                  </p>
                  {renameError ? (
                    <p id="rename-error" role="alert" className="mt-1 text-xs font-medium" style={{ color: "#8C1D18" }}>
                      {renameError}
                    </p>
                  ) : null}
                  <div className="mt-2 flex gap-2">
                    <Button type="submit" style={{ backgroundColor: brand.primaryColor, color: "#FFFFFF" }}>
                      <Check className="mr-1 h-4 w-4" aria-hidden="true" />
                      Save title
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
                  style={{ backgroundColor: "rgba(227,181,5,0.14)", borderColor: "#D9C068", color: "#6B5200" }}
                >
                  Extracting text, chunking and embedding. This usually finishes within a couple of
                  minutes — you can leave this page. Until it is ready, this document is not used as context.
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
                <div className="flex justify-between gap-3">
                  <dt style={{ color: brand.neutralColor }}>Chunks indexed</dt>
                  <dd className="font-medium tabular-nums">
                    {selected.status === "ready" ? selected.chunk_count : "0"}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt style={{ color: brand.neutralColor }}>Document ID</dt>
                  <dd className="font-mono">{selected.id}</dd>
                </div>
                <div>
                  <dt style={{ color: brand.neutralColor }}>Storage key</dt>
                  <dd className="mt-0.5 break-all font-mono">{selected.storage_key}</dd>
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

                {selected.status === "failed" ? (
                  <Button
                    type="button"
                    onClick={() => retryIngestion(selected)}
                    className="w-full justify-center"
                  >
                    <Upload className="mr-1.5 h-4 w-4" aria-hidden="true" />
                    Retry ingestion
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
              <h2 id="delete-title" className="text-base font-semibold" style={{ color: brand.primaryColor }}>
                Delete “{deleteTarget.title}”?
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
            <p id="delete-desc" className="mt-2 text-sm leading-relaxed" style={{ color: brand.neutralColor }}>
              This removes the document record, the stored original file and all{" "}
              <strong className="font-semibold" style={{ color: "#1B2430" }}>
                {deleteTarget.chunk_count} chunks
              </strong>{" "}
              from your search index, so this material can never be retrieved or cited again. Past
              conversations that cited it will say the source is no longer available.{" "}
              <strong className="font-semibold" style={{ color: "#1B2430" }}>
                This action cannot be undone.
              </strong>
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button type="button" onClick={closeDialog}>
                Cancel
              </Button>
              <button
                type="button"
                ref={confirmRef}
                onClick={confirmDelete}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                style={{ backgroundColor: "#8C1D18", borderRadius: brand.radius }}
              >
                Delete permanently
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

const { Check } = Icons;
