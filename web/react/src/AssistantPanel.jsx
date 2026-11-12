// Drop-in assistant panel. Uses your app's auth via the `headers` prop; no global state.
//
//   <AssistantPanel endpoint="/chat" headers={() => ({ Authorization: `Bearer ${session.token}` })}
//                   customerId={session.customerId} />
import { useEffect, useRef, useState } from "react";
import { useChatStream } from "./useChatStream.js";
import "./AssistantPanel.css";

function Sources({ sources }) {
  const [open, setOpen] = useState(false);
  if (!sources.length) return null;
  return (
    <>
      <button type="button" className="rag-toggle" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {open ? "Hide sources" : `Sources (${sources.length})`}
      </button>
      {open && (
        <ul className="rag-sources">
          {sources.map((s) => (
            <li key={s.n}>
              <b>[{s.n}] {s.label}</b>
              <small>{s.excerpt}</small>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Turn({ turn }) {
  const f = turn.final;
  return (
    <div className="rag-turn">
      <div className="rag-q">{turn.question}</div>
      {turn.error ? (
        <div className="rag-error">{turn.error}</div>
      ) : (
        <div className={`rag-a${f?.refused ? " rag-refused" : ""}`}>
          {turn.answer || <span className="rag-typing">…</span>}
        </div>
      )}
      {f && (
        <div className="rag-meta">
          <Sources sources={f.sources} />
          {f.refused && <span className="rag-badge">Not in your documents</span>}
          {!f.grounded && <span className="rag-flag">⚠ no valid citation</span>}
          <span>first token {f.first_token_ms} ms</span>
        </div>
      )}
    </div>
  );
}

export function AssistantPanel({ endpoint = "/chat", headers, customerId, title = "Ask your documents" }) {
  const { turns, busy, ask } = useChatStream({ endpoint, headers, customerId });
  const [q, setQ] = useState("");
  const logRef = useRef(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [turns]);

  const submit = (e) => {
    e.preventDefault();
    ask(q);
    setQ("");
  };

  return (
    <section className="rag-panel" aria-label={title}>
      <header className="rag-head">{title}</header>
      <div className="rag-log" ref={logRef} aria-live="polite">
        {turns.length === 0 && (
          <p className="rag-empty">Answers come only from your records and documents, with sources.</p>
        )}
        {turns.map((t) => (
          <Turn key={t.id} turn={t} />
        ))}
      </div>
      <form className="rag-form" onSubmit={submit}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. What is the late fee on rent?"
          aria-label="Your question"
          autoComplete="off"
        />
        <button disabled={busy || !q.trim()}>{busy ? "…" : "Ask"}</button>
      </form>
    </section>
  );
}
