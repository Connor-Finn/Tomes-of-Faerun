/** Pages reached from emails: check-your-inbox, verify, forgot and reset password. */
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ErrorSummary, PasswordField, TextField } from "../../components/Form";
import { PasswordStrength } from "../../components/PasswordStrength";
import { api, type FieldErrors } from "../../lib/api";
import { useFlash } from "../../lib/flash";

export function CheckEmail() {
  const [params] = useSearchParams();
  const { flash } = useFlash();
  const email = params.get("email") ?? "";

  async function resend() {
    const res = await api.post<{ message: string }>("/api/auth/resend-verification", { email });
    flash("info", res.data.message ?? "Verification email sent.");
  }

  return (
    <section className="card narrow center">
      <h1>Check your email</h1>
      <p data-testid="check-email-message">
        We sent a verification link to <strong>{email || "your email address"}</strong>. Open it to activate your
        account.
      </p>
      <p className="muted">
        No real emails are sent while developing. Open the <Link to={`/mailbox?to=${encodeURIComponent(email)}`}>dev mailbox</Link> to find it.
      </p>
      {email && (
        <button type="button" className="btn ghost" onClick={resend}>
          Resend verification email
        </button>
      )}
    </section>
  );
}

export function VerifyEmail() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const { flash } = useFlash();
  const [failed, setFailed] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // React StrictMode runs effects twice in dev
    started.current = true;
    void api.post<{ message: string }>("/api/auth/verify", { token }).then((res) => {
      if (res.ok) {
        flash("success", res.data.message, { afterNavigate: true });
        navigate("/login", { replace: true });
      } else {
        setFailed(true);
      }
    });
  }, [token, navigate, flash]);

  return (
    <section className="card narrow center">
      {failed ? (
        <>
          <h1>Link expired</h1>
          <p data-testid="verify-invalid">This verification link is invalid or has expired.</p>
          <Link to="/login" className="btn ghost">Back to log in</Link>
        </>
      ) : (
        <p className="muted">Verifying your email…</p>
      )}
    </section>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.post("/api/auth/forgot-password", { email });
    if (res.ok) setSent(true);
    else setErrors(res.data.errors ?? {});
  }

  return (
    <section className="card narrow">
      <h1>Forgot your password?</h1>
      {sent ? (
        <p className="notice" data-testid="forgot-confirmation">
          If an account exists for {email}, we've sent a password reset link. It's valid for 1 hour.
        </p>
      ) : (
        <form onSubmit={onSubmit}>
          <p className="muted">Enter your email and we'll send you a link to reset it.</p>
          <TextField label="Email" name="email" type="email" required error={errors.email}
            value={email} onChange={(e) => setEmail(e.target.value)} />
          <button type="submit" className="btn primary block">Send reset link</button>
        </form>
      )}
      <p className="muted center"><Link to="/login">Back to log in</Link></p>
    </section>
  );
}

export function ResetPassword() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const { flash } = useFlash();
  const [valid, setValid] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});

  useEffect(() => {
    void api.get(`/api/auth/reset-password/${encodeURIComponent(token)}`).then((res) => setValid(res.ok));
  }, [token]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.post<{ message: string }>(`/api/auth/reset-password/${encodeURIComponent(token)}`, {
      password, confirm_password: confirm,
    });
    if (res.ok) {
      flash("success", res.data.message, { afterNavigate: true });
      navigate("/login");
    } else if (res.data.errors) {
      setErrors(res.data.errors);
    } else {
      setValid(false);
    }
  }

  if (valid === null) return <p className="muted center">Checking your link…</p>;
  if (!valid) {
    return (
      <section className="card narrow center">
        <h1>Link expired</h1>
        <p data-testid="reset-invalid">This reset link is invalid, has expired or has already been used.</p>
        <Link to="/forgot-password" className="btn ghost">Request a new link</Link>
      </section>
    );
  }
  return (
    <section className="card narrow">
      <h1>Choose a new password</h1>
      <ErrorSummary errors={errors} />
      <form onSubmit={onSubmit} noValidate>
        <PasswordField label="New password" name="password" autoComplete="new-password" error={errors.password}
          value={password} onChange={(e) => setPassword(e.target.value)} hint={<PasswordStrength password={password} />} />
        <PasswordField label="Confirm new password" name="confirm_password" autoComplete="new-password"
          error={errors.confirm_password} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        <button type="submit" className="btn primary block">Reset password</button>
      </form>
    </section>
  );
}
