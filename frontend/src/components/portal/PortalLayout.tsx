import { Component, useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { WS_BASE } from "../../lib/api";
import Logo from "../layout/Logo";

interface MenuItem {
  label: string;
  to: string;
  permission?: string;
  icon: string;
}

const MENU: MenuItem[] = [
  { label: "Executive Overview", to: "/portal", permission: "analytics:read", icon: "\u{1F4CA}" },
  { label: "Revenue Analytics", to: "/portal/revenue", permission: "analytics:read", icon: "\u{1F4B0}" },
  { label: "Service Operations", to: "/portal/operations", permission: "analytics:read", icon: "\u{1F527}" },
  { label: "Technician Performance", to: "/portal/technicians", permission: "analytics:read", icon: "\u{1F468}‍\u{1F527}" },
  { label: "Assistant Performance", to: "/portal/assistant", permission: "analytics:read", icon: "\u{1F916}" },
  { label: "Recall & Safety Insights", to: "/portal/recalls", permission: "analytics:read", icon: "⚠️" },
  { label: "Live Conversations", to: "/portal/live", permission: "conversations:read", icon: "\u{1F4AC}" },
  { label: "Escalations", to: "/portal/escalations", permission: "escalations:read", icon: "\u{1F6A8}" },
  { label: "Appointments", to: "/portal/appointments", permission: "appointments:read", icon: "\u{1F4C5}" },
  { label: "Knowledge Base", to: "/portal/kb", permission: "kb:read", icon: "\u{1F4DA}" },
  { label: "Test Console", to: "/portal/test-console", permission: "test_console:use", icon: "\u{1F9EA}" },
  { label: "Admin", to: "/portal/admin", permission: "users:manage", icon: "⚙️" },
];

export function RequireAuth() {
  const { token } = useAuth();
  const location = useLocation();
  if (!token) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <Outlet />;
}

export default function PortalLayout() {
  const { user, token, logout, hasPermission } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [dark, setDark] = useState(false);
  const [notifications, setNotifications] = useState<{ id: string; text: string }[]>([]);
  const [notifOpen, setNotifOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  useEffect(() => {
    if (!token) return;
    const ws = new WebSocket(`${WS_BASE}/api/v1/portal/live`);
    wsRef.current = ws;
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        setNotifications((prev) => [
          { id: `${Date.now()}`, text: `New ${payload.reason ?? "escalation"} (${payload.priority ?? "?"} priority)` },
          ...prev,
        ].slice(0, 20));
      } catch {
        // ignore malformed frames
      }
    };
    return () => ws.close();
  }, [token]);

  const activeItem = MENU.find((m) => (m.to === "/portal" ? location.pathname === "/portal" : location.pathname.startsWith(m.to)));

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className={`shrink-0 border-r border-slate-200 bg-navy text-white transition-all ${collapsed ? "w-16" : "w-64"}`}>
        <div className="flex h-16 items-center justify-between px-4">
          {!collapsed && <Logo dark className="h-6" />}
          <button onClick={() => setCollapsed((v) => !v)} className="rounded p-1.5 text-slate-300 hover:bg-white/10" aria-label="Toggle sidebar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          </button>
        </div>
        <nav className="mt-2 flex flex-col gap-0.5 px-2" aria-label="Portal navigation">
          {MENU.filter((m) => !m.permission || hasPermission(m.permission)).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/portal"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? "bg-accent text-white" : "text-slate-300 hover:bg-white/10"
                }`
              }
            >
              <span aria-hidden="true">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
          <div>
            <p className="text-xs text-slate-400">Meridian Auto Group / Staff Portal</p>
            <h1 className="text-sm font-bold text-navy">{activeItem?.label ?? "Portal"}</h1>
          </div>
          <div className="flex items-center gap-3">
            <GlobalSearch />
            <div className="relative">
              <button
                onClick={() => setNotifOpen((v) => !v)}
                className="relative rounded-full p-2 text-slate-500 hover:bg-slate-100"
                aria-label={`Notifications (${notifications.length})`}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" stroke="currentColor" strokeWidth="1.8" /><path d="M13.7 21a2 2 0 0 1-3.4 0" stroke="currentColor" strokeWidth="1.8" /></svg>
                {notifications.length > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-danger text-[9px] font-bold text-white">
                    {notifications.length}
                  </span>
                )}
              </button>
              {notifOpen && (
                <div className="absolute right-0 top-full mt-2 w-80 rounded-lg border border-slate-200 bg-white p-2 shadow-lg">
                  {notifications.length === 0 && <p className="p-3 text-sm text-slate-400">No new notifications.</p>}
                  {notifications.map((n) => (
                    <p key={n.id} className="rounded px-3 py-2 text-xs text-slate-700 hover:bg-slate-50">{n.text}</p>
                  ))}
                </div>
              )}
            </div>
            <button onClick={() => setDark((v) => !v)} className="rounded-full p-2 text-slate-500 hover:bg-slate-100" aria-label="Toggle dark mode">
              {dark ? "☀️" : "\u{1F319}"}
            </button>
            <div className="flex items-center gap-2 border-l border-slate-200 pl-3">
              <div className="text-right">
                <p className="text-xs font-semibold text-navy">{user?.display_name ?? user?.email}</p>
                <p className="text-[10px] text-slate-400">{user?.roles.join(", ")}</p>
              </div>
              <button
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
                className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-200"
              >
                Sign Out
              </button>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6">
          <PortalErrorBoundary>
            <Outlet />
          </PortalErrorBoundary>
        </main>
      </div>
    </div>
  );
}

function GlobalSearch() {
  const [q, setQ] = useState("");
  return (
    <form
      className="hidden sm:block"
      onSubmit={(e) => {
        e.preventDefault();
      }}
    >
      <label htmlFor="portal-search" className="sr-only">Search customer, reference code, or VIN</label>
      <input
        id="portal-search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search customer, reference code, VIN last 6..."
        className="w-72 rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      />
    </form>
  );
}

class PortalErrorBoundary extends Component<{ children: React.ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-[var(--radius-card)] border border-red-200 bg-red-50 p-6 text-center">
          <p className="font-semibold text-danger">Something went wrong loading this page.</p>
          <p className="mt-1 text-sm text-red-700">{this.state.error.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
