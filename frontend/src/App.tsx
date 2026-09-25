import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import { useState } from "react";
import Overview from "./pages/Overview";
import Documents from "./pages/Documents";
import Conversations from "./pages/Conversations";
import Evaluations from "./pages/Evaluations";
import Cost from "./pages/Cost";
import Settings from "./pages/Settings";
import Prompt from "./pages/Prompt";
import Users from "./pages/Users";
import ChatbotDemo from "./pages/ChatbotDemo";
import { getToken, setToken } from "./api";
import { StoragePanel } from "./components/StoragePanel";
import {
  IconDashboard, IconFile, IconPrompt, IconChat, IconEval,
  IconCost, IconSettings, IconLogout, IconLock, IconSpark, IconUsers,
} from "./components/icons";

const NAV = [
  { to: "/admin", label: "Overview", icon: IconDashboard, end: true },
  { to: "/admin/documents", label: "Documents", icon: IconFile },
  { to: "/admin/prompt", label: "System Prompt", icon: IconPrompt },
  { to: "/admin/conversations", label: "Conversations", icon: IconChat },
  { to: "/admin/users", label: "Users", icon: IconUsers },
  { to: "/admin/evaluations", label: "Evaluations", icon: IconEval },
  { to: "/admin/cost", label: "Cost", icon: IconCost },
  { to: "/admin/settings", label: "Settings", icon: IconSettings },
];

/** Token-gated admin console, served at /admin/*. The public chatbot at /
 *  needs no token — it only calls the public /api/chat endpoint. */
function AdminApp() {
  const [authed, setAuthed] = useState(!!getToken());

  if (!authed) {
    return (
      <div className="login">
        <div className="login-card">
          <div className="login-logo"><IconSpark size={26} /></div>
          <h1>Probee Admin</h1>
          <p>Enter your admin token to continue.</p>
          <input
            type="password"
            placeholder="ADMIN_TOKEN"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                setToken((e.target as HTMLInputElement).value);
                setAuthed(true);
              }
            }}
          />
          <button
            className="primary"
            onClick={() => {
              const input = document.querySelector(".login-card input") as HTMLInputElement;
              setToken(input?.value ?? "");
              setAuthed(true);
            }}
          >
            <span className="inline"><IconLock size={15} /> Unlock Dashboard</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-logo"><IconSpark size={19} /></span>
          Probee Admin
        </div>
        <nav>
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}>
              <Icon size={17} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <StoragePanel />
        <div className="sidebar-foot">
          <button
            onClick={() => {
              localStorage.removeItem("rag_admin_token");
              location.reload();
            }}
          >
            <IconLogout size={17} />
            <span>Log out</span>
          </button>
        </div>
      </aside>
      <main className="content">
        <Routes>
          <Route index element={<Overview />} />
          <Route path="documents" element={<Documents />} />
          <Route path="prompt" element={<Prompt />} />
          <Route path="conversations" element={<Conversations />} />
          <Route path="users" element={<Users />} />
          <Route path="evaluations" element={<Evaluations />} />
          <Route path="cost" element={<Cost />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/admin" />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      {/* Public chatbot — embeddable as an API-like page in other sites */}
      <Route path="/" element={<ChatbotDemo />} />
      {/* Admin console */}
      <Route path="/admin/*" element={<AdminApp />} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}
