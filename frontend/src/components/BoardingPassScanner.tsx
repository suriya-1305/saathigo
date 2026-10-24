import { useRef, useState } from "react";
import { api, ApiError, formatDate } from "../api/client";
import type { BoardingPassScan } from "../api/types";

/** Uploads a boarding pass for in-memory OCR. The server discards the file immediately. */
export function BoardingPassScanner({ onScanned }: { onScanned: (scan: BoardingPassScan) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scan, setScan] = useState<BoardingPassScan | null>(null);

  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await api<BoardingPassScan>("/trips/scan-boarding-pass", { method: "POST", body: form });
      setScan(res);
      onScanned(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Scan failed");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  return (
    <div className="scanner card">
      <div className="row space-between">
        <div>
          <h3>Scan boarding pass</h3>
          <p className="muted small">
            Photo or PDF. We read the route &amp; flight, check authenticity, then delete the file instantly — it's
            never saved.
          </p>
        </div>
        <span className="shield">🔒</span>
      </div>
      <input
        ref={input}
        type="file"
        accept="image/*,application/pdf"
        capture="environment"
        hidden
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
      />
      <button type="button" className="btn btn-block" disabled={busy} onClick={() => input.current?.click()}>
        {busy ? "Reading boarding pass…" : scan ? "Scan again" : "📷 Scan / upload boarding pass"}
      </button>
      {error && <div className="alert alert-error">{error}</div>}
      {scan && (
        <div className={`scan-result ${scan.verified ? "ok" : "warn"}`}>
          <p>
            <strong>{scan.message}</strong>
          </p>
          {scan.origin_code && scan.destination_code && (
            <p className="route">
              {scan.origin_city} ({scan.origin_code}) → {scan.destination_city} ({scan.destination_code})
            </p>
          )}
          <p className="muted small">
            Flight {scan.flight_number ?? "—"} · {formatDate(scan.travel_date)} · Authenticity score {scan.score}/100
          </p>
          <ul className="checks">
            {scan.checks.map((c) => (
              <li key={c.label} className={c.ok ? "ok" : "no"}>
                {c.ok ? "✔" : "✖"} {c.label}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
