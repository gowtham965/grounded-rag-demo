// Streams answers from POST /chat (Server-Sent Events) into React state.
// Events: {type:"token", text} ... then {type:"final", answer, sources, refused, grounded, ...}
//         or {type:"error", message}.
import { useCallback, useRef, useState } from "react";

async function errorText(res) {
  try {
    const body = await res.json();
    const d = body.detail;
    return typeof d === "string" ? d : JSON.stringify(d);
  } catch {
    return res.statusText;
  }
}

// Parses an SSE byte stream, calling onEvent for each `data:` JSON payload.
async function readEvents(body, onEvent) {
  const reader = body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const line = buf.slice(0, i);
      buf = buf.slice(i + 2);
      if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)));
    }
  }
}

/**
 * @param {object} opts
 * @param {string} opts.endpoint      URL of the /chat endpoint
 * @param {() => object} opts.headers Returns auth headers (e.g. from your app's session)
 * @param {string} opts.customerId    Demo only: in production the server takes it from the session
 */
export function useChatStream({ endpoint = "/chat", headers = () => ({}), customerId }) {
  const [turns, setTurns] = useState([]);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  const update = (id, patch) =>
    setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, ...(typeof patch === "function" ? patch(t) : patch) } : t)));

  const ask = useCallback(
    async (question) => {
      if (busyRef.current || !question.trim()) return;
      busyRef.current = true;
      setBusy(true);
      const id = crypto.randomUUID();
      setTurns((ts) => [...ts, { id, question, answer: "", final: null, error: null }]);
      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...headers() },
          body: JSON.stringify({ customer_id: customerId, question }),
        });
        if (!res.ok) {
          update(id, { error: `Error ${res.status}: ${await errorText(res)}` });
          return;
        }
        await readEvents(res.body, (ev) => {
          if (ev.type === "token") update(id, (t) => ({ answer: t.answer + ev.text }));
          else if (ev.type === "final") update(id, { answer: ev.answer, final: ev });
          else if (ev.type === "error") update(id, { error: `Something went wrong (${ev.message}). Please try again.` });
        });
      } catch (e) {
        update(id, { error: `Network error: ${e.message}` });
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [endpoint, headers, customerId],
  );

  const clear = useCallback(() => setTurns([]), []);
  return { turns, busy, ask, clear };
}
