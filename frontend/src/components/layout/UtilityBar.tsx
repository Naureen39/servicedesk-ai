import { Link } from "react-router-dom";
import { useLocations } from "../../lib/LocationsContext";
import { formatHoursToday } from "../../lib/format";

export default function UtilityBar() {
  const { locations, selectedId, setSelectedId, selected } = useLocations();

  return (
    <div className="hidden bg-navy text-slate-200 md:block">
      <div className="container-page flex h-9 items-center justify-between text-xs">
        <div className="flex items-center gap-4">
          {locations.length > 0 && (
            <label className="flex items-center gap-1.5">
              <span className="sr-only">Choose your location</span>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 22s7-6.5 7-12a7 7 0 10-14 0c0 5.5 7 12 7 12z" stroke="currentColor" strokeWidth="1.6" />
                <circle cx="12" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.6" />
              </svg>
              <select
                value={selectedId ?? ""}
                onChange={(e) => setSelectedId(Number(e.target.value))}
                className="cursor-pointer border-none bg-transparent text-xs text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-white rounded"
              >
                {locations.map((loc) => (
                  <option key={loc.location_id} value={loc.location_id} className="text-slate-900">
                    {loc.city}, {loc.state}
                  </option>
                ))}
              </select>
            </label>
          )}
          {selected && <span>{formatHoursToday(selected)}</span>}
        </div>
        <div className="flex items-center gap-4">
          {selected?.phone && (
            <a href={`tel:${selected.phone}`} className="hover:text-white">
              {selected.phone}
            </a>
          )}
          <Link to="/recalls" className="font-semibold text-accent hover:text-blue-300">
            Recall Check
          </Link>
        </div>
      </div>
    </div>
  );
}
