# SaathiGo — peer-to-peer cross-border delivery for India

Two modules:

| Module | Who | Flow |
|---|---|---|
| **Buy from overseas** | Buyer in India | Paste product link → details auto-filled → request listed under its **source country** → anyone travelling from that country to India offers with one click (reward fixed at **20% of product value**) → buyer accepts & pays (escrow) → traveller buys, uploads receipt/photo → hands over in India → buyer shares **delivery OTP** → payout released |
| **Send to overseas** | Sender in India | Enter what it is, its **value**, from/to → listed for everyone travelling from India to that country → any traveller takes it with one click (traveller earns **20%** of the value, SaathiGo keeps **2%**) → sender pays (escrow) → at handover traveller **photographs the item** (authenticity) → recipient shares OTP on delivery → payout released |

**Pricing:** based on the product value only — traveller earns TRAVELLER_REWARD_PCT (20%), SaathiGo keeps PLATFORM_FEE_PCT (2%). Send: sender pays 22% of value. Buy: buyer pays product + 20% + 2%.

**No trip setup needed:** when a traveller takes a parcel or offers on a request, a trip on that route is reused or created automatically (optional travel date).

**Ask Saathi popup:** the ✨ button on every page answers questions about your orders and the marketplace (POST /api/agents/assistant, Tracking & Support agent with rule-based fallback) and links straight to the order.

**Boarding-pass verification (disabled by default):** set BOARDING_PASS_ENABLED=true to turn it back on. Passes are processed **in memory only** (BCBP barcode text + OCR), a SHA-256 fingerprint blocks reuse and the file is never stored; when enabled only verified trips can make offers / accept parcels.

## Structure

```
backend/                 FastAPI + SQLAlchemy
  app/api/routes/        auth, meta, trips, requests, shipments, payments, agents (Saathi)
  app/services/          boarding_pass, link_preview, pricing, escrow, storage
  app/services/agents/   AgenticOrg client + Saathi orchestration (7 agents, fallbacks)
  app/data/dabbas.py     Swadeshi / Videshi dabba catalogue
  app/services/shipping/ rate_card (built-in), shiprocket (stub) – pluggable
  app/services/payments/ pinelabs (Plural API), mock – pluggable
  app/models/            entities (money stored in paise), agent_runs audit
  tests/                 unit + end-to-end flow tests
frontend/                React 19 + Vite + TypeScript
  src/pages/             Home, Saathi (chat), Dabbas, Buy*, Send*, Trips, Dashboard, ReviewQueue …
  src/components/        Layout, Saathi (agent UI), BoardingPassScanner, PhotoCapture, Cards
```

## Run locally

Backend (Python 3.11+):
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # then edit SECRET_KEY etc.
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
.\.venv\Scripts\python -m app.seed    # demo accounts, parcels, requests & trips (idempotent)
.\.venv\Scripts\python -m pytest -q   # tests
```

Demo accounts (password `secret123`): senders/buyers `priya@`, `rahul@`, `meera@`, `anita@example.com`; travellers `karan@`, `neha@`, `arjun@`, `sana@example.com`.
API docs: http://localhost:8000/docs

Frontend:
```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

### Boarding-pass OCR (only when `BOARDING_PASS_ENABLED=true`)
PDF boarding passes with text work out of the box. For photos/screenshots install Tesseract:
`winget install UB-Mannheim.TesseractOCR` and set `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` in `backend/.env`. Without it, image scans return HTTP 503.

## Pine Labs (Plural) payments

By default `PAYMENT_PROVIDER=mock` shows a local fake checkout page. To go live in `backend/.env`:
```
PAYMENT_PROVIDER=pinelabs
PINELABS_ENV=uat            # or prod
PINELABS_CLIENT_ID=...
PINELABS_CLIENT_SECRET=...
PINELABS_MERCHANT_ID=...
PINELABS_WEBHOOK_SECRET=...
BACKEND_URL=https://<public-backend-host>   # Pine Labs must reach the callback
FRONTEND_URL=https://<frontend-host>
```
- Checkout: hosted checkout (`/api/checkout/v1/orders`), user is redirected to Pine Labs.
- Callback: `/api/payments/callback` — never trusts query params; re-fetches order status from Pine Labs.
- Webhook: register `https://<backend>/api/payments/pinelabs/webhook` in the Pine Labs dashboard (HMAC-SHA256 verified).
- Refunds: `PineLabsProvider.refund()` is implemented (used on cancellation of paid orders by ops).
- Verify the `purchase_details.customer` field names against your merchant's API docs.

## Saathi agents (Pine Labs AgenticOrg) — agent-driven flow

Every order is driven by seven AgenticOrg agents. Each agent receives **platform-verified data** plus a strict JSON
contract, its output is normalised and validated, and a **deterministic rule-based fallback** runs if the agent
is unreachable or refuses. **A person always confirms** the final step (create order, accept price, mark reviewed).

| Agent | Where it runs | What it does |
|---|---|---|
| 🙏 Concierge | `/saathi` chat | Understands the message, detects intent (send / buy / dabba / track / travel), replies |
| 📝 Intake | `/saathi` chat (in parallel with Concierge) | Turns the message into a draft order (items, route, date, weight) → prefilled form |
| 🎁 Dabba Curator | `/dabbas` | Fills a Swadeshi (India → abroad) or Videshi (abroad → India) box **only** from the catalogue, within the weight cap |
| 🛃 Compliance | Chat draft, dabba, **New shipment (gate)** | Per item: clear / needs label check / not allowed. `blocked` → shipment rejected (422); `needs_review` → sender must acknowledge. Hard-rule regex overrides a model "clear" for prohibited items |
| 🧭 Matching | Shipment & request detail (owner), Trip matches (traveller) | Ranks verified, eligible travellers / orders. Platform filters decide eligibility; agent exclusions stay visible as *flagged* |
| 🤝 Negotiation | New request, offer form, offers list | Suggests a fair reward grounded on the platform pricing formula, assesses pending offers (fair / high / low) |
| 📍 Tracking & Support | Shipment & request detail (parties) | Answers from the live order record; damage / loss / refund keywords force escalation to a human |

- Endpoints: `backend/app/api/routes/agents.py` (`/api/agents/*`); orchestration & prompts: `app/services/agents/saathi.py`; HTTP client: `app/services/agents/client.py`.
- Every call is logged in the `agent_runs` table (source, confidence, latency, run id) and shown as **Saathi activity** on the order.
- `status: hitl_triggered` from AgenticOrg (low confidence) and every escalation land in the **human review queue** at `/review` — visible to users listed in `ADMIN_EMAILS`.
- Compliance results are bound to the exact item list with a short-lived signed token, so the shipment form can't reuse a check for different items.
- Config (`backend/.env`): `AGENTICORG_API_KEY`, `AGENTICORG_BASE_URL`, `AGENT_*_ID`. `AGENT_PROVIDER=mock` forces the rule-based fallbacks (used by the tests). Keep the API key out of git.
- No migrations yet: after pulling schema changes, delete `backend/tagalong.db` (dev SQLite) so tables are recreated.

## Business rules (configurable in `.env`)
- `TRAVELLER_REWARD_PCT=0.20` — traveller earns 20% of the product value (send and buy).
- `PLATFORM_FEE_PCT=0.02` — SaathiGo keeps 2% of the product value.
- `BOARDING_PASS_ENABLED=false` — boarding-pass scan/verify flow off; anyone can carry.

## Not yet included (next steps)
- Automated traveller payout settlement (Payout records are created as `pending`; settle via Pine Labs payouts/UPI as an ops job).
- Admin console beyond the Saathi review queue, disputes, KYC, OTP rate-limiting, DB migrations (Alembic).

## Postgres
`docker compose up -d`, `pip install "psycopg[binary]"`, set `DATABASE_URL=postgresql+psycopg://tagalong:tagalong@localhost:5432/tagalong`.
