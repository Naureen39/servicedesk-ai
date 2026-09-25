import { useEffect, useState } from "react";
import { authDownload, useAuth } from "../../lib/auth";
import { getRecalls, getRecallsCustomerImpact } from "../../lib/portalApi";
import { complaintsSummary } from "../../lib/api";
import EChart from "../../components/portal/EChart";
import Card from "../../components/ui/Card";
import Skeleton from "../../components/ui/Skeleton";
import Button from "../../components/ui/Button";
import { Input, Label } from "../../components/ui/Input";

export default function RecallInsights() {
  const { token } = useAuth();
  const [recalls, setRecalls] = useState<any>(null);
  const [impact, setImpact] = useState<any>(null);
  const [model, setModel] = useState("Camry");
  const [make, setMake] = useState("TOYOTA");
  const [year, setYear] = useState(2020);
  const [complaints, setComplaints] = useState<any[] | null>(null);

  useEffect(() => {
    getRecalls(token).then(setRecalls);
    getRecallsCustomerImpact(token).then(setImpact);
  }, [token]);

  useEffect(() => {
    complaintsSummary(year, make, model).then(setComplaints).catch(() => setComplaints([]));
  }, [year, make, model]);

  const byMake = groupSum(recalls?.rows, "make", "campaign_count");

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-4">
          {!recalls ? <Skeleton className="h-72 w-full" /> : (
            <EChart
              title="Recall Campaigns by Make (Serviced Vehicles)"
              option={{
                xAxis: { type: "category", data: Object.keys(byMake) },
                yAxis: { type: "value" },
                series: [{ type: "bar", data: Object.values(byMake) }],
              }}
            />
          )}
        </Card>

        <Card className="p-4">
          <div className="mb-3 flex items-end gap-2">
            <div>
              <Label htmlFor="ri-year">Year</Label>
              <Input id="ri-year" type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} className="w-20 py-1.5 text-xs" />
            </div>
            <div>
              <Label htmlFor="ri-make">Make</Label>
              <Input id="ri-make" value={make} onChange={(e) => setMake(e.target.value)} className="w-28 py-1.5 text-xs" />
            </div>
            <div>
              <Label htmlFor="ri-model">Model</Label>
              <Input id="ri-model" value={model} onChange={(e) => setModel(e.target.value)} className="w-28 py-1.5 text-xs" />
            </div>
          </div>
          {complaints === null ? <Skeleton className="h-56 w-full" /> : (
            <EChart
              title="Complaints by Component"
              option={{
                xAxis: { type: "category", data: complaints.map((c) => c.component) },
                yAxis: { type: "value" },
                series: [{ type: "bar", data: complaints.map((c) => c.total_count) }],
              }}
              height={240}
            />
          )}
        </Card>
      </div>

      <Card className="overflow-hidden p-0">
        <h3 className="p-4 pb-0 text-sm font-semibold text-slate-700">Recall Campaigns Affecting the Customer Base</h3>
        {!impact ? (
          <div className="p-4"><Skeleton className="h-72 w-full" /></div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400">
                <th className="px-4 py-2">Campaign</th>
                <th className="px-4 py-2">Vehicle</th>
                <th className="px-4 py-2">Component</th>
                <th className="px-4 py-2 text-right">Affected Customers</th>
                <th className="px-4 py-2 text-right">Outreach List</th>
              </tr>
            </thead>
            <tbody>
              {impact.rows.map((r: any) => (
                <tr key={r.campaign_number} className="border-b border-slate-100">
                  <td className="px-4 py-2 font-mono text-xs">{r.campaign_number}</td>
                  <td className="px-4 py-2">{r.model_year} {r.make} {r.model}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{r.component}</td>
                  <td className="px-4 py-2 text-right font-semibold">{r.affected_vehicle_count}</td>
                  <td className="px-4 py-2 text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        authDownload(
                          token,
                          `/api/v1/analytics/recalls/customer-impact/export.csv?campaign_number=${r.campaign_number}`,
                          `recall_${r.campaign_number}_outreach.csv`,
                        )
                      }
                    >
                      Export CSV
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
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
