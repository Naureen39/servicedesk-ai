import { authJson } from "./auth";

export interface DateRange {
  from?: string;
  to?: string;
  location_id?: number;
}

function qs(params: Record<string, string | number | undefined>): string {
  const url = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") url.set(k, String(v));
  }
  const s = url.toString();
  return s ? `?${s}` : "";
}

const rangeParams = (r: DateRange) => ({ from: r.from, to: r.to, location_id: r.location_id });

// --- Analytics ---
export const getOverview = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/overview${qs(rangeParams(r))}`);

export const getRevenue = (token: string | null, r: DateRange, granularity: "day" | "month" = "day", compare?: string) =>
  authJson<any>(token, `/api/v1/analytics/revenue${qs({ ...rangeParams(r), granularity, compare })}`);

export const getTopServices = (token: string | null, r: DateRange, limit = 10) =>
  authJson<any>(token, `/api/v1/analytics/revenue/top-services${qs({ ...rangeParams(r), limit })}`);

export const getRevenueByPayType = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/revenue/by-pay-type${qs(rangeParams(r))}`);

export const getRevenueByLocation = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/revenue/by-location${qs(rangeParams(r))}`);

export const getRevenueByCategory = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/revenue/by-category${qs(rangeParams(r))}`);

export const getAroDistribution = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/revenue/aro-distribution${qs(rangeParams(r))}`);

export const getOperations = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/operations${qs(rangeParams(r))}`);

export const getOperationsFunnel = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/operations/funnel${qs(rangeParams(r))}`);

export const getOperationsHeatmap = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/operations/heatmap${qs(rangeParams(r))}`);

export const getWaitVsPromise = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/operations/wait-vs-promise${qs(rangeParams(r))}`);

export const getTechnicians = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/technicians${qs(rangeParams(r))}`);

export const getAssistant = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/assistant${qs(rangeParams(r))}`);

export const getAssistantSummary = (token: string | null, r: DateRange) =>
  authJson<any>(token, `/api/v1/analytics/assistant/summary${qs(rangeParams(r))}`);

export const getRecalls = (token: string | null, make?: string) =>
  authJson<any>(token, `/api/v1/analytics/recalls${qs({ make })}`);

export const getRecallsCustomerImpact = (token: string | null) =>
  authJson<any>(token, "/api/v1/analytics/recalls/customer-impact");

export const exportRevenueCsvUrl = (r: DateRange) =>
  `/api/v1/analytics/export.csv${qs(rangeParams(r))}`;

// --- Staff: conversations / escalations ---
export const listConversations = (token: string | null, params: { location_id?: number; channel?: string; limit?: number } = {}) =>
  authJson<any[]>(token, `/api/v1/conversations${qs(params)}`);

export const getConversation = (token: string | null, id: string) =>
  authJson<any>(token, `/api/v1/conversations/${id}`);

export const listEscalations = (token: string | null, params: { status?: string; priority?: string; location_id?: number } = {}) =>
  authJson<any[]>(token, `/api/v1/escalations${qs(params)}`);

export const patchEscalation = (token: string | null, id: string, payload: Record<string, unknown>) =>
  authJson<any>(token, `/api/v1/escalations/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });

export const replyToEscalation = (token: string | null, id: string, text: string) =>
  authJson<any>(token, `/api/v1/escalations/${id}/reply`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });

// --- Appointments ---
export const listAppointmentsStaff = (token: string | null, params: { location_id?: number; status?: string; limit?: number } = {}) =>
  authJson<any[]>(token, `/api/v1/appointments${qs(params)}`);

export const patchAppointment = (token: string | null, id: string, payload: Record<string, unknown>) =>
  authJson<any>(token, `/api/v1/appointments/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });

// --- Admin ---
export const listUsers = (token: string | null) => authJson<any[]>(token, "/api/v1/admin/users");
export const createAdminUser = (token: string | null, payload: Record<string, unknown>) =>
  authJson<any>(token, "/api/v1/admin/users", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
export const patchAdminUser = (token: string | null, id: string, payload: Record<string, unknown>) =>
  authJson<any>(token, `/api/v1/admin/users/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
export const listRoles = (token: string | null) => authJson<any[]>(token, "/api/v1/admin/roles");
export const listAuditLogs = (token: string | null, params: { entity_type?: string; action?: string; limit?: number } = {}) =>
  authJson<any[]>(token, `/api/v1/admin/audit-logs${qs(params)}`);
export const getAdminSettings = (token: string | null) => authJson<any>(token, "/api/v1/admin/settings");
export const patchAdminSettings = (token: string | null, payload: Record<string, unknown>) =>
  authJson<any>(token, "/api/v1/admin/settings", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });

export const listKbDocuments = (token: string | null) => authJson<any[]>(token, "/api/v1/admin/kb");
export const getKbDocument = (token: string | null, id: number) => authJson<any>(token, `/api/v1/admin/kb/${id}`);
export const createKbDocument = (token: string | null, payload: Record<string, unknown>) =>
  authJson<any>(token, "/api/v1/admin/kb", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
export const updateKbDocument = (token: string | null, id: number, payload: Record<string, unknown>) =>
  authJson<any>(token, `/api/v1/admin/kb/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
export const publishKbDocument = (token: string | null, id: number) =>
  authJson<any>(token, `/api/v1/admin/kb/${id}/publish`, { method: "POST" });

// --- Test console ---
export const sendTestConsoleMessage = (token: string | null, conversationId: string | null, text: string) =>
  authJson<any>(token, "/api/v1/test-console/message", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, text }),
  });
