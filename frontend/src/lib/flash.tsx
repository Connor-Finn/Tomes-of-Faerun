import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

export type FlashKind = "success" | "info" | "warning" | "error";
interface Flash {
  id: number;
  kind: FlashKind;
  message: string;
  /** True until the flash has survived one page change. */
  carry: boolean;
}

interface FlashState {
  flashes: Flash[];
  /**
   * Show a banner message. Pass `{ afterNavigate: true }` when you are about to
   * redirect, so the message shows on the page you land on (like "Welcome back!").
   */
  flash: (kind: FlashKind, message: string, opts?: { afterNavigate?: boolean }) => void;
  dismiss: (id: number) => void;
}

const FlashContext = createContext<FlashState | null>(null);
let nextId = 1;

export function FlashProvider({ children }: { children: ReactNode }) {
  const [flashes, setFlashes] = useState<Flash[]>([]);
  const location = useLocation();

  // On every page change drop old messages and keep the ones meant for the new page.
  useEffect(() => {
    setFlashes((current) => current.filter((f) => f.carry).map((f) => ({ ...f, carry: false })));
  }, [location.key]);

  const flash = useCallback<FlashState["flash"]>((kind, message, opts) => {
    const item = { id: nextId++, kind, message, carry: Boolean(opts?.afterNavigate) };
    setFlashes((current) => [...current.filter((f) => f.message !== message), item]);
  }, []);

  const dismiss = useCallback((id: number) => setFlashes((current) => current.filter((f) => f.id !== id)), []);

  return <FlashContext.Provider value={{ flashes, flash, dismiss }}>{children}</FlashContext.Provider>;
}

export function useFlash(): FlashState {
  const ctx = useContext(FlashContext);
  if (!ctx) throw new Error("useFlash must be used inside <FlashProvider>");
  return ctx;
}

export function Flashes() {
  const { flashes, dismiss } = useFlash();
  if (!flashes.length) return null;
  return (
    <div className="flashes">
      {flashes.map((f) => (
        <div key={f.id} className={`flash flash-${f.kind}`} role={f.kind === "error" ? "alert" : "status"}>
          <span data-testid={`flash-${f.kind}`}>{f.message}</span>
          <button type="button" className="flash-close" aria-label="Dismiss message" onClick={() => dismiss(f.id)}>
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
