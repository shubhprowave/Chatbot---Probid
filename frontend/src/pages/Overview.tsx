import { useQuery } from "@tanstack/react-query";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, CartesianGrid,
} from "recharts";
import { API } from "../api";
import { StatCard } from "../components/StatCard";
import { SystemHealth } from "../components/SystemHealth";
import {
  IconDashboard, IconFile, IconCost, IconEval, IconSettings, IconSpark,
} from "../components/icons";

const AXIS = { fontSize: 11, fill: "#8b93a6", tickLine: false, axisLine: false };

function tooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "#14181f", color: "#fff", borderRadius: 10, padding: "10px 12px",
        fontSize: 12, boxShadow: "0 8px 24px rgba(0,0,0,.25)",
      }}
    >
      <div style={{ opacity: 0.7, marginBottom: 4 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ margin: "2px 0" }}>
          <span style={{ color: p.color }}>{p.dataKey}</span>: <b>{p.value}</b>
        </div>
      ))}
    </div>
  );
}

export default function Overview() {
  const { data: stats } = useQuery({ queryKey: ["overview"], queryFn: () => API.overview(24) });
  const { data: ts } = useQuery({ queryKey: ["ts"], queryFn: () => API.timeseries(24) });
  const { data: lat } = useQuery({ queryKey: ["lat"], queryFn: () => API.latency(24) });
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: API.health });

  const chartData = ts
    ? ts.timestamps.map((t: string, i: number) => ({
        time: new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        users: ts.users[i],
        questions: ts.questions[i],
      }))
    : [];

  const latencyData = lat?.buckets.map((b: any) => ({
    name: `${Math.round(b.range_ms[0] / 1000)}s`,
    count: b.count,
  })) ?? [];

  return (
    <div>
      <h1>Overview</h1>
      <p className="page-desc">Your RAG assistant's activity over the last 24 hours.</p>

      <div className="stat-grid">
        <StatCard icon={<IconDashboard size={17} />} tone="indigo" label="Unique Users" value={stats?.unique_users} />
        <StatCard icon={<IconSpark size={17} />} tone="sky" label="Questions" value={stats?.questions} />
        <StatCard icon={<IconEval size={17} />} tone="amber" label="Avg Latency" value={stats?.avg_latency_ms ? `${stats.avg_latency_ms} ms` : "—"} />
        <StatCard icon={<IconEval size={17} />} tone="rose" label="P95 Latency" value={stats?.p95_latency_ms ? `${stats.p95_latency_ms} ms` : "—"} />
        <StatCard icon={<IconSettings size={17} />} tone="green" label="Cache Hit" value={stats?.cache_hit_rate != null ? `${(stats.cache_hit_rate * 100).toFixed(1)}%` : "—"} />
        <StatCard icon={<IconDashboard size={17} />} tone="emerald" label="Satisfaction" value={stats?.satisfaction != null ? `${(stats.satisfaction * 100).toFixed(1)}%` : "—"} />
        <StatCard icon={<IconFile size={17} />} tone="violet" label="Documents" value={stats?.doc_count} />
        <StatCard icon={<IconCost size={17} />} tone="pink" label="Chunks" value={stats?.chunk_count} />
      </div>

      <h2>Traffic</h2>
      <div className="panel">
        <div className="panel-head">
          <span className="panel-title">Questions & Users per hour</span>
          <span className="panel-sub">last 24h</span>
        </div>
        <div className="panel-pad">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="gUsers" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#5a67f2" />
                  <stop offset="100%" stopColor="#7c5ff0" />
                </linearGradient>
                <linearGradient id="gQuestions" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#0d9488" />
                  <stop offset="100%" stopColor="#14b8a6" />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 6" stroke="#eef1f6" vertical={false} />
              <XAxis dataKey="time" tick={AXIS} dy={6} />
              <YAxis tick={AXIS} />
              <Tooltip content={tooltip} cursor={{ stroke: "#c7cee0" }} />
              <Line type="monotone" dataKey="users" stroke="url(#gUsers)" strokeWidth={2.4} dot={false} activeDot={{ r: 4 }} />
              <Line type="monotone" dataKey="questions" stroke="url(#gQuestions)" strokeWidth={2.4} dot={false} activeDot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <h2>Latency distribution</h2>
      <div className="panel">
        <div className="panel-head">
          <span className="panel-title">Response-time buckets</span>
          <span className="panel-sub">seconds</span>
        </div>
        <div className="panel-pad">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={latencyData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="gBar" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#5a67f2" />
                  <stop offset="100%" stopColor="#9aa3ff" />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 6" stroke="#eef1f6" vertical={false} />
              <XAxis dataKey="name" tick={AXIS} dy={6} />
              <YAxis tick={AXIS} />
              <Tooltip content={tooltip} cursor={{ fill: "rgba(90,103,242,.06)" }} />
              <Bar dataKey="count" fill="url(#gBar)" radius={[6, 6, 0, 0]} maxBarSize={42} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <h2>System health</h2>
      <SystemHealth health={health} />
    </div>
  );
}