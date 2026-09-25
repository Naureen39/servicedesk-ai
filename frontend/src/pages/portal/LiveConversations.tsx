import { useEffect, useState } from "react";
import { useAuth } from "../../lib/auth";
import { WS_BASE } from "../../lib/api";
import { getConversation, listConversations } from "../../lib/portalApi";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Skeleton from "../../components/ui/Skeleton";

export default function LiveConversations() {
  const { token } = useAuth();
  const [conversations, setConversations] = useState<any[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<any | null>(null);
  const [liveEvents, setLiveEvents] = useState<any[]>([]);

  useEffect(() => {
    listConversations(token, { limit: 50 }).then(setConversations);
  }, [token]);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/api/v1/portal/live`);
    ws.onmessage = (event) => {
      try {
        setLiveEvents((prev) => [JSON.parse(event.data), ...prev].slice(0, 10));
        listConversations(token, { limit: 50 }).then(setConversations);
      } catch {
        // ignore
      }
    };
    return () => ws.close();
  }, [token]);

  useEffect(() => {
    if (!selected) return;
    getConversation(token, selected).then(setDetail);
  }, [token, selected]);

  return (
    <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
      <Card className="overflow-hidden p-0">
        <h3 className="border-b border-slate-100 p-4 text-sm font-semibold text-slate-700">Recent Conversations</h3>
        {liveEvents.length > 0 && (
          <div className="border-b border-amber-100 bg-amber-50 p-2 text-xs text-amber-800">
            {liveEvents.length} live escalation event(s) received this session
          </div>
        )}
        {!conversations ? (
          <div className="p-4"><Skeleton className="h-96 w-full" /></div>
        ) : (
          <ul className="max-h-[70vh] overflow-y-auto">
            {conversations.map((c) => (
              <li key={c.conversation_id}>
                <button
                  onClick={() => setSelected(c.conversation_id)}
                  className={`flex w-full flex-col items-start gap-1 border-b border-slate-100 px-4 py-3 text-left hover:bg-slate-50 ${selected === c.conversation_id ? "bg-blue-50" : ""}`}
                >
                  <span className="flex w-full items-center justify-between">
                    <span className="text-xs font-mono text-slate-500">{c.conversation_id}</span>
                    <Badge tone={c.escalated ? "danger" : c.contained ? "success" : "neutral"}>
                      {c.escalated ? "Escalated" : c.contained ? "Contained" : "Active"}
                    </Badge>
                  </span>
                  <span className="text-xs text-slate-400">{c.channel} &middot; {c.intent ?? "unclassified"}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-4">
        {!detail ? (
          <p className="text-sm text-slate-400">Select a conversation to view its transcript.</p>
        ) : (
          <div>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-navy">{detail.conversation.conversation_id}</h3>
              <button
                className="rounded-full bg-accent px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
                title="Takeover requires a live channel session to hand off into -- recorded here as an intent, not yet wired to an active socket handoff"
              >
                Takeover
              </button>
            </div>
            <div className="space-y-3">
              {detail.messages.map((m: any) => (
                <div key={m.message_id} className={`max-w-[80%] rounded-xl p-3 text-sm ${m.sender === "customer" ? "bg-slate-100" : "ml-auto bg-blue-50"}`}>
                  <p>{m.text}</p>
                  {m.sender === "assistant" && m.intent && (
                    <div className="mt-1.5 flex gap-1.5">
                      <Badge tone="accent">{m.intent}</Badge>
                      {m.confidence != null && <Badge tone="neutral">{Math.round(m.confidence * 100)}% confidence</Badge>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
