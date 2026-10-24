export interface User {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  city: string | null;
  upi_id: string | null;
  current_country?: string | null;
  is_admin?: boolean;
}

export interface PublicUser {
  id: number;
  name: string;
  city: string | null;
}

export interface Country {
  code: string;
  name: string;
  currency: string;
  zone: string;
}

export interface AppConfig {
  app_name: string;
  countries: Country[];
  currencies: string[];
  fx_to_inr: Record<string, number>;
  shipment_categories: string[];
  traveller_reward_pct: number;
  platform_fee_pct: number;
  boarding_pass_enabled: boolean;
  payment_provider: string;
}

export interface Trip {
  id: number;
  origin_code: string | null;
  origin_city: string;
  origin_country: string;
  destination_code: string | null;
  destination_city: string;
  destination_country: string;
  travel_date: string;
  flight_number: string | null;
  capacity_kg: number;
  notes: string | null;
  status: string;
  verified: boolean;
  verification_score: number;
  created_at: string;
}

export interface BoardingPassScan {
  origin_code: string | null;
  origin_city: string | null;
  origin_country: string | null;
  destination_code: string | null;
  destination_city: string | null;
  destination_country: string | null;
  flight_number: string | null;
  travel_date: string | null;
  passenger_name: string | null;
  score: number;
  verified: boolean;
  checks: { label: string; ok: boolean }[];
  scan_token: string | null;
  message: string;
}

export interface Offer {
  id: number;
  request_id: number;
  traveller: PublicUser;
  trip: Trip;
  reward_paise: number;
  expected_delivery: string | null;
  message: string | null;
  status: string;
  created_at: string;
}

export interface ProductRequest {
  id: number;
  product_url: string;
  title: string;
  description: string | null;
  image_url: string | null;
  store_name: string | null;
  quantity: number;
  price_amount: number;
  price_currency: string;
  item_price_paise: number;
  reward_paise: number;
  service_fee_paise: number;
  total_paise: number;
  source_country: string;
  source_country_name: string;
  deliver_city: string;
  needed_by: string | null;
  status: string;
  buyer: PublicUser;
  traveller: PublicUser | null;
  offers_count: number;
  created_at: string;
  offers: Offer[] | null;
  delivery_otp: string | null;
  purchase_photo_url: string | null;
  is_buyer: boolean;
  is_traveller: boolean;
}

export interface LinkPreview {
  url: string;
  title: string | null;
  description: string | null;
  image_url: string | null;
  price: number | null;
  currency: string | null;
  store_name: string | null;
  source_country: string | null;
}

export interface CountryGroup<T> {
  country: string;
  country_name: string;
  count: number;
  items: T[];
}

export interface Shipment {
  id: number;
  item_name: string;
  description: string | null;
  category: string;
  weight_kg: number;
  length_cm: number;
  width_cm: number;
  height_cm: number;
  declared_value_paise: number;
  pickup_city: string;
  destination_country: string;
  destination_country_name: string;
  destination_city: string;
  needed_by: string | null;
  shipping_provider: string;
  courier_estimate_paise: number;
  price_paise: number;
  traveller_payout_paise: number;
  status: string;
  sender: PublicUser;
  traveller: PublicUser | null;
  trip: Trip | null;
  handover_photo_url: string | null;
  handover_at: string | null;
  delivery_photo_url: string | null;
  delivered_at: string | null;
  created_at: string;
  compliance_status: ComplianceOverall | null;
  compliance_report: ComplianceReport | null;
  recipient_name: string | null;
  recipient_phone: string | null;
  recipient_address: string | null;
  delivery_otp: string | null;
  platform_fee_paise: number | null;
  is_sender: boolean;
  is_traveller: boolean;
}

export interface Payment {
  id: number;
  purpose: "product_request" | "shipment";
  reference_id: number;
  amount_paise: number;
  currency: string;
  provider: string;
  status: string;
  provider_order_id: string | null;
  created_at: string;
}

export interface Payout {
  id: number;
  purpose: string;
  reference_id: number;
  amount_paise: number;
  status: string;
  created_at: string;
}

// ---------------------------------------------------------------- Saathi agents (AgenticOrg)

export type AgentName =
  | "concierge"
  | "intake"
  | "dabba_curator"
  | "compliance"
  | "matching"
  | "negotiation"
  | "tracking_support";

export interface AgentMeta {
  agent: AgentName;
  source: "agenticorg" | "fallback";
  confidence: number | null;
  needs_human: boolean;
  note: string | null;
  latency_ms: number;
}

export type ComplianceStatus = "clear" | "needs_label_check" | "not_allowed";
export type ComplianceOverall = "clear" | "needs_review" | "blocked";

export interface ComplianceReport {
  route: string;
  items: { item: string; status: ComplianceStatus; reason: string; packing_note: string }[];
  overall: ComplianceOverall;
  guidance: string;
  next_step: string;
  meta?: AgentMeta;
}

export interface DraftItem {
  name: string;
  quantity: number;
  unit: string;
  approx_weight_kg: number | null;
  approx_value_inr: number | null;
}

export interface SendDraft {
  kind: "send";
  items?: DraftItem[];
  item_name?: string | null;
  description?: string | null;
  category?: string | null;
  pickup_city?: string | null;
  destination_country?: string | null;
  destination_city?: string | null;
  needed_by?: string | null;
  weight_kg?: number | null;
  declared_value_inr?: number | null;
  recipient_name?: string | null;
  missing_fields?: string[];
}

export interface BuyDraft {
  kind: "buy";
  product_url?: string | null;
  title?: string | null;
  description?: string | null;
  quantity?: number;
  source_country?: string | null;
  deliver_city?: string | null;
  needed_by?: string | null;
  price_amount?: number | null;
  price_currency?: string | null;
  missing_fields?: string[];
}

export type OrderDraft = SendDraft | BuyDraft;

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  reply: string;
  intent: string;
  draft: OrderDraft | null;
  estimate: { value_paise: number; price_paise: number; traveller_payout_paise: number; platform_fee_paise: number } | null;
  agents: AgentMeta[];
}

export interface DabbaItem {
  name: string;
  unit: string;
  approx_weight_kg: number;
  approx_value_inr: number;
  quantity?: number;
}

export interface Dabba {
  id: string;
  kind: "swadeshi" | "videshi";
  emoji: string;
  name: string;
  tagline: string;
  category: string;
  max_weight_kg: number;
  candidates: DabbaItem[];
}

export interface CuratedDabba {
  box: {
    dabba_id: string;
    name: string;
    kind: "swadeshi" | "videshi";
    items: DabbaItem[];
    notes: string;
    total_weight_kg: number;
    total_value_inr: number;
  };
  draft: OrderDraft;
  agent: AgentMeta;
}

export interface RankedTraveller {
  id: number;
  score: number;
  reason: string;
  flagged?: boolean;
  trip: {
    id: number;
    origin_city: string;
    destination_city: string;
    travel_date: string;
    flight_number: string | null;
    capacity_kg: number;
    verification_score: number;
  };
  traveller: { id: number; name: string; city: string | null; completed_deliveries: number };
}

export interface RankedOpportunity {
  score: number;
  reason: string;
  flagged?: boolean;
  kind: "request" | "shipment";
  id: number;
  title: string;
  reward_inr: number;
}

export interface RewardAdvice {
  suggested_reward_inr: number;
  min_inr: number;
  max_inr: number;
  rationale: string;
  message: string;
  offer_assessments: { offer_id: number; verdict: "fair" | "high" | "low"; note: string }[];
  agent: AgentMeta;
}

export interface SupportReply {
  reply: string;
  escalate: boolean;
  next_steps: string[];
  agent: AgentMeta;
}

export interface AgentRunRow {
  id: number;
  agent: AgentName;
  source: string;
  status: string;
  confidence: number | null;
  needs_human: boolean;
  resolved: boolean;
  summary: string;
  created_at: string;
  entity_type: string | null;
  entity_id: number | null;
}

export interface AssistantReply {
  reply: string;
  escalate: boolean;
  links: { ref: string; label: string; path: string }[];
  agent: AgentMeta;
}