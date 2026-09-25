import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { API } from "../api";

export default function Conversations() {
  const { data } = useQuery({ queryKey: ["convs"], queryFn: API.conversations });
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div>
      <h1>Conversations</h1>
      <p className="page-desc">Browse what users have asked your assistant.</p>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Session</th>
              <th>First question</th>
              <th>Q count</th>
              <th>Last activity</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data?.map((c) => (
              <tr key={c.id}>
                <td>{c.session_id.slice(0, 12)}…</td>
                <td className="table-text">{c.first_question?.slice(0, 80)}</td>
                <td>{c.question_count}</td>
                <td>{c.last_message_at ? new Date(c.last_message_at).toLocaleString() : "—"}</td>
                <td><button onClick={() => setSelected(c.id)}>Open</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected && <ConversationView id={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function ConversationView({ id, onClose }: { id: string; onClose: () => void }) {
  const { data } = useQuery({ queryKey: ["conv", id], queryFn: () => API.conversation(id) });
  return (
    <div className="modal">
      <div className="modal-body">
        <button className="close" onClick={onClose}>✕</button>
        <h2>Conversation</h2>
        <div className="messages">
          {data?.messages.map((m: any) => (
            <div key={m.id} className={`bubble ${m.role}`}>
              <div className="meta">
                {m.role} · {m.latency_ms ? `${m.latency_ms} ms` : ""} ·{" "}
                {m.cache_hit ? "cached" : m.model}
              </div>
              <div>{m.content}</div>
              {m.sources?.length > 0 && (
                <div className="sources">
                  Sources: {m.sources.map((s: any) => `[${s.id}] ${s.title}`).join(", ")}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}