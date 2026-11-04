import type { ReactNode } from "react";
import { DragonIcon, MapIcon, ScrollIcon, ShieldIcon, SparkleIcon, SwordIcon, UsersIcon } from "../components/Icons";

export interface Feature {
  key: string;
  title: string;
  blurb: string;
  icon: ReactNode;
  status: "live" | "soon";
}

/** The product roadmap, shown on the home page. */
export const FEATURES: Feature[] = [
  { key: "characters", title: "Character builder", icon: <ShieldIcon />, status: "soon",
    blurb: "Roll stats, pick a race, class and background, and get a full character sheet." },
  { key: "bestiary", title: "Bestiary", icon: <DragonIcon />, status: "soon",
    blurb: "Search every SRD monster by challenge rating, type and environment." },
  { key: "spells", title: "Spells & spellbook", icon: <SparkleIcon />, status: "soon",
    blurb: "Browse the spell catalogue and keep a personal spellbook for each caster." },
  { key: "items", title: "Items & equipment", icon: <SwordIcon />, status: "soon",
    blurb: "Weapons, armour, gear and magic items with full rules text." },
  { key: "campaigns", title: "Campaigns", icon: <MapIcon />, status: "soon",
    blurb: "Run campaigns, keep session notes and track your party's progress." },
  { key: "party", title: "Parties & messaging", icon: <UsersIcon />, status: "soon",
    blurb: "Share characters, form a party with friends and chat between sessions." },
  { key: "adventure", title: "Solo text adventure", icon: <ScrollIcon />, status: "soon",
    blurb: "Take your characters on an offline, single-player adventure to learn the rules." },
];
