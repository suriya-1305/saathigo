import { useState } from "react";
import { Link } from "react-router-dom";
import { flag } from "../api/client";
import type { CountryGroup, ProductRequest } from "../api/types";
import { RequestCard } from "../components/Cards";
import { EmptyState, Spinner } from "../components/Layout";
import { useLiveList } from "../hooks/useLiveList";
import { useCountries, useMyLocation } from "../context/AuthContext";

export default function BuyBrowse() {
  const { data: groups, error, reload } = useLiveList<CountryGroup<ProductRequest>[]>("/requests/grouped");
  const [active, setActive] = useState<string>("ALL");
  const { location, setLocation } = useMyLocation();
  const { countries, name } = useCountries();

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
  const ordered = [...groups].sort((a, b) => Number(b.country === location) - Number(a.country === location));
  const shown = active === "ALL" ? ordered : ordered.filter((g) => g.country === active);
  const here = groups.find((g) => g.country === location);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Buy from overseas</h1>
          <p className="muted">Open requests grouped by the country they need to be bought in.</p>
        </div>
        <Link to="/buy/new" className="btn">
          + New request
        </Link>
      </div>

      <div className="card row wrap gap">
        <label className="row gap">
          📍 You're in
          <select value={location} onChange={(e) => setLocation(e.target.value)}>
            {countries.map((c) => (
              <option key={c.code} value={c.code}>
                {flag(c.code)} {c.name}
              </option>
            ))}
          </select>
        </label>
        <span className="muted small">
          {location === "IN"
            ? "You can buy any product below - a traveller will bring it to you."
            : here
              ? `You're in ${name(location)} - you can buy & bring ${here.count} request(s) and earn the 20% reward.`
              : `No open requests from ${name(location)} yet. You can still buy items from other countries.`}
        </span>
      </div>

      <div className="chips">
        <button className={active === "ALL" ? "chip active" : "chip"} onClick={() => setActive("ALL")}>
          All countries
        </button>
        {groups.map((g) => (
          <button
            key={g.country}
            className={active === g.country ? "chip active" : "chip"}
            onClick={() => setActive(g.country)}
          >
            {flag(g.country)} {g.country_name} <span className="count">{g.count}</span>
          </button>
        ))}
      </div>

      {shown.length === 0 && (
        <EmptyState title="No open requests yet">
          <Link to="/buy/new">Be the first to request a product</Link>
        </EmptyState>
      )}

      {shown.map((g) => (
        <section key={g.country} className="country-group">
          <div className="row space-between wrap gap">
            <h2>
              {flag(g.country)} From {g.country_name} <span className="muted">({g.count})</span>
            </h2>
            <Link to={`/trips/new?from=${g.country}`} className="btn btn-sm btn-ghost">
              ✈ Flying from {g.country_name}? Bring these
            </Link>
          </div>
          <div className="cards">
            {g.items.map((r) => (
              <RequestCard key={r.id} r={r} location={location} />
            ))}
          </div>
        </section>
      ))}
    </>
  );
}
