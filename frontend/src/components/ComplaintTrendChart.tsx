import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { complaintsSummary, type ComplaintSummaryOut } from "../lib/api";
import Skeleton from "./ui/Skeleton";

export default function ComplaintTrendChart({ year, make, model }: { year?: number; make?: string; model?: string }) {
  const [data, setData] = useState<ComplaintSummaryOut[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!make || !model) {
      setData(null);
      return;
    }
    setLoading(true);
    complaintsSummary(year, make, model)
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [year, make, model]);

  if (!make || !model) return null;
  if (loading) return <Skeleton className="h-56 w-full" />;
  if (!data || data.length === 0) {
    return <p className="text-sm text-slate-500">No historical complaint data on file for this vehicle.</p>;
  }

  const chartData = data.slice(0, 6).map((d) => ({ name: d.component, count: d.total_count }));

  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold text-slate-700">Reported complaints by component</h4>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ left: 0, right: 8, top: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={60} />
          <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-slate-400">Source: NHTSA complaint data on file for this vehicle.</p>
    </div>
  );
}
