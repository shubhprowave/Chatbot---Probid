const KNOWN = ["postgres", "redis", "llm"];

function prettyName(key: string) {
  const map: Record<string, string> = {
    postgres: "PostgreSQL",
    redis: "Redis",
    llm: "LLM (Groq)",
  };
  return map[key] ?? key;
}

export function SystemHealth({ health }: { health?: Record<string, any> | null }) {
  if (!health) return <p className="muted">Health data unavailable.</p>;

  const items = KNOWN
    .filter((k) => k in health)
    .map((k) => {
      const v = health[k];
      const ok = v === "ok" || String(v).startsWith("http 20");
      return { key: k, label: prettyName(k), value: v, ok };
    });

  return (
    <div className="health">
      {items.map(({ key, label, value, ok }) => (
        <div key={key} className={`health-item ${ok ? "ok" : "down"}`}>
          <span><span className="dot" />{label}</span>
          <strong>{ok ? "Healthy" : String(value)}</strong>
        </div>
      ))}
    </div>
  );
}