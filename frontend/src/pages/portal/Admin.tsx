import { useEffect, useState } from "react";
import { useAuth } from "../../lib/auth";
import { createAdminUser, getAdminSettings, listAuditLogs, listRoles, listUsers, patchAdminSettings, patchAdminUser } from "../../lib/portalApi";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/Tabs";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { Input, Label, Select } from "../../components/ui/Input";
import Skeleton from "../../components/ui/Skeleton";

export default function Admin() {
  return (
    <Tabs defaultValue="users">
      <TabsList aria-label="Admin sections">
        <TabsTrigger value="users">Users</TabsTrigger>
        <TabsTrigger value="roles">Roles</TabsTrigger>
        <TabsTrigger value="audit">Audit Log</TabsTrigger>
        <TabsTrigger value="settings">Settings</TabsTrigger>
      </TabsList>
      <TabsContent value="users"><UsersTab /></TabsContent>
      <TabsContent value="roles"><RolesTab /></TabsContent>
      <TabsContent value="audit"><AuditTab /></TabsContent>
      <TabsContent value="settings"><SettingsTab /></TabsContent>
    </Tabs>
  );
}

function UsersTab() {
  const { token } = useAuth();
  const [users, setUsers] = useState<any[] | null>(null);
  const [roles, setRoles] = useState<any[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", display_name: "", role_names: [] as string[] });
  const [error, setError] = useState<string | null>(null);

  const reload = () => listUsers(token).then(setUsers);

  useEffect(() => {
    reload();
    listRoles(token).then(setRoles).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const toggleActive = async (u: any) => {
    await patchAdminUser(token, u.id, { is_active: !u.is_active });
    reload();
  };

  const submitCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await createAdminUser(token, form);
      setCreating(false);
      setForm({ email: "", password: "", display_name: "", role_names: [] });
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setCreating((v) => !v)}>{creating ? "Cancel" : "+ New User"}</Button>
      </div>
      {creating && (
        <Card className="p-4">
          <form className="grid gap-3 sm:grid-cols-2" onSubmit={submitCreate}>
            <div><Label htmlFor="nu-email">Email</Label><Input id="nu-email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div><Label htmlFor="nu-pass">Password</Label><Input id="nu-pass" type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
            <div><Label htmlFor="nu-name">Display Name</Label><Input id="nu-name" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></div>
            <div>
              <Label htmlFor="nu-role">Role</Label>
              <Select id="nu-role" value={form.role_names[0] ?? ""} onChange={(e) => setForm({ ...form, role_names: [e.target.value] })}>
                <option value="">Select role</option>
                {roles?.map((r) => <option key={r.id} value={r.name}>{r.name}</option>)}
              </Select>
            </div>
            {error && <p className="sm:col-span-2 text-sm text-danger">{error}</p>}
            <Button type="submit" size="sm" className="sm:col-span-2 w-fit">Create</Button>
          </form>
        </Card>
      )}
      <Card className="overflow-hidden p-0">
        {!users ? <div className="p-4"><Skeleton className="h-64 w-full" /></div> : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400">
              <th className="px-4 py-2">Email</th><th className="px-4 py-2">Roles</th><th className="px-4 py-2">MFA</th><th className="px-4 py-2">Active</th><th className="px-4 py-2" />
            </tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-slate-100">
                  <td className="px-4 py-2">{u.email}</td>
                  <td className="px-4 py-2">{u.roles.map((r: string) => <Badge key={r} tone="accent" className="mr-1">{r}</Badge>)}</td>
                  <td className="px-4 py-2">{u.mfa_enabled ? "Yes" : "No"}</td>
                  <td className="px-4 py-2"><Badge tone={u.is_active ? "success" : "neutral"}>{u.is_active ? "Active" : "Disabled"}</Badge></td>
                  <td className="px-4 py-2 text-right"><Button size="sm" variant="ghost" onClick={() => toggleActive(u)}>{u.is_active ? "Disable" : "Enable"}</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function RolesTab() {
  const { token } = useAuth();
  const [roles, setRoles] = useState<any[] | null>(null);
  useEffect(() => { listRoles(token).then(setRoles); }, [token]);
  if (!roles) return <Skeleton className="h-64 w-full" />;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {roles.map((r) => (
        <Card key={r.id} className="p-4">
          <h3 className="font-bold text-navy">{r.name}</h3>
          <p className="text-xs text-slate-500">{r.description}</p>
          <div className="mt-2 flex flex-wrap gap-1">
            {r.permissions.map((p: string) => <Badge key={p} tone="neutral">{p}</Badge>)}
          </div>
        </Card>
      ))}
    </div>
  );
}

function AuditTab() {
  const { token } = useAuth();
  const [logs, setLogs] = useState<any[] | null>(null);
  const [entityType, setEntityType] = useState("");
  const [action, setAction] = useState("");

  useEffect(() => {
    listAuditLogs(token, { entity_type: entityType || undefined, action: action || undefined, limit: 100 }).then(setLogs);
  }, [token, entityType, action]);

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Input placeholder="Filter by entity type" value={entityType} onChange={(e) => setEntityType(e.target.value)} className="w-56 py-1.5 text-xs" />
        <Input placeholder="Filter by action" value={action} onChange={(e) => setAction(e.target.value)} className="w-56 py-1.5 text-xs" />
      </div>
      <Card className="overflow-hidden p-0">
        {!logs ? <div className="p-4"><Skeleton className="h-64 w-full" /></div> : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400">
              <th className="px-4 py-2">When</th><th className="px-4 py-2">Action</th><th className="px-4 py-2">Entity</th><th className="px-4 py-2">Actor</th><th className="px-4 py-2">IP</th>
            </tr></thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-b border-slate-100">
                  <td className="px-4 py-2 text-xs text-slate-500">{l.created_at ? new Date(l.created_at).toLocaleString() : "—"}</td>
                  <td className="px-4 py-2 font-medium">{l.action}</td>
                  <td className="px-4 py-2 text-xs">{l.entity_type} {l.entity_id ? `#${l.entity_id}` : ""}</td>
                  <td className="px-4 py-2 font-mono text-[10px]">{l.actor_user_id?.slice(0, 8) ?? "system"}</td>
                  <td className="px-4 py-2 text-xs text-slate-400">{l.ip}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function SettingsTab() {
  const { token, hasPermission } = useAuth();
  const [settings, setSettings] = useState<any | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const canManage = hasPermission("settings:manage");

  useEffect(() => { getAdminSettings(token).then(setSettings); }, [token]);

  const save = async () => {
    setStatus(null);
    try {
      const updated = await patchAdminSettings(token, settings);
      setSettings(updated);
      setStatus("Saved -- takes effect on the next conversation turn, no restart needed.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Failed to save");
    }
  };

  if (!settings) return <Skeleton className="h-64 w-full" />;

  return (
    <Card className="max-w-lg p-5">
      <div className="space-y-4">
        <div>
          <Label htmlFor="s-primary">Primary LLM Provider</Label>
          <Select id="s-primary" value={settings.llm_primary} onChange={(e) => setSettings({ ...settings, llm_primary: e.target.value })} disabled={!canManage}>
            <option value="groq">Groq</option>
            <option value="gemini">Gemini</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="s-conf">Confidence Threshold ({settings.confidence_threshold})</Label>
          <input id="s-conf" type="range" min="0" max="1" step="0.01" value={settings.confidence_threshold} onChange={(e) => setSettings({ ...settings, confidence_threshold: Number(e.target.value) })} disabled={!canManage} className="w-full" />
        </div>
        <div>
          <Label htmlFor="s-cache">Cache Similarity Threshold ({settings.cache_similarity_threshold})</Label>
          <input id="s-cache" type="range" min="0" max="1" step="0.01" value={settings.cache_similarity_threshold} onChange={(e) => setSettings({ ...settings, cache_similarity_threshold: Number(e.target.value) })} disabled={!canManage} className="w-full" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><Label htmlFor="s-budget-groq">Daily Budget (Groq)</Label><Input id="s-budget-groq" type="number" value={settings.daily_budget_groq} onChange={(e) => setSettings({ ...settings, daily_budget_groq: Number(e.target.value) })} disabled={!canManage} /></div>
          <div><Label htmlFor="s-budget-gemini">Daily Budget (Gemini)</Label><Input id="s-budget-gemini" type="number" value={settings.daily_budget_gemini} onChange={(e) => setSettings({ ...settings, daily_budget_gemini: Number(e.target.value) })} disabled={!canManage} /></div>
        </div>
        {canManage && <Button onClick={save}>Save Settings</Button>}
        {!canManage && <p className="text-xs text-slate-400">Only admins can edit these settings.</p>}
        {status && <p className="text-xs text-slate-500">{status}</p>}
      </div>
    </Card>
  );
}
