import { Link } from "react-router-dom";
import { useState } from "react";
import Logo from "./Logo";
import { useLocations } from "../../lib/LocationsContext";
import { formatHoursToday } from "../../lib/format";
import { Input } from "../ui/Input";
import Button from "../ui/Button";

const COLUMNS: { title: string; links: { label: string; to: string }[] }[] = [
  {
    title: "Services",
    links: [
      { label: "Oil Changes", to: "/services?category=Maintenance" },
      { label: "Brakes & Tires", to: "/services?category=Brakes" },
      { label: "Diagnostics", to: "/services?category=Diagnostics" },
      { label: "Book Service", to: "/book" },
    ],
  },
  {
    title: "Customer Care",
    links: [
      { label: "Check Recalls", to: "/recalls" },
      { label: "Warranty", to: "/warranty" },
      { label: "Contact Us", to: "/contact" },
      { label: "Locations", to: "/locations" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About Us", to: "/about" },
      { label: "Staff Login", to: "/login" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy Policy", to: "/privacy" },
      { label: "Terms of Use", to: "/terms" },
      { label: "Accessibility Statement", to: "/accessibility" },
      { label: "Cookie Preferences", to: "/privacy#cookies" },
    ],
  },
];

export default function Footer() {
  const { locations } = useLocations();
  const [subscribed, setSubscribed] = useState(false);

  return (
    <footer className="bg-navy text-slate-300">
      <div className="container-page grid gap-10 py-14 md:grid-cols-2 lg:grid-cols-6">
        <div className="lg:col-span-2">
          <Logo dark />
          <p className="mt-4 max-w-xs text-sm text-slate-400">
            Real-time diagnostics, AI-assisted booking, and certified technicians across every location.
          </p>
          <div className="mt-5 flex gap-3">
            {["X", "FB", "IG", "IN"].map((s) => (
              <span
                key={s}
                aria-hidden="true"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-slate-300"
              >
                {s}
              </span>
            ))}
          </div>
        </div>

        {COLUMNS.map((col) => (
          <div key={col.title}>
            <h3 className="text-sm font-bold text-white">{col.title}</h3>
            <ul className="mt-3 space-y-2">
              {col.links.map((link) => (
                <li key={link.to}>
                  <Link to={link.to} className="text-sm text-slate-400 hover:text-white">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}

        <div className="lg:col-span-1">
          <h3 className="text-sm font-bold text-white">Stay Updated</h3>
          <form
            className="mt-3 flex flex-col gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setSubscribed(true);
            }}
          >
            <label htmlFor="newsletter-email" className="sr-only">
              Email address
            </label>
            <Input id="newsletter-email" type="email" required placeholder="you@example.com" className="bg-white/5 text-white placeholder:text-slate-500 border-white/20" />
            <Button type="submit" size="sm" variant="primary">
              {subscribed ? "Subscribed!" : "Subscribe"}
            </Button>
          </form>
        </div>
      </div>

      {locations.length > 0 && (
        <div className="border-t border-white/10">
          <div className="container-page grid gap-4 py-8 sm:grid-cols-2 lg:grid-cols-3">
            {locations.map((loc) => (
              <div key={loc.location_id} className="text-sm">
                <div className="font-semibold text-white">{loc.name}</div>
                <div className="text-slate-400">{loc.address}, {loc.city}, {loc.state} {loc.zip}</div>
                <div className="text-slate-400">{formatHoursToday(loc)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="border-t border-white/10 py-6">
        <div className="container-page flex flex-col items-center justify-between gap-2 text-xs text-slate-500 sm:flex-row">
          <p>&copy; {new Date().getFullYear()} Meridian Auto Group. All rights reserved.</p>
          <p>Demonstration website. Meridian Auto Group is a fictional company.</p>
        </div>
      </div>
    </footer>
  );
}
