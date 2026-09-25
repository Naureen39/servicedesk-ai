import { useDocumentHead } from "../lib/useDocumentHead";
import Avatar from "../components/Avatar";
import ResponsiveImage from "../components/ResponsiveImage";
import { IMAGES } from "../lib/imageSlugs";

const LEADERSHIP = [
  { name: "Ada Ramirez", title: "Chief Executive Officer" },
  { name: "Devon Marsh", title: "VP of Service Operations" },
  { name: "Priya Natarajan", title: "Regional Service Director" },
  { name: "Yusuf Rahman", title: "Head of Customer Analytics" },
];

const VALUES = [
  { title: "Transparent Pricing", description: "Every price we quote online is the price you pay at checkout -- no surprise fees." },
  { title: "Real Answers, Any Hour", description: "Our AI assistant is backed by live NHTSA data and real appointment availability, not scripted guesses." },
  { title: "Certified Technicians Only", description: "Every technician across our locations is ASE certified before they touch a customer's vehicle." },
  { title: "Safety First", description: "Open recalls are always flagged and repaired free of charge, no matter how you found us." },
];

const MILESTONES = [
  { year: "2011", text: "Meridian Auto Group opens its first location in Columbus, Ohio." },
  { year: "2015", text: "Expands to a second location; adopts electronic repair order tracking." },
  { year: "2019", text: "Opens a third location and launches a customer-facing online booking system." },
  { year: "2024", text: "Introduces the Meridian Assist AI chat and voice assistant for 24/7 recall checks and booking." },
  { year: "2026", text: "Assistant-driven bookings account for a growing share of all appointments across all three locations." },
];

export default function About() {
  useDocumentHead({ title: "About Us", description: "Meridian Auto Group's mission, leadership, and history.", path: "/about" });

  return (
    <div>
      <div className="relative">
        <ResponsiveImage slug={IMAGES.modernDealershipShowroom[0]} alt="Meridian Auto Group showroom" className="h-72 w-full object-cover sm:h-96" priority />
        <div className="absolute inset-0 flex items-center bg-navy/60">
          <div className="container-page">
            <h1 className="font-display text-3xl font-extrabold text-white sm:text-5xl">Expert service, built on trust</h1>
          </div>
        </div>
      </div>

      <div className="container-page max-w-4xl py-16">
        <section>
          <h2 className="font-display text-2xl font-bold text-navy">Our Mission</h2>
          <p className="mt-3 text-slate-700">
            We believe getting your car serviced shouldn't mean sitting on hold or guessing at pricing. Meridian Auto
            Group combines certified technicians and genuine parts with real-time booking and recall data, so you
            always know exactly what's happening with your vehicle -- any hour, any channel.
          </p>
        </section>

        <section className="mt-14">
          <h2 className="font-display text-2xl font-bold text-navy">Our Values</h2>
          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            {VALUES.map((v) => (
              <div key={v.title} className="rounded-[var(--radius-card)] border border-slate-200 p-5">
                <h3 className="font-semibold text-navy">{v.title}</h3>
                <p className="mt-1.5 text-sm text-slate-600">{v.description}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-14">
          <h2 className="font-display text-2xl font-bold text-navy">Leadership</h2>
          <div className="mt-6 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {LEADERSHIP.map((person) => (
              <div key={person.name} className="text-center">
                <Avatar name={person.name} />
                <p className="mt-3 font-semibold text-navy">{person.name}</p>
                <p className="text-sm text-slate-500">{person.title}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-14">
          <h2 className="font-display text-2xl font-bold text-navy">Milestones</h2>
          <ol className="mt-6 space-y-6 border-l-2 border-slate-200 pl-6">
            {MILESTONES.map((m) => (
              <li key={m.year} className="relative">
                <span className="absolute -left-[31px] top-1 h-3 w-3 rounded-full bg-accent" aria-hidden="true" />
                <p className="text-sm font-bold text-accent">{m.year}</p>
                <p className="mt-1 text-slate-700">{m.text}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}
