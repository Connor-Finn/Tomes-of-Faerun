import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { MODE_LABELS, useMode, type Mode } from "../lib/mode";
import { sectionsFor } from "../lib/sections";

const MODE_OPTIONS: { mode: Mode; hint: string }[] = [
  { mode: "player", hint: "Play your characters" },
  { mode: "dm", hint: "Run the table" },
];

const SHELF_TITLES: Record<Mode, string> = {
  player: "The adventurer's shelf",
  dm: "The Dungeon Master's shelf",
};

/** The hub: pick a mode, then take a tome off the shelf. */
export function GuildHall() {
  const { user } = useAuth();
  const { mode, setMode } = useMode();
  if (!user) return null;

  return (
    <div className="guild-hall">
      <header className="guild-hall-header">
        <p className="eyebrow">Pull up a chair, {user.name}</p>
        <h1>The Guild Hall</h1>
        <p className="lead">Choose how you're playing tonight, then take a tome from the shelf.</p>
      </header>

      <fieldset className="mode-switch" data-testid="mode-switch">
        <legend className="sr-only">Mode</legend>
        {MODE_OPTIONS.map(({ mode: option, hint }) => (
          <label key={option} className="mode-option">
            <input
              type="radio"
              name="mode"
              value={option}
              checked={mode === option}
              onChange={() => setMode(option)}
            />
            <span className="mode-name">{MODE_LABELS[option]}</span>
            <span className="mode-hint">{hint}</span>
          </label>
        ))}
      </fieldset>

      <section aria-labelledby="shelf-heading" className="shelf-section">
        <h2 id="shelf-heading" className="section-title">
          {SHELF_TITLES[mode]}
        </h2>
        <ul className="shelf" data-testid="shelf">
          {sectionsFor(mode).map((s) => (
            <li key={s.key}>
              <Link
                to={`/${s.path}`}
                className={`book cover-${s.cover}${s.sealed ? " sealed" : ""}`}
                data-testid="tome-cover"
              >
                <span className="book-icon">{s.icon}</span>
                <span className="book-title">{s.title}</span>
                <span className="book-blurb">{s.blurb}</span>
                {s.sealed && <span className="book-seal">Sealed</span>}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
