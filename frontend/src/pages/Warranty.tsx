import { Link } from "react-router-dom";
import { useDocumentHead } from "../lib/useDocumentHead";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/Tabs";
import Button from "../components/ui/Button";
import FaqAccordion from "../components/FaqAccordion";

const COVERAGE_TABS = [
  {
    value: "powertrain",
    label: "Powertrain",
    duration: "5 years / 60,000 miles",
    items: ["Engine block and internal components", "Transmission and transfer case", "Drive axles and driveshafts", "Seals and gaskets for covered components"],
  },
  {
    value: "bumper",
    label: "Bumper to Bumper",
    duration: "3 years / 36,000 miles",
    items: ["Electrical system and infotainment", "Air conditioning and heating", "Steering and suspension", "Fuel system components"],
  },
  {
    value: "corrosion",
    label: "Corrosion",
    duration: "5 years / unlimited miles",
    items: ["Sheet metal perforation from rust", "Body panel corrosion", "Frame and structural rust-through"],
  },
  {
    value: "recall",
    label: "Recall Repairs",
    duration: "No time limit",
    items: ["Any open safety recall is repaired free of charge, regardless of vehicle age or mileage", "Parts and labor fully covered", "Loaner vehicle available where required by the remedy"],
  },
];

const FAQ = [
  { question: "How long is my powertrain warranty?", answer: "Powertrain coverage runs 5 years or 60,000 miles, whichever comes first, covering the engine, transmission, and drivetrain." },
  { question: "Does the warranty cover a transmission repair?", answer: "Yes -- the transmission and transfer case are covered under the powertrain warranty for 5 years or 60,000 miles." },
  { question: "Is a recall repair covered even if I'm out of warranty?", answer: "Yes. Safety recalls are repaired free of charge regardless of your vehicle's age, mileage, or warranty status -- this is required by federal law, not tied to our warranty terms." },
  { question: "What does my bumper-to-bumper warranty include?", answer: "Bumper-to-bumper coverage (3 years / 36,000 miles) includes electrical, climate control, steering, suspension, and fuel system components not covered separately under powertrain." },
  { question: "Do I need to pay if my car is still under warranty?", answer: "Covered repairs during the warranty period have no parts or labor cost to you, aside from your standard maintenance items like fluids and filters." },
  { question: "What's not covered by the warranty?", answer: "Routine maintenance (oil changes, tire rotations, brake pads from normal wear), damage from accidents, and aftermarket modifications are not covered." },
  { question: "How many miles does my warranty last?", answer: "It depends on the coverage type: powertrain is 60,000 miles, bumper-to-bumper is 36,000 miles, and corrosion coverage has no mileage limit." },
  { question: "Is an oil change covered under warranty?", answer: "No -- oil changes and other routine maintenance items are considered normal wear and are billed at standard service pricing, though we'll flag any warranty-covered issue found during the visit." },
];

export default function Warranty() {
  useDocumentHead({ title: "Warranty Coverage", description: "See what's covered under your Meridian Auto Group vehicle warranty, and for how long.", path: "/warranty" });

  return (
    <div className="container-page max-w-4xl py-16">
      <h1 className="font-display text-3xl font-extrabold text-navy sm:text-4xl">Warranty Coverage</h1>
      <p className="mt-3 text-slate-600">
        Every vehicle we service is backed by manufacturer-grade warranty coverage. Here's exactly what's covered,
        for how long, and how to use it.
      </p>

      <Tabs defaultValue="powertrain" className="mt-10">
        <TabsList aria-label="Warranty coverage type">
          {COVERAGE_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {COVERAGE_TABS.map((tab) => (
          <TabsContent key={tab.value} value={tab.value}>
            <p className="text-sm font-semibold text-accent">{tab.duration}</p>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              {tab.items.map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="text-success" aria-hidden="true">&#10003;</span>
                  {item}
                </li>
              ))}
            </ul>
          </TabsContent>
        ))}
      </Tabs>

      <section id="parts" className="mt-16 rounded-[var(--radius-card)] bg-slate-50 p-8">
        <h2 className="font-display text-2xl font-bold text-navy">Genuine Parts</h2>
        <p className="mt-3 text-slate-700">
          Every repair uses OEM or OEM-equivalent parts, backed by the same warranty coverage as the vehicle itself.
          We flag parts availability in real time during booking -- if a recall repair needs a part that's
          temporarily out of stock, we'll tell you upfront and follow up the moment it's back in.
        </p>
        <Link to="/book" className="mt-5 inline-block">
          <Button>Book a Service</Button>
        </Link>
      </section>

      <section className="mt-16">
        <h2 className="font-display text-2xl font-bold text-navy">Warranty FAQ</h2>
        <div className="mt-6">
          <FaqAccordion items={FAQ} />
        </div>
      </section>
    </div>
  );
}
