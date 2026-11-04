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
          "Bring a character: it plays as its own copy, with any notes your DM left on it.",
          "Track hit points and level up in the campaign.",
        ],
      },
      {
        slug: "parties",
        title: "Parties",
        summary: "The adventuring parties you belong to, and their chat.",
        plans: [
          "Accept or decline invitations from Dungeon Masters.",
          "Chat with your party on enchanted parchment.",
          "Suggest your friends to the party's Dungeon Master.",
        ],
      },
      {
        slug: "find",
        title: "Find a party",
        summary: "Public parties looking for players. Ask to join and the Dungeon Master decides.",
        plans: ["Search the public parties and ask to join, with a note for the Dungeon Master."],
      },
      {
        slug: "friends",
        title: "Friends",
        summary: "Find other adventurers, send friend requests, and keep your friends close.",
        plans: ["Search for adventurers by name and send friend requests.", "Accept or decline requests sent to you."],
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
          "Choose which of the character's level roadmaps to include: none, some or all.",
          "See how many players copied each one, and unpublish at any time.",
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
          "Chat with your party on enchanted parchment.",
          "Invite your friends without typing their email.",
        ],
      },
      {
        slug: "requests",
        title: "Join requests",
        summary: "Adventurers asking to join one of your parties.",
        plans: [
          "Players find your public parties and ask to join; your players suggest their friends.",
          "Accept or decline each request, and get an email when a new one arrives.",
        ],
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
        summary: "Every spell in the System Reference Document, with your favourites starred.",
        plans: [
          "Search and filter by level, school, class, concentration and ritual.",
          "Read each spell's full rules text.",
          "Star your favourite spells; they're starred in the character builder too.",
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
          "Add collections to a campaign's encounters.",
        ],
      },
      {
        slug: "environments",
        title: "Environments",
        summary: "Where your monsters live. The SRD doesn't say, so you decide.",
        plans: ["Make environments such as “Underdark” and filter the bestiary by them."],
      },
      {
        slug: "items",
        title: "Items",
        summary: "Equipment and magic items from the System Reference Document, with your favourites starred.",
        plans: [
          "Search and filter by kind, category and rarity.",
          "Read each item's full description: damage, armour class, cost, weight and magic.",
          "Star your favourite items; they come first in the character builder's item picker.",
        ],
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
