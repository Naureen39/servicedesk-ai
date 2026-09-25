import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useAuth } from "../../lib/auth";
import { createKbDocument, getKbDocument, listKbDocuments, publishKbDocument, updateKbDocument } from "../../lib/portalApi";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import { Input, Label, Textarea } from "../../components/ui/Input";
import Skeleton from "../../components/ui/Skeleton";

export default function KnowledgeBase() {
  const { token, hasPermission } = useAuth();
  const [docs, setDocs] = useState<any[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | "new" | null>(null);
  const [content, setContent] = useState("");
  const [title, setTitle] = useState("");
  const [sourcePath, setSourcePath] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const canWrite = hasPermission("kb:write");

  const reload = () => listKbDocuments(token).then(setDocs);

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const select = async (id: number | "new") => {
    setStatus(null);
    setSelectedId(id);
    if (id === "new") {
      setContent("# New Document\n\nWrite the article content here.");
      setTitle("");
      setSourcePath("");
      return;
    }
    const doc = await getKbDocument(token, id);
    setContent(doc.content);
    setTitle(doc.title ?? "");
    setSourcePath(doc.source_path);
  };

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      if (selectedId === "new") {
        const doc = await createKbDocument(token, { source_path: sourcePath, title, content });
        setStatus("Created and published.");
        setSelectedId(doc.id);
      } else if (selectedId) {
        await updateKbDocument(token, selectedId, { content, title });
        setStatus("Saved (not yet published -- click Publish to re-embed).");
      }
      reload();
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const publish = async () => {
    if (typeof selectedId !== "number") return;
    setSaving(true);
    try {
      const result = await publishKbDocument(token, selectedId);
      setStatus(result.unchanged ? "No changes to publish." : `Published -- ${result.chunk_count} chunks re-embedded.`);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
      <Card className="overflow-hidden p-0">
        <div className="flex items-center justify-between border-b border-slate-100 p-3">
          <h3 className="text-sm font-semibold text-slate-700">Documents</h3>
          {canWrite && <Button size="sm" variant="outline" onClick={() => select("new")}>+ New</Button>}
        </div>
        {!docs ? (
          <div className="p-3"><Skeleton className="h-64 w-full" /></div>
        ) : (
          <ul className="max-h-[70vh] overflow-y-auto">
            {docs.map((d) => (
              <li key={d.id}>
                <button onClick={() => select(d.id)} className={`block w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 ${selectedId === d.id ? "bg-blue-50 font-semibold text-accent" : "text-slate-700"}`}>
                  {d.title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {selectedId === null ? (
        <p className="text-sm text-slate-400">Select a document to view and edit it.</p>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="p-4">
            {selectedId === "new" && (
              <div className="mb-3 grid gap-2 sm:grid-cols-2">
                <div>
                  <Label htmlFor="kb-title">Title</Label>
                  <Input id="kb-title" value={title} onChange={(e) => setTitle(e.target.value)} disabled={!canWrite} />
                </div>
                <div>
                  <Label htmlFor="kb-path">File name (.md)</Label>
                  <Input id="kb-path" value={sourcePath} onChange={(e) => setSourcePath(e.target.value)} placeholder="my-new-doc.md" disabled={!canWrite} />
                </div>
              </div>
            )}
            {selectedId !== "new" && (
              <div className="mb-3">
                <Label htmlFor="kb-title-existing">Title</Label>
                <Input id="kb-title-existing" value={title} onChange={(e) => setTitle(e.target.value)} disabled={!canWrite} />
              </div>
            )}
            <Label htmlFor="kb-content">Markdown</Label>
            <Textarea id="kb-content" rows={18} value={content} onChange={(e) => setContent(e.target.value)} className="font-mono text-xs" disabled={!canWrite} />
            {canWrite && (
              <div className="mt-3 flex items-center gap-2">
                <Button size="sm" onClick={save} disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
                {typeof selectedId === "number" && (
                  <Button size="sm" variant="outline" onClick={publish} disabled={saving}>Publish (re-embed)</Button>
                )}
                {status && <span className="text-xs text-slate-500">{status}</span>}
              </div>
            )}
          </Card>
          <Card className="max-h-[70vh] overflow-y-auto p-4">
            <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">Preview</h3>
            <div className="prose-chat text-sm text-slate-700">
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
