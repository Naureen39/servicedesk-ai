import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../lib/auth";
import { useDateRange } from "../../lib/useDateRange";
import { getTechnicians } from "../../lib/portalApi";
import DateRangePicker from "../../components/portal/DateRangePicker";
import EChart from "../../components/portal/EChart";
import Card from "../../components/ui/Card";
import Skeleton from "../../components/ui/Skeleton";

type SortKey = "technician_id" | "ro_count" | "labor_hours_billed" | "revenue";

export default function TechnicianPerformance() {
  const { token } = useAuth();
  const { preset, setPreset, range, setCustom, compare, setCompare } = useDateRange("30D");
  const [data, setData] = useState<any>(null);
  const [sortKey, setSortKey] = useState<SortKey>("revenue");
  const [sortDesc, setSortDesc] = useState(true);

  useEffect(() => {
    getTechnicians(token, range).then(setData);
  }, [token, range.from, range.to]);

  const byTech = useMemo(() => {
    if (!data) return [];
    const grouped = new Map<string, { technician_id: string; ro_count: number; labor_hours_billed: number; revenue: number }>();
    for (const row of data.rows) {
      const existing = grouped.get(row.technician_id) ?? { technician_id: row.technician_id, ro_count: 0, labor_hours_billed: 0, revenue: 0 };
      existing.ro_count += Number(row.ro_count ?? 0);
      existing.labor_hours_billed += Number(row.labor_hours_billed ?? 0);
      existing.revenue += Number(row.revenue ?? 0);
      grouped.set(row.technician_id, existing);
    }
    return Array.from(grouped.values());
  }, [data]);

  const sorted = useMemo(() => {
    const rows = [...byTech];
    rows.sort((a, b) => {
      const cmp = typeof a[sortKey] === "string" ? String(a[sortKey]).localeCompare(String(b[sortKey])) : Number(a[sortKey]) - Number(b[sortKey]);
      return sortDesc ? -cmp : cmp;
    });
    return rows;
  }, [byTech, sortKey, sortDesc]);

  const avgRevenue = byTech.length ? byTech.reduce((s, t) => s + t.revenue, 0) / byTech.length : 0;

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setSortDesc((d) => !d);
    else {
      setSortKey(key);
      setSortDesc(true);
    }
  };

  return (
    <div className="space-y-6">
      <DateRangePicker preset={preset} setPreset={setPreset} range={range} setCustom={setCustom} compare={compare} setCompare={setCompare} />

      <Card className="p-4">
        {!data ? <Skeleton className="h-80 w-full" /> : (
          <EChart
            title="Revenue per Technician (target = team average)"
            option={{
              xAxis: { type: "category", data: sorted.map((t) => t.technician_id) },
              yAxis: { type: "value" },
              series: [
                { name: "Revenue", type: "bar", data: sorted.map((t) => Math.round(t.revenue)) },
                { name: "Team Average", type: "line", data: sorted.map(() => Math.round(avgRevenue)), symbol: "none", lineStyle: { type: "dashed" } },
              ],
            }}
          />
        )}
      </Card>

      <Card className="overflow-hidden p-0">
        <h3 className="p-4 pb-0 text-sm font-semibold text-slate-700">Leaderboard</h3>
        {!data ? (
          <div className="p-4"><Skeleton className="h-64 w-full" /></div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400">
                {(["technician_id", "ro_count", "labor_hours_billed", "revenue"] as SortKey[]).map((key) => (
                  <th key={key} className="cursor-pointer select-none px-4 py-2" onClick={() => toggleSort(key)}>
                    {key.replace(/_/g, " ")} {sortKey === key ? (sortDesc ? "↓" : "↑") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((t) => (
                <tr key={t.technician_id} className="border-b border-slate-100">
                  <td className="px-4 py-2 font-medium text-navy">{t.technician_id}</td>
                  <td className="px-4 py-2">{t.ro_count}</td>
                  <td className="px-4 py-2">{t.labor_hours_billed.toFixed(1)}</td>
                  <td className="px-4 py-2 font-semibold">${Math.round(t.revenue).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <p className="text-xs text-slate-400">
        Note: "hours flagged vs clocked" isn't implemented -- this dataset doesn't model a separate flagged/disputed
        hours concept per technician, only billed labor hours (shown above).
      </p>
    </div>
  );
}
