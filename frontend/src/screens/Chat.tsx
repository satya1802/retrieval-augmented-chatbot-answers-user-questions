/* eslint-disable @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment, react-hooks/rules-of-hooks */
// @ts-nocheck
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Button, Input, Textarea, Label, Select } = UI;
const { Plus, Search, X, ChevronRight, ChevronDown, FileText, Clock, Filter, ArrowRight, AlertCircle, CheckCircle } = Icons;

const INSUFFICIENT = "I don't have enough information in the provided context to answer that accurately.";

const DOCS = [
  { id: 'doc_01', title: 'Supplier Agreement — Northwind Logistics (2025)', file_type: 'PDF', status: 'ready', uploaded_at: '28 Sep 2026' },
  { id: 'doc_02', title: 'Incident Response Runbook v4', file_type: 'DOCX', status: 'ready', uploaded_at: '30 Sep 2026' },
  { id: 'doc_03', title: 'Data Retention Policy (rev 7)', file_type: 'MD', status: 'ready', uploaded_at: '1 Oct 2026' },
  { id: 'doc_04', title: 'Board Minutes — 12 Sep 2026', file_type: 'TXT', status: 'ready', uploaded_at: '2 Oct 2026' },
  { id: 'doc_07', title: 'Employee Handbook 2026', file_type: 'PDF', status: 'ready', uploaded_at: '3 Oct 2026' },
  { id: 'doc_05', title: 'Vendor Security Review — Halden Cloud', file_type: 'PDF', status: 'processing', uploaded_at: '6 Oct 2026' },
  { id: 'doc_06', title: 'Scanned Contract Appendix C', file_type: 'PDF', status: 'failed', uploaded_at: '5 Oct 2026', failure_reason: 'No readable text found. Scanned documents requiring OCR are not supported in this version.' },
];

const CHUNKS = {
  ch_1041: {
    id: 'ch_1041', document_id: 'doc_01', document_title_snapshot: 'Supplier Agreement — Northwind Logistics (2025)', chunk_position: 18, score: 0.88, available: true,
    text: '12.1 Termination for convenience. Either party may terminate this Agreement for convenience by serving not less than ninety (90) days written notice on the other party at its registered address. Notice takes effect on the date of delivery recorded by the courier.',
  },
  ch_1042: {
    id: 'ch_1042', document_id: 'doc_01', document_title_snapshot: 'Supplier Agreement — Northwind Logistics (2025)', chunk_position: 19, score: 0.84, available: true,
    text: '12.2 Where termination for convenience is served within the first twelve (12) months of the Initial Term, an early-exit fee of £12,500 becomes payable within 30 days of the termination date. 12.3 Termination for material breach is governed separately by clause 13 and requires 30 days notice to remedy.',
  },
  ch_1043: {
    id: 'ch_1043', document_id: 'doc_01', document_title_snapshot: 'Supplier Agreement — Northwind Logistics (2025)', chunk_position: 27, score: 0.79, available: true,
    text: '12.5 The early-exit fee is waived in full where termination follows (a) a failure to meet the service credit floor in two consecutive quarters, or (b) a change of control of the Supplier notified under clause 19. No other waiver is provided for in this Agreement.',
  },
  ch_1051: {
    id: 'ch_1051', document_id: 'doc_02', document_title_snapshot: 'Incident Response Runbook v4', chunk_position: 4, score: 0.83, available: true,
    text: 'Severity definitions. SEV-1: complete loss of a customer-facing service, or confirmed exposure of personal data. SEV-2: material degradation affecting more than 20% of requests, with no confirmed data exposure. SEV-3: single-tenant or cosmetic fault with a known workaround.',
  },
  ch_1052: {
    id: 'ch_1052', document_id: 'doc_02', document_title_snapshot: 'Incident Response Runbook v4', chunk_position: 11, score: 0.80, available: true,
    text: 'Escalation. A SEV-1 must be acknowledged by the on-call lead within 15 minutes and the Data Protection Officer informed immediately. Where personal data is involved, the supervisory authority is notified within 24 hours of confirmation.',
  },
  ch_1061: {
    id: 'ch_1061', document_id: 'doc_03', document_title_snapshot: 'Data Retention Policy (rev 7)', chunk_position: 6, score: 0.86, available: true,
    text: 'Section 4. Notifiable personal data breaches are reported to the supervisory authority no later than 72 hours after the organisation becomes aware of them. This revision supersedes the 24-hour internal target recorded in earlier operational material.',
  },
  ch_1062: {
    id: 'ch_1062', document_id: 'doc_03', document_title_snapshot: 'Data Retention Policy (rev 7)', chunk_position: 7, score: 0.78, available: true,
    text: 'Section 5. Operational logs are retained for 13 months. Customer records are retained for 6 years from the end of the contractual relationship, after which they are destroyed under the quarterly disposal schedule.',
  },
  ch_1071: {
    id: 'ch_1071', document_id: 'doc_07', document_title_snapshot: 'Employee Handbook 2026', chunk_position: 33, score: 0.74, available: true,
    text: 'Leave. Full-time employees receive 25 days annual leave plus public holidays, rising to 28 days after five years service. Requests are submitted at least two weeks in advance and approved by the line manager.',
  },
  ch_1081: {
    id: 'ch_1081', document_id: 'doc_04', document_title_snapshot: 'Board Minutes — 12 Sep 2026', chunk_position: 2, score: 0.71, available: true,
    text: 'Item 3. The Board approved the migration of the archive tier to Halden Cloud subject to completion of the security review, and asked that the supplier agreement renewal be brought back in November.',
  },
  ch_1101: {
    id: 'ch_1101', document_id: 'doc_99', document_title_snapshot: 'Procurement Approvals Log', chunk_position: 9, score: 0.69, available: false,
    text: '',
  },
};

const ANSWER_LIBRARY = [
  {
    keywords: ['system prompt', 'hidden instruction', 'your instructions', 'chain of thought', 'your reasoning'],
    docIds: [],
    sources: [],
    blocks: [
      { type: 'p', text: 'I can’t share my system prompt, hidden instructions or step-by-step private reasoning.' },
      { type: 'p', text: 'I can keep answering questions from your library as normal — ask anything about your uploaded documents and I’ll cite the chunks the answer came from.' },
    ],
  },
  {
    keywords: ['notice', 'terminat', 'exit fee', 'cancel the contract'],
    docIds: ['doc_01'],
    sources: ['ch_1041', 'ch_1042', 'ch_1043'],
    blocks: [
      { type: 'p', text: 'Either party may terminate for convenience on ninety (90) days written notice served at the other party’s registered address [S1].' },
      { type: 'bullets', items: [
        'Notice takes effect on the delivery date recorded by the courier [S1]',
        'Termination for convenience inside the first 12 months triggers an early-exit fee of £12,500, payable within 30 days [S2]',
        'The fee is waived after two consecutive quarters below the service credit floor, or on a change of control of the supplier [S3]',
      ] },
      { type: 'p', text: 'The retrieved context does not say whether notice may be served by email, so that part is not covered by the provided context.' },
    ],
  },
  {
    keywords: ['breach', 'notify', 'notification', '72', 'supervisory'],
    docIds: ['doc_03', 'doc_02'],
    sources: ['ch_1061', 'ch_1052'],
    blocks: [
      { type: 'p', text: 'Your sources give two different deadlines for notifying the supervisory authority, and the context resolves the conflict.' },
      { type: 'bullets', items: [
        'The retention policy requires notification no later than 72 hours after the organisation becomes aware of a notifiable breach [S1]',
        'The incident runbook records a 24-hour target once personal data involvement is confirmed [S2]',
      ] },
      { type: 'p', text: 'The policy states that revision 7 supersedes the earlier 24-hour internal target, so 72 hours is the governing external deadline and 24 hours stands only as an internal operational target [S1].' },
    ],
  },
  {
    keywords: ['severity', 'sev-1', 'sev1', 'incident', 'escalat', 'on-call'],
    docIds: ['doc_02'],
    sources: ['ch_1051', 'ch_1052'],
    blocks: [
      { type: 'p', text: 'The runbook defines three severity levels and one escalation path.' },
      { type: 'bullets', items: [
        'SEV-1 — complete loss of a customer-facing service, or confirmed exposure of personal data [S1]',
        'SEV-2 — material degradation affecting more than 20% of requests, no confirmed data exposure [S1]',
        'SEV-3 — single-tenant or cosmetic fault with a known workaround [S1]',
        'A SEV-1 is acknowledged by the on-call lead within 15 minutes and the DPO is informed immediately [S2]',
      ] },
    ],
  },
  {
    keywords: ['retention', 'retain', 'how long', 'destroy', 'logs'],
    docIds: ['doc_03'],
    sources: ['ch_1062', 'ch_1061'],
    blocks: [
      { type: 'p', text: 'Retention periods in the policy are set per record type.' },
      { type: 'bullets', items: [
        'Operational logs: 13 months [S1]',
        'Customer records: 6 years from the end of the contractual relationship, then destroyed on the quarterly disposal schedule [S1]',
      ] },
      { type: 'p', text: 'The policy covers breach reporting in the same section but says nothing about backup snapshots, which is not covered by the provided context [S2].' },
    ],
  },
  {
    keywords: ['leave', 'holiday', 'handbook', 'annual', 'sabbatical'],
    docIds: ['doc_07'],
    sources: ['ch_1071'],
    blocks: [
      { type: 'p', text: 'The handbook sets annual leave at 25 days plus public holidays, rising to 28 days after five years service, with requests submitted two weeks in advance [S1].' },
      { type: 'p', text: 'Sabbatical or unpaid long-term leave does not appear anywhere in the retrieved context, so I cannot say whether it is offered.' },
    ],
  },
];

const RETRY_COMPLETION = {
  sources: ['ch_1051', 'ch_1052'],
  blocks: [
    { type: 'p', text: 'The runbook sets the acknowledgement clock by severity.' },
    { type: 'bullets', items: [
      'SEV-1 is acknowledged by the on-call lead within 15 minutes, and the Data Protection Officer is informed immediately [S2]',
      'SEV-1 is defined as complete loss of a customer-facing service or confirmed exposure of personal data [S1]',
    ] },
    { type: 'p', text: 'No acknowledgement target for SEV-2 or SEV-3 appears in the retrieved context.' },
  ],
};

const INITIAL_CONVERSATIONS = [
  {
    id: 'conv_a',
    title: 'Northwind notice periods',
    created_at: 'Today, 09:12',
    group: 'Today',
    scope_document_ids: ['doc_01'],
    messages: [
      { id: 'm1', role: 'user', text: 'What notice do we have to give to terminate the Northwind agreement for convenience?', created_at: '09:12' },
      { id: 'm2', role: 'assistant', created_at: '09:12', sources: ['ch_1041', 'ch_1042', 'ch_1043'], blocks: ANSWER_LIBRARY[1].blocks },
      { id: 'm3', role: 'user', text: 'And what about the second one — can we avoid that fee?', created_at: '09:15' },
      {
        id: 'm4', role: 'assistant', created_at: '09:15', sources: ['ch_1043'],
        rewritten: 'Can the £12,500 early-exit fee under the Northwind supplier agreement be waived or avoided?',
        blocks: [
          { type: 'p', text: 'The fee is waived in only two situations set out in the agreement [S1].' },
          { type: 'bullets', items: [
            'The supplier fails to meet the service credit floor in two consecutive quarters [S1]',
            'A change of control of the supplier is notified under clause 19 [S1]',
          ] },
          { type: 'p', text: 'The clause states that no other waiver is provided for, so any negotiated waiver is not covered by the provided context.' },
        ],
      },
    ],
  },
  {
    id: 'conv_b',
    title: 'Breach notification deadline',
    created_at: 'Yesterday, 16:40',
    group: 'Yesterday',
    scope_document_ids: [],
    messages: [
      { id: 'm5', role: 'user', text: 'How quickly must we notify the supervisory authority after a personal data breach?', created_at: '16:40' },
      { id: 'm6', role: 'assistant', created_at: '16:41', sources: ['ch_1061', 'ch_1052'], blocks: ANSWER_LIBRARY[2].blocks },
    ],
  },
  {
    id: 'conv_c',
    title: 'Sabbatical leave policy',
    created_at: '3 Oct 2026, 11:02',
    group: 'Earlier',
    scope_document_ids: ['doc_07'],
    messages: [
      { id: 'm7', role: 'user', text: 'Does the handbook allow a six month unpaid sabbatical?', created_at: '11:02' },
      { id: 'm8', role: 'assistant', created_at: '11:02', insufficient: true, sources: [], blocks: [{ type: 'p', text: INSUFFICIENT }] },
    ],
  },
  {
    id: 'conv_d',
    title: 'SEV-1 acknowledgement window',
    created_at: '2 Oct 2026, 14:27',
    group: 'Earlier',
    scope_document_ids: ['doc_02'],
    messages: [
      { id: 'm9', role: 'user', text: 'How fast does a SEV-1 have to be acknowledged?', created_at: '14:27' },
      {
        id: 'm10', role: 'assistant', created_at: '14:27', is_incomplete: true, sources: ['ch_1051'],
        blocks: [{ type: 'p', text: 'The runbook sets the acknowledgement clock by severity. SEV-1 is defined as complete loss of a customer-facing' }],
      },
    ],
  },
  {
    id: 'conv_e',
    title: 'Halden Cloud board approval',
    created_at: '28 Sep 2026, 08:55',
    group: 'Earlier',
    scope_document_ids: [],
    messages: [
      { id: 'm11', role: 'user', text: 'Did the board approve the Halden Cloud migration?', created_at: '08:55' },
      {
        id: 'm12', role: 'assistant', created_at: '08:55', sources: ['ch_1081', 'ch_1101'],
        blocks: [
          { type: 'p', text: 'Yes — the Board approved migration of the archive tier to Halden Cloud, subject to completion of the security review [S1].' },
          { type: 'p', text: 'The approval reference was also recorded in the procurement log [S2]. The minutes ask for the supplier agreement renewal to return in November [S1].' },
        ],
      },
    ],
  },
];

const QUESTION_CAP = 50;

function countWords(blocks) {
  let n = 0;
  blocks.forEach((b) => {
    if (b.type === 'bullets') b.items.forEach((i) => { n += i.split(/\s+/).length; });
    else n += b.text.split(/\s+/).length;
  });
  return n;
}

function trimPartial(s) {
  return s.replace(/\s*\[S?\d*$/, '');
}

function sliceBlocks(blocks, limit) {
  let left = limit;
  const out = [];
  for (const b of blocks) {
    if (left <= 0) break;
    if (b.type === 'bullets') {
      const items = [];
      for (const it of b.items) {
        if (left <= 0) break;
        const w = it.split(/\s+/);
        items.push(trimPartial(w.slice(0, left).join(' ')));
        left -= Math.min(left, w.length);
      }
      out.push({ type: 'bullets', items });
    } else {
      const w = b.text.split(/\s+/);
      out.push({ type: 'p', text: trimPartial(w.slice(0, left).join(' ')) });
      left -= Math.min(left, w.length);
    }
  }
  return out;
}

function matchAnswer(question) {
  const t = question.toLowerCase();
  for (const a of ANSWER_LIBRARY) {
    if (a.keywords.some((k) => t.includes(k))) return a;
  }
  return null;
}

function statusMeta(status) {
  if (status === 'ready') return { label: 'Ready', Icon: Icons.CheckCircle, color: '#1F4E79', bg: '#E4EDF5' };
  if (status === 'processing') return { label: 'Processing', Icon: Icons.Clock, color: '#6B5A00', bg: '#FBF2CF' };
  return { label: 'Failed', Icon: Icons.AlertCircle, color: '#8A2D2D', bg: '#F7E3E3' };
}

export default function Screen() {
  const navigate = useNavigate();
  const primary = brand.primaryColor;
  const accent = brand.accentColor;
  const [conversations, setConversations] = React.useState(INITIAL_CONVERSATIONS);
  const [activeId, setActiveId] = React.useState('conv_a');
  const [search, setSearch] = React.useState('');
  const [draft, setDraft] = React.useState('');
  const [draftError, setDraftError] = React.useState('');
  const [scopeOpen, setScopeOpen] = React.useState(false);
  const [selectedChunkId, setSelectedChunkId] = React.useState(null);
  const [selectedMessageId, setSelectedMessageId] = React.useState('m4');
  const [remaining, setRemaining] = React.useState(4);
  const [stream, setStream] = React.useState(null); // { messageId, revealed }
  const [announce, setAnnounce] = React.useState('');
  const scopeButtonRef = React.useRef(null);

  const active = conversations.find((c) => c.id === activeId) || conversations[0];
  const readyDocs = DOCS.filter((d) => d.status === 'ready');
  const otherDocs = DOCS.filter((d) => d.status !== 'ready');

  const scopedDocs = active.scope_document_ids.length
    ? readyDocs.filter((d) => active.scope_document_ids.includes(d.id))
    : readyDocs;

  // streaming reveal
  React.useEffect(() => {
    if (!stream) return undefined;
    const conv = conversations.find((c) => c.id === stream.convId);
    if (!conv) return undefined;
    const msg = conv.messages.find((m) => m.id === stream.messageId);
    if (!msg) return undefined;
    const total = countWords(msg.blocks);
    if (stream.revealed >= total) {
      setConversations((prev) => prev.map((c) => (c.id !== stream.convId ? c : {
        ...c,
        messages: c.messages.map((m) => (m.id === stream.messageId ? { ...m, streaming: false } : m)),
      })));
      setStream(null);
      setAnnounce('Answer complete. ' + (msg.sources.length ? msg.sources.length + ' sources listed.' : 'No sources cited.'));
      return undefined;
    }
    const t = setTimeout(() => setStream((s) => (s ? { ...s, revealed: s.revealed + 4 } : s)), 55);
    return () => clearTimeout(t);
  }, [stream, conversations]);

  const openConversation = (id) => {
    setActiveId(id);
    setScopeOpen(false);
    setSelectedChunkId(null);
    const conv = conversations.find((c) => c.id === id);
    const lastAssistant = conv ? [...conv.messages].reverse().find((m) => m.role === 'assistant') : null;
    setSelectedMessageId(lastAssistant ? lastAssistant.id : null);
  };

  const newChat = () => {
    const id = 'conv_' + Math.random().toString(36).slice(2, 8);
    const conv = { id, title: 'New conversation', created_at: 'Today, 10:40', group: 'Today', scope_document_ids: [], messages: [] };
    setConversations((prev) => [conv, ...prev]);
    setActiveId(id);
    setSelectedChunkId(null);
    setSelectedMessageId(null);
    setDraft('');
    setDraftError('');
    setAnnounce('New conversation started.');
  };

  const toggleScopeDoc = (docId) => {
    setConversations((prev) => prev.map((c) => {
      if (c.id !== active.id) return c;
      const has = c.scope_document_ids.includes(docId);
      return { ...c, scope_document_ids: has ? c.scope_document_ids.filter((x) => x !== docId) : [...c.scope_document_ids, docId] };
    }));
  };

  const clearScope = () => {
    setConversations((prev) => prev.map((c) => (c.id === active.id ? { ...c, scope_document_ids: [] } : c)));
  };

  const pushMessages = (convId, msgs, titleIfNew) => {
    setConversations((prev) => prev.map((c) => (c.id !== convId ? c : {
      ...c,
      title: c.messages.length === 0 && titleIfNew ? titleIfNew : c.title,
      messages: [...c.messages, ...msgs],
    })));
  };

  const submit = (e) => {
    e.preventDefault();
    const q = draft.trim();
    if (!q) {
      setDraftError('Enter a question before sending.');
      return;
    }
    setDraftError('');
    const stamp = Date.now();
    const userMsg = { id: 'u' + stamp, role: 'user', text: q, created_at: '10:4' + (stamp % 10) };

    if (remaining <= 0) {
      pushMessages(active.id, [userMsg, {
        id: 's' + stamp, role: 'system', created_at: 'now',
        text: 'Monthly question limit reached (' + QUESTION_CAP + ' of ' + QUESTION_CAP + ' used). No answer was generated and no provider call was made. Your allowance resets on 1 November 2026.',
      }], q.slice(0, 48));
      setDraft('');
      setAnnounce('Monthly question limit reached.');
      return;
    }

    const match = matchAnswer(q);
    const scopeIds = active.scope_document_ids;
    const inScope = !match ? false : (match.docIds.length === 0 ? true : (scopeIds.length === 0 || match.docIds.some((d) => scopeIds.includes(d))));

    let answer;
    if (match && inScope) {
      answer = { blocks: match.blocks, sources: match.sources.filter((s) => {
        const c = CHUNKS[s];
        return scopeIds.length === 0 || !c.document_id.startsWith('doc_') || scopeIds.includes(c.document_id) || match.docIds.length === 0;
      }) };
      if (answer.sources.length === 0) answer.sources = match.sources;
    } else {
      answer = { blocks: [{ type: 'p', text: INSUFFICIENT }], sources: [], insufficient: true };
    }

    const assistantMsg = {
      id: 'a' + stamp, role: 'assistant', created_at: 'now',
      blocks: answer.blocks, sources: answer.sources, insufficient: answer.insufficient, streaming: true,
      rewritten: /^(and|what about|does it|do they|is it)\b/i.test(q) ? 'Rewritten for retrieval: ' + q.replace(/^(and\s+)/i, '') + ' (in the current conversation’s documents)' : null,
    };
    pushMessages(active.id, [userMsg, assistantMsg], q.slice(0, 48));
    setRemaining((r) => Math.max(0, r - 1));
    setSelectedMessageId(assistantMsg.id);
    setSelectedChunkId(null);
    setStream({ convId: active.id, messageId: assistantMsg.id, revealed: 0 });
    setDraft('');
    setAnnounce('Generating answer.');
  };

  const retry = (messageId) => {
    setConversations((prev) => prev.map((c) => (c.id !== active.id ? c : {
      ...c,
      messages: c.messages.map((m) => (m.id !== messageId ? m : {
        ...m, is_incomplete: false, streaming: true, blocks: RETRY_COMPLETION.blocks, sources: RETRY_COMPLETION.sources,
      })),
    })));
    setSelectedMessageId(messageId);
    setStream({ convId: active.id, messageId, revealed: 0 });
    setAnnounce('Retrying generation.');
  };

  const onCite = (chunkId, messageId) => {
    setSelectedChunkId(chunkId);
    setSelectedMessageId(messageId);
  };

  const filtered = conversations.filter((c) => {
    const t = search.trim().toLowerCase();
    if (!t) return true;
    return c.title.toLowerCase().includes(t) || c.messages.some((m) => (m.text || '').toLowerCase().includes(t));
  });

  const evidenceMessage = (() => {
    for (const c of conversations) {
      const m = c.messages.find((x) => x.id === selectedMessageId);
      if (m) return m;
    }
    return null;
  })();
  const evidenceChunks = evidenceMessage && evidenceMessage.sources ? evidenceMessage.sources.map((id) => CHUNKS[id]).filter(Boolean) : [];

  const focusRing = 'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-blue-900';

  const renderInline = (text, sources, messageId) => {
    const parts = String(text).split(/(\[S\d+\])/g);
    return parts.map((p, i) => {
      const m = p.match(/^\[S(\d+)\]$/);
      if (!m) return React.createElement(React.Fragment, { key: i }, p);
      const chunkId = sources[Number(m[1]) - 1];
      if (!chunkId) return null;
      const chunk = CHUNKS[chunkId];
      const isActive = selectedChunkId === chunkId;
      return (
        <button
          key={i}
          type="button"
          onClick={() => onCite(chunkId, messageId)}
          aria-label={'Show source S' + m[1] + ': ' + chunk.document_title_snapshot + ', chunk ' + chunk.chunk_position}
          className={'mx-0.5 inline-flex items-center rounded border px-1 align-baseline text-[11px] font-semibold leading-4 ' + focusRing}
          style={{
            borderColor: isActive ? primary : accent,
            backgroundColor: isActive ? '#E4EDF5' : '#FBF2CF',
            color: isActive ? primary : '#5B4800',
          }}
        >
          S{m[1]}
        </button>
      );
    });
  };

  const renderBlocks = (blocks, sources, messageId) => blocks.map((b, i) => {
    if (b.type === 'bullets') {
      return (
        <ul key={i} className="my-2 list-disc space-y-1 pl-5">
          {b.items.map((it, j) => <li key={j} className="leading-relaxed">{renderInline(it, sources, messageId)}</li>)}
        </ul>
      );
    }
    return <p key={i} className="my-2 leading-relaxed">{renderInline(b.text, sources, messageId)}</p>;
  });

  return (
    <div className="mx-auto max-w-[1500px] px-4 py-5" style={{ fontFamily: brand.fontBody, color: '#1B2430' }}>
      <div className="sr-only" aria-live="polite">{announce}</div>

      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: brand.fontHeading, color: primary }}>Chat</h1>
          <p className="mt-1 text-[13px]" style={{ color: brand.neutralColor }}>
            Answers are built only from your own document chunks. Every claim carries the source it came from.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-[13px]" style={{ color: remaining <= 5 ? '#6B5A00' : brand.neutralColor }}>
            {remaining > 0
              ? <span><span className="font-semibold">{remaining}</span> of {QUESTION_CAP} questions left this month &middot; resets 1 Nov 2026</span>
              : <span className="font-semibold">Monthly limit reached &middot; resets 1 Nov 2026</span>}
          </p>
          <UI.Button
            type="button"
            onClick={() => navigate('library')}
            className={'border bg-white px-3 py-1.5 text-[13px] font-medium ' + focusRing}
            style={{ borderColor: '#CBD3DC', color: primary, borderRadius: brand.radius }}
          >
            <Icons.FileText aria-hidden="true" className="mr-1.5 inline h-4 w-4" />
            My document library
          </UI.Button>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[15rem_minmax(0,1fr)_21rem]">
        {/* ---------------- history rail ---------------- */}
        <section aria-labelledby="hist-h" className="rounded-lg border bg-white" style={{ borderColor: '#DCE2E9', borderRadius: brand.radius }}>
          <div className="border-b p-3" style={{ borderColor: '#E6EAEF' }}>
            <div className="mb-2 flex items-center justify-between">
              <h2 id="hist-h" className="text-[13px] font-semibold uppercase tracking-wide" style={{ color: brand.neutralColor }}>Conversations</h2>
              <UI.Button
                type="button"
                onClick={newChat}
                aria-label="Start a new conversation"
                className={'inline-flex items-center gap-1 px-2 py-1 text-[12px] font-semibold text-white ' + focusRing}
                style={{ backgroundColor: primary, borderRadius: brand.radius }}
              >
                <Icons.Plus aria-hidden="true" className="h-3.5 w-3.5" /> New
              </UI.Button>
            </div>
            <UI.Label htmlFor="conv-search" className="sr-only">Search conversations</UI.Label>
            <div className="relative">
              <Icons.Search aria-hidden="true" className="pointer-events-none absolute left-2 top-2 h-4 w-4" style={{ color: brand.neutralColor }} />
              <UI.Input
                id="conv-search"
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search history"
                className={'w-full border py-1.5 pl-8 pr-2 text-[13px] ' + focusRing}
                style={{ borderColor: '#CBD3DC', borderRadius: brand.radius }}
              />
            </div>
          </div>

          {filtered.length === 0 ? (
            <p className="p-4 text-[13px]" style={{ color: brand.neutralColor }}>
              No conversations match &ldquo;{search}&rdquo;.
            </p>
          ) : (
            <ul className="max-h-[32rem] overflow-y-auto p-2">
              {filtered.map((c) => {
                const isActive = c.id === active.id;
                const last = c.messages.length ? c.messages[c.messages.length - 1] : null;
                const preview = last ? (last.text || (last.insufficient ? 'Insufficient context' : 'Answer with sources')) : 'No questions yet';
                return (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => openConversation(c.id)}
                      aria-current={isActive ? 'true' : undefined}
                      className={'mb-1 w-full rounded px-2 py-2 text-left ' + focusRing + (isActive ? '' : ' hover:bg-slate-50')}
                      style={isActive ? { backgroundColor: '#E4EDF5', boxShadow: 'inset 2px 0 0 ' + primary } : undefined}
                    >
                      <span className="block truncate text-[13px] font-medium" style={{ color: isActive ? primary : '#1B2430' }}>{c.title}</span>
                      <span className="mt-0.5 block truncate text-[12px]" style={{ color: brand.neutralColor }}>{preview}</span>
                      <span className="mt-0.5 block text-[11px]" style={{ color: brand.neutralColor }}>
                        {c.created_at} &middot; {c.messages.filter((m) => m.role === 'user').length} question{c.messages.filter((m) => m.role === 'user').length === 1 ? '' : 's'}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* ---------------- thread ---------------- */}
        <section aria-labelledby="conv-h" className="flex min-h-[34rem] flex-col rounded-lg border bg-white" style={{ borderColor: '#DCE2E9', borderRadius: brand.radius }}>
          <div className="border-b px-4 py-3" style={{ borderColor: '#E6EAEF' }}>
            <h2 id="conv-h" className="text-[15px] font-semibold" style={{ fontFamily: brand.fontHeading }}>{active.title}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button
                ref={scopeButtonRef}
                type="button"
                onClick={() => setScopeOpen((o) => !o)}
                aria-expanded={scopeOpen}
                aria-controls="scope-panel"
                className={'inline-flex items-center gap-1.5 rounded border px-2 py-1 text-[12px] font-medium ' + focusRing}
                style={{ borderColor: '#CBD3DC', color: primary, borderRadius: brand.radius }}
              >
                <Icons.Filter aria-hidden="true" className="h-3.5 w-3.5" />
                Scope: {active.scope_document_ids.length === 0 ? 'all ready documents (' + readyDocs.length + ')' : active.scope_document_ids.length + ' selected'}
                {scopeOpen ? <Icons.ChevronDown aria-hidden="true" className="h-3.5 w-3.5" /> : <Icons.ChevronRight aria-hidden="true" className="h-3.5 w-3.5" />}
              </button>
              <span className="text-[12px]" style={{ color: brand.neutralColor }}>
                Retrieval: semantic similarity, top 4 chunks, your account only
              </span>
            </div>

            {scopeOpen && (
              <div
                id="scope-panel"
                onKeyDown={(e) => { if (e.key === 'Escape') { setScopeOpen(false); if (scopeButtonRef.current) scopeButtonRef.current.focus(); } }}
                className="mt-3 rounded border p-3"
                style={{ borderColor: '#DCE2E9', backgroundColor: '#F7F9FB', borderRadius: brand.radius }}
              >
                <h3 className="text-[12px] font-semibold uppercase tracking-wide" style={{ color: brand.neutralColor }}>Limit this conversation to</h3>
                <ul className="mt-2 space-y-1.5">
                  {readyDocs.map((d) => (
                    <li key={d.id} className="flex items-start gap-2">
                      <input
                        id={'scope-' + d.id}
                        type="checkbox"
                        checked={active.scope_document_ids.includes(d.id)}
                        onChange={() => toggleScopeDoc(d.id)}
                        className={'mt-0.5 h-4 w-4 rounded border ' + focusRing}
                        style={{ accentColor: primary, borderColor: '#9AA7B4' }}
                      />
                      <label htmlFor={'scope-' + d.id} className="text-[13px] leading-5">
                        {d.title}
                        <span className="ml-2 text-[11px]" style={{ color: brand.neutralColor }}>{d.file_type} &middot; {d.uploaded_at}</span>
                      </label>
                    </li>
                  ))}
                </ul>
                <div className="mt-3 space-y-1 border-t pt-2" style={{ borderColor: '#E6EAEF' }}>
                  {otherDocs.map((d) => {
                    const meta = statusMeta(d.status);
                    return (
                      <p key={d.id} className="flex items-start gap-2 text-[12px]" style={{ color: brand.neutralColor }}>
                        <meta.Icon aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <span>
                          <span className="font-medium">{d.title}</span> &mdash; {meta.label.toLowerCase()}, not available for retrieval
                          {d.failure_reason ? '. ' + d.failure_reason : '.'}
                        </span>
                      </p>
                    );
                  })}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <UI.Button type="button" onClick={clearScope} className={'border bg-white px-2 py-1 text-[12px] font-medium ' + focusRing} style={{ borderColor: '#CBD3DC', color: primary, borderRadius: brand.radius }}>
                    Use all ready documents
                  </UI.Button>
                  <UI.Button type="button" onClick={() => { setScopeOpen(false); if (scopeButtonRef.current) scopeButtonRef.current.focus(); }} className={'px-2 py-1 text-[12px] font-semibold text-white ' + focusRing} style={{ backgroundColor: primary, borderRadius: brand.radius }}>
                    Done
                  </UI.Button>
                </div>
              </div>
            )}
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            {active.messages.length === 0 && (
              <div className="rounded border border-dashed p-6 text-center" style={{ borderColor: '#CBD3DC' }}>
                <Icons.Search aria-hidden="true" className="mx-auto h-5 w-5" style={{ color: brand.neutralColor }} />
                <p className="mt-2 text-[14px] font-medium">Ask your first question</p>
                <p className="mx-auto mt-1 max-w-sm text-[13px]" style={{ color: brand.neutralColor }}>
                  {scopedDocs.length} ready document{scopedDocs.length === 1 ? '' : 's'} will be searched. Answers come back as an Answer section followed by the sources they were drawn from.
                </p>
              </div>
            )}

            {active.messages.map((m) => {
              if (m.role === 'user') {
                return (
                  <article key={m.id} className="ml-auto max-w-[85%] rounded px-3 py-2" style={{ backgroundColor: '#E4EDF5', borderRadius: brand.radius }}>
                    <h3 className="sr-only">Your question</h3>
                    <p className="text-[13px] leading-relaxed" style={{ color: '#17324B' }}>{m.text}</p>
                    <p className="mt-1 text-[11px]" style={{ color: brand.neutralColor }}>You &middot; {m.created_at}</p>
                  </article>
                );
              }
              if (m.role === 'system') {
                return (
                  <div key={m.id} className="flex items-start gap-2 rounded border px-3 py-2" style={{ borderColor: accent, backgroundColor: '#FBF2CF', borderRadius: brand.radius }}>
                    <Icons.AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" style={{ color: '#6B5A00' }} />
                    <p className="text-[13px] leading-relaxed" style={{ color: '#5B4800' }}>{m.text}</p>
                  </div>
                );
              }
              const isStreaming = !!m.streaming;
              const shown = isStreaming && stream && stream.messageId === m.id ? sliceBlocks(m.blocks, stream.revealed) : m.blocks;
              const sources = m.sources || [];
              return (
                <article key={m.id} className="rounded border" style={{ borderColor: '#DCE2E9', borderRadius: brand.radius }}>
                  <div className="flex flex-wrap items-center gap-2 border-b px-3 py-1.5" style={{ borderColor: '#E6EAEF', backgroundColor: '#F7F9FB' }}>
                    <h3 className="text-[12px] font-semibold uppercase tracking-wide" style={{ color: primary }}>Answer</h3>
                    {isStreaming && (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium" style={{ color: '#6B5A00' }}>
                        <Icons.Clock aria-hidden="true" className="h-3.5 w-3.5" /> Generating&hellip;
                      </span>
                    )}
                    {m.is_incomplete && (
                      <span className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-semibold" style={{ borderColor: '#D9B3B3', backgroundColor: '#F7E3E3', color: '#8A2D2D' }}>
                        <Icons.AlertCircle aria-hidden="true" className="h-3 w-3" /> Incomplete
                      </span>
                    )}
                    {m.insufficient && (
                      <span className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-semibold" style={{ borderColor: '#CBD3DC', backgroundColor: '#EFF2F5', color: brand.neutralColor }}>
                        <Icons.X aria-hidden="true" className="h-3 w-3" /> No supporting context
                      </span>
                    )}
                    <span className="ml-auto text-[11px]" style={{ color: brand.neutralColor }}>{m.created_at}</span>
                  </div>

                  <div className="px-3 py-2 text-[13px]">
                    {m.rewritten && (
                      <p className="mb-2 rounded px-2 py-1 text-[11px]" style={{ backgroundColor: '#F2F5F8', color: brand.neutralColor }}>
                        <Icons.ArrowRight aria-hidden="true" className="mr-1 inline h-3 w-3" />
                        Follow-up rewritten for retrieval: &ldquo;{m.rewritten}&rdquo;
                      </p>
                    )}
                    {renderBlocks(shown, sources, m.id)}

                    {m.is_incomplete && (
                      <div className="mt-2 flex items-center gap-2 rounded border px-2 py-1.5" style={{ borderColor: '#D9B3B3', backgroundColor: '#FCF4F4' }}>
                        <p className="text-[12px]" style={{ color: '#8A2D2D' }}>Generation stopped before the answer finished. The text above is partial.</p>
                        <UI.Button type="button" onClick={() => retry(m.id)} className={'ml-auto px-2 py-1 text-[12px] font-semibold text-white ' + focusRing} style={{ backgroundColor: primary, borderRadius: brand.radius }}>
                          Retry
                        </UI.Button>
                      </div>
                    )}
                  </div>

                  {!isStreaming && (
                    <div className="border-t px-3 py-2" style={{ borderColor: '#E6EAEF' }}>
                      <h3 className="text-[12px] font-semibold uppercase tracking-wide" style={{ color: primary }}>Sources</h3>
                      {sources.length === 0 ? (
                        <p className="mt-1 text-[12px]" style={{ color: brand.neutralColor }}>
                          {m.insufficient ? 'None. No chunk in the retrieved context supported an answer.' : 'None cited — this reply is based on the supplied context only.'}
                        </p>
                      ) : (
                        <ol className="mt-1 space-y-1">
                          {sources.map((cid, idx) => {
                            const c = CHUNKS[cid];
                            const isActiveChunk = selectedChunkId === cid;
                            return (
                              <li key={cid}>
                                <button
                                  type="button"
                                  onClick={() => onCite(cid, m.id)}
                                  className={'flex w-full items-start gap-2 rounded px-1.5 py-1 text-left text-[12px] hover:bg-slate-50 ' + focusRing}
                                  style={isActiveChunk ? { backgroundColor: '#E4EDF5' } : undefined}
                                >
                                  <span className="mt-0.5 shrink-0 rounded border px-1 text-[11px] font-semibold" style={{ borderColor: accent, backgroundColor: '#FBF2CF', color: '#5B4800' }}>S{idx + 1}</span>
                                  <span>
                                    <span className="font-medium">{c.document_title_snapshot}</span>
                                    <span style={{ color: brand.neutralColor }}> &middot; chunk {c.chunk_position}</span>
                                    {!c.available && <span className="ml-1 font-medium" style={{ color: '#8A2D2D' }}>(document deleted)</span>}
                                  </span>
                                </button>
                              </li>
                            );
                          })}
                        </ol>
                      )}
                    </div>
                  )}
                </article>
              );
            })}
          </div>

          <form onSubmit={submit} className="border-t p-3" style={{ borderColor: '#E6EAEF' }}>
            <UI.Label htmlFor="question" className="text-[12px] font-medium" style={{ color: brand.neutralColor }}>
              Your question
            </UI.Label>
            <UI.Textarea
              id="question"
              rows={2}
              value={draft}
              onChange={(e) => { setDraft(e.target.value); if (draftError) setDraftError(''); }}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) submit(e); }}
              disabled={remaining <= 0}
              aria-describedby={draftError ? 'question-error question-hint' : 'question-hint'}
              aria-invalid={draftError ? 'true' : undefined}
              placeholder="e.g. What notice do we need to give Northwind?"
              className={'mt-1 w-full resize-none border px-2 py-1.5 text-[13px] ' + focusRing}
              style={{ borderColor: draftError ? '#8A2D2D' : '#CBD3DC', borderRadius: brand.radius, backgroundColor: remaining <= 0 ? '#F2F5F8' : '#fff' }}
            />
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <p id="question-hint" className="text-[11px]" style={{ color: brand.neutralColor }}>
                Searching {scopedDocs.length} ready document{scopedDocs.length === 1 ? '' : 's'}. Enter sends, Shift + Enter adds a line.
              </p>
              <UI.Button
                type="submit"
                disabled={remaining <= 0}
                className={'ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-semibold text-white ' + focusRing}
                style={{ backgroundColor: remaining <= 0 ? '#9AA7B4' : primary, borderRadius: brand.radius }}
              >
                <Icons.ArrowRight aria-hidden="true" className="h-4 w-4" /> Send question
              </UI.Button>
            </div>
            {draftError && <p id="question-error" className="mt-1 text-[12px] font-medium" style={{ color: '#8A2D2D' }}>{draftError}</p>}
            {remaining <= 0 && (
              <p className="mt-1 text-[12px] font-medium" style={{ color: '#6B5A00' }}>
                Monthly question limit reached. Your allowance resets on 1 November 2026.
              </p>
            )}
          </form>
        </section>

        {/* ---------------- evidence pane ---------------- */}
        <section aria-labelledby="ev-h" className="rounded-lg border bg-white" style={{ borderColor: '#DCE2E9', borderRadius: brand.radius }}>
          <div className="border-b px-3 py-3" style={{ borderColor: '#E6EAEF' }}>
            <h2 id="ev-h" className="text-[13px] font-semibold uppercase tracking-wide" style={{ color: brand.neutralColor }}>Evidence</h2>
            <p className="mt-1 text-[12px]" style={{ color: brand.neutralColor }}>
              Chunks retrieved for the selected answer, in similarity order. No re-ranking is applied.
            </p>
          </div>

          {evidenceChunks.length === 0 ? (
            <p className="p-4 text-[13px]" style={{ color: brand.neutralColor }}>
              {evidenceMessage && evidenceMessage.insufficient
                ? 'Nothing was retrieved above the threshold for this question, so the insufficient-context reply was returned.'
                : 'Select a citation in an answer to read the chunk it came from.'}
            </p>
          ) : (
            <ul className="max-h-[32rem] space-y-2 overflow-y-auto p-3">
              {evidenceChunks.map((c, idx) => {
                const isActiveChunk = selectedChunkId === c.id;
                return (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedChunkId(isActiveChunk ? null : c.id)}
                      aria-expanded={isActiveChunk}
                      className={'w-full rounded border p-2 text-left ' + focusRing}
                      style={{ borderColor: isActiveChunk ? primary : '#DCE2E9', backgroundColor: isActiveChunk ? '#F5F9FC' : '#fff', borderRadius: brand.radius }}
                    >
                      <span className="flex items-center gap-2">
                        <span className="shrink-0 rounded border px-1 text-[11px] font-semibold" style={{ borderColor: accent, backgroundColor: '#FBF2CF', color: '#5B4800' }}>S{idx + 1}</span>
                        <span className="truncate text-[12px] font-medium">{c.document_title_snapshot}</span>
                        <span className="ml-auto shrink-0 text-[11px]" style={{ color: brand.neutralColor }}>{c.score.toFixed(2)}</span>
                      </span>
                      <span className="mt-1 block text-[11px]" style={{ color: brand.neutralColor }}>chunk {c.chunk_position}</span>
                      {c.available ? (
                        <span
                          className="mt-1.5 block text-[12px] leading-relaxed"
                          style={isActiveChunk ? undefined : { maxHeight: '3.2rem', overflow: 'hidden' }}
                        >
                          {c.text}
                        </span>
                      ) : (
                        <span className="mt-1.5 flex items-start gap-1.5 text-[12px] leading-relaxed" style={{ color: '#8A2D2D' }}>
                          <Icons.AlertCircle aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                          This source document is no longer available — it was deleted from the library, so its text cannot be shown.
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="border-t px-3 py-3" style={{ borderColor: '#E6EAEF' }}>
            <h3 className="text-[12px] font-semibold uppercase tracking-wide" style={{ color: brand.neutralColor }}>Library status</h3>
            <ul className="mt-2 space-y-1">
              {DOCS.slice(0, 7).map((d) => {
                const meta = statusMeta(d.status);
                return (
                  <li key={d.id} className="flex items-center gap-2 text-[12px]">
                    <meta.Icon aria-hidden="true" className="h-3.5 w-3.5 shrink-0" style={{ color: meta.color }} />
                    <span className="truncate">{d.title}</span>
                    <span className="ml-auto shrink-0 rounded px-1.5 py-0.5 text-[11px] font-medium" style={{ backgroundColor: meta.bg, color: meta.color }}>{meta.label}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        </section>
      </div>
    </div>
  );
}
