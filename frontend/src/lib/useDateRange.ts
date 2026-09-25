import { useState } from "react";

export type Preset = "Today" | "7D" | "30D" | "QTD" | "YTD" | "12M" | "36M" | "Custom";

const PRESETS: Preset[] = ["Today", "7D", "30D", "QTD", "YTD", "12M", "36M", "Custom"];
export { PRESETS };

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function startOfQuarter(d: Date): Date {
  const q = Math.floor(d.getMonth() / 3);
  return new Date(d.getFullYear(), q * 3, 1);
}

export function rangeForPreset(preset: Preset): { from: string; to: string } {
  const now = new Date();
  const to = iso(now);
  switch (preset) {
    case "Today":
      return { from: to, to };
    case "7D":
      return { from: iso(new Date(now.getTime() - 6 * 86400000)), to };
    case "30D":
      return { from: iso(new Date(now.getTime() - 29 * 86400000)), to };
    case "QTD":
      return { from: iso(startOfQuarter(now)), to };
    case "YTD":
      return { from: iso(new Date(now.getFullYear(), 0, 1)), to };
    case "12M":
      return { from: iso(new Date(now.getFullYear() - 1, now.getMonth(), now.getDate())), to };
    case "36M":
      return { from: iso(new Date(now.getFullYear() - 3, now.getMonth(), now.getDate())), to };
    default:
      return { from: iso(new Date(now.getFullYear(), now.getMonth(), 1)), to };
  }
}

export function useDateRange(initial: Preset = "30D") {
  const [preset, setPreset] = useState<Preset>(initial);
  const [custom, setCustom] = useState(rangeForPreset(initial));
  const [compare, setCompare] = useState(false);

  const range = preset === "Custom" ? custom : rangeForPreset(preset);

  const setPresetAndRange = (p: Preset) => {
    setPreset(p);
    if (p !== "Custom") setCustom(rangeForPreset(p));
  };

  return { preset, setPreset: setPresetAndRange, range, setCustom, compare, setCompare };
}
