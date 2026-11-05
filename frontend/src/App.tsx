import { Navigate, Route, Routes } from "react-router-dom";
import { GuestOnly, RequireAdmin, RequireAuth } from "./components/Guards";
import { Layout } from "./components/Layout";
import { AdminUsers } from "./pages/AdminUsers";
import { Home } from "./pages/Home";
import { SectionTome } from "./pages/SectionTome";
import { GuildHall } from "./pages/GuildHall";
import { Mailbox, NotFound } from "./pages/Mailbox";
import { Profile } from "./pages/account/Profile";
import { Security } from "./pages/account/Security";
import { CheckEmail, ForgotPassword, ResetPassword, VerifyEmail } from "./pages/auth/EmailFlows";
import { Login } from "./pages/auth/Login";
import { Signup } from "./pages/auth/Signup";
import { SECTIONS } from "./lib/sections";
import { Builder } from "./pages/characters/Builder";
import { CharacterTome } from "./pages/characters/CharacterTome";
import { CampaignTome } from "./pages/campaigns/CampaignTome";
import { LevelUpPage } from "./pages/campaigns/LevelUp";

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

        {/* The guild hall hub and one tome per section (generated from lib/sections) */}
        <Route path="guild-hall" element={<RequireAuth><GuildHall /></RequireAuth>} />
        <Route path="dashboard" element={<Navigate to="/guild-hall" replace />} />
        {SECTIONS.map((s) => (
          <Route key={s.key} path={s.path}>
            <Route path=":page?" element={<RequireAuth><SectionTome section={s} /></RequireAuth>} />
            <Route path=":page/:sub" element={<RequireAuth><SectionTome section={s} /></RequireAuth>} />
          </Route>
        ))}

        {/* Each character is its own tome */}
        <Route path="play/characters/new" element={<RequireAuth><Builder /></RequireAuth>} />
        <Route path="play/characters/c/:id/edit" element={<RequireAuth><Builder /></RequireAuth>} />
        <Route path="play/characters/c/:id/:page?" element={<RequireAuth><CharacterTome /></RequireAuth>} />
        <Route path="play/characters/c/:id/:page/:sub" element={<RequireAuth><CharacterTome /></RequireAuth>} />
        <Route path="play/characters/c/:id/roadmaps/:roadmapId/level/:level" element={<RequireAuth><Builder /></RequireAuth>} />

        {/* Each campaign is its own tome, with a DM edition and a player edition */}
        <Route path="dm/campaigns/c/:id/:page?" element={<RequireAuth><CampaignTome mode="dm" /></RequireAuth>} />
        <Route path="dm/campaigns/c/:id/:page/:sub" element={<RequireAuth><CampaignTome mode="dm" /></RequireAuth>} />
        <Route path="play/campaigns/c/:id/:page?" element={<RequireAuth><CampaignTome mode="player" /></RequireAuth>} />
        <Route path="play/campaigns/c/:campaignId/character/level-up" element={<RequireAuth><LevelUpPage /></RequireAuth>} />

        {/* Developer tools */}
        <Route path="mailbox" element={<Mailbox />} />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
