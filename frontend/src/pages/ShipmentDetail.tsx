import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, flag, formatDate, formatINR, startCheckout } from "../api/client";
import type { Shipment } from "../api/types";
import { ErrorBox, Spinner, StatusBadge, Steps } from "../components/Layout";
import { PhotoCapture } from "../components/PhotoCapture";
import { AgentActivity, CompliancePanel, SupportChat, TravellerMatches } from "../components/Saathi";
import { useAuth } from "../context/AuthContext";

const FLOW = ["open", "matched", "paid", "in_transit", "delivered"];
const FLOW_LABELS = ["Finding traveller", "Matched", "Paid (escrow)", "Handed over", "Delivered"];

type Run = (fn: () => Promise<unknown>) => Promise<void>;

export default function ShipmentDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [s, setS] = useState<Shipment | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => api<Shipment>(`/shipments/${id}`).then(setS), [id]);
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);

  const run: Run = async (fn) => {
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed");
    }
  };

  if (!s) return error ? <ErrorBox error={error} /> : <Spinner />;

  return (
    <div className="detail">
      <div className="detail-main">
        <div className="card">
          <div className="row space-between">
            <span className="muted">
              {s.pickup_city} → {flag(s.destination_country)} {s.destination_city}, {s.destination_country_name}
            </span>
            <StatusBadge status={s.status} />
          </div>
          <h1>{s.item_name}</h1>
          {s.description && <p>{s.description}</p>}
          <p className="muted small">
            Value {formatINR(s.declared_value_paise)}
            {s.weight_kg > 0 && ` · ${s.weight_kg} kg`}
            {s.needed_by && ` · needed by ${formatDate(s.needed_by)}`} · Sender {s.sender.name}
          </p>
          {s.status !== "cancelled" && <Steps steps={FLOW_LABELS} current={FLOW.indexOf(s.status)} />}
        </div>
        {s.compliance_report && (
          <div className="card">
            <h3>🛃 Customs check</h3>
            <CompliancePanel report={s.compliance_report} compact={!s.is_sender && !s.is_traveller} />
          </div>
        )}
        <ErrorBox error={error} />

        {s.recipient_name && (
          <div className="card">
            <h3>Recipient</h3>
            <p>
              {s.recipient_name} · {s.recipient_phone}
              <br />
              <span className="muted">{s.recipient_address}</span>
            </p>
          </div>
        )}

        {s.is_sender && <SenderPanel s={s} run={run} />}
        {s.is_sender && s.status === "open" && (
          <TravellerMatches path={`/agents/shipments/${s.id}/travellers`} />
        )}
        {s.is_traveller && <TravellerPanel s={s} run={run} />}
        {!s.is_sender && !s.is_traveller && s.status === "open" &&
          (user ? (
            <AcceptPanel s={s} run={run} />
          ) : (
            <div className="card">
              <Link to="/login" state={{ from: `/send/${s.id}` }}>Log in</Link> to carry this item.
            </div>
          ))}

        {(s.handover_photo_url || s.delivery_photo_url) && (
          <div className="card">
            <h3>Photo proof</h3>
            <div className="row gap wrap">
              {s.handover_photo_url && (
                <figure>
                  <img src={s.handover_photo_url} alt="At handover" className="proof" />
                  <figcaption className="muted small">At handover · {formatDate(s.handover_at)}</figcaption>
                </figure>
              )}
              {s.delivery_photo_url && (
                <figure>
                  <img src={s.delivery_photo_url} alt="At delivery" className="proof" />
                  <figcaption className="muted small">At delivery · {formatDate(s.delivered_at)}</figcaption>
                </figure>
              )}
            </div>
          </div>
        )}
        {(s.is_sender || s.is_traveller) && (
          <>
            <SupportChat kind="shipment" id={s.id} />
            <AgentActivity entityType="shipment" entityId={s.id} refreshKey={s.status} />
          </>
        )}
      </div>

      <aside className="card summary">
        <h3>Price</h3>
        <div>
          <span>Product value</span>
          <span>{formatINR(s.declared_value_paise)}</span>
        </div>
        <div className="total">
          <span>Sender pays</span>
          <span>{formatINR(s.price_paise)}</span>
        </div>
        <div>
          <span>Traveller earns</span>
          <span>{formatINR(s.traveller_payout_paise)}</span>
        </div>
        <div>
          <span>SaathiGo fee</span>
          <span>{formatINR(s.platform_fee_paise ?? s.price_paise - s.traveller_payout_paise)}</span>
        </div>
        {s.trip && (
          <p className="muted small">
            {s.traveller?.name} travels on {formatDate(s.trip.travel_date)}
            {s.trip.flight_number && ` · flight ${s.trip.flight_number}`}
          </p>
        )}
      </aside>
    </div>
  );
}

function SenderPanel({ s, run }: { s: Shipment; run: Run }) {
  return (
    <div className="card">
      {s.status === "open" && <p className="muted">Everyone travelling from India to {s.destination_country_name} can see this and offer to carry it.</p>}
      {s.status === "matched" && (
        <>
          <h3>{s.traveller?.name} can carry this!</h3>
          <p className="muted">Pay to confirm. The traveller is paid only after your recipient confirms delivery.</p>
          <div className="row gap wrap">
            <button className="btn btn-lg" onClick={() => run(() => startCheckout("shipment", s.id))}>
              Pay {formatINR(s.price_paise)} with Pine Labs
            </button>
            <button className="btn btn-ghost" onClick={() => run(() => api(`/shipments/${s.id}/release`, { method: "POST" }))}>
              Decline traveller
            </button>
          </div>
        </>
      )}
      {(s.status === "paid" || s.status === "in_transit") && (
        <>
          <h3>Delivery OTP for your recipient</h3>
          <div className="otp">{s.delivery_otp}</div>
          <p className="muted small">
            Share this with {s.recipient_name || "your recipient"}. They give it to the traveller on receiving the item.
            {s.status === "paid" && " Hand the item to the traveller — they'll photograph it as proof."}
          </p>
        </>
      )}
      {s.status === "delivered" && <p className="alert alert-ok">Delivered{s.recipient_name ? ` to ${s.recipient_name}` : ""}. 🎉</p>}
      {(s.status === "open" || s.status === "matched") && (
        <button className="btn-link danger" onClick={() => confirm("Cancel this shipment?") && run(() => api(`/shipments/${s.id}/cancel`, { method: "POST" }))}>
          Cancel shipment
        </button>
      )}
    </div>
  );
}

function TravellerPanel({ s, run }: { s: Shipment; run: Run }) {
  const [otp, setOtp] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  return (
    <div className="card">
      <h3>You're carrying this</h3>
      {s.status === "matched" && (
        <>
          <p className="muted">Waiting for the sender to pay. Don't collect the item yet.</p>
          <button className="btn btn-ghost" onClick={() => run(() => api(`/shipments/${s.id}/release`, { method: "POST" }))}>
            Back out
          </button>
        </>
      )}
      {s.status === "paid" && (
        <PhotoCapture
          label="Collecting the item? Inspect it and take a clear photo"
          hint="Open the package and check the contents. Don't carry anything you're not comfortable with."
          submitLabel="Confirm handover"
          onSubmit={(file) => {
            const form = new FormData();
            form.append("photo", file);
            return run(() => api(`/shipments/${s.id}/handover`, { method: "POST", body: form }));
          }}
        />
      )}
      {s.status === "in_transit" && (
        <div className="form">
          <label>
            Recipient's OTP
            <input value={otp} onChange={(e) => setOtp(e.target.value)} maxLength={6} placeholder="6-digit OTP" />
          </label>
          <label>
            Delivery photo (optional)
            <input type="file" accept="image/*" capture="environment" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
          </label>
          <button
            className="btn"
            disabled={otp.length < 4}
            onClick={() => {
              const form = new FormData();
              form.append("otp", otp);
              if (photo) form.append("photo", photo);
              return run(() => api(`/shipments/${s.id}/deliver`, { method: "POST", body: form }));
            }}
          >
            Confirm delivery
          </button>
        </div>
      )}
      {s.status === "delivered" && <p className="alert alert-ok">Delivered! {formatINR(s.traveller_payout_paise)} is on its way to you.</p>}
    </div>
  );
}

function AcceptPanel({ s, run }: { s: Shipment; run: Run }) {
  const [date, setDate] = useState("");
  return (
    <div className="card form">
      <h3>
        Travelling from India to {s.destination_country_name}? Earn {formatINR(s.traveller_payout_paise)}
      </h3>
      <p className="muted small">
        Take this parcel, wait for {s.sender.name} to pay, collect it in {s.pickup_city} and deliver it in{" "}
        {s.destination_city}. You get paid when the recipient confirms with their OTP.
      </p>
      <label>
        When are you flying? <span className="muted small">(optional)</span>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </label>
      <button
        className="btn btn-lg"
        onClick={() => run(() => api(`/shipments/${s.id}/accept`, { method: "POST", json: { travel_date: date || null } }))}
      >
        I'll carry this
      </button>
    </div>
  );
}