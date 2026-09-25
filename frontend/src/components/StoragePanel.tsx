import { useQuery } from "@tanstack/react-query";
import { API } from "../api";

function fmt(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const val = bytes / Math.pow(1024, i);
  return `${val >= 100 ? Math.round(val) : val.toFixed(1)} ${units[i]}`;
}

export function StoragePanel() {
  const { data } = useQuery({
    queryKey: ["storage"],
    queryFn: API.storage,
    refetchInterval: 30_000,
  });

  if (!data) return null;

  const total = Math.max(data.total_bytes ?? 0, 1);
  const items = [
    { key: "files", label: "Files", bytes: data.files_bytes ?? 0, color: "#5a67f2" },
    { key: "chunks", label: "Chunks", bytes: data.chunks_bytes ?? 0, color: "#0d9488" },
    { key: "embeddings", label: "Embeddings", bytes: data.embeddings_bytes ?? 0, color: "#d97706" },
  ];

  return (
    <div className="storage">
      <div className="storage-head">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <ellipse cx="12" cy="5" rx="8" ry="3" />
          <path d="M4 5v7c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
          <path d="M4 12v7c0 1.66 3.58 3 8 3s8-1.34 8-3v-7" />
        </svg>
        <span>Storage</span>
        <b>{fmt(data.total_bytes ?? 0)}</b>
      </div>
      <div className="storage-bar">
        {items.map((it) => (
          <div key={it.key} style={{ width: `${(it.bytes / total) * 100}%`, background: it.color }} title={`${it.label}: ${fmt(it.bytes)}`} />
        ))}
      </div>
      <div className="storage-items">
        {items.map((it) => (
          <div key={it.key} className="storage-item">
            <span className="storage-dot" style={{ background: it.color }} />
            <span className="storage-label">{it.label}</span>
            <span className="storage-size">{fmt(it.bytes)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}