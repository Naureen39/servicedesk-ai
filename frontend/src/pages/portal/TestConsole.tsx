import { useState } from "react";
import { useAuth } from "../../lib/auth";
import { sendTestConsoleMessage } from "../../lib/portalApi";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";

interface Turn {
  role: "user" | "assistant";
  text: string;
  debug?: any;
}

export default function TestConsole() {
  const { token } = useAuth();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [lastDebug, setLastDebug] = useState<any | null>(null);

  const send = async () => {
    if (!draft.trim() || sending) return;
    const text = draft.trim();
    setDraft("");
    setTurns((prev) => [...prev, { role: "user", text }]);
    setSending(true);
    try {
      const result = await sendTestConsoleMessage(token, conversationId, text);
      setConversationId(result.conversation_id);
      setTurns((prev) => [...prev, { role: "assistant", text: result.reply_text, debug: result }]);
      setLastDebug(result);
    } catch (e) {
      setTurns((prev) => [...prev, { role: "assistant", text: `Error: ${e instanceof Error ? e.message : "failed"}` }]);
    } finally {
      setSending(false);
    }
  };

  const reset = () => {
    setConversationId(null);
    setTurns([]);
    setLastDebug(null);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <Card className="flex h-[70vh] flex-col p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Conversation {conversationId ? `(${conversationId})` : "(new)"}</h3>
          <Button size="sm" variant="outline" onClick={reset}>New Conversation</Button>
        </div>
        <div className="flex-1 space-y-2 overflow-y-auto">
          {turns.map((t, i) => (
            <div key={i} className={`max-w-[80%] rounded-xl p-3 text-sm ${t.role === "user" ? "ml-auto bg-accent text-white" : "bg-slate-100"}`}>
              {t.text}
            </div>
          ))}
        </div>
        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <label htmlFor="console-input" className="sr-only">Message</label>
          <Input id="console-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Ask something to test the assistant..." />
          <Button type="submit" disabled={sending || !draft.trim()}>{sending ? "..." : "Send"}</Button>
        </form>
      </Card>

      <Card className="h-[70vh] overflow-y-auto p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-700">Debug Panel</h3>
        {!lastDebug ? (
          <p className="text-xs text-slate-400">Send a message to see debug output.</p>
        ) : (
          <dl className="space-y-3 text-xs">
            <Row label="Intent"><Badge tone="accent">{lastDebug.intent ?? "—"}</Badge></Row>
            <Row label="Confidence">{lastDebug.confidence != null ? `${Math.round(lastDebug.confidence * 100)}%` : "—"}</Row>
            <Row label="Escalated"><Badge tone={lastDebug.escalated ? "danger" : "success"}>{String(lastDebug.escalated)}</Badge></Row>
            <Row label="Provider">{lastDebug.provider ?? "template (no LLM call)"}</Row>
            <Row label="Tokens">{lastDebug.tokens_in} in / {lastDebug.tokens_out} out</Row>
            <Row label="Cache Hit">{String(lastDebug.cache_hit)}</Row>
            <Row label="Latency">{lastDebug.latency_ms} ms</Row>
            <div>
              <dt className="font-semibold text-slate-500">Slots</dt>
              <dd className="mt-1 rounded bg-slate-50 p-2 font-mono text-[10px]">{JSON.stringify(lastDebug.slots, null, 2)}</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-500">Retrieved Chunks ({lastDebug.retrieved_chunks.length})</dt>
              <dd className="mt-1 space-y-1.5">
                {lastDebug.retrieved_chunks.map((c: any, i: number) => (
                  <div key={i} className="rounded bg-slate-50 p-2">
                    <p className="font-semibold text-slate-600">{c.title} &middot; {c.section} ({(c.similarity * 100).toFixed(0)}%)</p>
                    <p className="mt-0.5 text-slate-500">{c.content.slice(0, 140)}...</p>
                  </div>
                ))}
              </dd>
            </div>
          </dl>
        )}
      </Card>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 pb-2">
      <dt className="font-semibold text-slate-500">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
