import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Flashes, useFlash } from "../lib/flash";
import { BookIcon } from "./Icons";

export function Layout() {
  const { user } = useAuth();
  return (
    <div className="app">
      <header className="topbar">
        <Link className="brand" to="/" data-testid="nav-home">
          <BookIcon />
          <span>
            <span className="brand-name">Tomes of Faerun</span>
            <span className="brand-tagline">A D&amp;D adventure tool</span>
          </span>
        </Link>
        <nav className="main-nav" aria-label="Main">
          {user && <NavLink to="/guild-hall" data-testid="nav-guild-hall">Guild Hall</NavLink>}
          {user?.role === "admin" && (
            <NavLink to="/admin/users" data-testid="nav-admin">
              Admin
            </NavLink>
          )}
          {user ? (
            <UserMenu />
          ) : (
            <>
              <NavLink to="/login">Log in</NavLink>
              <Link to="/signup" className="btn primary small">
                Sign up
              </Link>
            </>
          )}
        </nav>
      </header>

      <main className="container">
        <Flashes />
        <Outlet />
      </main>

      <footer className="footer">
        <span>Tomes of Faerun · a fan-made D&amp;D 5e companion</span>
        <span className="muted">
          Rules content from the 5e System Reference Document ·{" "}
          <Link to="/mailbox" data-testid="nav-mailbox">
            Dev mailbox
          </Link>
        </span>
      </footer>
    </div>
  );
}

function UserMenu() {
  const { user, setUser } = useAuth();
  const { flash } = useFlash();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => setOpen(false), [location.key]);
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;

  async function logout() {
    await api.post("/api/auth/logout");
    setUser(null);
    flash("info", "You have been logged out.", { afterNavigate: true });
    navigate("/login");
  }

  return (
    <div className="user-menu" ref={ref}>
      <button
        type="button"
        className="user-menu-button"
        data-testid="user-menu-button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls="user-menu"
        onClick={() => setOpen((o) => !o)}
      >
        {user.avatar_url ? (
          <img src={user.avatar_url} alt="" className="avatar-sm" />
        ) : (
          <span className="avatar-sm initials" aria-hidden="true">
            {user.name.charAt(0).toUpperCase()}
          </span>
        )}
        <span>{user.name}</span> <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <div id="user-menu" className="dropdown" role="menu">
          <Link role="menuitem" to="/account/profile">
            Profile
          </Link>
          <Link role="menuitem" to="/account/security">
            Security
          </Link>
          <button type="button" role="menuitem" onClick={logout}>
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
