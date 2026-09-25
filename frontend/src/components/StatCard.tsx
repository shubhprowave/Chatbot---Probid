type Tone = "indigo" | "sky" | "amber" | "rose" | "green" | "emerald" | "violet" | "pink" | "slate";

export function StatCard({ label, value, icon, tone = "indigo" }: {
  label: string;
  value: any;
  icon?: React.ReactNode;
  tone?: Tone;
}) {
  return (
    <div className="stat">
      {icon && <div className={`stat-icon tone-${tone}`}>{icon}</div>}
      <div>
        <span>{label}</span>
      </div>
      <strong>{value ?? "—"}</strong>
    </div>
  );
}