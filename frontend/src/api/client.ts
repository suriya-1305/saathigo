const TOKEN_KEY = "tagalong_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message);
  }
}

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
    if (Array.isArray(detail)) {
      return detail
        .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`)
        .join("; ");
    }
  }
  return fallback;
}

export async function api<T>(path: string, options: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let body = options.body;
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.json);
  }
  const res = await fetch(`/api${path}`, { ...options, headers, body });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    if (res.status === 401 && token) tokenStore.clear();
    throw new ApiError(res.status, errorMessage(data, res.statusText), data?.detail);
  }
  return data as T;
}

export const formatINR = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
    paise / 100,
  );

export const flag = (code: string) =>
  code
    .toUpperCase()
    .replace(/./g, (c) => String.fromCodePoint(127397 + c.charCodeAt(0)));

export const formatDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—";

export async function startCheckout(purpose: "product_request" | "shipment", referenceId: number) {
  const res = await api<{ payment_id: number; redirect_url: string }>("/payments/checkout", {
    method: "POST",
    json: { purpose, reference_id: referenceId },
  });
  window.location.href = res.redirect_url;
}

/** Value-based pricing: traveller earns `reward` (20%) and SaathiGo keeps `fee` (2%) of the product value. */
export function splitPrice(valuePaise: number, cfg?: { traveller_reward_pct: number; platform_fee_pct: number } | null) {
  const reward = Math.round(valuePaise * (cfg?.traveller_reward_pct ?? 0.2));
  const fee = Math.round(valuePaise * (cfg?.platform_fee_pct ?? 0.02));
  return { reward, fee, rewardPct: Math.round((cfg?.traveller_reward_pct ?? 0.2) * 100), feePct: Math.round((cfg?.platform_fee_pct ?? 0.02) * 100) };
}