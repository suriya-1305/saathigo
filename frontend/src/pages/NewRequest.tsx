import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, ApiError, formatINR, splitPrice } from "../api/client";
import type { BuyDraft, LinkPreview, ProductRequest } from "../api/types";
import { ErrorBox } from "../components/Layout";
import { useAuth, useCountries } from "../context/AuthContext";

export default function NewRequest() {
  const navigate = useNavigate();
  const location = useLocation();
  const stateDraft = (location.state as { draft?: BuyDraft } | null)?.draft;
  const draft = stateDraft?.kind === "buy" ? stateDraft : undefined;
  const { config } = useAuth();
  const { abroad } = useCountries();
  const [url, setUrl] = useState(draft?.product_url ?? "");
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    title: draft?.title ?? "",
    description: draft?.description ?? "",
    image_url: "",
    store_name: "",
    quantity: draft?.quantity ? String(draft.quantity) : "",
    price_amount: draft?.price_amount ? String(draft.price_amount) : "",
    price_currency:
      draft?.price_currency && config?.currencies.includes(draft.price_currency) ? draft.price_currency : "",
    source_country: draft?.source_country ?? "",
    deliver_city: draft?.deliver_city ?? "",
    needed_by: draft?.needed_by ?? "",
  });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const fetchPreview = async () => {
    setFetching(true);
    setError(null);
    try {
      const p = await api<LinkPreview>(`/requests/preview?url=${encodeURIComponent(url)}`);
      setForm((f) => ({
        ...f,
        title: p.title ?? f.title,
        description: p.description ?? f.description,
        image_url: p.image_url ?? f.image_url,
        store_name: p.store_name ?? f.store_name,
        price_amount: p.price ? String(p.price) : f.price_amount,
        price_currency: p.currency && config?.currencies.includes(p.currency) ? p.currency : f.price_currency,
        source_country: p.source_country ?? f.source_country,
      }));
      if (!p.title) setError("Couldn't read all details from that page — please fill them in.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not fetch the link");
    } finally {
      setFetching(false);
    }
  };

  const rate = config?.fx_to_inr[form.price_currency] ?? 0;
  const itemsPaise = Math.round(Number(form.price_amount || 0) * rate * 100) * Math.max(1, Number(form.quantity || 1));
  const { reward: rewardPaise, fee: feePaise, rewardPct, feePct } = splitPrice(itemsPaise, config);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api<ProductRequest>("/requests", {
        method: "POST",
        json: {
          ...form,
          product_url: url,
          image_url: form.image_url || null,
          description: form.description || null,
          store_name: form.store_name || null,
          needed_by: form.needed_by || null,
          price_amount: Number(form.price_amount),
          quantity: Number(form.quantity || 1),
        },
      });
      navigate(`/buy/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create request");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="narrow">
      <h1>Request a product from abroad</h1>
      <div className="card">
        <label className="field-label">Product link</label>
        <div className="row gap">
          <input
            className="grow"
            type="url"
            placeholder="https://www.amazon.ae/…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <button type="button" className="btn" disabled={!url || fetching} onClick={fetchPreview}>
            {fetching ? "Fetching…" : "Fetch details"}
          </button>
        </div>
      </div>

      <form className="card form" onSubmit={submit}>
        {form.image_url && <img src={form.image_url} alt="" className="preview-img" />}
        <label>
          Product name
          <input required value={form.title} onChange={set("title")} placeholder="e.g. Apple AirPods Pro" />
        </label>
        <label>
          Notes for traveller <span className="muted small">(size, colour, variant)</span>
          <textarea rows={2} value={form.description} onChange={set("description")} placeholder="Optional" />
        </label>
        <div className="grid-3">
          <label>
            Buy in country
            <select required value={form.source_country} onChange={set("source_country")}>
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
            Price
            <input required type="number" min="0.01" step="0.01" value={form.price_amount} onChange={set("price_amount")} placeholder="e.g. 249" />
          </label>
          <label>
            Currency
            <select required value={form.price_currency} onChange={set("price_currency")}>
              <option value="" disabled>
                Choose…
              </option>
              {config?.currencies.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="grid-2">
          <label>
            Quantity
            <input type="number" min={1} max={10} value={form.quantity} onChange={set("quantity")} placeholder="1" />
          </label>
          <label>
            Needed by <span className="muted small">(optional)</span>
            <input type="date" value={form.needed_by} onChange={set("needed_by")} />
          </label>
        </div>
        <label>
          Deliver to (city in India)
          <input required value={form.deliver_city} onChange={set("deliver_city")} placeholder="e.g. Bengaluru" />
        </label>
        <div className="summary">
          <div>
            <span>Product (≈ INR)</span>
            <span>{formatINR(itemsPaise)}</span>
          </div>
          <div>
            <span>Traveller earns ({rewardPct}%)</span>
            <span>{formatINR(rewardPaise)}</span>
          </div>
          <div>
            <span>{config?.app_name ?? "SaathiGo"} fee ({feePct}%)</span>
            <span>{formatINR(feePaise)}</span>
          </div>
          <div className="total">
            <span>You pay</span>
            <span>{formatINR(itemsPaise + rewardPaise + feePaise)}</span>
          </div>
          <p className="muted small">You pay only after you accept a traveller's offer. Funds stay in escrow until delivery.</p>
        </div>
        <ErrorBox error={error} />
        <button className="btn btn-block" disabled={busy || !url}>
          {busy ? "Posting…" : "Post request"}
        </button>
      </form>
    </div>
  );
}
