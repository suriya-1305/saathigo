import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError, flag, formatINR } from "../api/client";
import type { BuyDraft, ChatResponse, ChatTurn, ComplianceReport, OrderDraft, SendDraft } from "../api/types";
import { AgentBadge, AgentThinking, CompliancePanel, shipmentItems } from "../components/Saathi";
import { useCountries } from "../context/AuthContext";

type Compliance = { report: ComplianceReport; token: string | null };
type Msg = ChatTurn & { res?: ChatResponse; compliance?: Compliance | "loading" };

const KEY = "saathi_chat";
const EXAMPLES = [
  "Send 1 kg homemade laddoos and 2 kurtas to my son in Dubai from Pune before 5 Nov",
  "I want a Sony WH-1000XM5 from the US delivered to Bengaluru",
  "Make a Diwali dabba for my parents in London",
  "Where is my parcel?",
];
const FIELD_LABELS: Record<string, string> = {
  item_name: "what you're sending",
  pickup_city: "pickup city in India",
  destination_country: "destination country",
  destination_city: "destination city",
  weight_kg: "approx. weight",
  product_url: "product link",
  title: "product name",
  source_country: "country to buy from",
  deliver_city: "your city in India",
};

export default function SaathiPage() {
  const navigate = useNavigate();
  const { name: countryLabel } = useCountries();
  const [msgs, setMsgs] = useState<Msg[]>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(KEY) ?? "[]");
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    sessionStorage.setItem(KEY, JSON.stringify(msgs.map((m) => (m.compliance === "loading" ? { ...m, compliance: undefined } : m))));
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, busy]);

  const patchLast = (patch: Partial<Msg>) =>
    setMsgs((all) => all.map((m, i) => (i === all.length - 1 ? { ...m, ...patch } : m)));

  const runCompliance = async (d: SendDraft) => {
    if (!d.item_name || !d.destination_country) return;
    patchLast({ compliance: "loading" });
    try {
      const c = await api<Compliance>("/agents/compliance", {
        method: "POST",
        json: { items: shipmentItems(d.item_name, d.description), destination_country: d.destination_country },
      });
      patchLast({ compliance: c });
    } catch {
      patchLast({ compliance: undefined });
    }
  };

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    const history = msgs.map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { role: "user", content: message }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api<ChatResponse>("/agents/chat", { method: "POST", json: { message, history } });
      setMsgs((m) => [...m, { role: "assistant", content: res.reply, res }]);
      if (res.draft?.kind === "send") await runCompliance(res.draft);
    } catch (e) {
      setMsgs((m) => [
        ...m,
        { role: "assistant", content: e instanceof ApiError ? e.message : "Sorry, Saathi is unavailable right now." },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(input);
  };

  const proceed = (draft: OrderDraft, compliance?: Compliance) =>
    navigate(draft.kind === "send" ? "/send/new" : "/buy/new", { state: { draft, compliance } });

  const lastDraftIdx = msgs.map((m) => !!m.res?.draft).lastIndexOf(true);

  return (
    <div className="saathi-page">
      <div className="page-head">
        <div>
          <h1>✨ Saathi</h1>
          <p className="muted">
            Your travel-delivery helper. Tell it what you want to send or buy — a team of agents drafts the order,
            checks customs rules and finds travellers. You confirm every step.
          </p>
        </div>
        {msgs.length > 0 && (
          <button className="btn-link" onClick={() => setMsgs([])}>
            Start over
          </button>
        )}
      </div>

      <div className="card chat">
        <div className="chat-log">
          {msgs.length === 0 && (
            <div className="chat-empty">
              <p>Try one of these:</p>
              <div className="chips">
                {EXAMPLES.map((e) => (
                  <button key={e} className="chip" onClick={() => send(e)}>
                    {e}
                  </button>
                ))}
              </div>
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              <p>{m.content}</p>
              {m.res && (
                <>
                  <div className="row gap wrap">
                    {m.res.agents.map((a) => (
                      <AgentBadge key={a.agent} meta={a} />
                    ))}
                  </div>
                  <IntentAction intent={m.res.intent} hasDraft={!!m.res.draft} />
                  {m.res.draft && (
                    <DraftCard
                      draft={m.res.draft}
                      estimate={m.res.estimate}
                      countryName={countryLabel}
                      compliance={m.compliance}
                      stale={i !== lastDraftIdx}
                      onProceed={() => proceed(m.res!.draft!, m.compliance === "loading" ? undefined : m.compliance)}
                    />
                  )}
                </>
              )}
            </div>
          ))}
          {busy && <AgentThinking agents={["concierge", "intake", "compliance"]} />}
          <div ref={end} />
        </div>
        <form className="chat-input" onSubmit={submit}>
          <input
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. Send a silk saree to my sister in Singapore by 12 Nov"
          />
          <button className="btn" disabled={busy || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

function IntentAction({ intent, hasDraft }: { intent: string; hasDraft: boolean }) {
  if (hasDraft) return null;
  const links: Record<string, [string, string]> = {
    dabba: ["/dabbas", "🎁 Browse ready-made dabbas"],
    track_order: ["/dashboard", "📍 Open my orders"],
    traveller: ["/trips/new", "✈ Add & verify my trip"],
  };
  const l = links[intent];
  return l ? (
    <Link to={l[0]} className="btn btn-sm btn-ghost intent-link">
      {l[1]}
    </Link>
  ) : null;
}

function DraftCard({
  draft,
  estimate,
  countryName,
  compliance,
  stale,
  onProceed,
}: {
  draft: OrderDraft;
  estimate: ChatResponse["estimate"];
  countryName: (c: string) => string;
  compliance?: Compliance | "loading";
  stale: boolean;
  onProceed: () => void;
}) {
  const missing = (draft.missing_fields ?? []).map((f) => FIELD_LABELS[f] ?? f);
  const blocked = compliance && compliance !== "loading" && compliance.report.overall === "blocked";
  return (
    <div className={`draft-card ${stale ? "stale" : ""}`}>
      <div className="row space-between">
        <strong>📝 {draft.kind === "send" ? "Parcel draft" : "Buy request draft"}</strong>
        {stale && <span className="muted small">superseded</span>}
      </div>
      {draft.kind === "send" ? <SendSummary d={draft} countryName={countryName} /> : <BuySummary d={draft} countryName={countryName} />}
      {estimate && (
        <div className="draft-price">
          Value {formatINR(estimate.value_paise)} · Traveller earns {formatINR(estimate.traveller_payout_paise)} · You pay{" "}
          <b>{formatINR(estimate.price_paise)}</b>
        </div>
      )}
      {missing.length > 0 && <p className="small muted">Still need: {missing.join(", ")} — tell me, or fill it in on the next step.</p>}
      {compliance === "loading" && <AgentThinking agents={["compliance"]} />}
      {compliance && compliance !== "loading" && <CompliancePanel report={compliance.report} compact />}
      {!stale && (
        <button className="btn btn-sm" onClick={onProceed} disabled={!!blocked || compliance === "loading"}>
          {blocked ? "Remove blocked items first" : "Review & confirm →"}
        </button>
      )}
    </div>
  );
}

function SendSummary({ d, countryName }: { d: SendDraft; countryName: (c: string) => string }) {
  return (
    <dl className="draft-fields">
      <dt>Items</dt>
      <dd>
        {d.items?.length
          ? d.items
              .map((i) => (/^(items?|pieces?|pcs?|nos?|units?|count)?$/i.test(i.unit ?? "") ? `${i.quantity} ${i.name}` : `${i.quantity} ${i.unit} ${i.name}`))
              .join(", ")
          : d.item_name || "—"}
      </dd>
      <dt>Route</dt>
      <dd>
        {d.pickup_city || "?"} → {d.destination_city || "?"}
        {d.destination_country ? `, ${flag(d.destination_country)} ${countryName(d.destination_country)}` : ""}
      </dd>
      <dt>Weight</dt>
      <dd>{d.weight_kg ? `${d.weight_kg} kg` : "—"}</dd>
      <dt>Needed by</dt>
      <dd>{d.needed_by || "—"}</dd>
      {d.recipient_name && (
        <>
          <dt>For</dt>
          <dd>{d.recipient_name}</dd>
        </>
      )}
    </dl>
  );
}

function BuySummary({ d, countryName }: { d: BuyDraft; countryName: (c: string) => string }) {
  return (
    <dl className="draft-fields">
      <dt>Product</dt>
      <dd>{d.title || "—"}</dd>
      <dt>Buy in</dt>
      <dd>{d.source_country ? `${flag(d.source_country)} ${countryName(d.source_country)}` : "—"}</dd>
      <dt>Deliver to</dt>
      <dd>{d.deliver_city || "—"}</dd>
      <dt>Link</dt>
      <dd className="clamp">{d.product_url || "—"}</dd>
      <dt>Needed by</dt>
      <dd>{d.needed_by || "—"}</dd>
    </dl>
  );
}
