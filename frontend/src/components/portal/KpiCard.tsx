import Card from "../ui/Card";

interface KpiCardProps {
  label: string;
  value: string;
  delta?: number | null;
  sparkline?: number[];
}

export default function KpiCard({ label, value, delta, sparkline }: KpiCardProps) {
  const positive = (delta ?? 0) >= 0;
  return (
    <Card className="p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1.5 font-display text-2xl font-bold text-navy">{value}</p>
      <div className="mt-2 flex items-center justify-between">
        {delta != null ? (
          <span className={`text-xs font-semibold ${positive ? "text-success" : "text-danger"}`}>
            {positive ? "↑" : "↓"} {Math.abs(delta * 100).toFixed(1)}% vs previous period
          </span>
        ) : (
          <span className="text-xs text-slate-400">No previous period selected</span>
        )}
        {sparkline && sparkline.length > 1 && <MiniSparkline values={sparkline} />}
      </div>
    </Card>
  );
}

function MiniSparkline({ values }: { values: number[] }) {
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * 60},${20 - ((v - min) / range) * 20}`)
    .join(" ");
  return (
    <svg width="60" height="20" viewBox="0 0 60 20" aria-hidden="true">
      <polyline points={points} fill="none" stroke="#2563EB" strokeWidth="1.5" />
    </svg>
  );
}
