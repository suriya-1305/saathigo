import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { ErrorBox } from "../components/Layout";
import { useAuth } from "../context/AuthContext";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";
  const [form, setForm] = useState({ name: "", email: "", password: "", phone: "", city: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(form.email, form.password);
      else await register({ ...form, phone: form.phone || undefined, city: form.city || undefined });
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth card">
      <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
      <form onSubmit={submit} className="form">
        {mode === "register" && (
          <label>
            Full name
            <input required value={form.name} onChange={set("name")} />
          </label>
        )}
        <label>
          Email
          <input type="email" required value={form.email} onChange={set("email")} />
        </label>
        <label>
          Password
          <input type="password" required minLength={8} value={form.password} onChange={set("password")} />
        </label>
        {mode === "register" && (
          <div className="grid-2">
            <label>
              Mobile
              <input value={form.phone} onChange={set("phone")} placeholder="98xxxxxxxx" />
            </label>
            <label>
              City
              <input value={form.city} onChange={set("city")} placeholder="Bengaluru" />
            </label>
          </div>
        )}
        <ErrorBox error={error} />
        <button className="btn btn-block" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Log in" : "Sign up"}
        </button>
      </form>
      <p className="muted small center">
        {mode === "login" ? (
          <>
            New here? <Link to="/register" state={location.state}>Create an account</Link>
          </>
        ) : (
          <>
            Already registered? <Link to="/login" state={location.state}>Log in</Link>
          </>
        )}
      </p>
    </div>
  );
}
