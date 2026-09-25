import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { API } from "../api";

export default function Evaluations() {
  const qc = useQueryClient();
  const { data: golden } = useQuery({ queryKey: ["golden"], queryFn: API.goldenList });
  const { data: runs } = useQuery({ queryKey: ["runs"], queryFn: API.evalRuns });
  const [busy, setBusy] = useState(false);
  const [newQ, setNewQ] = useState({ question: "", ground_truth: "", category: "" });

  const start = async () => {
    setBusy(true);
    await API.evalStart({ name: `run-${Date.now()}`, tenant_id: "default" });
    setTimeout(() => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      setBusy(false);
    }, 3000);
  };

  return (
    <div>
      <h1>Evaluations</h1>
      <p className="page-desc">Golden QA sets and RAG quality metrics.</p>

      <h2>Golden Q/A Set ({golden?.length || 0})</h2>
      <div className="card">
        <input
          placeholder="Question"
          value={newQ.question}
          onChange={(e) => setNewQ({ ...newQ, question: e.target.value })}
        />
        <input
          placeholder="Expected answer"
          value={newQ.ground_truth}
          onChange={(e) => setNewQ({ ...newQ, ground_truth: e.target.value })}
        />
        <input
          placeholder="Category (optional)"
          value={newQ.category}
          onChange={(e) => setNewQ({ ...newQ, category: e.target.value })}
        />
        <button
          disabled={!newQ.question || !newQ.ground_truth}
          onClick={async () => {
            await API.goldenAdd({ ...newQ, tenant_id: "default" });
            setNewQ({ question: "", ground_truth: "", category: "" });
            qc.invalidateQueries({ queryKey: ["golden"] });
          }}
        >
          + Add
        </button>
      </div>

      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Question</th><th>Expected</th><th>Category</th><th></th></tr></thead>
          <tbody>
            {golden?.map((g) => (
              <tr key={g.id}>
                <td className="table-text">{g.question}</td>
                <td className="table-text">{g.ground_truth}</td>
                <td>{g.category}</td>
                <td>
                  <button onClick={async () => {
                    await API.goldenDelete(g.id);
                    qc.invalidateQueries({ queryKey: ["golden"] });
                  }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Runs</h2>
      <button disabled={busy} onClick={start}>
        {busy ? "Starting…" : "▶ Start New Evaluation"}
      </button>

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th><th>Status</th><th>Faithfulness</th>
              <th>Relevancy</th><th>Precision</th><th>Recall</th>
              <th>Correctness</th><th>Started</th>
            </tr>
          </thead>
          <tbody>
            {runs?.map((r) => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td><span className={`badge ${r.status}`}>{r.status}</span></td>
                <td>{fmt(r.summary?.faithfulness)}</td>
                <td>{fmt(r.summary?.answer_relevancy)}</td>
                <td>{fmt(r.summary?.context_precision)}</td>
                <td>{fmt(r.summary?.context_recall)}</td>
                <td>{fmt(r.summary?.answer_correctness)}</td>
                <td>{new Date(r.started_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function fmt(v?: number) {
  return v == null ? "—" : v.toFixed(3);
}