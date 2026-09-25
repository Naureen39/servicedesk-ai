import { lazy, Suspense, useState } from "react";
import { useDocumentHead } from "../lib/useDocumentHead";
import RecallQuickCheck from "../components/RecallQuickCheck";
import FaqAccordion from "../components/FaqAccordion";
import Skeleton from "../components/ui/Skeleton";

const ComplaintTrendChart = lazy(() => import("../components/ComplaintTrendChart"));

const RECALL_PROCESS = [
  { step: "1. We identify your vehicle", detail: "By year, make, and model, or VIN -- resolved against NHTSA's own vehicle database so spelling always matches." },
  { step: "2. We check live NHTSA data", detail: "Every lookup calls NHTSA's recallsByVehicle API directly -- never a cached or outdated list." },
  { step: "3. You see the real remedy", detail: "Campaign number, the exact issue, the risk, and what the manufacturer's fix actually is." },
  { step: "4. We schedule the repair", detail: "Recall repairs are always free of charge and prioritized for parts availability." },
];

const FAQ = [
  { question: "Is checking for recalls free?", answer: "Yes, always. Recall lookups use NHTSA's public data and cost nothing, whether you use this page, chat, or voice." },
  { question: "Do I have to be a customer to check recalls?", answer: "No -- anyone can check any vehicle's recall status here, no account or appointment required." },
  { question: "How current is this data?", answer: "Every search calls NHTSA's live recallsByVehicle API in real time -- it's not a cached snapshot." },
];

export default function Recalls() {
  useDocumentHead({ title: "Recalls & Safety", description: "Check your vehicle for open recalls using live NHTSA data.", path: "/recalls" });
  const [lastChecked, setLastChecked] = useState<{ year: number; make: string; model: string } | null>(null);

  return (
    <div className="container-page max-w-5xl py-16">
      <h1 className="font-display text-3xl font-extrabold text-navy sm:text-4xl">Recalls &amp; Safety</h1>
      <p className="mt-3 max-w-2xl text-slate-600">
        Check any vehicle for open safety recalls using live data straight from the National Highway Traffic Safety
        Administration. No account needed.
      </p>

      <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_360px]">
        <div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {RECALL_PROCESS.map((p) => (
              <div key={p.step} className="rounded-[var(--radius-card)] border border-slate-200 p-4">
                <p className="text-sm font-bold text-navy">{p.step}</p>
                <p className="mt-1.5 text-xs text-slate-600">{p.detail}</p>
              </div>
            ))}
          </div>

          <section id="complaints" className="mt-12 rounded-[var(--radius-card)] border border-slate-200 p-6">
            <h2 className="font-display text-lg font-bold text-navy">Complaint Trends</h2>
            <p className="mt-1 text-sm text-slate-500">Run a recall check to see historical complaint data for that vehicle.</p>
            <div className="mt-4">
              {lastChecked ? (
                <Suspense fallback={<Skeleton className="h-56 w-full" />}>
                  <ComplaintTrendChart year={lastChecked.year} make={lastChecked.make} model={lastChecked.model} />
                </Suspense>
              ) : (
                <p className="text-sm text-slate-400">No vehicle selected yet.</p>
              )}
            </div>
          </section>

          <section className="mt-12">
            <h2 className="font-display text-lg font-bold text-navy">Frequently Asked Questions</h2>
            <div className="mt-4">
              <FaqAccordion items={FAQ} />
            </div>
          </section>

          <p className="mt-10 text-xs text-slate-400">
            Recall and complaint data provided by the National Highway Traffic Safety Administration (NHTSA), a part
            of the U.S. Department of Transportation. This site queries NHTSA's public APIs directly and is not
            affiliated with or endorsed by NHTSA.
          </p>
        </div>

        <div className="lg:sticky lg:top-24 lg:self-start">
          <RecallQuickCheck onChecked={setLastChecked} />
        </div>
      </div>
    </div>
  );
}
