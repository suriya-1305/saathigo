import { useState } from "react";
import { Link } from "react-router-dom";
import { flag } from "../api/client";
import type { CountryGroup, Shipment } from "../api/types";
import { ShipmentCard } from "../components/Cards";
import { EmptyState, Spinner } from "../components/Layout";
import { useLiveList } from "../hooks/useLiveList";

export default function SendBrowse() {
  const { data: groups, error, reload } = useLiveList<CountryGroup<Shipment>[]>("/shipments/grouped");
  const [active, setActive] = useState("ALL");

  if (!groups)
    return error ? (
      <div className="alert alert-error row space-between">
        <span>{error}</span>
        <button className="btn btn-sm" onClick={reload}>
          Retry
        </button>
      </div>
    ) : (
      <Spinner />
    );
  const shown = active === "ALL" ? groups : groups.filter((g) => g.country === active);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Send to overseas</h1>
          <p className="muted">
            Parcels from families across India, waiting for a traveller — grouped by destination. Flying out of India?
            Tag one along and earn.
          </p>
        </div>
        <Link to="/send/new" className="btn">
          + Send something
        </Link>
      </div>
      {error && <div className="alert alert-warn small">{error}</div>}
      <div className="chips">
        <button className={active === "ALL" ? "chip active" : "chip"} onClick={() => setActive("ALL")}>
          All destinations
        </button>
        {groups.map((g) => (
          <button key={g.country} className={active === g.country ? "chip active" : "chip"} onClick={() => setActive(g.country)}>
            {flag(g.country)} {g.country_name} <span className="count">{g.count}</span>
          </button>
        ))}
      </div>
      {shown.length === 0 && (
        <EmptyState title="Nothing waiting to be sent">
          <Link to="/send/new">Send something to family abroad</Link>
        </EmptyState>
      )}
      {shown.map((g) => (
        <section key={g.country} className="country-group">
          <div className="row space-between wrap gap">
            <h2>
              {flag(g.country)} To {g.country_name} <span className="muted">({g.count})</span>
            </h2>
            <Link to={`/trips/new?to=${g.country}`} className="btn btn-sm btn-ghost">
              ✈ Flying to {g.country_name}? Carry these
            </Link>
          </div>
          <div className="cards">
            {g.items.map((s) => (
              <ShipmentCard key={s.id} s={s} />
            ))}
          </div>
          {g.count > g.items.length && (
            <p className="muted small">
              +{g.count - g.items.length} more — add your trip to {g.country_name} to see every parcel on your route.
            </p>
          )}
        </section>
      ))}
    </>
  );
}
