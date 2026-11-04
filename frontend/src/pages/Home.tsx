import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { FEATURES } from "../lib/features";

export function Home() {
  const { user } = useAuth();
  return (
    <>
      <section className="hero">
        <p className="eyebrow">Pull up a chair, adventurer</p>
        <h1>Your adventures, bound in one tome.</h1>
        <p className="lead">
          Build characters, look up spells and monsters, run campaigns with your party, and practise the rules in a
          solo text adventure. Built on the free D&amp;D 5e System Reference Document.
        </p>
        <div className="hero-actions">
          {user ? (
            <Link to="/guild-hall" className="btn primary">
              Enter the guild hall
            </Link>
          ) : (
            <>
              <Link to="/signup" className="btn primary">
                Start your adventure
              </Link>
              <Link to="/login" className="btn ghost">
                I already have an account
              </Link>
            </>
          )}
        </div>
      </section>

      <section aria-labelledby="features-heading">
        <h2 id="features-heading" className="section-title">
          What's inside
        </h2>
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <article key={f.key} className="feature-card" data-testid="feature-card">
              <div className="feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.blurb}</p>
              {f.status === "soon" && <span className="badge">Coming soon</span>}
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
