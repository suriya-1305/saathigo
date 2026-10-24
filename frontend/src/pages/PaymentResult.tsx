import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, formatINR } from "../api/client";
import type { Payment } from "../api/types";
import { Spinner } from "../components/Layout";

export default function PaymentResult() {
  const [params] = useSearchParams();
  const id = params.get("payment_id");
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let tries = 0;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const p = await api<Payment>(`/payments/${id}`);
        setPayment(p);
        if ((p.status === "pending" || p.status === "created") && tries++ < 10) timer = setTimeout(poll, 3000);
      } catch (e) {
        setError((e as Error).message);
      }
    };
    poll();
    return () => clearTimeout(timer);
  }, [id]);

  if (error) return <div className="alert alert-error">{error}</div>;
  if (!payment) return <Spinner />;
  const link = payment.purpose === "shipment" ? `/send/${payment.reference_id}` : `/buy/${payment.reference_id}`;
  const ok = payment.status === "success";
  const pending = payment.status === "pending" || payment.status === "created";

  return (
    <div className="narrow card center">
      <div className="big-icon">{ok ? "✅" : pending ? "⏳" : "❌"}</div>
      <h1>{ok ? "Payment successful" : pending ? "Confirming payment…" : "Payment not completed"}</h1>
      <p className="muted">
        {formatINR(payment.amount_paise)} · Ref {payment.provider_order_id}
      </p>
      {ok && <p>Your money is held safely in escrow until delivery is confirmed with your OTP.</p>}
      <Link to={link} className="btn">
        {ok ? "View order" : "Back to order"}
      </Link>
    </div>
  );
}
