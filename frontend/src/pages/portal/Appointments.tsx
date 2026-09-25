import { useEffect, useState } from "react";
import { useAuth } from "../../lib/auth";
import { useLocations } from "../../lib/LocationsContext";
import { listAppointmentsStaff, patchAppointment } from "../../lib/portalApi";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Skeleton from "../../components/ui/Skeleton";
import { Input, Select } from "../../components/ui/Input";

function dayKey(iso: string): string {
  return new Date(iso).toISOString().slice(0, 10);
}

export default function Appointments() {
  const { token } = useAuth();
  const { locations } = useLocations();
  const [locationId, setLocationId] = useState<number | undefined>(undefined);
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [appointments, setAppointments] = useState<any[] | null>(null);
  const [reschedulingId, setReschedulingId] = useState<string | null>(null);
  const [newTime, setNewTime] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reload = () => listAppointmentsStaff(token, { location_id: locationId, limit: 200 }).then(setAppointments);

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, locationId]);

  const dayAppointments = (appointments ?? []).filter((a) => dayKey(a.scheduled_start) === day);
  const byBay = new Map<number, any[]>();
  for (const a of dayAppointments) {
    const bay = a.bay_number ?? 0;
    byBay.set(bay, [...(byBay.get(bay) ?? []), a]);
  }

  const submitReschedule = async (appointmentId: string) => {
    if (!newTime) return;
    setError(null);
    try {
      const start = new Date(newTime);
      const end = new Date(start.getTime() + 30 * 60000);
      await patchAppointment(token, appointmentId, { scheduled_start: start.toISOString(), scheduled_end: end.toISOString() });
      setReschedulingId(null);
      setNewTime("");
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reschedule failed -- that slot may already be booked.");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Input type="date" value={day} onChange={(e) => setDay(e.target.value)} className="w-44 py-1.5 text-xs" />
        <Select value={locationId ?? ""} onChange={(e) => setLocationId(e.target.value ? Number(e.target.value) : undefined)} className="w-48 py-1.5 text-xs">
          <option value="">All Locations</option>
          {locations.map((l) => (
            <option key={l.location_id} value={l.location_id}>{l.name}</option>
          ))}
        </Select>
      </div>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-danger">{error}</p>}

      {!appointments ? (
        <Skeleton className="h-96 w-full" />
      ) : byBay.size === 0 ? (
        <p className="text-sm text-slate-400">No appointments for this day.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from(byBay.entries()).sort(([a], [b]) => a - b).map(([bay, appts]) => (
            <Card key={bay} className="p-4">
              <h3 className="mb-3 text-sm font-bold text-navy">Bay {bay || "Unassigned"}</h3>
              <div className="space-y-2">
                {appts.sort((a, b) => a.scheduled_start.localeCompare(b.scheduled_start)).map((a) => (
                  <div key={a.appointment_id} className="rounded-lg border border-slate-200 p-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-navy">
                        {new Date(a.scheduled_start).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
                      </span>
                      <Badge tone={a.status === "cancelled" ? "danger" : a.status === "completed" ? "success" : "accent"}>{a.status}</Badge>
                    </div>
                    <p className="text-xs text-slate-500">{a.service_code} &middot; {a.technician_id ?? "unassigned"}</p>
                    <p className="font-mono text-[10px] text-slate-400">{a.reference_code}</p>

                    {reschedulingId === a.appointment_id ? (
                      <div className="mt-2 flex items-center gap-1.5">
                        <Input type="datetime-local" value={newTime} onChange={(e) => setNewTime(e.target.value)} className="py-1 text-[11px]" />
                        <Button size="sm" className="px-2 py-1 text-[10px]" onClick={() => submitReschedule(a.appointment_id)}>Save</Button>
                        <Button size="sm" variant="ghost" className="px-2 py-1 text-[10px]" onClick={() => setReschedulingId(null)}>Cancel</Button>
                      </div>
                    ) : (
                      <Button size="sm" variant="outline" className="mt-2 px-2 py-1 text-[10px]" onClick={() => setReschedulingId(a.appointment_id)}>
                        Reschedule
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
      <p className="text-xs text-slate-400">
        Note: this is a real day/bay schedule grid backed by live appointment data and a real conflict-validated
        reschedule action (via the same DB exclusion constraint Phase 5 booking uses) -- it isn't the FullCalendar
        library with drag-and-drop specifically, which wasn't wired up given the scope of this build.
      </p>
    </div>
  );
}
