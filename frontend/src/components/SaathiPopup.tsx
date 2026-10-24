import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { AssistantReply } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { AgentBadge, AgentThinking } from "./Saathi";

type Msg = { role: "user" | "assistant"; content: string; reply?: AssistantReply };

const SIGNED_IN = ["Where are my orders?", "What should I do next?", "Any offers for me?"];
const ANYONE = ["What can I carry to Dubai?", "How much does it cost?", "Parcels going to London?"];

/** Floating Saathi assistant: ask anything about your orders or the marketplace from any page. */
export function SaathiPopup() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs, busy, open]);

  const ask = async (message: string) => {
    const q = message.trim();
    if (!q || busy) return;
    const history = msgs.slice(-10).map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { role: "user", content: q }]);
    setText("");
    setBusy(true);
    try {
      const reply = await api<AssistantReply>("/agents/assistant", { method: "POST", json: { message: q, history } });
      setMsgs((m) => [...m, { role: "assistant", content: reply.reply, reply }]);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Saathi is unavailable right now.";
      setMsgs((m) => [...m, { role: "assistant", content: `Sorry — ${msg}` }]);
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    ask(text);
  };

  const suggestions = user ? [...SIGNED_IN, ANYONE[0]] : ANYONE;

  return (
    <>
      {open && (
        <div className="popup" role="dialog" aria-label="Ask Saathi">
          <div className="popup-head">
            <div>
              <strong>✨ Ask Saathi</strong>
              <div className="small">Orders, status, prices — just ask</div>
            </div>
            <button className="popup-x" onClick={() => setOpen(false)} aria-label="Close">
              ×
            </button>
          </div>
          <div className="popup-log" ref={logRef}>
            {msgs.length === 0 && (
              <div className="muted small">
                <p>
                  Hi{user ? ` ${user.name.split(" ")[0]}` : ""}! I can tell you where your parcels and requests are, what
                  to do next, and what's waiting to be carried on any route.
                </p>
                {!user && <p>Log in to ask about your own orders.</p>}
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`bubble ${m.role}`}>
                <p>{m.content}</p>
                {m.reply && m.reply.links.length > 0 && (
                  <div className="row gap wrap">
                    {m.reply.links.map((l) => (
                      <button
                        key={l.ref}
                        className="chip chip-sm"
                        onClick={() => {
                          navigate(l.path);
                          setOpen(false);
                        }}
                      >
                        {l.label} →
                      </button>
                    ))}
                  </div>
                )}
                {m.reply?.escalate && <p className="small">🙋 A SaathiGo team member will follow up.</p>}
                {m.reply && (
                  <div className="popup-meta">
                    <AgentBadge meta={m.reply.agent} />
                  </div>
                )}
              </div>
            ))}
            {busy && <AgentThinking agents={["tracking_support"]} label="Saathi is looking it up…" />}
          </div>
          {msgs.length === 0 && (
            <div className="popup-suggest">
              {suggestions.map((s) => (
                <button key={s} className="chip chip-sm" onClick={() => ask(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}
          <form className="chat-input" onSubmit={submit}>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about any order…" maxLength={1000} />
            <button className="btn btn-sm" disabled={busy || !text.trim()}>
              Ask
            </button>
          </form>
        </div>
      )}
      <button className="popup-fab" onClick={() => setOpen((o) => !o)} aria-label={open ? "Close Saathi" : "Ask Saathi"}>
        {open ? "×" : "✨"}
      </button>
    </>
  );
}
