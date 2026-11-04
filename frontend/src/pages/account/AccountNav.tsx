import { NavLink } from "react-router-dom";

export function AccountNav() {
  return (
    <nav className="account-nav" aria-label="Account">
      <NavLink to="/account/profile">Profile</NavLink>
      <NavLink to="/account/security">Security</NavLink>
    </nav>
  );
}
