import { useState } from "react";
import { Link } from "react-router-dom";
import { flag } from "../api/client";
import type { CountryGroup, ProductRequest } from "../api/types";
import { RequestCard } from "../components/Cards";
import { EmptyState, Spinner } from "../components/Layout";
import { useLiveList } from "../hooks/useLiveList";

export default function BuyBrowse() {
  const { data: groups, error, reload } = useLiveList<CountryGroup<ProductRequest>[]>("/requests/grouped");
  const [active, setActive] = useState<string>("ALL");

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
          <h1>Buy from overseas</h1>
          <p className="muted">Open requests grouped by the country they need to be bought in.</p>
        </div>
        <Link to="/buy/new" className="btn">
          + New request
        </Link>
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
              <RequestCard key={r.id} r={r} />
            ))}
          </div>
        </section>
      ))}
    </>
  );
}
