import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import Logo from "./Logo";
import Button from "../ui/Button";

interface MenuColumn {
  label: string;
  to: string;
  description: string;
}

interface MenuGroup {
  label: string;
  columns: MenuColumn[];
}

const MENU: MenuGroup[] = [
  {
    label: "Service",
    columns: [
      { label: "All Services", to: "/services", description: "Browse our full service menu with real pricing" },
      { label: "Maintenance", to: "/services?category=Maintenance", description: "Oil changes, 60k service, inspections" },
      { label: "Brakes & Tires", to: "/services?category=Brakes", description: "Brake pads, rotors, alignments" },
      { label: "Book Service", to: "/book", description: "Schedule an appointment in minutes" },
    ],
  },
  {
    label: "Recalls & Safety",
    columns: [
      { label: "Check Your Recalls", to: "/recalls", description: "Live NHTSA lookup by year, make, and model" },
      { label: "Complaint Trends", to: "/recalls#complaints", description: "See reported issues for your vehicle" },
    ],
  },
  {
    label: "Parts",
    columns: [{ label: "Genuine Parts", to: "/warranty#parts", description: "OEM parts backed by our warranty" }],
  },
  {
    label: "Warranty",
    columns: [{ label: "Warranty Coverage", to: "/warranty", description: "What's covered, for how long" }],
  },
  {
    label: "Locations",
    columns: [{ label: "Find a Location", to: "/locations", description: "Hours, address, and directions" }],
  },
  {
    label: "About",
    columns: [
      { label: "Our Story", to: "/about", description: "Mission, values, and milestones" },
      { label: "Contact Us", to: "/contact", description: "Questions? We're here to help" },
    ],
  },
];

export default function Header() {
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpenMenu(null);
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="container-page flex h-16 items-center justify-between">
        <Link to="/" aria-label="Meridian Auto Group home">
          <Logo />
        </Link>

        <nav className="hidden lg:flex lg:items-center lg:gap-1" aria-label="Primary">
          {MENU.map((group) => (
            <div
              key={group.label}
              className="relative"
              onMouseEnter={() => setOpenMenu(group.label)}
              onMouseLeave={() => setOpenMenu(null)}
            >
              <button
                className="flex items-center gap-1 rounded px-3 py-2 text-sm font-semibold text-slate-700 hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                aria-haspopup="true"
                aria-expanded={openMenu === group.label}
                onClick={() => setOpenMenu(openMenu === group.label ? null : group.label)}
              >
                {group.label}
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              {openMenu === group.label && (
                <div className="absolute left-0 top-full w-80 rounded-[var(--radius-card)] border border-slate-200 bg-white p-3 shadow-lg">
                  {group.columns.map((col) => (
                    <Link
                      key={col.to}
                      to={col.to}
                      className="block rounded-lg px-3 py-2.5 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                      onClick={() => setOpenMenu(null)}
                    >
                      <div className="text-sm font-semibold text-navy">{col.label}</div>
                      <div className="text-xs text-slate-500">{col.description}</div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <Link to="/login" className="hidden text-sm font-semibold text-slate-600 hover:text-accent sm:block">
            Staff Login
          </Link>
          <Link to="/book">
            <Button size="sm">Book Service</Button>
          </Link>
          <button
            className="rounded p-2 text-slate-700 lg:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            aria-label="Toggle menu"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((v) => !v)}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {mobileOpen && (
        <nav className="border-t border-slate-200 bg-white lg:hidden" aria-label="Mobile">
          <ul className="container-page flex flex-col gap-1 py-3">
            {MENU.map((group) => (
              <li key={group.label}>
                <NavLink
                  to={group.columns[0].to}
                  className="block rounded px-2 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                  onClick={() => setMobileOpen(false)}
                >
                  {group.label}
                </NavLink>
              </li>
            ))}
            <li>
              <NavLink to="/login" className="block rounded px-2 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50" onClick={() => setMobileOpen(false)}>
                Staff Login
              </NavLink>
            </li>
          </ul>
        </nav>
      )}
    </header>
  );
}
