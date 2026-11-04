import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { safeNext } from "../../components/Guards";
import { PasswordField, TextField } from "../../components/Form";
import { api, type User } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useFlash } from "../../lib/flash";

export function Login() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const { flash } = useFlash();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showResend, setShowResend] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const res = await api.post<{ user: User }>("/api/auth/login", { email, password, remember });
    setBusy(false);
    if (!res.ok) {
      setError(res.data.error ?? "Something went wrong.");
      setShowResend(res.data.code === "unverified");
      setPassword("");
      return;
    }
    setUser(res.data.user);
    flash("success", `Welcome back, ${res.data.user.name}!`, { afterNavigate: true });
    navigate(safeNext(params.get("next")) ?? "/dashboard");
  }

  async function resend() {
    const res = await api.post<{ message: string }>("/api/auth/resend-verification", { email });
    flash("info", res.data.message ?? "Verification email sent.", { afterNavigate: true });
    navigate(`/signup/check-email?email=${encodeURIComponent(email)}`);
  }

  return (
    <section className="card narrow">
      <h1>Log in</h1>
      <p className="muted">Welcome back, adventurer.</p>
      {error && (
        <div className="form-error-summary" role="alert">
          <span data-testid="login-error">{error}</span>
          {showResend && (
            <button type="button" className="btn ghost small" onClick={resend}>
              Resend verification email
            </button>
          )}
        </div>
      )}
      <form onSubmit={onSubmit}>
        <TextField label="Email" name="email" type="email" autoComplete="email" required
          value={email} onChange={(e) => setEmail(e.target.value)} />
        <PasswordField label="Password" name="password" autoComplete="current-password" required
          value={password} onChange={(e) => setPassword(e.target.value)} />
        <div className="row between">
          <label className="check">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
            Remember me
          </label>
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        <button type="submit" className="btn primary block" disabled={busy}>
          Log in
        </button>
      </form>
      <p className="muted center">
        New to the realms? <Link to="/signup">Create an account</Link>
      </p>
    </section>
  );
}
