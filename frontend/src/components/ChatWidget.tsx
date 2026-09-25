import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { SERVICES, SUB_MENUS } from "./serviceMenus";
import "./ChatWidget.css";

export interface ChatSource {
  id: number;
  title: string | null;
  score: number;
}

export interface TenderResult {
  pbid: string | null;
  tender_no?: string | null;
  description: string | null;
  agency: string | null;
  state: string | null;
  city: string | null;
  value: string | number | null;
  due_date: string | null;
  open_date: string | null;
  source: string | null;
  link?: string | null;
}

interface ChatMsg {
  role: "user" | "bot";
  text: string;
  sources?: ChatSource[];
  tenders?: TenderResult[];
}

interface ChatWidgetProps {
  /** Base URL of the backend. Default "" = same origin (works behind the
   *  Vite proxy in dev and when served by the backend in prod).
   *  Override with e.g. http://127.0.0.1:8000 when embedding cross-origin. */
  apiBase?: string;
  title?: string;
  greeting?: string;
  tenantId?: string;
  /** Name + 10-digit mobile gate before chatting (same as legacy widget). */
  requireLead?: boolean;
}

type MenuView = null | { level: "services" } | { level: "sub"; menuKey: string };

const DEFAULT_GREETING =
  "Namaste! 🙏 Welcome to ProBid Consultants LLP.\nI'm Probee, your Government Tender & GeM portal assistant.\nHow can I help you today?";

function getSessionId(): string {
  const KEY = "rag_session_id";
  try {
    let s = localStorage.getItem(KEY);
    if (!s) {
      s = "s_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(KEY, s);
    }
    return s;
  } catch {
    return "s_anon_" + Date.now().toString(36);
  }
}

function leadFlag(sessionId: string): string {
  return `probee_lead_${sessionId}`;
}

function httpErrorMessage(err: unknown): string {
  const s = err instanceof Error ? `${err.name} ${err.message}` : String(err);
  if (s.includes("Failed to fetch") || s.includes("NetworkError")) {
    return "Cannot reach the server. Check your connection.";
  }
  if (s.includes("HTTP 401") || s.includes("401")) {
    return "Session expired. Please refresh.";
  }
  if (s.includes("HTTP 500") || s.includes("500")) {
    return "Server error. Please try again in a moment.";
  }
  const m = s.match(/HTTP (\d+)/);
  if (m) return `Server returned an error (${m[1]}).`;
  return "Sorry, something went wrong.";
}

function formatINR(v: string | number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const n = Number(String(v).replace(/[^0-9.]/g, ""));
  if (!isNaN(n) && n > 0) return "₹ " + n.toLocaleString("en-IN");
  return "—";
}

/** Tiny safe renderer: **bold**, paragraphs, "- " / "1. " lists.
 *  No dangerouslySetInnerHTML — everything stays as React text nodes. */
function renderRich(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let bullets: string[] = [];
  let numbered: string[] = [];
  const flush = (key: string) => {
    if (bullets.length > 0) {
      out.push(
        <ul key={`${key}-ul`}>
          {bullets.map((b, j) => (
            <li key={j}>{inlineBold(b)}</li>
          ))}
        </ul>
      );
      bullets = [];
    }
    if (numbered.length > 0) {
      out.push(
        <ol key={`${key}-ol`}>
          {numbered.map((b, j) => (
            <li key={j}>{inlineBold(b)}</li>
          ))}
        </ol>
      );
      numbered = [];
    }
  };
  text.split("\n").forEach((ln, i) => {
    const t = ln.trim();
    if (t.startsWith("- ")) {
      if (numbered.length > 0) flush(`n${i}`);
      bullets.push(t.slice(2));
    } else if (/^\d+\.\s/.test(t)) {
      if (bullets.length > 0) flush(`b${i}`);
      numbered.push(t.replace(/^\d+\.\s/, ""));
    } else {
      flush(`f${i}`);
      if (t === "") {
        out.push(<br key={i} />);
      } else {
        out.push(
          <p key={i} style={{ margin: "0 0 6px" }}>
            {inlineBold(t)}
          </p>
        );
      }
    }
  });
  flush("end");
  return out;
}

function inlineBold(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") && p.length > 4 ? (
      <strong key={i}>{p.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}

function TenderTable({ tenders }: { tenders: TenderResult[] }) {
  return (
    <div className="cw-tender-wrap">
      <table className="cw-tender-table">
        <thead>
          <tr>
            <th>PBID</th>
            <th>Tender Description</th>
            <th>Agency</th>
            <th>State</th>
            <th>Tender Value</th>
            <th>Due Date</th>
            <th>Open Date</th>
          </tr>
        </thead>
        <tbody>
          {tenders.map((t, i) => {
            const desc = (t.description || "").replace(/\s+/g, " ").trim();
            const shortDesc = desc.length > 120 ? desc.slice(0, 120) + "…" : desc;
            const place = [t.city, t.state].filter(Boolean).join(", ");
            return (
              <tr key={i}>
                <td className="t-pbid">
                  <span className={`t-badge ${t.source === "fresh" ? "fresh" : "live"}`}>
                    {t.source === "fresh" ? "Fresh" : "Live"}
                  </span>
                  {t.pbid ?? "—"}
                </td>
                <td className="t-desc" title={desc}>
                  {shortDesc || "—"}
                </td>
                <td>{t.agency || "—"}</td>
                <td>{place || "—"}</td>
                <td className="t-val">{formatINR(t.value)}</td>
                <td>{t.due_date || "—"}</td>
                <td>{t.open_date || "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function ChatWidget({
  apiBase = "",
  title = "Probee",
  greeting = DEFAULT_GREETING,
  tenantId = "default",
  requireLead = true,
}: ChatWidgetProps) {
  const [sessionId] = useState<string>(getSessionId);
  const [leadDone, setLeadDone] = useState<boolean>(() => {
    if (!requireLead) return true;
    try {
      return sessionStorage.getItem(leadFlag(sessionId)) === "1";
    } catch {
      return false;
    }
  });
  const [messages, setMessages] = useState<ChatMsg[]>([
    { role: "bot", text: greeting },
  ]);
  const [menu, setMenu] = useState<MenuView>({ level: "services" });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [leadName, setLeadName] = useState("");
  const [leadPhone, setLeadPhone] = useState("");
  const [leadError, setLeadError] = useState("");
  const [leadSaving, setLeadSaving] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight });
  }, [messages, menu, leadDone]);

  async function sendQuestion(question: string) {
    const q = question.trim();
    if (!q || busy || !leadDone) return;
    setBusy(true);
    const history = messages.slice(-6).map((m) => ({
      role: m.role === "bot" ? "assistant" : "user",
      content: m.text,
    }));
    setMessages((ms) => [...ms, { role: "user", text: q }]);
    let botText = "";
    let botSources: ChatSource[] | undefined;
    let botTenders: TenderResult[] | undefined;
    setMessages((ms) => [...ms, { role: "bot", text: "" }]);
    const push = () => {
      const text = botText;
      const sources = botSources;
      const tenders = botTenders;
      setMessages((ms) => {
        const copy = [...ms];
        copy[copy.length - 1] = { role: "bot", text, sources, tenders };
        return copy;
      });
    };
    try {
      const resp = await fetch(`${apiBase}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          session_id: sessionId,
          tenant_id: tenantId,
          history,
        }),
      });
      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const frames = buf.split("\n\n");
        buf = frames.pop() ?? "";
        for (const fr of frames) {
          const line = fr.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          const payload = line.slice(5).trim();
          if (payload === "[DONE]") continue;
          try {
            const evt = JSON.parse(payload) as {
              type: string;
              data?: string;
              sources?: ChatSource[];
              tenders?: TenderResult[];
            };
            if (evt.type === "meta") {
              if (evt.sources) botSources = evt.sources;
              if (evt.tenders) botTenders = evt.tenders;
              push();
            } else if (evt.type === "token" && typeof evt.data === "string") {
              botText += evt.data;
              push();
            }
          } catch {
            /* ignore malformed frames / pings */
          }
        }
      }
      if (!botText.trim() && !(botTenders && botTenders.length > 0)) {
        botText = "I couldn't generate a response. Please try again.";
      }
      push();
    } catch (err) {
      const text = httpErrorMessage(err);
      setMessages((ms) => {
        const copy = [...ms];
        copy[copy.length - 1] = { role: "bot", text };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!leadDone || busy) return;
    const q = input.trim();
    if (!q) return;
    setInput("");
    void sendQuestion(q);
  }

  function pickService(menuKey: string, label: string) {
    const sub = SUB_MENUS[menuKey];
    if (!sub) return;
    setMessages((ms) => [
      ...ms,
      { role: "user", text: label },
      { role: "bot", text: sub.prompt },
    ]);
    setMenu({ level: "sub", menuKey });
  }

  async function submitLead(e: FormEvent) {
    e.preventDefault();
    const name = leadName.trim();
    const phone = leadPhone.replace(/\D/g, "");
    if (name.length < 2 || phone.length !== 10) {
      setLeadError("Please enter your name (min 2 chars) and a valid 10-digit mobile number.");
      return;
    }
    setLeadError("");
    setLeadSaving(true);
    try {
      const resp = await fetch(`${apiBase}/api/user/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, phone, session_id: sessionId, tenant_id: tenantId }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      try {
        sessionStorage.setItem(leadFlag(sessionId), "1");
      } catch {
        /* private mode — chat still works this session */
      }
      setLeadDone(true);
    } catch {
      setLeadError("Could not save your details. Please try again.");
    } finally {
      setLeadSaving(false);
    }
  }

  return (
    <div className="cw">
      <div className="cw-head">
        <div className="cw-avatar">🙏</div>
        <div>
          <div className="cw-title">{title}</div>
          <div className="cw-sub">ProBid Consultants LLP · Tender &amp; GeM help</div>
        </div>
        <div className={`cw-dot ${busy ? "busy" : ""}`} title={busy ? "Thinking…" : "Online"} />
      </div>

      {!leadDone ? (
        <form className="cw-lead" onSubmit={submitLead}>
          <div className="cw-lead-title">Get started</div>
          <p className="cw-lead-sub">
            Share your name &amp; mobile number so our team can assist you personally.
          </p>
          <input
            type="text"
            placeholder="Your name"
            maxLength={100}
            autoComplete="name"
            value={leadName}
            onChange={(e) => setLeadName(e.target.value)}
          />
          <input
            type="tel"
            placeholder="Mobile number (10 digits)"
            maxLength={15}
            autoComplete="tel"
            inputMode="numeric"
            value={leadPhone}
            onChange={(e) => setLeadPhone(e.target.value)}
          />
          {leadError && <p className="cw-lead-error">{leadError}</p>}
          <button type="submit" disabled={leadSaving}>
            {leadSaving ? "Saving…" : "Start Chat ⟶"}
          </button>
          <span className="cw-lead-hint">Your details are only used by our team to follow up.</span>
        </form>
      ) : (
        <>
          <div className="cw-body" ref={bodyRef}>
            {messages.map((m, i) => (
              <div key={i} className={`cw-row ${m.role}`}>
                <div className={`cw-bubble${m.tenders && m.tenders.length > 0 ? " has-table" : ""}`}>
                  {m.role === "bot" && m.text === "" && busy ? (
                    <span className="cw-typing">
                      <span />
                      <span />
                      <span />
                    </span>
                  ) : (
                    renderRich(m.text)
                  )}
                  {m.role === "bot" && m.tenders && m.tenders.length > 0 && (
                    <TenderTable tenders={m.tenders} />
                  )}
                  {m.role === "bot" && m.sources && m.sources.length > 0 && (
                    <div className="cw-sources">
                      Sources: {m.sources.map((s) => s.title ?? `#${s.id}`).join(" · ")}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {menu && menu.level === "services" && (
              <div className="cw-row bot">
                <div className="cw-bubble cw-menu-bubble">
                  <div className="cw-menu-title">👋 How can I help you?</div>
                  <div className="cw-quick">
                    {SERVICES.map((s) => (
                      <button
                        key={s.key}
                        type="button"
                        className="cw-quick-btn"
                        onClick={() => pickService(s.key, s.label)}
                      >
                        <span>{s.label}</span>
                        <span className="cw-quick-arrow">→</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
            {menu && menu.level === "sub" && SUB_MENUS[menu.menuKey] && (
              <div className="cw-row bot">
                <div className="cw-bubble cw-menu-bubble">
                  <div className="cw-quick">
                    {SUB_MENUS[menu.menuKey].items.map((q) => (
                      <button
                        key={q}
                        type="button"
                        className="cw-quick-btn chip"
                        disabled={busy}
                        onClick={() => void sendQuestion(q)}
                      >
                        <span>{q}</span>
                      </button>
                    ))}
                    <button
                      type="button"
                      className="cw-quick-btn back"
                      onClick={() => setMenu({ level: "services" })}
                    >
                      <span>← All services</span>
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <form className="cw-input" onSubmit={onSubmit}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about tenders, GeM, documents…"
              rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSubmit(e as unknown as FormEvent);
                }
              }}
            />
            <button type="submit" disabled={busy || input.trim() === ""} aria-label="Send">
              ➤
            </button>
          </form>
        </>
      )}
    </div>
  );
}
