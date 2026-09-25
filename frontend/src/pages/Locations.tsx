import { Link } from "react-router-dom";
import { lazy, Suspense } from "react";
import { useLocations } from "../lib/LocationsContext";
import { formatWeeklyHours } from "../lib/format";
import { useDocumentHead } from "../lib/useDocumentHead";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";
import Skeleton from "../components/ui/Skeleton";

const LocationMap = lazy(() => import("../components/LocationMap"));

export default function Locations() {
  useDocumentHead({ title: "Locations", description: "Find a Meridian Auto Group location near you, with hours and directions.", path: "/locations" });
  const { locations, loading } = useLocations();

  return (
    <div className="container-page py-16">
      <h1 className="font-display text-3xl font-extrabold text-navy sm:text-4xl">Find a Location</h1>
      <p className="mt-3 max-w-2xl text-slate-600">Three full-service locations, all with certified technicians and real-time online booking.</p>

      <div className="mt-10 overflow-hidden rounded-[var(--radius-card)] border border-slate-200">
        <Suspense fallback={<Skeleton className="h-96 w-full" />}>
          {!loading && locations.length > 0 && <LocationMap locations={locations} />}
        </Suspense>
      </div>

      <div className="mt-10 grid gap-6 md:grid-cols-3">
        {loading &&
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-72 w-full" />)}
        {locations.map((loc) => (
          <Card key={loc.location_id} className="p-6">
            <h2 className="font-display text-xl font-bold text-navy">{loc.name}</h2>
            <p className="mt-1 text-sm text-slate-600">
              {loc.address}
              <br />
              {loc.city}, {loc.state} {loc.zip}
            </p>
            {loc.phone && (
              <a href={`tel:${loc.phone}`} className="mt-2 inline-block text-sm font-semibold text-accent">
                {loc.phone}
              </a>
            )}
            <dl className="mt-4 space-y-1 text-xs text-slate-500">
              {formatWeeklyHours(loc).map((h) => (
                <div key={h.day} className="flex justify-between">
                  <dt>{h.day}</dt>
                  <dd>{h.hours}</dd>
                </div>
              ))}
            </dl>
            <Link to="/book" className="mt-5 block">
              <Button size="sm" className="w-full">
                Book at this Location
              </Button>
            </Link>
          </Card>
        ))}
      </div>
    </div>
  );
}
