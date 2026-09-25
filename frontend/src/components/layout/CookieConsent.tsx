import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Button from "../ui/Button";

const STORAGE_KEY = "meridian-cookie-consent";

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setVisible(true);
    } catch {
      setVisible(true);
    }
  }, []);

  const decide = (value: "accepted" | "declined") => {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // private browsing / storage blocked -- the banner just won't remember the choice
    }
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      role="region"
      aria-label="Cookie consent"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-slate-200 bg-white p-4 shadow-[0_-4px_16px_rgba(0,0,0,0.08)]"
    >
      <div className="container-page flex flex-col items-center justify-between gap-3 sm:flex-row">
        <p className="text-sm text-slate-600">
          This demonstration site uses functional cookies only to remember your preferences -- no trackers or third-party
          analytics. See our{" "}
          <Link to="/privacy" className="font-semibold text-accent underline">
            Privacy Policy
          </Link>
          .
        </p>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" size="sm" onClick={() => decide("declined")}>
            Decline
          </Button>
          <Button size="sm" onClick={() => decide("accepted")}>
            Accept
          </Button>
        </div>
      </div>
    </div>
  );
}
