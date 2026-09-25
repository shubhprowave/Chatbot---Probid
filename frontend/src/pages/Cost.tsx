import { useQuery } from "@tanstack/react-query";
import { API } from "../api";

export default function Cost() {
  const { data } = useQuery({ queryKey: ["cost"], queryFn: () => API.cost(30) });
  if (!data) return <div>Loading…</div>;
  return (
    <div>
      <h1>Cost</h1>
      <p className="page-desc">Inference spend for the last {data.days} days.</p>
      <div className="stat-grid">
        <div className="stat"><span>Answers</span><strong>{data.answers}</strong></div>
        <div className="stat"><span>Tokens in</span><strong>{data.tokens_in.toLocaleString()}</strong></div>
        <div className="stat"><span>Tokens out</span><strong>{data.tokens_out.toLocaleString()}</strong></div>
        <div className="stat"><span>Self-hosted cost</span><strong>${data.actual_cost_usd}</strong></div>
        <div className="stat"><span>Savings vs GPT-4o mini</span><strong>${data.savings_vs_gpt4o_mini}</strong></div>
      </div>
      <h2>Cloud comparison</h2>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Provider</th><th>Cost (USD)</th></tr></thead>
          <tbody>
            {Object.entries(data.comparison_cloud_usd).map(([k, v]) => (
              <tr key={k}><td>{k}</td><td>${(v as number).toFixed(4)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}