import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";

interface Email {
  id: number;
  to: string;
  subject: string;
  body: string;
  link: string | null;
  created_at: string;
}

/** Development-only inbox: every "sent" email lands here instead of a real inbox. */
export function Mailbox() {
  const [params] = useSearchParams();
  const to = params.get("to") ?? "";
  const [emails, setEmails] = useState<Email[] | null>(null);
  const [disabled, setDisabled] = useState(false);

  const load = useCallback(async () => {
    const res = await api.get<{ emails: Email[] }>(`/api/dev/mailbox?to=${encodeURIComponent(to)}`);
    if (res.status === 404) setDisabled(true);
    else if (res.ok) setEmails(res.data.emails);
  }, [to]);

  useEffect(() => {
    void load();
  }, [load]);

  if (disabled) return <p className="card narrow center">The dev mailbox is turned off on this server.</p>;

  return (
    <section className="card">
      <div className="row between">
        <h1>Dev mailbox</h1>
        <button type="button" className="btn ghost small"
          onClick={async () => { await api.delete("/api/dev/mailbox"); await load(); }}>
          Clear mailbox
        </button>
      </div>
      <p className="muted">
        No real emails are sent while developing. {to ? <>Showing emails to <strong>{to}</strong>.</> : "Showing the latest 50 emails."}
      </p>
      {emails?.length === 0 && <p className="muted" data-testid="empty-state">The mailbox is empty.</p>}
      <ul className="mail-list">
        {emails?.map((m) => (
          <li key={m.id} className="mail" data-testid="email">
            <div className="row between">
              <strong>{m.subject}</strong>
              <span className="muted small">{new Date(m.created_at).toLocaleString()}</span>
            </div>
            <p className="muted small">To: {m.to}</p>
            <p className="mail-body">{m.body}</p>
            {m.link && (
              <a href={m.link} data-testid="email-link">{m.link}</a>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function NotFound() {
  return (
    <section className="card narrow center">
      <h1>Page not found</h1>
      <p className="muted">This page is lost somewhere in the Underdark.</p>
    </section>
  );
}
