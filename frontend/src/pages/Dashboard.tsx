import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { FEATURES } from "../lib/features";

export function Dashboard() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <>
      <header className="page-header">
        <h1>Welcome, {user.name}</h1>
        <p className="muted">Your adventuring hub. New tools are being added to the tome.</p>
      </header>

      <div className="dashboard-grid">
        <section className="card" aria-labelledby="profile-heading">
          <h2 id="profile-heading">Your profile</h2>
          <dl className="details">
            <dt>Email</dt>
            <dd>{user.email}</dd>
            <dt>Role</dt>
            <dd data-testid="profile-role">{user.role === "admin" ? "Dungeon Master (admin)" : "Adventurer"}</dd>
            <dt>Member since</dt>
            <dd>{new Date(user.created_at).toLocaleDateString()}</dd>
          </dl>
          <Link to="/account/profile" className="btn ghost small">
            Edit profile
          </Link>
        </section>

        <section className="card" aria-labelledby="roadmap-heading">
          <h2 id="roadmap-heading">Coming to the tome</h2>
          <ul className="roadmap">
            {FEATURES.map((f) => (
              <li key={f.key}>
                <span className="feature-icon small">{f.icon}</span>
                <span>{f.title}</span>
                <span className="badge">Coming soon</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
