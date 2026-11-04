import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ErrorSummary, FieldError, PasswordField, TextField } from "../../components/Form";
import { PasswordStrength } from "../../components/PasswordStrength";
import { api, type FieldErrors } from "../../lib/api";
import { useAccountOptions } from "../../lib/useOptions";

const EMPTY = { name: "", email: "", password: "", confirm_password: "", experience: "", newsletter: false, terms: false };

export function Signup() {
  const navigate = useNavigate();
  const options = useAccountOptions();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);

  const set = <K extends keyof typeof EMPTY>(key: K, value: (typeof EMPTY)[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    const res = await api.post<{ email: string }>("/api/auth/signup", form);
    setBusy(false);
    if (res.ok) {
      navigate(`/signup/check-email?email=${encodeURIComponent(res.data.email)}`);
      return;
    }
    setErrors(res.data.errors ?? {});
    // Passwords are never kept after a failed submit.
    setForm((f) => ({ ...f, password: "", confirm_password: "" }));
  }

  return (
    <section className="card narrow">
      <h1>Create your account</h1>
      <p className="muted">Join the guild and start building your adventurers.</p>
      <ErrorSummary errors={errors} />
      <form onSubmit={onSubmit} noValidate>
        <TextField label="Display name" name="name" autoComplete="nickname" error={errors.name}
          value={form.name} onChange={(e) => set("name", e.target.value)} />
        <TextField label="Email" name="email" type="email" autoComplete="email" error={errors.email}
          value={form.email} onChange={(e) => set("email", e.target.value)} />
        <PasswordField label="Password" name="password" autoComplete="new-password" error={errors.password}
          value={form.password} onChange={(e) => set("password", e.target.value)}
          hint={<PasswordStrength password={form.password} />} />
        <PasswordField label="Confirm password" name="confirm_password" autoComplete="new-password"
          error={errors.confirm_password} value={form.confirm_password}
          onChange={(e) => set("confirm_password", e.target.value)} />

        <div className="field">
          <label htmlFor="experience">Experience level</label>
          <select id="experience" name="experience" value={form.experience}
            aria-invalid={errors.experience ? true : undefined}
            aria-describedby={errors.experience ? "experience-error" : undefined}
            onChange={(e) => set("experience", e.target.value)}>
            <option value="">Choose one…</option>
            {options?.experience_levels.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <FieldError id="experience-error" field="experience" error={errors.experience} />
        </div>

        <label className="check">
          <input type="checkbox" checked={form.newsletter} onChange={(e) => set("newsletter", e.target.checked)} />
          Send me news about new features
        </label>
        <label className="check">
          <input type="checkbox" checked={form.terms} onChange={(e) => set("terms", e.target.checked)}
            aria-invalid={errors.terms ? true : undefined}
            aria-describedby={errors.terms ? "terms-error" : undefined} />
          I agree to the Terms of Service
        </label>
        <FieldError id="terms-error" field="terms" error={errors.terms} />

        <button type="submit" className="btn primary block" disabled={busy}>
          Create account
        </button>
      </form>
      <p className="muted center">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </section>
  );
}
