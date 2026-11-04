import { Navigate, Route, Routes } from "react-router-dom";
import { GuestOnly, RequireAdmin, RequireAuth } from "./components/Guards";
import { Layout } from "./components/Layout";
import { AdminUsers } from "./pages/AdminUsers";
import { Home } from "./pages/Home";
import { SectionTome } from "./pages/SectionTome";
import { Tavern } from "./pages/Tavern";
import { Mailbox, NotFound } from "./pages/Mailbox";
import { Profile } from "./pages/account/Profile";
import { Security } from "./pages/account/Security";
import { CheckEmail, ForgotPassword, ResetPassword, VerifyEmail } from "./pages/auth/EmailFlows";
import { Login } from "./pages/auth/Login";
import { Signup } from "./pages/auth/Signup";
import { SECTIONS } from "./lib/sections";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />

        {/* Accounts */}
        <Route path="login" element={<GuestOnly><Login /></GuestOnly>} />
        <Route path="signup" element={<GuestOnly><Signup /></GuestOnly>} />
        <Route path="signup/check-email" element={<CheckEmail />} />
        <Route path="verify/:token" element={<VerifyEmail />} />
        <Route path="forgot-password" element={<ForgotPassword />} />
        <Route path="reset-password/:token" element={<ResetPassword />} />
        <Route path="account/profile" element={<RequireAuth><Profile /></RequireAuth>} />
        <Route path="account/security" element={<RequireAuth><Security /></RequireAuth>} />
        <Route path="admin/users" element={<RequireAdmin><AdminUsers /></RequireAdmin>} />

        {/* The tavern hub and one tome per section (generated from lib/sections) */}
        <Route path="tavern" element={<RequireAuth><Tavern /></RequireAuth>} />
        <Route path="dashboard" element={<Navigate to="/tavern" replace />} />
        {SECTIONS.map((s) => (
          <Route
            key={s.key}
            path={`${s.path}/:page?`}
            element={<RequireAuth><SectionTome section={s} /></RequireAuth>}
          />
        ))}

        {/* Developer tools */}
        <Route path="mailbox" element={<Mailbox />} />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
