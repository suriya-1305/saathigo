import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, formatDate, formatINR } from "../api/client";
import type { Payout, ProductRequest, Shipment } from "../api/types";
import { RequestCard, ShipmentCard } from "../components/Cards";
import { ErrorBox, Spinner, StatusBadge } from "../components/Layout";
import { useAuth } from "../context/AuthContext";

const TABS = ["My requests", "My shipments", "Deliveries", "Earnings", "Profile"] as const;
type Tab = (typeof TABS)[number];

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("My requests");
  return (
    <>
      <h1>Dashboard</h1>
      <div className="chips">
        {TABS.map((t) => (
          <button key={t} className={t === tab ? "chip active" : "chip"} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      {tab === "My requests" && <ListOf<ProductRequest> path="/requests/mine" empty="/buy/new" render={(r) => <RequestCard key={r.id} r={r} />} />}
      {tab === "My shipments" && <ListOf<Shipment> path="/shipments/mine" empty="/send/new" render={(s) => <ShipmentCard key={s.id} s={s} />} />}
      {tab === "Deliveries" && (
        <>
          <h3>Products you're bringing</h3>
          <ListOf<ProductRequest> path="/requests/deliveries" render={(r) => <RequestCard key={r.id} r={r} />} />
          <h3>Items you're carrying abroad</h3>
          <ListOf<Shipment> path="/shipments/carrying" render={(s) => <ShipmentCard key={s.id} s={s} />} />
        </>
      )}
      {tab === "Earnings" && <Earnings />}
      {tab === "Profile" && <Profile />}
    </>
  );
}

function ListOf<T>({ path, render, empty }: { path: string; render: (item: T) => React.ReactNode; empty?: string }) {
  const [items, setItems] = useState<T[] | null>(null);
  useEffect(() => {
    api<T[]>(path).then(setItems);
  }, [path]);
  if (!items) return <Spinner />;
  if (!items.length)
    return (
      <p className="muted">
        Nothing here yet. {empty && <Link to={empty}>Create one →</Link>}
      </p>
    );
  return <div className="cards">{items.map(render)}</div>;
}

function Earnings() {
  const [payouts, setPayouts] = useState<Payout[] | null>(null);
  useEffect(() => {
    api<Payout[]>("/payouts/mine").then(setPayouts);
  }, []);
  if (!payouts) return <Spinner />;
  const total = payouts.reduce((a, p) => a + p.amount_paise, 0);
  return (
    <div className="card">
      <h3>Total earned: {formatINR(total)}</h3>
      <table className="table">
        <thead>
          <tr>
            <th>Date</th>
            <th>For</th>
            <th>Amount</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {payouts.map((p) => (
            <tr key={p.id}>
              <td>{formatDate(p.created_at)}</td>
              <td>
                <Link to={p.purpose === "shipment" ? `/send/${p.reference_id}` : `/buy/${p.reference_id}`}>
                  {p.purpose === "shipment" ? "Shipment" : "Order"} #{p.reference_id}
                </Link>
              </td>
              <td>{formatINR(p.amount_paise)}</td>
              <td>
                <StatusBadge status={p.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">Payouts are settled to your UPI ID (set it in Profile).</p>
    </div>
  );
}

function Profile() {
  const { user, refreshUser } = useAuth();
  const [form, setForm] = useState({ name: user?.name ?? "", phone: user?.phone ?? "", city: user?.city ?? "", upi_id: user?.upi_id ?? "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      className="card form narrow"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        try {
          await api("/auth/me", { method: "PATCH", json: form });
          await refreshUser();
          setMsg("Saved");
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Failed");
        }
      }}
    >
      {(["name", "phone", "city", "upi_id"] as const).map((k) => (
        <label key={k}>
          {k === "upi_id" ? "UPI ID (for payouts)" : k[0].toUpperCase() + k.slice(1)}
          <input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
        </label>
      ))}
      <ErrorBox error={error} />
      {msg && <div className="alert alert-ok">{msg}</div>}
      <button className="btn">Save</button>
    </form>
  );
}
