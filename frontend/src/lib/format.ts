import type { LocationOut } from "./api";

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function formatPriceRange(min: number | null, max: number | null): string {
  if (min == null && max == null) return "Call for pricing";
  if (min != null && max != null) return `${currency.format(min)}–${currency.format(max)}`;
  return currency.format((min ?? max) as number);
}

export function formatDuration(minutes: number | null): string {
  if (minutes == null) return "Varies";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} hr` : `${hours} hr ${rest} min`;
}

const HOUR_LABEL: Record<string, string> = {
  mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday", fri: "Friday", sat: "Saturday", sun: "Sunday",
};

function formatClock(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const hour12 = h % 12 === 0 ? 12 : h % 12;
  return m === 0 ? `${hour12} ${period}` : `${hour12}:${String(m).padStart(2, "0")} ${period}`;
}

type HoursKey = keyof Pick<
  LocationOut,
  | "mon_open" | "mon_close" | "tue_open" | "tue_close" | "wed_open" | "wed_close"
  | "thu_open" | "thu_close" | "fri_open" | "fri_close" | "sat_open" | "sat_close" | "sun_open" | "sun_close"
>;

export function formatHoursToday(location: LocationOut): string {
  const days = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  const today = days[new Date().getDay()];
  const open = location[`${today}_open` as HoursKey];
  const close = location[`${today}_close` as HoursKey];
  if (!open || !close) return "Closed today";
  return `Open today ${formatClock(open)} – ${formatClock(close)}`;
}

export function formatWeeklyHours(location: LocationOut): { day: string; hours: string }[] {
  const order = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
  return order.map((key) => {
    const open = location[`${key}_open` as HoursKey];
    const close = location[`${key}_close` as HoursKey];
    return { day: HOUR_LABEL[key], hours: open && close ? `${formatClock(open)} – ${formatClock(close)}` : "Closed" };
  });
}

export function formatSlotTime(isoString: string): string {
  return new Date(isoString).toLocaleString("en-US", {
    weekday: "long", month: "long", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export function formatSlotShort(isoString: string): string {
  return new Date(isoString).toLocaleString("en-US", { hour: "numeric", minute: "2-digit" });
}
