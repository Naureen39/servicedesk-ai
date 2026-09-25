import { useEffect, useState } from "react";
import { useAuth } from "../../lib/auth";
import { useLocations } from "../../lib/LocationsContext";
import { useDateRange } from "../../lib/useDateRange";
import { getOverview, getRevenue, getRevenueByLocation, getRevenueByPayType, getTopServices } from "../../lib/portalApi";
import DateRangePicker from "../../components/portal/DateRangePicker";
import KpiCard from "../../components/portal/KpiCard";
import EChart from "../../components/portal/EChart";
import Card from "../../components/ui/Card";
import Skeleton from "../../components/ui/Skeleton";
import { Select } from "../../components/ui/Input";

function fmtCurrency(v: number | string | null | undefined): string {
  const n = Number(v ?? 0);
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

function pctDelta(current: number, previous: number): number | null {
  if (!previous) return null;
  return (current - previous) / previous;
}

export default function ExecutiveOverview() {
  const { token } = useAuth();
  const { locations } = useLocations();
  const { preset, setPreset, range, setCustom, compare, setCompare } = useDateRange("30D");
  const [locationId, setLocationId] = useState<number | undefined>(undefined);
  const [overview, setOverview] = useState<any>(null);
  const [revenue, setRevenue] = useState<any>(null);
  const [byLocation, setByLocation] = useState<any>(null);
  const [byPayType, setByPayType] = useState<any>(null);
  const [topServices, setTopServices] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const r = { ...range, location_id: locationId };
    Promise.all([
      getOverview(token, r),
      getRevenue(token, r, "day", compare ? "previous_year" : undefined),
      getRevenueByLocation(token, r),
      getRevenueByPayType(token, r),
      getTopServices(token, r),
    ])
      .then(([o, rev, loc, pay, top]) => {
        setOverview(o);
        setRevenue(rev);
        setByLocation(loc);
        setByPayType(pay);
        setTopServices(top);
      })
      .catch((e) => setError(e.message));
  }, [token, range.from, range.to, locationId, compare]);

  if (error) return <ErrorState message={error} />;

  const current = overview?.current;
  const previous = overview?.previous;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <DateRangePicker preset={preset} setPreset={setPreset} range={range} setCustom={setCustom} compare={compare} setCompare={setCompare} />
        <Select value={locationId ?? ""} onChange={(e) => setLocationId(e.target.value ? Number(e.target.value) : undefined)} className="w-48 py-1.5 text-xs">
          <option value="">All Locations</option>
          {locations.map((l) => (
            <option key={l.location_id} value={l.location_id}>{l.name}</option>
          ))}
        </Select>
      </div>

      {!overview ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard label="Total Revenue" value={fmtCurrency(current?.total_revenue)} delta={current && previous ? pctDelta(Number(current.total_revenue), Number(previous.total_revenue || 0)) : null} />
          <KpiCard label="Repair Orders" value={String(current?.ro_count ?? 0)} delta={current && previous ? pctDelta(Number(current.ro_count), Number(previous.ro_count || 0)) : null} />
          <KpiCard label="ARO" value={overview.aro ? fmtCurrency(overview.aro) : "—"} />
          <KpiCard label="Effective Labor Rate" value={overview.effective_labor_rate ? fmtCurrency(overview.effective_labor_rate) : "—"} />
          <KpiCard label="Bay Utilization" value={overview.bay_utilization_pct != null ? `${(overview.bay_utilization_pct * 100).toFixed(1)}%` : "—"} />
          <KpiCard label="CSAT" value={overview.csat?.avg_csat ? Number(overview.csat.avg_csat).toFixed(1) : "—"} />
          <KpiCard label="Assistant Containment" value={overview.assistant_containment_rate != null ? `${(overview.assistant_containment_rate * 100).toFixed(0)}%` : "—"} />
          <KpiCard label="Gross Profit" value={current ? fmtCurrency(Number(current.total_revenue) - Number(current.parts_revenue || 0) * 0.5) : "—"} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-4">
          {!revenue ? <Skeleton className="h-80 w-full" /> : (
            <EChart
              title="Revenue Trend"
              option={{
                xAxis: { type: "category", data: revenue.rows.map((r: any) => r.bucket) },
                yAxis: { type: "value" },
                series: [
                  { name: "Revenue", type: "line", smooth: true, data: revenue.rows.map((r: any) => Number(r.total_revenue)) },
                  ...(compare && revenue.compare_rows?.length
                    ? [{ name: "Previous Year", type: "line", smooth: true, data: revenue.compare_rows.map((r: any) => Number(r.total_revenue)) }]
                    : []),
                ],
              }}
            />
          )}
        </Card>
        <Card className="p-4">
          {!byLocation ? <Skeleton className="h-80 w-full" /> : (
            <EChart
              title="Revenue by Location"
              option={{
                xAxis: { type: "category", data: byLocation.rows.map((r: any) => locations.find((l) => l.location_id === r.location_id)?.name ?? `#${r.location_id}`) },
                yAxis: { type: "value" },
                series: [{ type: "bar", data: byLocation.rows.map((r: any) => Number(r.revenue)) }],
              }}
            />
          )}
        </Card>
        <Card className="p-4">
          {!byPayType ? <Skeleton className="h-80 w-full" /> : <PayTypeStackedArea rows={byPayType.rows} />}
        </Card>
        <Card className="p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-700">Top 10 Services</h3>
          {!topServices ? <Skeleton className="h-72 w-full" /> : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400">
                  <th className="pb-2">Service</th>
                  <th className="pb-2 text-right">Lines</th>
                  <th className="pb-2 text-right">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {topServices.rows.map((r: any) => (
                  <tr key={r.service_code} className="border-b border-slate-100">
                    <td className="py-2 font-medium text-navy">{r.service_code}</td>
                    <td className="py-2 text-right text-slate-500">{r.line_count}</td>
                    <td className="py-2 text-right font-semibold">{fmtCurrency(r.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}

function PayTypeStackedArea({ rows }: { rows: any[] }) {
  const payTypes = Array.from(new Set(rows.map((r) => r.pay_type ?? "unknown")));
  const days = Array.from(new Set(rows.map((r) => r.day))).sort();
  const series = payTypes.map((pt) => ({
    name: pt,
    type: "line" as const,
    stack: "total",
    areaStyle: {},
    data: days.map((d) => {
      const match = rows.find((r) => r.day === d && (r.pay_type ?? "unknown") === pt);
      return match ? Number(match.revenue) : 0;
    }),
  }));
  return (
    <EChart
      title="Revenue by Pay Type"
      option={{ xAxis: { type: "category", data: days }, yAxis: { type: "value" }, series }}
    />
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-[var(--radius-card)] border border-red-200 bg-red-50 p-6 text-center text-sm text-danger">
      Failed to load: {message}
    </div>
  );
}
