import { Route, Routes } from "react-router-dom";
import { GuestOnly, RequireAdmin, RequireAuth } from "./components/Guards";
import { Layout } from "./components/Layout";
import { AdminUsers } from "./pages/AdminUsers";
import { Dashboard } from "./pages/Dashboard";
import { Home } from "./pages/Home";
import { Mailbox, NotFound } from "./pages/Mailbox";
import { Profile } from "./pages/account/Profile";
import { Security } from "./pages/account/Security";
import { CheckEmail, ForgotPassword, ResetPassword, VerifyEmail } from "./pages/auth/EmailFlows";
import { Login } from "./pages/auth/Login";
import { Signup } from "./pages/auth/Signup";

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
        <Route path="dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="account/profile" element={<RequireAuth><Profile /></RequireAuth>} />
        <Route path="account/security" element={<RequireAuth><Security /></RequireAuth>} />
        <Route path="admin/users" element={<RequireAdmin><AdminUsers /></RequireAdmin>} />

        {/* Developer tools */}
        <Route path="mailbox" element={<Mailbox />} />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
