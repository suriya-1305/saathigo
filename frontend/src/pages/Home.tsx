import { Link } from "react-router-dom";
import type { AgentName } from "../api/types";
import { AGENT_LABELS, SaathiCta } from "../components/Saathi";
import { useAuth } from "../context/AuthContext";

const AGENT_ROLES: Record<AgentName, string> = {
  concierge: "Understands what you want and routes it",
  intake: "Turns your message into a clear order",
  dabba_curator: "Fills a ready-made box for you",
  compliance: "Checks every item against customs rules",
  matching: "Finds and ranks travellers on your route",
  negotiation: "Suggests a fair reward for both sides",
  tracking_support: "Follows your order and escalates problems",
};

export default function Home() {
  const { config } = useAuth();
  const rewardPct = Math.round((config?.traveller_reward_pct ?? 0.2) * 100);
  const feePct = Math.round((config?.platform_fee_pct ?? 0.02) * 100);
  return (
    <>
      <section className="hero">
        <h1>
          Shop the world. Send love home-to-abroad.
          <br />
          <span className="accent">Powered by travellers.</span>
        </h1>
        <p className="lead">
          Get products from overseas delivered by people already flying to India — or send gifts and essentials to
          family abroad with travellers going their way. The traveller earns {rewardPct}% of the product value; we keep
          just {feePct}%.
        </p>
        <div className="row gap wrap">
          <Link to="/buy/new" className="btn btn-lg">
            Request a product
          </Link>
          <Link to="/send/new" className="btn btn-lg btn-secondary">
            Send something abroad
          </Link>
          <Link to="/trips/new" className="btn btn-lg btn-ghost">
            I'm travelling — earn
          </Link>
        </div>
        <SaathiCta />
      </section>

      <section className="card agents-strip">
        <h2>🤖 A team of Saathi agents runs every order</h2>
        <p className="muted">
          Powered by Pine Labs AgenticOrg. Agents draft, check and match — a person always confirms the final step.
        </p>
        <div className="agents-grid">
          {(Object.keys(AGENT_LABELS) as AgentName[]).map((a) => (
            <div key={a} className="agent-tile">
              <span className="agent-icon">{AGENT_LABELS[a].icon}</span>
              <b>{AGENT_LABELS[a].name}</b>
              <span className="small muted">{AGENT_ROLES[a]}</span>
            </div>
          ))}
        </div>
        <Link to="/dabbas" className="btn btn-ghost">
          🎁 Try a ready-made Swadeshi / Videshi Dabba →
        </Link>
      </section>

      <section className="grid-2">
        <div className="card module">
          <h2>🛍️ Buy from overseas</h2>
          <ol className="how">
            <li>Paste a product link — we fill in the details.</li>
            <li>Your request is listed under the country it's sold in.</li>
            <li>Anyone flying from there to India can offer to bring it.</li>
            <li>Pay securely via Pine Labs — money is held in escrow.</li>
            <li>Meet the traveller, share your OTP, payment is released.</li>
          </ol>
          <Link to="/buy" className="btn btn-ghost">
            Browse requests by country →
          </Link>
        </div>
        <div className="card module">
          <h2>📦 Send to overseas</h2>
          <ol className="how">
            <li>Say what it is, its value, and where it's going.</li>
            <li>Traveller earns {rewardPct}% of the value, {config?.app_name ?? "SaathiGo"} keeps {feePct}%.</li>
            <li>Anyone travelling from India to that place can take it.</li>
            <li>At handover the traveller photographs the item for proof.</li>
            <li>Recipient shares your OTP on delivery — done.</li>
          </ol>
          <Link to="/send" className="btn btn-ghost">
            Browse shipments by destination →
          </Link>
        </div>
      </section>

      <section className="card trust">
        <div>
          <h3>🤖 Ask Saathi anytime</h3>
          <p className="muted">
            Tap the ✨ button to ask about your orders, what you can carry, or what's next — no digging through pages.
          </p>
        </div>
        <div>
          <h3>💳 Escrow payments</h3>
          <p className="muted">Pine Labs secures every payment. Travellers are paid only after OTP-confirmed delivery.</p>
        </div>
        <div>
          <h3>📸 Photo proof</h3>
          <p className="muted">Item photos at purchase and handover protect both sides.</p>
        </div>
      </section>
    </>
  );
}
