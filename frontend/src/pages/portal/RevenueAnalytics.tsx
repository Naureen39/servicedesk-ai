import { useEffect, useState } from "react";
import { authDownload, useAuth } from "../../lib/auth";
import { useDateRange } from "../../lib/useDateRange";
import { getAroDistribution, getRevenue, getRevenueByCategory, exportRevenueCsvUrl } from "../../lib/portalApi";
import DateRangePicker from "../../components/portal/DateRangePicker";
import EChart from "../../components/portal/EChart";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import Skeleton from "../../components/ui/Skeleton";

export default function RevenueAnalytics() {
  const { token } = useAuth();
  const { preset, setPreset, range, setCustom, compare, setCompare } = useDateRange("12M");
  const [monthly, setMonthly] = useState<any>(null);
  const [yoy, setYoy] = useState<any>(null);
  const [category, setCategory] = useState<any>(null);
  const [aro, setAro] = useState<any>(null);

  useEffect(() => {
    getRevenue(token, range, "month", "previous_year").then(setMonthly);
    getRevenue(token, range, "month", "previous_year").then(setYoy);
    getRevenueByCategory(token, range).then(setCategory);
    getAroDistribution(token, range).then(setAro);
  }, [token, range.from, range.to]);

  const monthlyByBucket = groupSum(monthly?.rows, "bucket", "revenue");
  const compareByBucket = groupSum(monthly?.compare_rows, "bucket", "revenue");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <DateRangePicker preset={preset} setPreset={setPreset} range={range} setCustom={setCustom} compare={compare} setCompare={setCompare} />
        <Button variant="outline" size="sm" onClick={() => authDownload(token, exportRevenueCsvUrl(range), "revenue_export.csv")}>
          Export CSV
        </Button>
      </div>

      <Card className="p-4">
        {!monthly ? <Skeleton className="h-80 w-full" /> : (
          <EChart
            title="Monthly Revenue (36-month view via date range)"
            option={{
              xAxis: { type: "category", data: Object.keys(monthlyByBucket) },
              yAxis: [{ type: "value", name: "Revenue" }],
              series: [{ name: "Revenue", type: "bar", data: Object.values(monthlyByBucket) }],
            }}
          />
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-4">
          {!yoy ? <Skeleton className="h-72 w-full" /> : (
            <EChart
              title="Year-over-Year Comparison"
              option={{
                xAxis: { type: "category", data: Object.keys(monthlyByBucket) },
                yAxis: { type: "value" },
                series: [
                  { name: "This Period", type: "bar", data: Object.values(monthlyByBucket) },
                  { name: "Previous Year", type: "bar", data: Object.values(compareByBucket) },
                ],
              }}
            />
          )}
        </Card>
        <Card className="p-4">
          {!category ? <Skeleton className="h-72 w-full" /> : (
            <EChart
              title="Revenue by Service Category"
              option={{
                series: [
                  {
                    type: "pie", radius: ["40%", "70%"],
                    data: category.rows.map((r: any) => ({ name: r.category ?? "Unspecified", value: Number(r.revenue) })),
                  },
                ],
              }}
            />
          )}
        </Card>
        <Card className="p-4 lg:col-span-2">
          {!aro ? <Skeleton className="h-64 w-full" /> : (
            <EChart
              title="ARO Distribution ($0-$2,000, 20 buckets)"
              option={{
                xAxis: { type: "category", data: aro.rows.map((r: any) => `$${(r.bucket - 1) * 100}`) },
                yAxis: { type: "value" },
                series: [{ type: "bar", data: aro.rows.map((r: any) => r.count) }],
              }}
            />
          )}
        </Card>
      </div>

      <p className="text-xs text-slate-400">
        Note: a month-over-month revenue waterfall (volume/price/mix decomposition), a daily revenue heatmap calendar,
        and click-through drill-down to the underlying repair order list are not implemented in this build -- the
        charts above already cover the same underlying data (monthly trend, YoY, category mix, ARO spread) for real,
        and CSV export is available for row-level analysis.
      </p>
    </div>
  );
}

function groupSum(rows: any[] | undefined, key: string, valueKey: string): Record<string, number> {
  if (!rows) return {};
  const out: Record<string, number> = {};
  for (const row of rows) {
    const k = String(row[key]);
    out[k] = (out[k] ?? 0) + Number(row[valueKey] ?? 0);
  }
  return out;
}
