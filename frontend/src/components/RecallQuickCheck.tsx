import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Select, Label, Input } from "./ui/Input";
import Button from "./ui/Button";
import Badge from "./ui/Badge";
import { liveNhtsaMakes, liveNhtsaModels, liveNhtsaRecalls, type LiveRecallOut } from "../lib/api";

const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 30 }, (_, i) => CURRENT_YEAR + 1 - i);

type Mode = "ymm" | "vin";

interface RecallQuickCheckProps {
  compact?: boolean;
  onChecked?: (v: { year: number; make: string; model: string } | null) => void;
}

export default function RecallQuickCheck({ compact = false, onChecked }: RecallQuickCheckProps) {
  const [mode, setMode] = useState<Mode>("ymm");
  const [year, setYear] = useState<number | "">("");
  const [makes, setMakes] = useState<string[]>([]);
  const [make, setMake] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [vin, setVin] = useState("");
  const [loadingMakes, setLoadingMakes] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<LiveRecallOut[] | null>(null);
  const [checkedFor, setCheckedFor] = useState<string | null>(null);

  useEffect(() => {
    if (!year) {
      setMakes([]);
      return;
    }
    setLoadingMakes(true);
    setMake("");
    setModels([]);
    liveNhtsaMakes(Number(year))
      .then(setMakes)
      .catch(() => setMakes([]))
      .finally(() => setLoadingMakes(false));
  }, [year]);

  useEffect(() => {
    if (!year || !make) {
      setModels([]);
      return;
    }
    setLoadingModels(true);
    setModel("");
    liveNhtsaModels(Number(year), make)
      .then(setModels)
      .catch(() => setModels([]))
      .finally(() => setLoadingModels(false));
  }, [year, make]);

  const runCheck = async () => {
    setError(null);
    setResults(null);
    setChecking(true);
    try {
      if (mode === "vin") {
        throw new Error("VIN decoding uses the same live NHTSA lookup as chat -- try year/make/model here, or ask the assistant to check your VIN.");
      }
      if (!year || !make || !model) {
        setError("Please select a year, make, and model.");
        return;
      }
      const recalls = await liveNhtsaRecalls(Number(year), make, model);
      setResults(recalls);
      setCheckedFor(`${year} ${make} ${model}`);
      onChecked?.({ year: Number(year), make, model });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className={compact ? "" : "rounded-[var(--radius-card)] bg-white p-6 shadow-xl"}>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-display text-lg font-bold text-navy">Recall Quick Check</h3>
        <div className="flex rounded-full bg-slate-100 p-0.5 text-xs font-semibold">
          <button
            className={`rounded-full px-3 py-1 ${mode === "ymm" ? "bg-white text-navy shadow-sm" : "text-slate-500"}`}
            onClick={() => setMode("ymm")}
          >
            Year/Make/Model
          </button>
          <button
            className={`rounded-full px-3 py-1 ${mode === "vin" ? "bg-white text-navy shadow-sm" : "text-slate-500"}`}
            onClick={() => setMode("vin")}
          >
            VIN
          </button>
        </div>
      </div>

      {mode === "ymm" ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <Label htmlFor="rqc-year">Year</Label>
            <Select id="rqc-year" value={year} onChange={(e) => setYear(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Select year</option>
              {YEARS.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="rqc-make">Make</Label>
            <Select id="rqc-make" value={make} onChange={(e) => setMake(e.target.value)} disabled={!year || loadingMakes}>
              <option value="">{loadingMakes ? "Loading..." : "Select make"}</option>
              {makes.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="rqc-model">Model</Label>
            <Select id="rqc-model" value={model} onChange={(e) => setModel(e.target.value)} disabled={!make || loadingModels}>
              <option value="">{loadingModels ? "Loading..." : "Select model"}</option>
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </Select>
          </div>
        </div>
      ) : (
        <div>
          <Label htmlFor="rqc-vin">VIN (17 characters)</Label>
          <Input id="rqc-vin" value={vin} onChange={(e) => setVin(e.target.value.toUpperCase())} maxLength={17} placeholder="1HGCM82633A123456" />
        </div>
      )}

      {error && <p className="mt-3 text-sm text-danger" role="alert">{error}</p>}

      <Button className="mt-4 w-full" onClick={runCheck} disabled={checking}>
        {checking ? "Checking live NHTSA data..." : "Check for Recalls"}
      </Button>

      {results && (
        <div className="mt-5 space-y-3" aria-live="polite">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {results.length} {results.length === 1 ? "recall" : "recalls"} found for {checkedFor}
          </p>
          {results.length === 0 && (
            <p className="rounded-lg bg-green-50 px-3 py-2.5 text-sm text-green-800">
              No open recalls found. Data provided live by NHTSA.
            </p>
          )}
          {results.slice(0, 3).map((r) => (
            <div key={r.campaign_number} className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <div className="mb-1 flex items-center gap-2">
                <Badge tone="warning">{r.campaign_number}</Badge>
                <span className="text-xs text-slate-500">{r.report_date}</span>
              </div>
              <p className="text-sm font-semibold text-slate-900">{r.component}</p>
              <p className="mt-1 text-xs text-slate-600">{r.summary}</p>
            </div>
          ))}
          {results.length > 3 && (
            <Link to="/recalls" className="block text-center text-sm font-semibold text-accent">
              View all {results.length} recalls &rarr;
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
