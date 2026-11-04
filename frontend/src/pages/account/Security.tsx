import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorSummary, PasswordField, TextField } from "../../components/Form";
import { api, type FieldErrors } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useFlash } from "../../lib/flash";
import { AccountNav } from "./AccountNav";

export function Security() {
  return (
    <div className="account-layout">
      <AccountNav />
      <div className="stack">
        <ChangePassword />
        <DangerZone />
      </div>
    </div>
  );
}

function ChangePassword() {
  const { flash } = useFlash();
  const empty = { current_password: "", new_password: "", confirm_password: "" };
  const [form, setForm] = useState(empty);
  const [errors, setErrors] = useState<FieldErrors>({});

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.post<{ message: string }>("/api/account/password", form);
    if (res.ok) {
      setForm(empty);
      setErrors({});
      flash("success", res.data.message);
    } else {
      setErrors(res.data.errors ?? {});
    }
  }

  return (
    <section className="card" aria-labelledby="password-heading">
      <h1 id="password-heading">Security</h1>
      <h2>Change password</h2>
      <ErrorSummary errors={errors} />
      <form onSubmit={onSubmit} noValidate>
        <PasswordField label="Current password" name="current_password" autoComplete="current-password"
          error={errors.current_password} value={form.current_password}
          onChange={(e) => setForm({ ...form, current_password: e.target.value })} />
        <PasswordField label="New password" name="new_password" autoComplete="new-password"
          error={errors.new_password} value={form.new_password}
          onChange={(e) => setForm({ ...form, new_password: e.target.value })} />
        <PasswordField label="Confirm new password" name="confirm_password" autoComplete="new-password"
          error={errors.confirm_password} value={form.confirm_password}
          onChange={(e) => setForm({ ...form, confirm_password: e.target.value })} />
        <button type="submit" className="btn primary">Update password</button>
      </form>
    </section>
  );
}

function DangerZone() {
  const [open, setOpen] = useState(false);
  return (
    <section className="card danger" aria-labelledby="danger-heading">
      <h2 id="danger-heading">Delete account</h2>
      <p className="muted">This permanently deletes your account and everything in it. It can't be undone.</p>
      <button type="button" className="btn danger" onClick={() => setOpen(true)}>Delete my account</button>
      {open && <DeleteDialog onClose={() => setOpen(false)} />}
    </section>
  );
}

function DeleteDialog({ onClose }: { onClose: () => void }) {
  const { setUser } = useAuth();
  const { flash } = useFlash();
  const navigate = useNavigate();
  const ref = useRef<HTMLDialogElement>(null);
  const [password, setPassword] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.delete<{ message: string }>("/api/account", { password, confirm_text: confirmText });
    if (!res.ok) {
      setError(res.data.error ?? "Account not deleted.");
      return;
    }
    setUser(null);
    flash("info", res.data.message, { afterNavigate: true });
    navigate("/");
  }

  return (
    <dialog ref={ref} className="modal" aria-labelledby="delete-title" onClose={onClose}>
      <form onSubmit={onSubmit}>
        <h2 id="delete-title">Delete account?</h2>
        <p>This can't be undone. Enter your password and type DELETE to confirm.</p>
        {error && <p className="form-error-summary" role="alert" data-testid="delete-error">{error}</p>}
        <PasswordField label="Your password" name="delete_password" autoComplete="current-password"
          value={password} onChange={(e) => setPassword(e.target.value)} />
        <TextField label="Type DELETE to confirm" name="confirm_text" autoComplete="off"
          value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
        <div className="row end">
          <button type="button" className="btn ghost" onClick={() => ref.current?.close()}>Cancel</button>
          <button type="submit" className="btn danger" disabled={!password || confirmText !== "DELETE"}>
            Permanently delete account
          </button>
        </div>
      </form>
    </dialog>
  );
}
