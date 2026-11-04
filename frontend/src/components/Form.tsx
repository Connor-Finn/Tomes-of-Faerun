import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";
import type { FieldErrors } from "../lib/api";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  name: string;
  error?: string;
  hint?: ReactNode;
}

/** A labelled input with an accessible error message underneath. */
export function TextField({ label, name, error, hint, id, ...rest }: FieldProps) {
  const autoId = useId();
  const inputId = id ?? `${name}-${autoId}`;
  const errorId = `${inputId}-error`;
  return (
    <div className="field">
      <label htmlFor={inputId}>{label}</label>
      <input
        id={inputId}
        name={name}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        {...rest}
      />
      {hint}
      <FieldError id={errorId} field={name} error={error} />
    </div>
  );
}

/** Password input with a Show/Hide toggle. */
export function PasswordField({ label, name, error, hint, id, ...rest }: FieldProps) {
  const [visible, setVisible] = useState(false);
  const autoId = useId();
  const inputId = id ?? `${name}-${autoId}`;
  const errorId = `${inputId}-error`;
  return (
    <div className="field">
      <label htmlFor={inputId}>{label}</label>
      <div className="password-wrap">
        <input
          id={inputId}
          name={name}
          type={visible ? "text" : "password"}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          {...rest}
        />
        <button
          type="button"
          className="btn ghost small"
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          onClick={() => setVisible((v) => !v)}
        >
          {visible ? "Hide" : "Show"}
        </button>
      </div>
      {hint}
      <FieldError id={errorId} field={name} error={error} />
    </div>
  );
}

export function FieldError({ id, field, error }: { id: string; field: string; error?: string }) {
  if (!error) return null;
  return (
    <p className="field-error" id={id} data-testid={`error-${field}`}>
      {error}
    </p>
  );
}

/** "Please fix the highlighted fields" box shown above a form after a failed submit. */
export function ErrorSummary({ errors, message }: { errors: FieldErrors; message?: string }) {
  const count = Object.keys(errors).length;
  if (!count && !message) return null;
  return (
    <div className="form-error-summary" role="alert" data-testid="form-error-summary">
      {message ?? "Please fix the highlighted fields."}
      {count > 0 && (
        <span className="muted">
          {" "}
          ({count} {count === 1 ? "problem" : "problems"})
        </span>
      )}
    </div>
  );
}
