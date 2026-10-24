import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, formatDate } from "../api/client";
import type { AgentRunRow } from "../api/types";
import { EmptyState, ErrorBox, Spinner } from "../components/Layout";
import { AGENT_LABELS } from "../components/Saathi";

const LINKS: Record<string, (id: number) => string> = {
  shipment: (id) => `/send/${id}`,
  request: (id) => `/buy/${id}`,
  trip: (id) => `/trips/${id}/matches`,
};

/** Human-in-the-loop queue: agent escalations and low-confidence decisions a person must confirm. */
export default function ReviewQueue() {
  const [rows, setRows] = useState<AgentRunRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<AgentRunRow[]>("/agents/review-queue")
      .then(setRows)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load queue"));
  }, []);

  const resolve = async (id: number) => {
    try {
      await api(`/agents/review-queue/${id}/resolve`, { method: "POST" });
      setRows((r) => r?.filter((x) => x.id !== id) ?? null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not resolve");
    }
  };

  if (error) return <ErrorBox error={error} />;
  if (!rows) return <Spinner />;
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>🧑‍⚖️ Saathi review queue</h1>
          <p className="muted">Agent decisions flagged for a human: escalations and low-confidence calls.</p>
        </div>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="Nothing waiting for review" />
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Decision</th>
                <th>Source</th>
                <th>Order</th>
                <th>When</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>
                    {AGENT_LABELS[r.agent]?.icon} {AGENT_LABELS[r.agent]?.name ?? r.agent}
                  </td>
                  <td>{r.summary}</td>
                  <td className="small muted">
                    {r.source}
                    {r.confidence != null && ` · ${Math.round(r.confidence * 100)}%`}
                  </td>
                  <td>
                    {r.entity_type && r.entity_id && LINKS[r.entity_type] ? (
                      <Link to={LINKS[r.entity_type](r.entity_id)}>
                        {r.entity_type} #{r.entity_id}
                      </Link>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="small">{formatDate(r.created_at)}</td>
                  <td>
                    <button className="btn btn-sm" onClick={() => resolve(r.id)}>
                      Mark reviewed
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
