import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, formatDate } from "../api/client";
import type { AgentMeta, ProductRequest, RankedOpportunity, Shipment, Trip } from "../api/types";
import { RequestCard, ShipmentCard } from "../components/Cards";
import { EmptyState, ErrorBox, Spinner } from "../components/Layout";
import { AgentBadge, AgentThinking } from "../components/Saathi";

function SaathiPicks({ tripId }: { tripId: number }) {
  const [res, setRes] = useState<{ ranked: RankedOpportunity[]; agent: AgentMeta } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = async () => {
    setBusy(true);
    setError(null);
    try {
      setRes(await api(`/agents/trips/${tripId}/opportunities`));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Saathi Matching is unavailable");
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="card saathi-card">
      <div className="row space-between wrap gap">
        <h2>🧭 Saathi picks for this trip</h2>
        {res ? <AgentBadge meta={res.agent} /> : !busy && (
          <button className="btn btn-sm" onClick={load}>
            Rank the best orders for me
          </button>
        )}
      </div>
      {busy && <AgentThinking agents={["matching"]} />}
      <ErrorBox error={error} />
      {res && (
        <ol className="ranked">
          {res.ranked.map((o) => (
            <li key={`${o.kind}-${o.id}`} className={o.flagged ? "flagged" : ""}>
              <span className="score">{o.score}</span>
              <div className="grow">
                <Link to={o.kind === "request" ? `/buy/${o.id}` : `/send/${o.id}`}>
                  <strong>{o.title}</strong>
                </Link>{" "}
                <span className="muted small">
                  {o.kind === "request" ? "buy request" : "parcel"} · earn ₹{o.reward_inr.toLocaleString("en-IN")}
                </span>
                <p className="small muted">{o.reason}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

interface Matches {
  trip: Trip;
  requests: ProductRequest[];
  shipments: Shipment[];
}

export default function TripMatches() {
  const { id } = useParams();
  const [m, setM] = useState<Matches | null>(null);
  useEffect(() => {
    api<Matches>(`/trips/${id}/matches`).then(setM);
  }, [id]);
  if (!m) return <Spinner />;
  const { trip } = m;
  return (
    <>
      <div className="page-head">
        <div>
          <h1>
            {trip.origin_city} → {trip.destination_city}
          </h1>
          <p className="muted">
            {formatDate(trip.travel_date)} · {trip.capacity_kg} kg spare
          </p>
        </div>
      </div>
      {(m.requests.length > 0 || m.shipments.length > 0) && <SaathiPicks tripId={trip.id} />}
      {trip.destination_country === "IN" && (
        <section className="country-group">
          <h2>Products to buy in {trip.origin_city} ({m.requests.length})</h2>
          {m.requests.length ? (
            <div className="cards">{m.requests.map((r) => <RequestCard key={r.id} r={r} />)}</div>
          ) : (
            <EmptyState title="No open requests from this country yet" />
          )}
        </section>
      )}
      {trip.origin_country === "IN" && (
        <section className="country-group">
          <h2>Items to carry to {trip.destination_city} ({m.shipments.length})</h2>
          {m.shipments.length ? (
            <div className="cards">{m.shipments.map((s) => <ShipmentCard key={s.id} s={s} />)}</div>
          ) : (
            <EmptyState title="No items waiting for this destination yet" />
          )}
        </section>
      )}
    </>
  );
}
