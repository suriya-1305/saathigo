import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, formatDate } from "../api/client";
import type {
  AgentMeta,
  AgentName,
  AgentRunRow,
  ChatTurn,
  ComplianceReport,
  RankedTraveller,
  RewardAdvice,
  SupportReply,
} from "../api/types";

export const AGENT_LABELS: Record<AgentName, { name: string; icon: string }> = {
  concierge: { name: "Concierge", icon: "🙏" },
  intake: { name: "Intake", icon: "📝" },
  dabba_curator: { name: "Dabba Curator", icon: "🎁" },
  compliance: { name: "Compliance", icon: "🛃" },
  matching: { name: "Matching", icon: "🧭" },
  negotiation: { name: "Negotiation", icon: "🤝" },
  tracking_support: { name: "Tracking & Support", icon: "📍" },
};

export function AgentBadge({ meta }: { meta: AgentMeta }) {
  const a = AGENT_LABELS[meta.agent];
  const title = meta.note ?? (meta.source === "agenticorg" ? "Pine Labs AgenticOrg" : "Rule-based fallback");
  return (
    <span className={`agent-badge ${meta.source}`} title={title}>
      {a.icon} Saathi {a.name}
      {meta.confidence != null && <em>{Math.round(meta.confidence * 100)}%</em>}
      {meta.source === "fallback" && <em>rules</em>}
      {meta.needs_human && <em className="hitl">human check</em>}
    </span>
  );
}

export function AgentThinking({ agents, label }: { agents: AgentName[]; label?: string }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((n) => (n + 1) % agents.length), 1800);
    return () => clearInterval(t);
  }, [agents.length]);
  const a = AGENT_LABELS[agents[i]];
  return (
    <div className="agent-thinking">
      <span className="dots">
        <i />
        <i />
        <i />
      </span>
      {label ?? `${a.icon} Saathi ${a.name} is working…`}
    </div>
  );
}

const VERDICT: Record<string, { icon: string; label: string }> = {
  clear: { icon: "✅", label: "Clear" },
  needs_label_check: { icon: "⚠️", label: "Needs label check" },
  not_allowed: { icon: "⛔", label: "Not allowed" },
};

export function CompliancePanel({ report, compact = false }: { report: ComplianceReport; compact?: boolean }) {
  const cls = report.overall === "clear" ? "ok" : report.overall === "blocked" ? "err" : "warn";
  const headline =
    report.overall === "clear"
      ? "All items cleared for this route"
      : report.overall === "blocked"
        ? "Some items can't travel on this route"
        : "Some items need a label / packaging check";
  return (
    <div className={`compliance ${cls}`}>
      <div className="row space-between wrap gap">
        <strong>🛃 {headline}</strong>
        {report.meta && <AgentBadge meta={report.meta} />}
      </div>
      <p className="muted small">{report.route}</p>
      <ul className="verdicts">
        {report.items.map((i) => (
          <li key={i.item} className={i.status}>
            <div>
              {VERDICT[i.status]?.icon} <b>{i.item}</b> <span className="muted small">· {VERDICT[i.status]?.label}</span>
            </div>
            {!compact && i.reason && <div className="small">{i.reason}</div>}
            {!compact && i.packing_note && <div className="small muted">📦 {i.packing_note}</div>}
          </li>
        ))}
      </ul>
      {!compact && report.guidance && <p className="small muted">{report.guidance}</p>}
    </div>
  );
}

export function TravellerMatches({ path }: { path: string }) {
  const [data, setData] = useState<{ ranked: RankedTraveller[]; agent: AgentMeta } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = () => {
    setBusy(true);
    setError(null);
    api<{ ranked: RankedTraveller[]; agent: AgentMeta }>(path)
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Saathi Matching is unavailable"))
      .finally(() => setBusy(false));
  };
  return (
    <div className="card saathi-card">
      <div className="row space-between wrap gap">
        <h3>🧭 Saathi Matching</h3>
        {data && <AgentBadge meta={data.agent} />}
      </div>
      <p className="muted small">Travellers on your route, ranked by date fit, spare space and track record.</p>
      {busy ? (
        <AgentThinking agents={["matching"]} />
      ) : data ? (
        data.ranked.length ? (
          <ol className="ranked">
            {data.ranked.map((r) => (
              <li key={r.id} className={r.flagged ? "flagged" : ""}>
                <div className="score">{r.score}</div>
                <div className="grow">
                  <b>{r.traveller.name}</b>{" "}
                  <span className="muted small">
                    {r.trip.origin_city} → {r.trip.destination_city} · {formatDate(r.trip.travel_date)}
                    {r.trip.flight_number ? ` · ${r.trip.flight_number}` : ""} · {r.trip.capacity_kg} kg spare ·{" "}
                    {r.traveller.completed_deliveries} deliveries
                  </span>
                  <div className="small">{r.reason}</div>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">No travellers on this route yet — your order is visible to everyone who adds one.</p>
        )
      ) : (
        <button className="btn btn-ghost btn-sm" onClick={run}>
          Find & rank travellers
        </button>
      )}
      {error && <div className="alert alert-error">{error}</div>}
      {data && !busy && (
        <button className="btn-link small" onClick={run}>
          ↻ Re-rank
        </button>
      )}
    </div>
  );
}

export function RewardAdvisor({
  body,
  onApply,
  applyLabel = "Use this reward",
  onAdvice,
}: {
  body: Record<string, unknown>;
  onApply?: (inr: number) => void;
  applyLabel?: string;
  onAdvice?: (a: RewardAdvice) => void;
}) {
  const [advice, setAdvice] = useState<RewardAdvice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ask = async () => {
    setBusy(true);
    setError(null);
    try {
      const a = await api<RewardAdvice>("/agents/negotiate", { method: "POST", json: body });
      setAdvice(a);
      onAdvice?.(a);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Saathi Negotiation is unavailable");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="saathi-inline">
      {busy ? (
        <AgentThinking agents={["negotiation"]} />
      ) : advice ? (
        <div className="advice">
          <div className="row space-between wrap gap">
            <strong>
              🤝 Fair reward ≈ ₹{advice.suggested_reward_inr.toLocaleString("en-IN")}{" "}
              <span className="muted small">
                (₹{advice.min_inr.toLocaleString("en-IN")}–₹{advice.max_inr.toLocaleString("en-IN")})
              </span>
            </strong>
            <AgentBadge meta={advice.agent} />
          </div>
          <p className="small">{advice.message || advice.rationale}</p>
          <div className="row gap">
            {onApply && (
              <button type="button" className="btn btn-sm" onClick={() => onApply(advice.suggested_reward_inr)}>
                {applyLabel}
              </button>
            )}
            <button type="button" className="btn-link small" onClick={ask}>
              ↻ Ask again
            </button>
          </div>
          <p className="muted small">Saathi only suggests — you decide the final price.</p>
        </div>
      ) : (
        <button type="button" className="btn btn-ghost btn-sm" onClick={ask}>
          🤝 Ask Saathi for a fair reward
        </button>
      )}
      {error && <div className="alert alert-error">{error}</div>}
    </div>
  );
}

export function SupportChat({ kind, id }: { kind: "shipment" | "request"; id: number }) {
  const [history, setHistory] = useState<(ChatTurn & { meta?: SupportReply })[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [history, busy]);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const question = q.trim();
    if (!question) return;
    setQ("");
    const prior = history.map(({ role, content }) => ({ role, content }));
    setHistory((h) => [...h, { role: "user", content: question }]);
    setBusy(true);
    try {
      const r = await api<SupportReply>("/agents/support", {
        method: "POST",
        json: { kind, id, question, history: prior },
      });
      setHistory((h) => [...h, { role: "assistant", content: r.reply, meta: r }]);
    } catch (err) {
      setHistory((h) => [
        ...h,
        { role: "assistant", content: err instanceof ApiError ? err.message : "Support is unavailable right now." },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card saathi-card">
      <h3>📍 Ask Saathi about this order</h3>
      <div className="chat-log small-log">
        {history.length === 0 && (
          <p className="muted small">e.g. “Where is my parcel?”, “When will the traveller land?”, “Item arrived damaged”.</p>
        )}
        {history.map((t, i) => (
          <div key={i} className={`bubble ${t.role}`}>
            <p>{t.content}</p>
            {t.meta && (
              <>
                {t.meta.next_steps.length > 0 && (
                  <ul className="small">
                    {t.meta.next_steps.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                )}
                {t.meta.escalate && <div className="alert alert-warn small">🧑‍💼 Escalated to our support team.</div>}
                <AgentBadge meta={t.meta.agent} />
              </>
            )}
          </div>
        ))}
        {busy && <AgentThinking agents={["tracking_support"]} />}
        <div ref={end} />
      </div>
      <form className="row gap" onSubmit={send}>
        <input className="grow" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type your question…" />
        <button className="btn btn-sm" disabled={busy || !q.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
}

export function AgentActivity({ entityType, entityId, refreshKey }: { entityType: string; entityId: number; refreshKey?: unknown }) {
  const [rows, setRows] = useState<AgentRunRow[] | null>(null);
  useEffect(() => {
    api<AgentRunRow[]>(`/agents/activity?entity_type=${entityType}&entity_id=${entityId}`)
      .then(setRows)
      .catch(() => setRows([]));
  }, [entityType, entityId, refreshKey]);
  if (!rows?.length) return null;
  return (
    <div className="card">
      <h3>🤖 Saathi activity</h3>
      <ul className="activity">
        {rows.map((r) => (
          <li key={r.id}>
            <span>{AGENT_LABELS[r.agent]?.icon ?? "🤖"}</span>
            <div className="grow">
              <b>{AGENT_LABELS[r.agent]?.name ?? r.agent}</b> <span className="muted small">· {formatDate(r.created_at)}</span>
              <div className="small">{r.summary}</div>
            </div>
            {r.needs_human && <span className="badge badge-pending">{r.resolved ? "reviewed" : "human review"}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Mirrors backend `shipment_items`: the compliance token is bound to exactly these lines. */
export function shipmentItems(itemName: string, description: string | null | undefined): string[] {
  const lines = [itemName.trim()];
  for (const raw of (description ?? "").split(/\r?\n/)) {
    const line = raw.trim().replace(/^[-*•\s]+/, "").trim();
    if (line && line.toLowerCase() !== lines[0].toLowerCase()) lines.push(line.slice(0, 200));
  }
  return lines.slice(0, 20);
}

export function SaathiCta() {
  return (
    <Link to="/saathi" className="saathi-cta">
      <span>✨</span>
      <div>
        <b>Just tell Saathi what you need</b>
        <div className="small">“Send 2 kg laddoos to my son in Dubai before Diwali”</div>
      </div>
    </Link>
  );
}
