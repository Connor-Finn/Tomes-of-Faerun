import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

/** A modal "are you sure?" for things that can't be undone. */
export function ConfirmDialog({
  title,
  children,
  confirmLabel,
  cancelLabel = "Keep it",
  onConfirm,
  onClose,
}: {
  title: string;
  children: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  /** Return an error message to keep the dialog open, or nothing when it worked. */
  onConfirm: () => Promise<string | void>;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const problem = await onConfirm();
    if (problem) setError(problem);
    else ref.current?.close();
  }

  return (
    <dialog ref={ref} className="modal" aria-labelledby="confirm-title" onClose={onClose}>
      <form onSubmit={onSubmit}>
        <h2 id="confirm-title">{title}</h2>
        {children}
        {error && (
          <p className="form-error-summary" role="alert">
            {error}
          </p>
        )}
        <div className="row end">
          <button type="button" className="btn ghost" onClick={() => ref.current?.close()}>
            {cancelLabel}
          </button>
          <button type="submit" className="btn danger">
            {confirmLabel}
          </button>
        </div>
      </form>
    </dialog>
  );
}
