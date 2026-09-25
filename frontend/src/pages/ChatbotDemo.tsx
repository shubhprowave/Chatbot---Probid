import { useState } from "react";
import ChatWidget from "../components/ChatWidget";
import "./ChatbotDemo.css";

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

/**
 * Public chatbot page — served at `/`, styled like a website with a
 * floating widget icon (bottom-right) that pops the chat open.
 * Other sites embed it as: <iframe src="https://your-domain/" ... />
 * No admin token needed: only the public /api/chat endpoint is used.
 */
export default function ChatbotDemo() {
  const [open, setOpen] = useState(false);

  return (
    <div className="demo-wrap">
      <header className="demo-hero">
        <div className="demo-brand">
          <span className="demo-logo">🙏</span>
          <div>
            <h1>Probee</h1>
            <p>ProBid Consultants LLP · Government Tender &amp; GeM assistant</p>
          </div>
        </div>
        <p className="demo-tag">
          Ask about GeM registration, finding tenders, bidding, documents, pricing —
          in English, Hinglish or Hindi.
        </p>
      </header>

      <main className="demo-cards">
        <div className="demo-card">
          <span className="demo-card-icon">🏛️</span>
          <h3>GeM Registration</h3>
          <p>Registration, OEM panel, brand approval &amp; product listing help.</p>
        </div>
        <div className="demo-card">
          <span className="demo-card-icon">📑</span>
          <h3>Government Tenders</h3>
          <p>Find live tenders, check eligibility, bid with confidence.</p>
        </div>
        <div className="demo-card">
          <span className="demo-card-icon">💰</span>
          <h3>Pricing &amp; BOQ</h3>
          <p>Price your bid right with BOQ guidance and document checklists.</p>
        </div>
      </main>

      <footer className="demo-foot">
        <span>
          Need human help? Email{" "}
          <a href="mailto:sales@probidconsultants.com">sales@probidconsultants.com</a>{" "}
          or call <a href="tel:+917016628865">+91 70166 28865</a>
        </span>
      </footer>

      {/* Floating widget icon */}
      <button
        className={`demo-fab${open ? " open" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close chat" : "Open chat"}
      >
        {open ? "✕" : "💬"}
      </button>

      {/* Pop-up chat panel */}
      {open && (
        <div className="demo-panel">
          <ChatWidget apiBase={API_BASE} />
        </div>
      )}
    </div>
  );
}
