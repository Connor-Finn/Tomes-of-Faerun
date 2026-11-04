const RULES = [
  { key: "length", label: "At least 8 characters", test: (pw: string) => pw.length >= 8 },
  { key: "upper", label: "An uppercase letter", test: (pw: string) => /[A-Z]/.test(pw) },
  { key: "lower", label: "A lowercase letter", test: (pw: string) => /[a-z]/.test(pw) },
  { key: "number", label: "A number", test: (pw: string) => /\d/.test(pw) },
  { key: "special", label: "A special character", test: (pw: string) => /[^A-Za-z0-9]/.test(pw) },
];

const LABELS = ["Too short", "Weak", "Weak", "Fair", "Good", "Strong"];

export function passwordScore(pw: string): number {
  if (!pw) return 0;
  return Math.max(1, RULES.filter((r) => r.test(pw)).length);
}

/** Live strength meter and rules checklist (mirrors the server's rules). */
export function PasswordStrength({ password }: { password: string }) {
  const score = passwordScore(password);
  return (
    <div className="strength" aria-live="polite">
      <div className="strength-bar" data-score={score}>
        <span style={{ width: `${(score / RULES.length) * 100}%` }} />
      </div>
      <p className="strength-text">
        Strength: <strong data-testid="strength-label">{LABELS[score]}</strong>
      </p>
      <ul className="rules">
        {RULES.map((r) => {
          const met = r.test(password);
          return (
            <li key={r.key} data-rule={r.key} className={met ? "met" : undefined}>
              <span aria-hidden="true">{met ? "✓" : "○"}</span> {r.label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
