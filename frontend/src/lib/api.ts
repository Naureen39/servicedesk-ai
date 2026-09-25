export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

async function getJson<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  const resp = await fetch(url.toString());
  if (!resp.ok) throw new Error(`${path} failed: ${resp.status}`);
  return resp.json();
}

export interface VoiceSessionToken {
  session_token: string;
  conversation_id: string;
  expires_in: number;
}

export async function createVoiceSession(): Promise<VoiceSessionToken> {
  const resp = await fetch(`${API_BASE}/api/v1/chat/session?channel=voice`, { method: "POST" });
  if (!resp.ok) throw new Error(`Failed to create voice session: ${resp.status}`);
  return resp.json();
}

export async function createChatSession(): Promise<VoiceSessionToken> {
  const resp = await fetch(`${API_BASE}/api/v1/chat/session?channel=chat`, { method: "POST" });
  if (!resp.ok) throw new Error(`Failed to create chat session: ${resp.status}`);
  return resp.json();
}

export interface ChatMessageResult {
  conversation_id: string;
  message_id: string | null;
  text: string;
  escalated: boolean;
}

export async function sendChatMessage(token: string, conversationId: string, text: string): Promise<ChatMessageResult> {
  const resp = await fetch(`${API_BASE}/api/v1/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ conversation_id: conversationId, text }),
  });
  if (!resp.ok) throw new Error(`Chat message failed: ${resp.status}`);
  return resp.json();
}

export async function sendChatFeedback(token: string, conversationId: string, messageId: string, helpful: boolean): Promise<void> {
  await fetch(`${API_BASE}/api/v1/chat/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ conversation_id: conversationId, message_id: messageId, helpful }),
  });
}

export interface LocationOut {
  location_id: number;
  name: string;
  address: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  latitude: number | null;
  longitude: number | null;
  timezone: string | null;
  phone: string | null;
  mon_open: string | null; mon_close: string | null;
  tue_open: string | null; tue_close: string | null;
  wed_open: string | null; wed_close: string | null;
  thu_open: string | null; thu_close: string | null;
  fri_open: string | null; fri_close: string | null;
  sat_open: string | null; sat_close: string | null;
  sun_open: string | null; sun_close: string | null;
}

export interface ServiceCatalogOut {
  code: string;
  name: string;
  category: string | null;
  labor_hours_min: number | null;
  labor_hours_max: number | null;
  parts_cost_min: number | null;
  parts_cost_max: number | null;
  duration_min: number | null;
  parts_available: boolean;
}

export interface LiveRecallOut {
  campaign_number: string;
  component: string;
  summary: string;
  consequence: string;
  remedy: string;
  report_date: string;
}

export interface SlotOfferOut {
  start: string;
  end: string;
}

export interface AppointmentCreateResponse {
  appointment_id: string;
  reference_code: string;
  scheduled_start: string;
  scheduled_end: string;
  status: string;
}

export const listLocations = () => getJson<LocationOut[]>("/api/v1/locations");
export const listServices = (category?: string) => getJson<ServiceCatalogOut[]>("/api/v1/services", { category });
export const getService = (code: string) => getJson<ServiceCatalogOut>(`/api/v1/services/${code}`);

export const liveNhtsaMakes = (year: number) => getJson<string[]>("/api/v1/nhtsa/makes", { year });
export const liveNhtsaModels = (year: number, make: string) => getJson<string[]>("/api/v1/nhtsa/models", { year, make });
export const liveNhtsaRecalls = (year: number, make: string, model: string) =>
  getJson<LiveRecallOut[]>("/api/v1/nhtsa/recalls", { year, make, model });

export interface ComplaintSummaryOut {
  make: string;
  model: string;
  model_year: number;
  component: string;
  total_count: number;
  crash_count: number;
  fire_count: number;
  injured_count: number;
}
export const complaintsSummary = (year?: number, make?: string, model?: string) =>
  getJson<ComplaintSummaryOut[]>("/api/v1/complaints/summary", { year, make, model });

export const getAvailability = (locationId: number, serviceCode: string) =>
  getJson<SlotOfferOut[]>("/api/v1/availability", { location_id: locationId, service_code: serviceCode });

export interface AppointmentCreateRequest {
  location_id: number;
  service_code: string;
  scheduled_start: string;
  name: string;
  phone: string;
  email?: string;
  vehicle: { year: number; make: string; model: string; vin?: string };
}

export async function createAppointment(payload: AppointmentCreateRequest): Promise<AppointmentCreateResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/appointments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Booking failed: ${resp.status}`);
  }
  return resp.json();
}

export async function submitContact(payload: {
  name: string; email: string; phone?: string; location_id?: number; subject: string; message: string;
}): Promise<{ message_id: string; status: string }> {
  const resp = await fetch(`${API_BASE}/api/v1/contact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new Error(`Contact form failed: ${resp.status}`);
  return resp.json();
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  mfa_required: boolean;
  mfa_challenge_token: string | null;
}

export async function staffLogin(email: string, password: string): Promise<LoginResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(detail.detail ?? "Login failed");
  }
  return resp.json();
}

export async function staffMfaVerify(mfaChallengeToken: string, code: string): Promise<LoginResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/auth/mfa/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ mfa_challenge_token: mfaChallengeToken, code }),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(detail.detail ?? "Invalid code");
  }
  return resp.json();
}
