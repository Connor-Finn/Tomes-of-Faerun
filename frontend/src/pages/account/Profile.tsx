import { useState, type FormEvent } from "react";
import { ErrorSummary, FieldError, TextField } from "../../components/Form";
import { api, type FieldErrors, type User } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useFlash } from "../../lib/flash";
import { useAccountOptions } from "../../lib/useOptions";
import { AccountNav } from "./AccountNav";

export function Profile() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="account-layout">
      <AccountNav />
      <div className="stack">
        <AvatarCard user={user} />
        <ProfileForm user={user} />
      </div>
    </div>
  );
}

function ProfileForm({ user }: { user: User }) {
  const { setUser } = useAuth();
  const { flash } = useFlash();
  const options = useAccountOptions();
  const [form, setForm] = useState({
    name: user.name, bio: user.bio, timezone: user.timezone, experience: user.experience,
    notify_email: user.notify_email, notify_party: user.notify_party,
  });
  const [errors, setErrors] = useState<FieldErrors>({});
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await api.patch<{ user: User; message: string }>("/api/account/profile", form);
    if (res.ok) {
      setErrors({});
      setUser(res.data.user);
      flash("success", res.data.message);
    } else {
      setErrors(res.data.errors ?? {});
    }
  }

  return (
    <section className="card" aria-labelledby="profile-heading">
      <h1 id="profile-heading">Profile</h1>
      <ErrorSummary errors={errors} />
      <form onSubmit={onSubmit} noValidate>
        <TextField label="Display name" name="name" error={errors.name}
          value={form.name} onChange={(e) => set("name", e.target.value)} />
        <TextField label="Email" name="email" type="email" value={user.email} disabled
          hint={<p className="hint">Your email can't be changed.</p>} />

        <div className="field">
          <label htmlFor="bio">Bio</label>
          <textarea id="bio" name="bio" rows={3} maxLength={250} value={form.bio}
            placeholder="A little about you and the games you play"
            aria-invalid={errors.bio ? true : undefined} onChange={(e) => set("bio", e.target.value)} />
          <p className={`hint ${form.bio.length > 200 ? "over" : ""}`} data-testid="bio-counter">
            {form.bio.length} / 200
          </p>
          <FieldError id="bio-error" field="bio" error={errors.bio} />
        </div>

        <div className="field">
          <label htmlFor="timezone">Time zone</label>
          <select id="timezone" name="timezone" value={form.timezone} onChange={(e) => set("timezone", e.target.value)}>
            {options?.timezones.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
          </select>
          <FieldError id="timezone-error" field="timezone" error={errors.timezone} />
        </div>

        <fieldset className="field">
          <legend>Experience level</legend>
          <div className="radio-group">
            {options?.experience_levels.map((o) => (
              <label key={o.value} className="check">
                <input type="radio" name="experience" value={o.value} checked={form.experience === o.value}
                  onChange={() => set("experience", o.value)} />
                {o.label}
              </label>
            ))}
          </div>
          <FieldError id="experience-error" field="experience" error={errors.experience} />
        </fieldset>

        <fieldset className="field">
          <legend>Notifications</legend>
          <label className="check">
            <input type="checkbox" checked={form.notify_email} onChange={(e) => set("notify_email", e.target.checked)} />
            Email notifications
          </label>
          <label className="check">
            <input type="checkbox" checked={form.notify_party} onChange={(e) => set("notify_party", e.target.checked)} />
            Party message notifications
          </label>
        </fieldset>

        <button type="submit" className="btn primary">Save changes</button>
      </form>
    </section>
  );
}

function AvatarCard({ user }: { user: User }) {
  const { setUser } = useAuth();
  const { flash } = useFlash();
  const [file, setFile] = useState<File | null>(null);

  async function upload(e: FormEvent) {
    e.preventDefault();
    const body = new FormData();
    if (file) body.append("avatar", file);
    const res = await api.post<{ user: User; message: string }>("/api/account/avatar", body);
    if (res.ok) {
      setUser(res.data.user);
      setFile(null);
      (e.target as HTMLFormElement).reset();
      flash("success", res.data.message);
    } else {
      flash("error", res.data.error ?? "Upload failed.");
    }
  }

  async function remove() {
    const res = await api.delete<{ user: User; message: string }>("/api/account/avatar");
    if (res.ok) {
      setUser(res.data.user);
      flash("info", res.data.message);
    }
  }

  return (
    <section className="card avatar-card" aria-labelledby="avatar-heading">
      {user.avatar_url ? (
        <img src={user.avatar_url} alt="Your avatar" className="avatar-lg" data-testid="avatar-image" />
      ) : (
        <div className="avatar-lg initials" data-testid="avatar-placeholder" aria-hidden="true">
          {user.name.charAt(0).toUpperCase()}
        </div>
      )}
      <div>
        <h2 id="avatar-heading">Avatar</h2>
        <form onSubmit={upload} className="row wrap">
          <label htmlFor="avatar-file" className="sr-only">Upload a new avatar</label>
          <input id="avatar-file" type="file" accept="image/png,image/jpeg,image/gif"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button type="submit" className="btn small">Upload avatar</button>
          {user.avatar_url && (
            <button type="button" className="btn ghost small" onClick={remove}>Remove avatar</button>
          )}
        </form>
        <p className="hint">PNG, JPG or GIF, up to 1 MB.</p>
      </div>
    </section>
  );
}
