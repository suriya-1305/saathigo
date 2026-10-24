import { Link } from "react-router-dom";
import { flag, formatDate, formatINR } from "../api/client";
import type { ProductRequest, Shipment } from "../api/types";
import { StatusBadge } from "./Layout";

export function RequestCard({ r }: { r: ProductRequest }) {
  return (
    <Link to={`/buy/${r.id}`} className="card item-card">
      <div className="thumb">{r.image_url ? <img src={r.image_url} alt="" loading="lazy" /> : <span>🛍️</span>}</div>
      <div className="item-body">
        <div className="row space-between">
          <span className="muted small">
            {flag(r.source_country)} {r.store_name ?? r.source_country_name}
          </span>
          <StatusBadge status={r.status} />
        </div>
        <h4 className="clamp">{r.title}</h4>
        {r.is_buyer && <span className="badge badge-mine">Your request</span>}
        <p className="muted small">
          Deliver to {r.deliver_city}
          {r.needed_by ? ` · by ${formatDate(r.needed_by)}` : ""}
        </p>
        <div className="row space-between">
          <span>
            Price <strong>{formatINR(r.item_price_paise * r.quantity)}</strong>
          </span>
          <span className="reward">Reward {formatINR(r.reward_paise)}</span>
        </div>
      </div>
    </Link>
  );
}

const CATEGORY_ICON: Record<string, string> = {
  documents: "📄",
  clothing: "👕",
  food_sealed: "🥫",
  gifts: "🎁",
  books: "📚",
  electronics_small: "🔌",
  medicines_prescribed: "💊",
  other: "📦",
};

export function ShipmentCard({ s }: { s: Shipment }) {
  return (
    <Link to={`/send/${s.id}`} className="card item-card">
      <div className="thumb">
        <span>{CATEGORY_ICON[s.category] ?? "📦"}</span>
      </div>
      <div className="item-body">
        <div className="row space-between">
          <span className="muted small">
            {s.pickup_city} → {flag(s.destination_country)} {s.destination_city}
          </span>
          <StatusBadge status={s.status} />
        </div>
        <h4 className="clamp">{s.item_name}</h4>
        {s.is_sender && <span className="badge badge-mine">Your parcel</span>}
        <p className="muted small">
          Value {formatINR(s.declared_value_paise)}
          {s.needed_by ? ` · by ${formatDate(s.needed_by)}` : ""}
        </p>
        <div className="row space-between">
          <span className="muted small">{s.sender.name}</span>
          <span className="reward">Traveller earns {formatINR(s.traveller_payout_paise)}</span>
        </div>
      </div>
    </Link>
  );
}
