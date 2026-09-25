import { createContext, useCallback, useContext, useState } from "react";
import { API_BASE } from "./api";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  roles: string[];
  permissions: string[];
  mfa_enabled: boolean;
  location_id: number | null;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  login: (token: string) => Promise<void>;
  logout: () => void;
  hasPermission: (perm: string) => boolean;
}

const AuthContext = createContext<AuthState>({
  token: null, user: null, login: async () => {}, logout: () => {}, hasPermission: () => false,
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);

  const login = useCallback(async (accessToken: string) => {
    const resp = await fetch(`${API_BASE}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!resp.ok) throw new Error("Failed to load user profile");
    const profile: AuthUser = await resp.json();
    setToken(accessToken);
    setUser(profile);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    void fetch(`${API_BASE}/api/v1/auth/logout`, { method: "POST", credentials: "include" });
  }, []);

  const hasPermission = useCallback((perm: string) => user?.permissions.includes(perm) ?? false, [user]);

  return (
    <AuthContext.Provider value={{ token, user, login, logout, hasPermission }}>{children}</AuthContext.Provider>
  );
}

/** Authenticated fetch helper for the portal -- throws on 401 so callers can redirect to
 * /login rather than silently rendering an empty dashboard. Session persistence across a page
 * reload is intentionally NOT implemented via localStorage (the access token stays in memory
 * only); this is a deliberate security tradeoff for a demo -- refreshing the portal page ends
 * the session, matching how a short-lived access token should be handled without also wiring
 * up the httpOnly refresh-cookie silent-refresh flow, which needs HTTPS to work at all
 * (the refresh cookie is marked Secure) and this local dev setup runs over plain HTTP. */
export async function authFetch(token: string | null, path: string, init: RequestInit = {}): Promise<Response> {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init.headers ?? {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (resp.status === 401) {
    throw new Error("SESSION_EXPIRED");
  }
  return resp;
}

export async function authJson<T>(token: string | null, path: string, init: RequestInit = {}): Promise<T> {
  const resp = await authFetch(token, path, init);
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${path} failed: ${resp.status}`);
  }
  return resp.json();
}

/** A plain `<a href>` can't carry the Authorization header, so CSV/file exports that require
 * auth have to go through fetch + blob instead. */
export async function authDownload(token: string | null, path: string, filename: string): Promise<void> {
  const resp = await authFetch(token, path);
  if (!resp.ok) throw new Error(`Export failed: ${resp.status}`);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
