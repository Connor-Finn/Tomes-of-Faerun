import { useEffect, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useFlash } from "../lib/flash";

function Loading() {
  return (
    <p className="muted center" data-testid="page-loading">
      Opening the tome…
    </p>
  );
}

/** Pages that need a logged-in user. Anyone else is sent to /login?next=... */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const { flash } = useFlash();
  const location = useLocation();
  const mustLogIn = !loading && !user;

  useEffect(() => {
    if (mustLogIn) flash("warning", "Please log in to access that page.", { afterNavigate: true });
  }, [mustLogIn, flash]);

  if (loading) return <Loading />;
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <>{children}</>;
}

/** Admin-only pages. Logged-in non-admins see "Access denied". */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return (
    <RequireAuth>
      {user?.role === "admin" ? (
        children
      ) : (
        <section className="card narrow center">
          <h1>Access denied</h1>
          <p className="muted">You don't have permission to view this page.</p>
        </section>
      )}
    </RequireAuth>
  );
}

/** Pages only for logged-out visitors (login, signup). */
export function GuestOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (user) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

/** Only allow relative redirects (prevents "open redirect" attacks). */
export function safeNext(target: string | null): string | null {
  if (target && target.startsWith("/") && !target.startsWith("//") && !target.includes("\\")) return target;
  return null;
}
