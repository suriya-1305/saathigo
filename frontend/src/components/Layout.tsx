import type { ReactNode } from "react";
import { Link, NavLink, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { SaathiPopup } from "./SaathiPopup";

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout, config } = useAuth();
  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <Link to="/" className="brand">
            <span className="brand-mark">✈</span> {config?.app_name ?? "SaathiGo"}
          </Link>
          <nav className="nav">
            <NavLink to="/buy">Buy from abroad</NavLink>
            <NavLink to="/send">Send abroad</NavLink>
            <NavLink to="/trips">Travel &amp; earn</NavLink>
            <NavLink to="/dabbas">Dabbas</NavLink>
            <NavLink to="/saathi" className="nav-saathi">
              ✨ Saathi
            </NavLink>
            {user ? (
              <>
                <NavLink to="/dashboard">Dashboard</NavLink>
                {user.is_admin && <NavLink to="/review">Review</NavLink>}
                <button className="btn-link" onClick={logout}>
                  Log out
                </button>
              </>
            ) : (
              <NavLink to="/login" className="btn btn-sm">
                Log in
              </NavLink>
            )}
          </nav>
        </div>
      </header>
      <main className="container main">{children}</main>
      <footer className="footer">
        <div className="container">
          Payments secured by Pine Labs · Traveller earns 20% · SaathiGo fee 2%
        </div>
      </footer>
      <SaathiPopup />
    </>
  );
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />;
  return <>{children}</>;
}

export const Spinner = () => <div className="spinner" aria-label="Loading" />;

export function ErrorBox({ error }: { error: string | null }) {
  return error ? <div className="alert alert-error">{error}</div> : null;
}

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  accepted: "Awaiting payment",
  matched: "Awaiting payment",
  paid: "Paid · in escrow",
  purchased: "Purchased",
  in_transit: "In transit",
  delivered: "Delivered",
  cancelled: "Cancelled",
  pending: "Pending",
  rejected: "Declined",
  withdrawn: "Withdrawn",
  success: "Successful",
  failed: "Failed",
  active: "Active",
};

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABELS[status] ?? status}</span>;
}

export function Steps({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="steps">
      {steps.map((s, i) => (
        <li key={s} className={i < current ? "done" : i === current ? "current" : ""}>
          <span>{i + 1}</span>
          {s}
        </li>
      ))}
    </ol>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children}
    </div>
  );
}
