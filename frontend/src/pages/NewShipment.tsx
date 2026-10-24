import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, ApiError, formatINR, splitPrice } from "../api/client";
import type { ComplianceReport, SendDraft, Shipment } from "../api/types";
import { ErrorBox } from "../components/Layout";
import { AgentThinking, CompliancePanel } from "../components/Saathi";
import { useAuth, useCountries } from "../context/AuthContext";

type Compliance = { report: ComplianceReport; token: string | null };

export default function NewShipment() {
  const navigate = useNavigate();
  const location = useLocation();
  // Only filled when the user explicitly built a draft with Saathi chat / Dabbas.
  const prefill = (location.state as { draft?: SendDraft; compliance?: Compliance } | null) ?? {};
  const draft = prefill.draft?.kind === "send" ? prefill.draft : undefined;
  const { config } = useAuth();
  const { abroad } = useCountries();
  const [form, setForm] = useState({
    item_name: draft?.item_name ?? "",
    description: draft?.description ?? "",
    declared_value_inr: draft?.declared_value_inr ? String(Math.round(draft.declared_value_inr)) : "",
    pickup_city: draft?.pickup_city ?? "",
    destination_country: draft?.destination_country ?? "",
    destination_city: draft?.destination_city ?? "",
    needed_by: draft?.needed_by ?? "",
    recipient_name: draft?.recipient_name ?? "",
    recipient_phone: "",
    recipient_address: "",
  });
  const [blocked, setBlocked] = useState<ComplianceReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    if (k === "item_name" || k === "description" || k === "destination_country") setBlocked(null);
    setForm({ ...form, [k]: e.target.value });
  };

  const valuePaise = Math.max(0, Number(form.declared_value_inr || 0)) * 100;
  const { reward, fee, rewardPct, feePct } = splitPrice(valuePaise, config);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await api<Shipment>("/shipments", {
        method: "POST",
        json: {
          item_name: form.item_name,
          description: form.description || null,
          declared_value_inr: Number(form.declared_value_inr),
          pickup_city: form.pickup_city,
          destination_country: form.destination_country,
          destination_city: form.destination_city,
          needed_by: form.needed_by || null,
          category: draft?.category || null,
          weight_kg: draft?.weight_kg || null,
          recipient_name: form.recipient_name || null,
          recipient_phone: form.recipient_phone || null,
          recipient_address: form.recipient_address || null,
          compliance_token: prefill.compliance?.token ?? null,
        },
      });
      navigate(`/send/${s.id}`);
    } catch (err) {
      const detail = err instanceof ApiError ? (err.detail as { compliance?: ComplianceReport } | undefined) : undefined;
      if (detail && typeof detail === "object" && detail.compliance) setBlocked(detail.compliance);
      setError(err instanceof ApiError ? err.message : "Failed to post your parcel");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="detail">
      <form className="detail-main card form" onSubmit={submit}>
        <h1>Send something abroad</h1>
        <p className="muted">
          Post it once — everyone flying from India to that country sees it and can offer to carry it.
        </p>
        <label>
          What are you sending?
          <input required minLength={2} value={form.item_name} onChange={set("item_name")} placeholder="e.g. Silk saree" />
        </label>
        <div className="grid-2">
          <label>
            Product value (₹)
            <input required type="number" min={100} max={500000} value={form.declared_value_inr} onChange={set("declared_value_inr")} placeholder="e.g. 5000" />
          </label>
          <label>
            Needed by <span className="muted small">(optional)</span>
            <input type="date" value={form.needed_by} onChange={set("needed_by")} />
          </label>
        </div>
        <div className="grid-3">
          <label>
            From (city in India)
            <input required minLength={2} value={form.pickup_city} onChange={set("pickup_city")} placeholder="e.g. Pune" />
          </label>
          <label>
            To country
            <select required value={form.destination_country} onChange={set("destination_country")}>
              <option value="" disabled>
                Choose…
              </option>
              {abroad.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            To city
            <input required minLength={2} value={form.destination_city} onChange={set("destination_city")} placeholder="e.g. Dubai" />
          </label>
        </div>
        <label>
          Notes <span className="muted small">(optional)</span>
          <textarea rows={2} value={form.description} onChange={set("description")} placeholder="Anything the traveller should know" />
        </label>
        <details className="optional-block">
          <summary>Recipient details (optional — shared with the traveller only after you pay)</summary>
          <div className="grid-2">
            <label>
              Name
              <input value={form.recipient_name} onChange={set("recipient_name")} />
            </label>
            <label>
              Phone
              <input value={form.recipient_phone} onChange={set("recipient_phone")} placeholder="+971…" />
            </label>
          </div>
          <label>
            Address
            <textarea rows={2} value={form.recipient_address} onChange={set("recipient_address")} />
          </label>
        </details>
        {busy && <AgentThinking agents={["compliance"]} />}
        {blocked && <CompliancePanel report={blocked} />}
        <ErrorBox error={error} />
        <button className="btn btn-block" disabled={busy}>
          {busy ? "Saathi is checking customs rules…" : "Post parcel"}
        </button>
        <p className="muted small">
          No cash, gold, weapons, drugs, vapes or anything illegal. Saathi checks your item against customs rules when
          you post.
        </p>
      </form>

      <aside className="card summary">
        <h3>Price</h3>
        {valuePaise > 0 ? (
          <>
            <div>
              <span>Product value</span>
              <span>{formatINR(valuePaise)}</span>
            </div>
            <div>
              <span>Traveller earns ({rewardPct}%)</span>
              <span>{formatINR(reward)}</span>
            </div>
            <div>
              <span>{config?.app_name ?? "SaathiGo"} fee ({feePct}%)</span>
              <span>{formatINR(fee)}</span>
            </div>
            <div className="total">
              <span>You pay</span>
              <span>{formatINR(reward + fee)}</span>
            </div>
            <p className="muted small">You pay only after a traveller takes your parcel.</p>
          </>
        ) : (
          <p className="muted">
            Enter the product value. The traveller earns {rewardPct}% of it and {config?.app_name ?? "SaathiGo"} keeps{" "}
            {feePct}%.
          </p>
        )}
      </aside>
    </div>
  );
}
