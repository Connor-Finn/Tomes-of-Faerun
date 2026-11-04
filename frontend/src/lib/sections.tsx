import type { ReactNode } from "react";
import {
  BooksIcon,
  CrownIcon,
  MapIcon,
  QuillIcon,
  ScrollIcon,
  ShieldIcon,
} from "../components/Icons";
import type { Mode } from "./mode";

/**
 * The app's map: every tome on the guild hall shelf, by mode.
 *
 * The hub, the routes and the tables of contents are all generated from this list, so adding a
 * section or a page is a one-line change here. Pages that aren't built yet show their `plans`
 * as a draft, so the app always shows where it's heading.
 */
export interface TomePageDef {
  slug: string;
  title: string;
  summary: string;
  plans: string[];
}

export type Cover = "oxblood" | "forest" | "navy" | "umber" | "plum" | "slate" | "ochre";

export interface SectionDef {
  key: string;
  mode: Mode;
  /** URL path without the leading slash, e.g. "play/characters". */
  path: string;
  title: string;
  blurb: string;
  icon: ReactNode;
  cover: Cover;
  /** Sealed tomes are on the shelf but not written yet. */
  sealed?: boolean;
  pages: TomePageDef[];
}

export const SECTIONS: SectionDef[] = [
  // ---------------------------------------------------------------- Player Mode
  {
    key: "player-campaigns",
    mode: "player",
    path: "play/campaigns",
    title: "Campaigns",
    blurb: "The campaigns you're playing in and the parties you've joined.",
    icon: <MapIcon />,
    cover: "forest",
    pages: [
      {
        slug: "current",
        title: "Current campaigns",
        summary: "Every campaign you're playing in, with the character you brought to each one.",
        plans: [
          "See each campaign's party, Dungeon Master and story so far.",
          "Open your character as it stands in that campaign, with any notes your DM left on it.",
          "Level up, or follow one of your character's level roadmaps.",
        ],
      },
      {
        slug: "parties",
        title: "Parties",
        summary: "The adventuring parties you belong to.",
        plans: [
          "Accept invitations or ask to join a public party.",
          "Chat with your party on enchanted parchment.",
          "Find other adventurers and send friend requests.",
        ],
      },
    ],
  },
  {
    key: "character-manager",
    mode: "player",
    path: "play/characters",
    title: "Character Manager",
    blurb: "Create, level and publish your characters.",
    icon: <ShieldIcon />,
    cover: "oxblood",
    pages: [
      {
        slug: "my-characters",
        title: "My characters",
        summary: "Your characters as you built them, untouched by any campaign.",
        plans: [
          "Each character's sheet, spellbook, inventory, features, notes and campaigns.",
          "Plan level-ups ahead of time with named level roadmaps, up to level 20.",
          "Switch between Easy and Standard build for each character.",
        ],
      },
      {
        slug: "create",
        title: "Create a character",
        summary: "Write a new character onto a fresh sheet of paper.",
        plans: [
          "Start from a class template or from a character another player published.",
          "Easy build: a guided, step-by-step tutorial for levels 1 to 3.",
          "Standard build: levels 1 to 20 with every rule enforced.",
        ],
      },
      {
        slug: "publish",
        title: "Publish a character",
        summary: "Share a character as a template other players can start from.",
        plans: [
          "Publishing makes a fixed copy, so later edits to your character don't change it.",
          "Choose which of the character's level roadmaps to include.",
        ],
      },
    ],
  },
  {
    key: "solo-adventure",
    mode: "player",
    path: "play/solo-adventure",
    title: "Solo Adventure",
    blurb: "Take your characters on an offline text adventure to practise the rules.",
    icon: <ScrollIcon />,
    cover: "umber",
    sealed: true,
    pages: [],
  },

  // ---------------------------------------------------------------- Dungeon Master Mode
  {
    key: "dm-campaigns",
    mode: "dm",
    path: "dm/campaigns",
    title: "Campaigns",
    blurb: "Run your campaigns and gather your parties.",
    icon: <CrownIcon />,
    cover: "navy",
    pages: [
      {
        slug: "campaigns",
        title: "Your campaigns",
        summary: "The campaigns you run, each kept in its own tome.",
        plans: [
          "Create a campaign, with or without a party.",
          "Each campaign has an overview, party, session log, encounters and DM notes.",
          "View your players' characters and leave notes on them.",
        ],
      },
      {
        slug: "parties",
        title: "Parties",
        summary: "The parties you lead.",
        plans: [
          "Create public or private parties and invite players.",
          "Attach a party to one or more campaigns.",
          "Decide whether players may invite their friends.",
        ],
      },
      {
        slug: "requests",
        title: "Join requests",
        summary: "Adventurers asking to join one of your parties.",
        plans: ["Accept or decline each request.", "Get notified when a new request arrives."],
      },
    ],
  },
  {
    key: "browse-tomes",
    mode: "dm",
    path: "dm/tomes",
    title: "Browse Tomes",
    blurb: "Spells, monsters and items from the 5e System Reference Document.",
    icon: <BooksIcon />,
    cover: "plum",
    pages: [
      {
        slug: "spells",
        title: "Spells",
        summary: "Every spell in the System Reference Document.",
        plans: [
          "Search and filter by level, school and class.",
          "Read each spell's full rules text.",
        ],
      },
      {
        slug: "bestiary",
        title: "Bestiary",
        summary: "Every monster in the System Reference Document.",
        plans: [
          "Search by name, challenge rating, size and creature type.",
          "Read each monster's full stat block.",
          "Save monsters into collections and sort them into environments.",
        ],
      },
      {
        slug: "collections",
        title: "Monster collections",
        summary: "Your own groups of monsters, such as “Warlock boss dungeon”.",
        plans: [
          "Tag each monster as a minion, an elite or the boss, and say how many there are.",
          "See the total XP of everything in a collection.",
          "Later: add collections to a campaign's encounters.",
        ],
      },
      {
        slug: "environments",
        title: "Environments",
        summary: "Where your monsters live. The SRD doesn't say, so you decide.",
        plans: ["Make environments such as “Underdark” and filter the bestiary by them."],
      },
      {
        slug: "equipment",
        title: "Equipment",
        summary: "Weapons, armour, adventuring gear and tools.",
        plans: ["Costs, weights, damage and properties for every item."],
      },
      {
        slug: "magic-items",
        title: "Magic items",
        summary: "Wondrous items, magic weapons, potions and more.",
        plans: ["Search by rarity and type, with the full description of each item."],
      },
    ],
  },
  {
    key: "create-solo-adventure",
    mode: "dm",
    path: "dm/solo-adventures",
    title: "Create Solo Adventure",
    blurb: "Write text adventures for players to take their characters on.",
    icon: <ScrollIcon />,
    cover: "slate",
    sealed: true,
    pages: [],
  },
  {
    key: "homebrew",
    mode: "dm",
    path: "dm/homebrew",
    title: "Create Homebrew",
    blurb: "Write your own spells, items and monsters.",
    icon: <QuillIcon />,
    cover: "ochre",
    sealed: true,
    pages: [],
  },
];

export function sectionsFor(mode: Mode): SectionDef[] {
  return SECTIONS.filter((s) => s.mode === mode);
}
