import { useCallback, useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { api } from "../../lib/api";
import {
  CHAT_POLL_MS,
  MESSAGE_MAX,
  WRITING_PING_MS,
  chatTime,
  writingLine,
  type ChatMessage,
  type ChatPage,
} from "../../lib/chat";
import { ConfirmDialog } from "../bestiary/ConfirmDialog";

/** How long struck-out ink takes to fade before the message leaves the page (matches the CSS). */
const FADE_MS = 1100;

/**
 * Merge the latest page from the server into what's on the page.
 * Messages older than the page are kept (they came from "turn back the page"); anything inside the
 * page's range that the server no longer has was struck out, so it starts fading.
 */
function merge(prev: ChatMessage[], latest: ChatMessage[]): { next: ChatMessage[]; gone: number[]; added: number[] } {
  const latestIds = new Set(latest.map((m) => m.id));
  const floor = latest.length > 0 ? latest[0].id : -Infinity;
  const prevIds = new Set(prev.map((m) => m.id));
  const gone: number[] = [];
  const kept = prev.map((m) => {
    if (m.id < floor) return m;
    if (!latestIds.has(m.id)) gone.push(m.id);
    return latest.find((l) => l.id === m.id) ?? m;
  });
  const added = latest.filter((m) => !prevIds.has(m.id));
  return { next: [...kept, ...added].sort((a, b) => a.id - b.id), gone, added: added.map((m) => m.id) };
}

/**
 * A party's chat, written on enchanted parchment: new words ink in one by one, old lines fade as
 * they drift up the page, and struck-out messages dissolve. Polls the server every couple of seconds.
 */
export function PartyChat({ partyId }: { partyId: number }) {
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [writing, setWriting] = useState<string[]>([]);
  const [firstUnread, setFirstUnread] = useState<number | null>(null);
  const [inking, setInking] = useState<Set<number>>(new Set());
  const [fading, setFading] = useState<Set<number>>(new Set());
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [newBelow, setNewBelow] = useState(false);
  const [striking, setStriking] = useState<ChatMessage | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const pageRef = useRef<HTMLOListElement>(null);
  const messagesRef = useRef<ChatMessage[] | null>(null);
  const lastPing = useRef(0);
  const stickToBottom = useRef(true);
  const keepOffset = useRef<number | null>(null);
  messagesRef.current = messages;

  const fadeOut = useCallback((ids: number[]) => {
    if (ids.length === 0) return;
    setFading((f) => new Set([...f, ...ids]));
    window.setTimeout(() => {
      setMessages((ms) => ms?.filter((m) => !ids.includes(m.id)) ?? ms);
      setFading((f) => new Set([...f].filter((id) => !ids.includes(id))));
    }, FADE_MS);
  }, []);

  const nearBottom = () => {
    const el = pageRef.current;
    return !el || el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  const poll = useCallback(async () => {
    const res = await api.get<ChatPage>(`/api/parties/${partyId}/messages`);
    if (!res.ok) {
      setLoadError(res.status === 404 ? "You're no longer in this party." : (res.data.error ?? "The parchment went blank."));
      return;
    }
    setLoadError(null);
    setWriting(res.data.writing);
    const prev = messagesRef.current;
    if (prev === null) {
      // First look: everything appears at once; only later arrivals ink in word by word.
      setMessages(res.data.messages);
      setHasMore(res.data.has_more);
      const unread = res.data.messages.find((m) => m.id > res.data.last_read_id && !m.mine);
      setFirstUnread(unread ? unread.id : null);
      return;
    }
    const { next, gone, added } = merge(prev, res.data.messages);
    const fresh = added.filter((id) => !next.find((m) => m.id === id)?.mine);
    stickToBottom.current = nearBottom();
    if (added.length > 0 || gone.length > 0) setMessages(next);
    if (fresh.length > 0) {
      setInking((s) => new Set([...s, ...fresh]));
      if (!stickToBottom.current) setNewBelow(true);
    }
    fadeOut(gone.filter((id) => !fading.has(id)));
  }, [partyId, fadeOut, fading]);

  // Poll while the tab is visible.
  const pollRef = useRef(poll);
  pollRef.current = poll;
  useEffect(() => {
    let alive = true;
    let timer = 0;
    const tick = async () => {
      if (!document.hidden) await pollRef.current();
      if (alive) timer = window.setTimeout(tick, CHAT_POLL_MS);
    };
    void tick();
    const wake = () => {
      if (!document.hidden) void pollRef.current();
    };
    document.addEventListener("visibilitychange", wake);
    return () => {
      alive = false;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", wake);
    };
  }, [partyId]);

  // Keep the newest writing in view, unless the reader has scrolled back to read older lines.
  useLayoutEffect(() => {
    const el = pageRef.current;
    if (!el || messages === null) return;
    if (keepOffset.current !== null) {
      el.scrollTop = el.scrollHeight - keepOffset.current;
      keepOffset.current = null;
    } else if (stickToBottom.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]);

  async function olderPage() {
    const first = messages?.[0];
    if (!first) return;
    const res = await api.get<ChatPage>(`/api/parties/${partyId}/messages?before=${first.id}`);
    if (!res.ok) return;
    const el = pageRef.current;
    keepOffset.current = el ? el.scrollHeight - el.scrollTop : null;
    setMessages((ms) => [...res.data.messages, ...(ms ?? [])]);
    setHasMore(res.data.has_more);
  }

  function onType(value: string) {
    setDraft(value);
    setError(null);
    const now = Date.now();
    if (value.trim() && now - lastPing.current > WRITING_PING_MS) {
      lastPing.current = now;
      void api.post(`/api/parties/${partyId}/writing`);
    }
  }

  async function send(e?: FormEvent) {
    e?.preventDefault();
    if (!draft.trim()) {
      setError("Write something first.");
      return;
    }
    setSending(true);
    const res = await api.post<{ message: ChatMessage }>(`/api/parties/${partyId}/messages`, { body: draft });
    setSending(false);
    if (!res.ok) {
      setError(res.data.errors?.body ?? res.data.error ?? "The ink wouldn't take.");
      return;
    }
    const mine = res.data.message;
    lastPing.current = 0;
    setDraft("");
    setFirstUnread(null);
    stickToBottom.current = true;
    setNewBelow(false);
    setMessages((ms) => (ms?.some((m) => m.id === mine.id) ? ms : [...(ms ?? []), mine]));
    setInking((s) => new Set([...s, mine.id]));
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send();
    }
  }

  function toBottom() {
    const el = pageRef.current;
    if (el) el.scrollTop = el.scrollHeight;
    setNewBelow(false);
  }

  return (
    <section className="magic-paper" aria-labelledby="chat-title" data-testid="party-chat">
      <h3 id="chat-title" className="magic-paper-title">
        Party chat
      </h3>
      <p className="magic-paper-hint">Words written here appear on every party member's parchment.</p>

      {loadError && (
        <p className="form-error-summary" role="alert">
          {loadError}
        </p>
      )}

      <div className="magic-paper-page">
        <ol
          ref={pageRef}
          className="chat-lines"
          role="log"
          aria-live="polite"
          aria-label="Party chat messages"
          data-testid="chat-log"
          onScroll={() => {
            if (nearBottom()) setNewBelow(false);
          }}
        >
          {hasMore && (
            <li className="chat-older">
              <button type="button" className="btn ghost small" onClick={olderPage}>
                Turn back the page
              </button>
            </li>
          )}
          {messages === null && !loadError && <li className="chat-blank">The ink is settling…</li>}
          {messages?.length === 0 && (
            <li className="chat-blank" data-testid="chat-empty">
              The parchment is blank. Write the first words.
            </li>
          )}
          {messages?.map((m) => (
            <ChatLine
              key={m.id}
              message={m}
              unreadMark={m.id === firstUnread}
              inking={inking.has(m.id)}
              fading={fading.has(m.id)}
              onStrike={() => setStriking(m)}
            />
          ))}
        </ol>
        {newBelow && (
          <button type="button" className="chat-new-below" onClick={toBottom}>
            New writing below ↓
          </button>
        )}
      </div>

      <p className={`chat-writing${writing.length ? " on" : ""}`} data-testid="chat-writing" aria-live="polite">
        {writingLine(writing)}
      </p>

      <form className="chat-compose" onSubmit={send} aria-label="Write to your party">
        <label htmlFor="chat-message" className="sr-only">
          Your message
        </label>
        <textarea
          id="chat-message"
          rows={2}
          maxLength={MESSAGE_MAX}
          value={draft}
          placeholder="Dip your quill and write…"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "chat-error" : "chat-help"}
          onChange={(e) => onType(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <button type="submit" className="btn primary" disabled={sending}>
          Write
        </button>
      </form>
      {error ? (
        <p className="field-error" id="chat-error" data-testid="chat-error">
          {error}
        </p>
      ) : (
        <p className="hint" id="chat-help">
          Enter to write, Shift+Enter for a new line.
        </p>
      )}

      {striking && (
        <ConfirmDialog
          title="Strike out this message?"
          confirmLabel="Strike out"
          onClose={() => setStriking(null)}
          onConfirm={async () => {
            const res = await api.delete<{ message: string }>(`/api/parties/${partyId}/messages/${striking.id}`);
            if (!res.ok && res.status !== 404) return res.data.error ?? "The ink wouldn't lift.";
            fadeOut([striking.id]);
          }}
        >
          <blockquote className="chat-quote">{striking.body}</blockquote>
          <p>The ink fades from everyone's parchment, and it can't be brought back.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}

function ChatLine({
  message: m,
  unreadMark,
  inking,
  fading,
  onStrike,
}: {
  message: ChatMessage;
  unreadMark: boolean;
  inking: boolean;
  fading: boolean;
  onStrike: () => void;
}) {
  const who = m.author?.name ?? "A departed adventurer";
  const ink = m.mine ? "mine" : m.from_dm ? "dm" : "other";
  // Each word inks in a moment after the last, like writing appearing on its own.
  const words = m.body.split(/(\s+)/);
  return (
    <>
      {unreadMark && (
        <li className="chat-unread" data-testid="chat-unread">
          <span>New since you last looked</span>
        </li>
      )}
      <li
        className={`chat-line ink-${ink}${inking ? " inking" : ""}${fading ? " fading" : ""}`}
        data-testid="chat-message"
        aria-hidden={fading || undefined}
      >
        <p className="chat-meta">
          <span className="chat-author" data-testid="chat-author">
            {m.mine ? "You" : who}
          </span>
          {m.from_dm && <span className="chat-dm-tag">Dungeon Master</span>}
          <time className="chat-time" dateTime={m.created_at}>
            {chatTime(m.created_at)}
          </time>
          {m.can_strike && !fading && (
            <button
              type="button"
              className="chat-strike"
              aria-label={m.mine ? "Strike out your message" : `Strike out ${who}'s message`}
              onClick={onStrike}
            >
              Strike out
            </button>
          )}
        </p>
        <p className="chat-body" data-testid="chat-body">
          {inking
            ? words.map((w, i) =>
                /^\s+$/.test(w) ? (
                  w
                ) : (
                  <span key={i} className="ink-word" style={{ animationDelay: `${Math.min(i, 120) * 45}ms` }}>
                    {w}
                  </span>
                ),
              )
            : m.body}
        </p>
      </li>
    </>
  );
}
