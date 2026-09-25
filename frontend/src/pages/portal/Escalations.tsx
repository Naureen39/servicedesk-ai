import { useEffect, useState } from "react";
import { useAuth } from "../../lib/auth";
import { listEscalations, patchEscalation, replyToEscalation } from "../../lib/portalApi";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Skeleton from "../../components/ui/Skeleton";
import { Textarea } from "../../components/ui/Input";

const STAGES = ["open", "assigned", "in_progress", "resolved", "closed"] as const;
const STAGE_LABEL: Record<string, string> = {
  open: "Open", assigned: "Assigned", in_progress: "In Progress", resolved: "Resolved", closed: "Closed",
};

export default function Escalations() {
  const { token, user } = useAuth();
  const [escalations, setEscalations] = useState<any[] | null>(null);
  const [view, setView] = useState<"kanban" | "table">("kanban");
  const [selected, setSelected] = useState<any | null>(null);
  const [replyText, setReplyText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reload = () => listEscalations(token).then(setEscalations).catch((e) => setError(e.message));

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const move = async (id: string, status: string) => {
    setError(null);
    try {
      await patchEscalation(token, id, { status });
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update status");
    }
  };

  const assignToMe = async (id: string) => {
    await patchEscalation(token, id, { assigned_to: user?.display_name ?? user?.email, status: "assigned" });
    reload();
  };

  const sendReply = async () => {
    if (!selected || !replyText.trim()) return;
    await replyToEscalation(token, selected.escalation_id, replyText);
    setReplyText("");
    await move(selected.escalation_id, "resolved");
    setSelected(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex rounded-lg border border-slate-200 bg-white p-0.5">
          {(["kanban", "table"] as const).map((v) => (
            <button key={v} onClick={() => setView(v)} className={`rounded-md px-3 py-1.5 text-xs font-semibold capitalize ${view === v ? "bg-accent text-white" : "text-slate-600"}`}>
              {v}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-danger">{error}</p>}

      {!escalations ? (
        <Skeleton className="h-96 w-full" />
      ) : view === "kanban" ? (
        <div className="grid gap-4 lg:grid-cols-5">
          {STAGES.map((stage) => (
            <div key={stage} className="rounded-[var(--radius-card)] bg-slate-100 p-3">
              <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">
                {STAGE_LABEL[stage]} ({escalations.filter((e) => e.status === stage).length})
              </h3>
              <div className="space-y-2">
                {escalations.filter((e) => e.status === stage).map((e) => (
                  <Card key={e.escalation_id} className="cursor-pointer p-3" onClick={() => setSelected(e)}>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] text-slate-400">{e.escalation_id}</span>
                      <SlaChip escalation={e} />
                    </div>
                    <p className="mt-1 text-xs font-semibold text-navy">{e.reason ?? "unspecified"}</p>
                    <p className="text-[10px] text-slate-400">{e.assigned_to ?? "Unassigned"}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {stage === "open" && (
                        <Button size="sm" variant="outline" className="px-2 py-1 text-[10px]" onClick={(ev) => { ev.stopPropagation(); assignToMe(e.escalation_id); }}>
                          Assign to me
                        </Button>
                      )}
                      {STAGES.filter((s) => s !== stage).slice(0, 2).map((next) => (
                        <Button key={next} size="sm" variant="ghost" className="px-2 py-1 text-[10px]" onClick={(ev) => { ev.stopPropagation(); move(e.escalation_id, next); }}>
                          &rarr; {STAGE_LABEL[next]}
                        </Button>
                      ))}
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Card className="overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400">
                <th className="px-4 py-2">ID</th><th className="px-4 py-2">Reason</th><th className="px-4 py-2">Priority</th>
                <th className="px-4 py-2">Status</th><th className="px-4 py-2">SLA</th><th className="px-4 py-2">Assigned</th>
              </tr>
            </thead>
            <tbody>
              {escalations.map((e) => (
                <tr key={e.escalation_id} className="cursor-pointer border-b border-slate-100 hover:bg-slate-50" onClick={() => setSelected(e)}>
                  <td className="px-4 py-2 font-mono text-xs">{e.escalation_id}</td>
                  <td className="px-4 py-2">{e.reason}</td>
                  <td className="px-4 py-2"><Badge tone={e.priority === "P1" ? "danger" : "neutral"}>{e.priority}</Badge></td>
                  <td className="px-4 py-2">{STAGE_LABEL[e.status]}</td>
                  <td className="px-4 py-2"><SlaChip escalation={e} /></td>
                  <td className="px-4 py-2 text-xs text-slate-500">{e.assigned_to ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy/50 p-4" onClick={() => setSelected(null)}>
          <Card className="w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-bold text-navy">{selected.escalation_id}</h3>
            <p className="mt-1 text-sm text-slate-600">{selected.summary ?? "No summary available."}</p>
            <label htmlFor="reply-text" className="mt-4 block text-xs font-semibold text-slate-600">Reply &amp; resolve with notes</label>
            <Textarea id="reply-text" rows={3} value={replyText} onChange={(e) => setReplyText(e.target.value)} className="mt-1" />
            <div className="mt-3 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setSelected(null)}>Close</Button>
              <Button size="sm" onClick={sendReply} disabled={!replyText.trim()}>Send &amp; Resolve</Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

function SlaChip({ escalation }: { escalation: any }) {
  if (!escalation.sla_due_at) return <span className="text-[10px] text-slate-300">No SLA</span>;
  const due = new Date(escalation.sla_due_at).getTime();
  const remainingMin = Math.round((due - Date.now()) / 60000);
  const breached = escalation.sla_breached || remainingMin < 0;
  return (
    <Badge tone={breached ? "danger" : remainingMin < 30 ? "warning" : "success"}>
      {breached ? "SLA breached" : `${remainingMin}m left`}
    </Badge>
  );
}
