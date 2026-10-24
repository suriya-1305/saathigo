import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, formatINR } from "../api/client";
import type { ComplianceReport, CuratedDabba, Dabba } from "../api/types";
import { ErrorBox, Spinner } from "../components/Layout";
import { AgentBadge, AgentThinking, CompliancePanel, shipmentItems } from "../components/Saathi";
import { useAuth, useCountries } from "../context/AuthContext";

type Compliance = { report: ComplianceReport; token: string | null };

export default function Dabbas() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [dabbas, setDabbas] = useState<Dabba[] | null>(null);
  const [selected, setSelected] = useState<Dabba | null>(null);

  useEffect(() => {
    api<Dabba[]>("/agents/dabbas").then(setDabbas).catch(() => setDabbas([]));
  }, []);

  useEffect(() => {
    const id = window.location.hash.slice(1);
    if (id && dabbas) setSelected(dabbas.find((d) => d.id === id) ?? null);
  }, [dabbas]);

  if (!dabbas) return <Spinner />;
  const section = (kind: Dabba["kind"], title: string, sub: string) => (
    <section className="dabba-section">
      <h2>{title}</h2>
      <p className="muted">{sub}</p>
      <div className="cards">
        {dabbas
          .filter((d) => d.kind === kind)
          .map((d) => (
            <button
              key={d.id}
              className={`card dabba ${selected?.id === d.id ? "selected" : ""}`}
              onClick={() => (user ? setSelected(d) : navigate("/login", { state: { from: "/dabbas" } }))}
            >
              <div className="dabba-emoji">{d.emoji}</div>
              <h3>{d.name}</h3>
              <p className="muted small">{d.tagline}</p>
              <p className="small">Up to {d.max_weight_kg} kg · {d.candidates.length} curated items</p>
            </button>
          ))}
      </div>
    </section>
  );

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>🎁 Dabbas</h1>
          <p className="muted">
            Ready-made boxes. Saathi Dabba Curator fills the box for your destination and preferences, Saathi Compliance
            checks it for customs — then it becomes a normal order.
          </p>
        </div>
      </div>
      {selected && <CurateBox key={selected.id} dabba={selected} onClose={() => setSelected(null)} />}
      {section("swadeshi", "🇮🇳 Swadeshi Dabbas", "From India to your family abroad — carried by a traveller who earns 20% of its value.")}
      {section("videshi", "🌍 Videshi Dabbas", "Overseas favourites brought home to India by a traveller.")}
    </div>
  );
}

function CurateBox({ dabba, onClose }: { dabba: Dabba; onClose: () => void }) {
  const navigate = useNavigate();
  const { abroad } = useCountries();
  const [country, setCountry] = useState(dabba.kind === "swadeshi" ? "AE" : "US");
  const [neededBy, setNeededBy] = useState("");
  const [prefs, setPrefs] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CuratedDabba | null>(null);
  const [compliance, setCompliance] = useState<Compliance | "loading" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const curate = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    setCompliance(null);
    try {
      const r = await api<CuratedDabba>(`/agents/dabbas/${dabba.id}/curate`, {
        method: "POST",
        json: { country, needed_by: neededBy || null, preferences: prefs || null },
      });
      setResult(r);
      if (r.draft.kind === "send" && r.draft.item_name) {
        setCompliance("loading");
        const c = await api<Compliance>("/agents/compliance", {
          method: "POST",
          json: { items: shipmentItems(r.draft.item_name, r.draft.description), destination_country: country },
        });
        setCompliance(c);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not curate this dabba");
      setCompliance(null);
    } finally {
      setBusy(false);
    }
  };

  const proceed = () => {
    if (!result) return;
    navigate(result.draft.kind === "send" ? "/send/new" : "/buy/new", {
      state: { draft: result.draft, compliance: compliance && compliance !== "loading" ? compliance : undefined },
    });
  };
  const blocked = compliance && compliance !== "loading" && compliance.report.overall === "blocked";

  return (
    <div className="card curate">
      <div className="row space-between">
        <h2>
          {dabba.emoji} {dabba.name}
        </h2>
        <button className="btn-link" onClick={onClose}>
          ✕
        </button>
      </div>
      <div className="grid-3 form">
        <label>
          {dabba.kind === "swadeshi" ? "Send to" : "Bring from"}
          <select value={country} onChange={(e) => setCountry(e.target.value)}>
            {abroad.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Needed by
          <input type="date" value={neededBy} onChange={(e) => setNeededBy(e.target.value)} />
        </label>
        <label>
          Preferences
          <input value={prefs} onChange={(e) => setPrefs(e.target.value)} placeholder="no nuts, kids' sizes…" />
        </label>
      </div>
      <button className="btn" onClick={curate} disabled={busy}>
        {result ? "↻ Re-curate" : "🎁 Curate my dabba"}
      </button>
      <ErrorBox error={error} />
      {busy && !result && <AgentThinking agents={["dabba_curator"]} />}
      {result && (
        <div className="curated">
          <div className="row space-between wrap gap">
            <h3>Inside your box</h3>
            <AgentBadge meta={result.agent} />
          </div>
          <table className="table">
            <tbody>
              {result.box.items.map((i) => (
                <tr key={i.name}>
                  <td>
                    {i.quantity} × {i.name}
                  </td>
                  <td className="muted">{(i.approx_weight_kg * (i.quantity ?? 1)).toFixed(2)} kg</td>
                  <td>{formatINR(i.approx_value_inr * (i.quantity ?? 1) * 100)}</td>
                </tr>
              ))}
              <tr>
                <th>Total</th>
                <th>{result.box.total_weight_kg} kg</th>
                <th>{formatINR(result.box.total_value_inr * 100)}</th>
              </tr>
            </tbody>
          </table>
          {result.box.notes && <p className="small muted">{result.box.notes}</p>}
          {compliance === "loading" && <AgentThinking agents={["compliance"]} />}
          {compliance && compliance !== "loading" && <CompliancePanel report={compliance.report} />}
          <button className="btn btn-secondary" onClick={proceed} disabled={!!blocked || compliance === "loading"}>
            {result.draft.kind === "send" ? "Send this dabba →" : "Request this dabba →"}
          </button>
        </div>
      )}
    </div>
  );
}
