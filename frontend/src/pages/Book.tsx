import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useDocumentHead } from "../lib/useDocumentHead";
import { useLocations } from "../lib/LocationsContext";
import {
  listServices, liveNhtsaMakes, liveNhtsaModels, getAvailability, createAppointment,
  type ServiceCatalogOut, type SlotOfferOut, type AppointmentCreateResponse,
} from "../lib/api";
import { formatDuration, formatPriceRange, formatSlotShort, formatSlotTime } from "../lib/format";
import { Input, Label, Select } from "../components/ui/Input";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import Skeleton from "../components/ui/Skeleton";
import { API_BASE } from "../lib/api";

const STEPS = ["Vehicle", "Service", "Date & Time", "Contact"] as const;
const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 30 }, (_, i) => CURRENT_YEAR + 1 - i);

export default function Book() {
  useDocumentHead({ title: "Book Service", description: "Schedule a real service appointment in minutes.", path: "/book" });
  const routerLocation = useLocation();
  const { locations, selectedId, setSelectedId } = useLocations();
  const preselectedServiceCode = (routerLocation.state as { serviceCode?: string } | null)?.serviceCode;

  const [step, setStep] = useState(0);

  // Vehicle
  const [year, setYear] = useState<number | "">("");
  const [makes, setMakes] = useState<string[]>([]);
  const [make, setMake] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [vin, setVin] = useState("");

  // Service
  const [services, setServices] = useState<ServiceCatalogOut[] | null>(null);
  const [serviceCode, setServiceCode] = useState(preselectedServiceCode ?? "");

  // Date/Time
  const [slots, setSlots] = useState<SlotOfferOut[] | null>(null);
  const [slotsError, setSlotsError] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<SlotOfferOut | null>(null);

  // Contact
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<AppointmentCreateResponse | null>(null);

  useEffect(() => {
    listServices().then(setServices).catch(() => setServices([]));
  }, []);

  useEffect(() => {
    if (!year) return;
    liveNhtsaMakes(Number(year)).then(setMakes).catch(() => setMakes([]));
  }, [year]);

  useEffect(() => {
    if (!year || !make) return;
    liveNhtsaModels(Number(year), make).then(setModels).catch(() => setModels([]));
  }, [year, make]);

  useEffect(() => {
    if (step !== 2 || !selectedId || !serviceCode) return;
    setSlots(null);
    setSlotsError(null);
    getAvailability(selectedId, serviceCode)
      .then(setSlots)
      .catch(() => setSlotsError("No availability could be found. Please try a different service or location."));
  }, [step, selectedId, serviceCode]);

  const selectedService = services?.find((s) => s.code === serviceCode) ?? null;
  const selectedLocation = locations.find((l) => l.location_id === selectedId) ?? null;

  const canProceed = [
    !!year && !!make && !!model,
    !!serviceCode,
    !!selectedSlot,
    name.trim().length > 0 && /^[\d\s()+-]{7,}$/.test(phone),
  ][step];

  const handleSubmit = async () => {
    if (!selectedSlot || !selectedId) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await createAppointment({
        location_id: selectedId,
        service_code: serviceCode,
        scheduled_start: selectedSlot.start,
        name,
        phone,
        email: email || undefined,
        vehicle: { year: Number(year), make, model, vin: vin || undefined },
      });
      setConfirmation(result);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Booking failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (confirmation) {
    const last4 = phone.replace(/\D/g, "").slice(-4);
    return (
      <div className="container-page max-w-lg py-24 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-3xl text-success" aria-hidden="true">
          &#10003;
        </div>
        <h1 className="mt-6 font-display text-2xl font-bold text-navy">Appointment confirmed</h1>
        <p className="mt-2 text-slate-600">{formatSlotTime(confirmation.scheduled_start)}</p>
        <p className="mt-4 rounded-lg bg-slate-100 px-4 py-3 font-mono text-lg font-bold tracking-wide text-navy">
          {confirmation.reference_code}
        </p>
        <p className="mt-2 text-sm text-slate-500">Save this code along with your phone number to reschedule or cancel later.</p>
        <div className="mt-6 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <a
            href={`${API_BASE}/api/v1/appointments/by-reference/${confirmation.reference_code}/calendar.ics?phone_last4=${last4}`}
            className="inline-block"
          >
            <Button variant="outline">Add to Calendar</Button>
          </a>
          <Button onClick={() => window.location.assign("/")}>Back to Home</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container-page py-16">
      <h1 className="font-display text-3xl font-extrabold text-navy sm:text-4xl">Book Service</h1>

      <ol className="mt-8 flex flex-wrap gap-x-6 gap-y-2" aria-label="Booking steps">
        {STEPS.map((s, i) => (
          <li key={s} className={`flex items-center gap-2 text-sm font-semibold ${i === step ? "text-accent" : i < step ? "text-success" : "text-slate-400"}`}>
            <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${i === step ? "bg-accent text-white" : i < step ? "bg-success text-white" : "bg-slate-200"}`}>
              {i < step ? "✓" : i + 1}
            </span>
            {s}
          </li>
        ))}
      </ol>

      <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_320px]">
        <Card className="p-6 sm:p-8">
          {step === 0 && (
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <Label htmlFor="book-year">Year</Label>
                <Select id="book-year" value={year} onChange={(e) => { setYear(e.target.value ? Number(e.target.value) : ""); setMake(""); setModel(""); }}>
                  <option value="">Select year</option>
                  {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
                </Select>
              </div>
              <div>
                <Label htmlFor="book-make">Make</Label>
                <Select id="book-make" value={make} onChange={(e) => { setMake(e.target.value); setModel(""); }} disabled={!year}>
                  <option value="">Select make</option>
                  {makes.map((m) => <option key={m} value={m}>{m}</option>)}
                </Select>
              </div>
              <div>
                <Label htmlFor="book-model">Model</Label>
                <Select id="book-model" value={model} onChange={(e) => setModel(e.target.value)} disabled={!make}>
                  <option value="">Select model</option>
                  {models.map((m) => <option key={m} value={m}>{m}</option>)}
                </Select>
              </div>
              <div className="sm:col-span-3">
                <Label htmlFor="book-vin">VIN (optional)</Label>
                <Input id="book-vin" value={vin} onChange={(e) => setVin(e.target.value.toUpperCase())} maxLength={17} placeholder="Optional -- helps us confirm exact trim" />
              </div>
            </div>
          )}

          {step === 1 && (
            <div>
              {services === null && <Skeleton className="h-40 w-full" />}
              <div className="grid gap-3 sm:grid-cols-2">
                {services?.map((s) => (
                  <button
                    key={s.code}
                    onClick={() => setServiceCode(s.code)}
                    className={`rounded-[var(--radius-card)] border p-4 text-left transition-colors ${
                      serviceCode === s.code ? "border-accent bg-blue-50" : "border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    <p className="font-semibold text-navy">{s.name}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {formatDuration(s.duration_min)} &middot; {formatPriceRange(s.parts_cost_min, s.parts_cost_max)}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <Label htmlFor="book-location">Location</Label>
              <Select id="book-location" value={selectedId ?? ""} onChange={(e) => setSelectedId(Number(e.target.value))} className="mb-5 max-w-sm">
                {locations.map((loc) => (
                  <option key={loc.location_id} value={loc.location_id}>{loc.name}</option>
                ))}
              </Select>

              {slots === null && !slotsError && <Skeleton className="h-32 w-full" />}
              {slotsError && <p className="text-sm text-danger">{slotsError}</p>}
              {slots && slots.length === 0 && <p className="text-sm text-slate-500">No open slots in the next few weeks for this service.</p>}

              <div className="grid gap-2 sm:grid-cols-3">
                {slots?.map((slot) => (
                  <button
                    key={slot.start}
                    onClick={() => setSelectedSlot(slot)}
                    className={`rounded-[var(--radius-input)] border p-3 text-left text-sm ${
                      selectedSlot?.start === slot.start ? "border-accent bg-blue-50 font-semibold text-accent" : "border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    {formatSlotTime(slot.start).split(" at ")[0]}
                    <br />
                    {formatSlotShort(slot.start)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="book-name">Full Name</Label>
                <Input id="book-name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="book-phone">Phone</Label>
                <Input id="book-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="614-555-0100" />
              </div>
              <div className="sm:col-span-2">
                <Label htmlFor="book-email">Email (optional)</Label>
                <Input id="book-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              {submitError && <p className="sm:col-span-2 text-sm text-danger" role="alert">{submitError}</p>}
            </div>
          )}

          <div className="mt-8 flex justify-between">
            <Button variant="outline" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>
              Back
            </Button>
            {step < STEPS.length - 1 ? (
              <Button onClick={() => setStep((s) => s + 1)} disabled={!canProceed}>
                Continue
              </Button>
            ) : (
              <Button onClick={handleSubmit} disabled={!canProceed || submitting}>
                {submitting ? "Booking..." : "Confirm Booking"}
              </Button>
            )}
          </div>
        </Card>

        <Card className="h-fit p-6">
          <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">Summary</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <SummaryRow label="Vehicle" value={year && make && model ? `${year} ${make} ${model}` : undefined} />
            <SummaryRow label="Service" value={selectedService?.name} />
            <SummaryRow label="Location" value={selectedLocation?.name} />
            <SummaryRow label="Time" value={selectedSlot ? formatSlotTime(selectedSlot.start) : undefined} />
            <SummaryRow label="Estimated Price" value={selectedService ? formatPriceRange(selectedService.parts_cost_min, selectedService.parts_cost_max) : undefined} />
          </dl>
        </Card>
      </div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-100 pb-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-navy">{value ?? "—"}</dd>
    </div>
  );
}
