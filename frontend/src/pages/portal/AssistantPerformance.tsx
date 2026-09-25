import { useEffect, useState } from "react";
import { useAuth } from "../../lib/auth";
import { useDateRange } from "../../lib/useDateRange";
import { getAssistant, getAssistantSummary } from "../../lib/portalApi";
import DateRangePicker from "../../components/portal/DateRangePicker";
import EChart from "../../components/portal/EChart";
import KpiCard from "../../components/portal/KpiCard";
import Card from "../../components/ui/Card";
import Skeleton from "../../components/ui/Skeleton";

export default function AssistantPerformance() {
  const { token } = useAuth();
  const { preset, setPreset, range, setCustom, compare, setCompare } = useDateRange("30D");
  const [daily, setDaily] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);

  useEffect(() => {
    getAssistant(token, range).then(setDaily);
    getAssistantSummary(token, range).then(setSummary);
  }, [token, range.from, range.to]);

  const byDay = groupByDayChannel(daily?.rows);

  return (
    <div className="space-y-6">
      <DateRangePicker preset={preset} setPreset={setPreset} range={range} setCustom={setCustom} compare={compare} setCompare={setCompare} />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {!summary ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)
        ) : (
          <>
            <KpiCard label="Assistant-Attributed ROs" value={String(summary.assistant_attributed?.ro_count ?? 0)} />
            <KpiCard label="Assistant-Attributed Revenue" value={`$${Math.round(Number(summary.assistant_attributed?.revenue ?? 0)).toLocaleString()}`} />
            <KpiCard label="Avg Turns to Booking" value={summary.avg_turns_to_booking ? Number(summary.avg_turns_to_booking).toFixed(1) : "—"} />
            <KpiCard label="Est. Advisor Hours Saved" value={`${summary.estimated_advisor_hours_saved ?? 0} hrs`} />
          </>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-4">
          {!daily ? <Skeleton className="h-72 w-full" /> : (
            <EChart
              title="Conversations per Day by Channel"
              option={{
                xAxis: { type: "category", data: byDay.days },
                yAxis: { type: "value" },
                series: byDay.channels.map((ch) => ({
                  name: ch, type: "line", stack: "total", areaStyle: {},
                  data: byDay.days.map((d) => byDay.matrix[`${d}|${ch}`] ?? 0),
                })),
              }}
            />
          )}
        </Card>

        <Card className="p-4">
          {!daily ? <Skeleton className="h-72 w-full" /> : (
            <EChart
              title="Containment vs Escalation Rate"
              option={{
                xAxis: { type: "category", data: byDay.days },
                yAxis: { type: "value", max: 1, axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` } },
                series: [
                  { name: "Containment", type: "line", data: byDay.days.map((d) => byDay.containmentByDay[d] ?? 0) },
                  { name: "Escalation", type: "line", data: byDay.days.map((d) => byDay.escalationByDay[d] ?? 0) },
                ],
              }}
            />
          )}
        </Card>

        <Card className="p-4">
          {!summary ? <Skeleton className="h-72 w-full" /> : (
            <EChart
              title="Intent Distribution"
              option={{ series: [{ type: "pie", radius: "65%", data: summary.intent_distribution.map((r: any) => ({ name: r.intent, value: r.count })) }] }}
            />
          )}
        </Card>

        <Card className="p-4">
          {!summary ? <Skeleton className="h-72 w-full" /> : (
            <EChart
              title="Confidence Distribution (10 buckets, 0-1)"
              option={{
                xAxis: { type: "category", data: summary.confidence_histogram.map((r: any) => `${((r.bucket - 1) * 10)}%`) },
                yAxis: { type: "value" },
                series: [{ type: "bar", data: summary.confidence_histogram.map((r: any) => r.count) }],
              }}
            />
          )}
        </Card>

        <Card className="p-4">
          {!daily ? <Skeleton className="h-72 w-full" /> : (
            <EChart
              title="Avg LLM Tokens per Message"
              option={{
                xAxis: { type: "category", data: byDay.days },
                yAxis: { type: "value" },
                series: [{ type: "line", data: byDay.days.map((d) => byDay.tokensByDay[d] ?? 0) }],
              }}
            />
          )}
        </Card>

        <Card className="p-4">
          {!daily || !summary ? <Skeleton className="h-72 w-full" /> : (
            <EChart
              title="Cache Hit Rate & Provider Split"
              option={{
                xAxis: { type: "category", data: ["Cache Hit Rate", ...summary.provider_split.map((p: any) => p.provider ?? "none")] },
                yAxis: { type: "value" },
                series: [{
                  type: "bar",
                  data: [
                    Math.round((byDay.avgCacheHitRate ?? 0) * 100),
                    ...summary.provider_split.map((p: any) => p.count),
                  ],
                }],
              }}
            />
          )}
        </Card>
      </div>
    </div>
  );
}

function groupByDayChannel(rows: any[] | undefined) {
  const days = Array.from(new Set((rows ?? []).map((r) => r.day))).sort();
  const channels = Array.from(new Set((rows ?? []).map((r) => r.channel).filter(Boolean)));
  const matrix: Record<string, number> = {};
  const containmentByDay: Record<string, number> = {};
  const escalationByDay: Record<string, number> = {};
  const tokensByDay: Record<string, number> = {};
  let cacheSum = 0;
  let cacheN = 0;

  const byDay = new Map<string, { total: number; contained: number; escalated: number; tokens: number[] }>();
  for (const row of rows ?? []) {
    matrix[`${row.day}|${row.channel}`] = (matrix[`${row.day}|${row.channel}`] ?? 0) + Number(row.conversation_count ?? 0);
    const acc = byDay.get(row.day) ?? { total: 0, contained: 0, escalated: 0, tokens: [] };
    acc.total += Number(row.conversation_count ?? 0);
    acc.contained += Number(row.contained_count ?? 0);
    acc.escalated += Number(row.escalated_count ?? 0);
    if (row.avg_tokens_per_message) acc.tokens.push(Number(row.avg_tokens_per_message));
    byDay.set(row.day, acc);
    if (row.cache_hit_rate != null) {
      cacheSum += Number(row.cache_hit_rate);
      cacheN += 1;
    }
  }
  for (const [day, acc] of byDay) {
    containmentByDay[day] = acc.total ? acc.contained / acc.total : 0;
    escalationByDay[day] = acc.total ? acc.escalated / acc.total : 0;
    tokensByDay[day] = acc.tokens.length ? acc.tokens.reduce((s, v) => s + v, 0) / acc.tokens.length : 0;
  }

  return { days, channels, matrix, containmentByDay, escalationByDay, tokensByDay, avgCacheHitRate: cacheN ? cacheSum / cacheN : 0 };
}
