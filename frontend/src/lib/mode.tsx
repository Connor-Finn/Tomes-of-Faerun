import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

/**
 * Player Mode or Dungeon Master Mode.
 *
 * The mode decides which tomes the guild hall shelf shows. It is a viewing preference, not a permission:
 * anyone can run a campaign as a DM and play in someone else's as a player. It is remembered per
 * browser, and opening any section page (e.g. a deep link to /dm/tomes) switches to that section's mode.
 */
export type Mode = "player" | "dm";

export const MODE_LABELS: Record<Mode, string> = {
  player: "Player Mode",
  dm: "Dungeon Master Mode",
};

const STORAGE_KEY = "tof.mode";

function readStoredMode(): Mode {
  try {
    return localStorage.getItem(STORAGE_KEY) === "dm" ? "dm" : "player";
  } catch {
    return "player"; // storage can be blocked (private windows, strict settings)
  }
}

interface ModeState {
  mode: Mode;
  setMode: (mode: Mode) => void;
}

const ModeContext = createContext<ModeState | null>(null);

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<Mode>(readStoredMode);

  const setMode = useCallback((next: Mode) => {
    setModeState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* the mode still works for this visit */
    }
  }, []);

  const value = useMemo(() => ({ mode, setMode }), [mode, setMode]);
  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export function useMode(): ModeState {
  const ctx = useContext(ModeContext);
  if (!ctx) throw new Error("useMode must be used inside <ModeProvider>");
  return ctx;
}

/** Switch to `mode` when a page belonging to that mode opens. */
export function useEnterMode(mode: Mode) {
  const { mode: current, setMode } = useMode();
  useEffect(() => {
    if (current !== mode) setMode(mode);
  }, [current, mode, setMode]);
}
