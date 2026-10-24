import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError, flag, formatDate } from "../api/client";
import type { BoardingPassScan, Trip } from "../api/types";
import { BoardingPassScanner } from "../components/BoardingPassScanner";
import { EmptyState, ErrorBox, Spinner, StatusBadge } from "../components/Layout";
import { useAuth, useCountries } from "../context/AuthContext";

export function Trips() {
  const { config } = useAuth();
  const bp = Boolean(config?.boarding_pass_enabled);
  const [trips, setTrips] = useState<Trip[] | null>(null);
  const [params, setParams] = useSearchParams();
  const verifyId = (bp && Number(params.get("verify"))) || null;
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<Trip[]>("/trips/mine").then(setTrips), []);
  useEffect(() => {
    load();
  }, [load]);

  const onScanned = async (scan: BoardingPassScan) => {
    if (!verifyId || !scan.scan_token) return;
    try {
      await api(`/trips/${verifyId}/verify`, { method: "POST", json: { scan_token: scan.scan_token } });
      setParams({});
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Verification failed");
    }
  };

  if (!trips) return <Spinner />;
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Your trips</h1>
          <p className="muted">Travelling to or from India? Carry items and earn 20% of their value.</p>
        </div>
        <Link to="/trips/new" className="btn">
          + Add trip
        </Link>
      </div>
      {verifyId && (
        <div className="narrow">
          <p>Scan the boarding pass for trip #{verifyId} to verify it.</p>
          <BoardingPassScanner onScanned={onScanned} />
          <ErrorBox error={error} />
        </div>
      )}
      {trips.length === 0 && (
        <EmptyState title="No trips yet">
          <Link to="/trips/new">Add your first trip</Link>
        </EmptyState>
      )}
      <div className="cards">
        {trips.map((t) => (
          <div key={t.id} className="card trip">
            <div className="row space-between">
              <StatusBadge status={t.status} />
              {bp && (t.verified ? <span className="badge badge-paid">✔ Verified</span> : <span className="badge badge-pending">Unverified</span>)}
            </div>
            <h3>
              {flag(t.origin_country)} {t.origin_city} → {flag(t.destination_country)} {t.destination_city}
            </h3>
            <p className="muted small">
              {formatDate(t.travel_date)} {t.flight_number && `· ${t.flight_number}`} · {t.capacity_kg} kg spare
            </p>
            <div className="row gap wrap">
              {t.status === "active" && (
                <Link to={`/trips/${t.id}/matches`} className="btn btn-sm">
                  See matching items
                </Link>
              )}
              {bp && !t.verified && t.status === "active" && (
                <button className="btn btn-sm btn-ghost" onClick={() => setParams({ verify: String(t.id) })}>
                  Verify with boarding pass
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

export function NewTrip() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { countries } = useCountries();
  const { config } = useAuth();
  const bp = Boolean(config?.boarding_pass_enabled);
  const [scan, setScan] = useState<BoardingPassScan | null>(null);
  const toCountry = params.get("to");
  const fromCountry = params.get("from");
  const returnTo = params.get("return");
  const [form, setForm] = useState({
    origin_city: "",
    origin_country: fromCountry || (toCountry ? "IN" : ""),
    destination_city: params.get("city") ?? "",
    destination_country: toCountry || (fromCountry ? "IN" : ""),
    travel_date: "",
    flight_number: "",
    capacity_kg: "",
    notes: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const onScanned = (s: BoardingPassScan) => {
    setScan(s);
    if (s.origin_city && s.destination_city) {
      setForm((f) => ({
        ...f,
        origin_city: s.origin_city!,
        origin_country: s.origin_country!,
        destination_city: s.destination_city!,
        destination_country: s.destination_country!,
        travel_date: s.travel_date ?? f.travel_date,
        flight_number: s.flight_number ?? f.flight_number,
      }));
    }
  };
  // Route from a scan is locked so the verified trip matches the boarding pass.
  const locked = Boolean(scan?.scan_token);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const trip = await api<Trip>("/trips", {
        method: "POST",
        json: {
          ...form,
          capacity_kg: Number(form.capacity_kg || 5),
          flight_number: form.flight_number || null,
          notes: form.notes || null,
          scan_token: scan?.scan_token ?? null,
        },
      });
      navigate(returnTo?.startsWith("/") && !returnTo.startsWith("//") ? returnTo : `/trips/${trip.id}/matches`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save trip");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="narrow">
      <h1>Add a trip</h1>
      {bp && (
        <>
          <BoardingPassScanner onScanned={onScanned} />
          <p className="muted small center">No boarding pass yet? Add the trip manually and verify it later.</p>
        </>
      )}
      {!bp && <p className="muted">Tell us where you're flying — you'll see every parcel and product request on your route.</p>}
      <form className="card form" onSubmit={submit}>
        <div className="grid-2">
          <label>
            From city
            <input required disabled={locked} value={form.origin_city} onChange={set("origin_city")} placeholder="e.g. Mumbai" />
          </label>
          <label>
            From country
            <select required disabled={locked} value={form.origin_country} onChange={set("origin_country")}>
              <option value="" disabled>
                Choose…
              </option>
              {countries.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            To city
            <input required disabled={locked} value={form.destination_city} onChange={set("destination_city")} placeholder="e.g. Dubai" />
          </label>
          <label>
            To country
            <select required disabled={locked} value={form.destination_country} onChange={set("destination_country")}>
              <option value="" disabled>
                Choose…
              </option>
              {countries.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Travel date
            <input required type="date" value={form.travel_date} onChange={set("travel_date")} />
          </label>
          <label>
            Flight number <span className="muted small">(optional)</span>
            <input value={form.flight_number} onChange={set("flight_number")} placeholder="EK 512" />
          </label>
          <label>
            Spare luggage (kg) <span className="muted small">(optional)</span>
            <input type="number" min="0.5" max="40" step="0.5" value={form.capacity_kg} onChange={set("capacity_kg")} placeholder="5" />
          </label>
        </div>
        <label>
          Notes <span className="muted small">(optional)</span>
          <textarea rows={2} value={form.notes} onChange={set("notes")} placeholder="Happy to carry small electronics, no liquids" />
        </label>
        <ErrorBox error={error} />
        <button className="btn btn-block" disabled={busy}>
          {busy ? "Saving…" : bp && scan?.verified ? "Save verified trip" : "Save trip"}
        </button>
      </form>
    </div>
  );
}
