import { useEffect, useState } from "react";
import { useAuth } from "../../lib/auth";
import { useLocations } from "../../lib/LocationsContext";
import { useDateRange } from "../../lib/useDateRange";
import { getOperations, getOperationsFunnel, getOperationsHeatmap, getWaitVsPromise } from "../../lib/portalApi";
import DateRangePicker from "../../components/portal/DateRangePicker";
import EChart from "../../components/portal/EChart";
import Card from "../../components/ui/Card";
import Skeleton from "../../components/ui/Skeleton";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export default function ServiceOperations() {
  const { token } = useAuth();
  const { locations } = useLocations();
  const { preset, setPreset, range, setCustom, compare, setCompare } = useDateRange("30D");
  const [heatmap, setHeatmap] = useState<any>(null);
  const [funnel, setFunnel] = useState<any>(null);
  const [bay, setBay] = useState<any>(null);
  const [wait, setWait] = useState<any>(null);

  useEffect(() => {
    getOperationsHeatmap(token, range).then(setHeatmap);
    getOperationsFunnel(token, range).then(setFunnel);
    getOperations(token, range).then(setBay);
    getWaitVsPromise(token, range).then(setWait);
  }, [token, range.from, range.to]);

  return (
    <div className="space-y-6">
      <DateRangePicker preset={preset} setPreset={setPreset} range={range} setCustom={setCustom} compare={compare} setCompare={setCompare} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-4">
          {!heatmap ? <Skeleton className="h-80 w-full" /> : <WeekdayHourHeatmap rows={heatmap.rows} />}
        </Card>

        <Card className="p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Appointment Funnel</h3>
          {!funnel ? <Skeleton className="h-64 w-full" /> : <Funnel funnel={funnel} />}
        </Card>

        <Card className="p-4">
          {!funnel ? <Skeleton className="h-64 w-full" /> : (
            <EChart
              title="No-Show & Cancellation Trend"
              option={{
                xAxis: { type: "category", data: funnel.trend.map((r: any) => r.day) },
                yAxis: { type: "value" },
                series: [
                  { name: "No-Show", type: "line", data: funnel.trend.map((r: any) => r.no_show_count) },
                  { name: "Cancelled", type: "line", data: funnel.trend.map((r: any) => r.cancelled_count) },
                ],
              }}
            />
          )}
        </Card>

        <Card className="p-4">
          {!wait ? <Skeleton className="h-64 w-full" /> : (
            <EChart
              title="Average Wait vs Promise Time (minutes)"
              option={{
                xAxis: { type: "category", data: wait.rows.map((r: any) => r.day) },
                yAxis: { type: "value" },
                series: [
                  { name: "Actual Wait", type: "line", data: wait.rows.map((r: any) => Number(r.avg_wait)) },
                  { name: "Promised", type: "line", data: wait.rows.map((r: any) => Number(r.avg_promise)) },
                ],
              }}
            />
          )}
        </Card>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-slate-700">Bay Utilization by Location</h3>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {!bay
            ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32 w-full" />)
            : locations.map((loc) => <BayGauge key={loc.location_id} name={loc.name} rows={bay.rows.filter((r: any) => r.location_id === loc.location_id)} />)}
        </div>
      </div>
    </div>
  );
}

function WeekdayHourHeatmap({ rows }: { rows: any[] }) {
  const data = rows.map((r) => [r.hour, r.weekday, r.count]);
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <EChart
      title="Appointments by Weekday and Hour"
      option={{
        tooltip: { position: "top" },
        grid: { top: 40, left: 60, right: 16, bottom: 20 },
        xAxis: { type: "category", data: Array.from({ length: 24 }, (_, i) => `${i}:00`), splitArea: { show: true } },
        yAxis: { type: "category", data: WEEKDAYS, splitArea: { show: true } },
        visualMap: { min: 0, max, calculable: true, orient: "horizontal", left: "center", bottom: 0 },
        series: [{ type: "heatmap", data, emphasis: { itemStyle: { shadowBlur: 10 } } }],
      }}
      height={340}
    />
  );
}

function Funnel({ funnel }: { funnel: any }) {
  const byStatus: Record<string, number> = {};
  for (const row of funnel.by_status) byStatus[row.status] = Number(row.count);
  const stages = [
    { label: "Booked", value: (byStatus.booked ?? 0) + (byStatus.completed ?? 0) + (byStatus.no_show ?? 0) + (byStatus.cancelled ?? 0) },
    { label: "Completed", value: byStatus.completed ?? 0 },
    { label: "Invoiced", value: funnel.invoiced_count ?? 0 },
  ];
  const max = Math.max(...stages.map((s) => s.value), 1);
  return (
    <div className="space-y-2">
      {stages.map((s) => (
        <div key={s.label}>
          <div className="flex justify-between text-xs text-slate-500"><span>{s.label}</span><span>{s.value}</span></div>
          <div className="h-6 rounded bg-slate-100">
            <div className="h-6 rounded bg-accent" style={{ width: `${(s.value / max) * 100}%` }} />
          </div>
        </div>
      ))}
      <p className="pt-2 text-xs text-slate-400">
        No-show: {byStatus.no_show ?? 0} &middot; Cancelled: {byStatus.cancelled ?? 0}. This dataset has no separate
        "arrived" check-in event, so the funnel goes booked &rarr; completed &rarr; invoiced.
      </p>
    </div>
  );
}

function BayGauge({ name, rows }: { name: string; rows: any[] }) {
  const totalBooked = rows.reduce((sum, r) => sum + Number(r.booked_minutes ?? 0), 0);
  const bayCount = new Set(rows.map((r) => r.bay_number)).size || 1;
  const dayCount = new Set(rows.map((r) => r.day)).size || 1;
  const available = bayCount * dayCount * 24 * 60;
  const pct = available ? Math.min(100, (totalBooked / available) * 100) : 0;
  return (
    <Card className="p-4 text-center">
      <EChart
        height={140}
        option={{
          series: [
            {
              type: "gauge", startAngle: 180, endAngle: 0, min: 0, max: 100,
              progress: { show: true, width: 10 }, axisLine: { lineStyle: { width: 10 } },
              pointer: { show: false }, axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
              detail: { valueAnimation: true, fontSize: 20, offsetCenter: [0, "0%"], formatter: "{value}%" },
              data: [{ value: Math.round(pct) }],
            },
          ],
        }}
      />
      <p className="-mt-2 text-xs font-semibold text-slate-600">{name}</p>
    </Card>
  );
}
