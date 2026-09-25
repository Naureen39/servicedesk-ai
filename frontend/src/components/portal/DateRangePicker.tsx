import { PRESETS, type Preset } from "../../lib/useDateRange";
import { Input } from "../ui/Input";

interface Props {
  preset: Preset;
  setPreset: (p: Preset) => void;
  range: { from: string; to: string };
  setCustom: (r: { from: string; to: string }) => void;
  compare: boolean;
  setCompare: (v: boolean) => void;
}

export default function DateRangePicker({ preset, setPreset, range, setCustom, compare, setCompare }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex rounded-lg border border-slate-200 bg-white p-0.5">
        {PRESETS.map((p) => (
          <button
            key={p}
            onClick={() => setPreset(p)}
            className={`rounded-md px-2.5 py-1 text-xs font-semibold ${
              preset === p ? "bg-accent text-white" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {p}
          </button>
        ))}
      </div>
      {preset === "Custom" && (
        <div className="flex items-center gap-1.5">
          <Input type="date" value={range.from} onChange={(e) => setCustom({ ...range, from: e.target.value })} className="w-40 py-1.5 text-xs" />
          <span className="text-slate-400">&ndash;</span>
          <Input type="date" value={range.to} onChange={(e) => setCustom({ ...range, to: e.target.value })} className="w-40 py-1.5 text-xs" />
        </div>
      )}
      <label className="flex items-center gap-1.5 text-xs font-semibold text-slate-600">
        <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} className="rounded" />
        Compare
      </label>
    </div>
  );
}
