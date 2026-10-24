import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, flag, formatDate, formatINR, startCheckout } from "../api/client";
import type { ProductRequest } from "../api/types";
import { ErrorBox, Spinner, StatusBadge, Steps } from "../components/Layout";
import { PhotoCapture } from "../components/PhotoCapture";
import { AgentActivity, SupportChat, TravellerMatches } from "../components/Saathi";
import { useAuth } from "../context/AuthContext";

const FLOW = ["open", "accepted", "paid", "purchased", "delivered"];
const FLOW_LABELS = ["Offers", "Accepted", "Paid (escrow)", "Purchased", "Delivered"];

export default function RequestDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [req, setReq] = useState<ProductRequest | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => api<ProductRequest>(`/requests/${id}`).then(setReq), [id]);
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed");
    }
  };

  if (!req) return error ? <ErrorBox error={error} /> : <Spinner />;
  const step = FLOW.indexOf(req.status);

  return (
    <div className="detail">
      <div className="detail-main">
        <div className="card">
          <div className="row gap-lg wrap">
            <div className="thumb thumb-lg">{req.image_url ? <img src={req.image_url} alt="" /> : <span>🛍️</span>}</div>
            <div className="grow">
              <div className="row space-between">
                <span className="muted">
                  {flag(req.source_country)} Buy in {req.source_country_name}
                </span>
                <StatusBadge status={req.status} />
              </div>
              <h1>{req.title}</h1>
              <a href={req.product_url} target="_blank" rel="noreferrer noopener" className="small">
                View on {req.store_name ?? "store"} ↗
              </a>
              {req.description && <p>{req.description}</p>}
              <p className="muted small">
                Qty {req.quantity} · {req.price_currency} {req.price_amount} each · Deliver to {req.deliver_city}
                {req.needed_by && ` · Needed by ${formatDate(req.needed_by)}`} · Requested by {req.buyer.name}
              </p>
            </div>
          </div>
          {req.status !== "cancelled" && <Steps steps={FLOW_LABELS} current={step} />}
        </div>

        <ErrorBox error={error} />

        {req.is_buyer && <BuyerPanel req={req} run={run} />}
        {req.is_buyer && req.status === "open" && <TravellerMatches path={`/agents/requests/${req.id}/travellers`} />}
        {req.is_traveller && <TravellerPanel req={req} run={run} />}
        {!req.is_buyer && !req.is_traveller && req.status === "open" &&
          (user ? (
            <OfferForm req={req} run={run} />
          ) : (
            <div className="card">
              <Link to="/login" state={{ from: `/buy/${req.id}` }}>
                Log in
              </Link>{" "}
              to make an offer.
            </div>
          ))}
        {(req.is_buyer || req.is_traveller) && (
          <>
            <SupportChat kind="request" id={req.id} />
            <AgentActivity entityType="request" entityId={req.id} refreshKey={req.status} />
          </>
        )}
      </div>

      <aside className="card summary">
        <h3>Price breakdown</h3>
        <div>
          <span>Product</span>
          <span>{formatINR(req.item_price_paise * req.quantity)}</span>
        </div>
        <div>
          <span>Traveller earns (20%)</span>
          <span>{formatINR(req.reward_paise)}</span>
        </div>
        <div>
          <span>SaathiGo fee (2%)</span>
          <span>{formatINR(req.service_fee_paise)}</span>
        </div>
        <div className="total">
          <span>Buyer pays</span>
          <span>{formatINR(req.total_paise)}</span>
        </div>
        {req.traveller && <p className="muted small">Traveller: {req.traveller.name}</p>}
      </aside>
    </div>
  );
}

type Run = (fn: () => Promise<unknown>) => Promise<void>;

function BuyerPanel({ req, run }: { req: ProductRequest; run: Run }) {
  return (
    <div className="card">
      {req.status === "open" && (
        <>
          <h3>Offers ({req.offers?.length ?? 0})</h3>
          {!req.offers?.length && <p className="muted">Waiting for travellers from {req.source_country_name}…</p>}
          {req.offers?.map((o) => (
            <div key={o.id} className="offer">
              <div>
                <strong>{o.traveller.name}</strong>
                <p className="muted small">
                  {o.trip.origin_city} → {o.trip.destination_city} on {formatDate(o.trip.travel_date)}
                  {o.expected_delivery && ` · delivers by ${formatDate(o.expected_delivery)}`}
                </p>
                {o.message && <p className="small">“{o.message}”</p>}
              </div>
              <div className="right">
                <div className="reward">{formatINR(o.reward_paise)}</div>
                {o.status === "pending" ? (
                  <button className="btn btn-sm" onClick={() => run(() => api(`/requests/${req.id}/offers/${o.id}/accept`, { method: "POST" }))}>
                    Accept
                  </button>
                ) : (
                  <StatusBadge status={o.status} />
                )}
              </div>
            </div>
          ))}
        </>
      )}
      {req.status === "accepted" && (
        <>
          <h3>Pay to confirm</h3>
          <p className="muted">
            {req.traveller?.name} will buy your item once paid. Your money is held in escrow until you receive it.
          </p>
          <button className="btn btn-lg" onClick={() => run(() => startCheckout("product_request", req.id))}>
            Pay {formatINR(req.total_paise)} with Pine Labs
          </button>
        </>
      )}
      {(req.status === "paid" || req.status === "purchased") && (
        <>
          <h3>Your delivery OTP</h3>
          <div className="otp">{req.delivery_otp}</div>
          <p className="muted small">Share this only when you have the item in hand. It releases payment to the traveller.</p>
        </>
      )}
      {req.purchase_photo_url && (
        <>
          <h4>Purchase proof from traveller</h4>
          <img src={req.purchase_photo_url} alt="Purchased item" className="proof" />
        </>
      )}
      {req.status === "delivered" && <p className="alert alert-ok">Delivered. Enjoy your purchase!</p>}
      {(req.status === "open" || req.status === "accepted") && (
        <button className="btn-link danger" onClick={() => confirm("Cancel this request?") && run(() => api(`/requests/${req.id}/cancel`, { method: "POST" }))}>
          Cancel request
        </button>
      )}
    </div>
  );
}

function TravellerPanel({ req, run }: { req: ProductRequest; run: Run }) {
  const [otp, setOtp] = useState("");
  return (
    <div className="card">
      <h3>You're delivering this</h3>
      {req.status === "accepted" && <p className="muted">Waiting for the buyer to pay. Don't buy the item yet.</p>}
      {req.status === "paid" && (
        <PhotoCapture
          label="Bought it? Upload a photo of the item / receipt"
          submitLabel="Mark as purchased"
          onSubmit={(file) => {
            const form = new FormData();
            form.append("photo", file);
            return run(() => api(`/requests/${req.id}/purchased`, { method: "POST", body: form }));
          }}
        />
      )}
      {req.status === "purchased" && (
        <>
          {req.purchase_photo_url && <img src={req.purchase_photo_url} alt="Purchased item" className="proof" />}
          <label className="field-label">Hand over the item and enter the buyer's OTP</label>
          <div className="row gap">
            <input value={otp} onChange={(e) => setOtp(e.target.value)} maxLength={6} placeholder="6-digit OTP" />
            <button
              className="btn"
              disabled={otp.length < 4}
              onClick={() => {
                const form = new FormData();
                form.append("otp", otp);
                return run(() => api(`/requests/${req.id}/deliver`, { method: "POST", body: form }));
              }}
            >
              Confirm delivery
            </button>
          </div>
        </>
      )}
      {req.status === "delivered" && (
        <p className="alert alert-ok">
          Delivered! {formatINR(req.item_price_paise * req.quantity + req.reward_paise)} is on its way to you.
        </p>
      )}
    </div>
  );
}

function OfferForm({ req, run }: { req: ProductRequest; run: Run }) {
  const [date, setDate] = useState("");
  const [message, setMessage] = useState("");

  const mine = req.offers?.find((o) => o.status === "pending");
  if (mine)
    return (
      <div className="card">
        <h3>You offered to bring this for {formatINR(mine.reward_paise)}</h3>
        <p className="muted">Waiting for {req.buyer.name} to accept.</p>
        <button className="btn btn-ghost" onClick={() => run(() => api(`/requests/${req.id}/offers/${mine.id}/withdraw`, { method: "POST" }))}>
          Withdraw offer
        </button>
      </div>
    );

  return (
    <div className="card form">
      <h3>
        Travelling from {req.source_country_name} to India? Earn {formatINR(req.reward_paise)}
      </h3>
      <p className="muted small">
        Once {req.buyer.name} accepts and pays, buy the item, bring it to {req.deliver_city} and get the product cost
        plus your reward when they confirm with their OTP.
      </p>
      <div className="grid-2">
        <label>
          When are you flying? <span className="muted small">(optional)</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label>
          Message <span className="muted small">(optional)</span>
          <input value={message} onChange={(e) => setMessage(e.target.value)} />
        </label>
      </div>
      <button
        className="btn btn-lg"
        onClick={() =>
          run(() =>
            api(`/requests/${req.id}/offers`, {
              method: "POST",
              json: { travel_date: date || null, message: message || null },
            }),
          )
        }
      >
        I can bring this
      </button>
    </div>
  );
}