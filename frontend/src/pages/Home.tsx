import { Link } from "react-router-dom";
import { lazy, Suspense, useEffect, useState } from "react";
import { useDocumentHead } from "../lib/useDocumentHead";
import { useFadeUp } from "../lib/useFadeUp";
import { useLocations } from "../lib/LocationsContext";
import { listServices, type ServiceCatalogOut } from "../lib/api";
import { imageForService, IMAGES } from "../lib/imageSlugs";
import ResponsiveImage from "../components/ResponsiveImage";
import RecallQuickCheck from "../components/RecallQuickCheck";
import ServiceCard from "../components/ServiceCard";
import Testimonials from "../components/Testimonials";
import FaqAccordion from "../components/FaqAccordion";
import Button from "../components/ui/Button";
import Skeleton from "../components/ui/Skeleton";

const LocationMap = lazy(() => import("../components/LocationMap"));

const HOW_IT_WORKS = [
  { title: "Ask", detail: "Chat, talk, or browse -- ask about recalls, pricing, or availability, any hour of the day.", icon: "\u{1F4AC}" },
  { title: "Book", detail: "Pick a real open time slot at your nearest location. No phone hold, no double-booking.", icon: "\u{1F4C5}" },
  { title: "Drive", detail: "Certified technicians, genuine parts, and a confirmation code you can use to reschedule anytime.", icon: "\u{1F697}" },
];

const FAQ = [
  { question: "How do I check if my car has an open recall?", answer: "Use the Recall Quick Check above, or ask our chat or voice assistant -- both pull live data directly from NHTSA." },
  { question: "How far in advance can I book?", answer: "We show real availability up to several weeks out, refreshed live as other customers book -- same-day appointments need at least 2 hours' notice." },
  { question: "Do you use genuine parts?", answer: "Yes, every repair uses OEM or OEM-equivalent parts backed by our standard warranty." },
  { question: "Can I talk to the assistant instead of typing?", answer: "Yes -- click the microphone icon on the chat widget to start a real voice conversation with Meridian Assist." },
  { question: "Is recall repair really free?", answer: "Yes, always, regardless of your vehicle's age or whether you're a returning customer -- this is required by federal law." },
  { question: "What if I need to reschedule?", answer: "Use your confirmation code and the last 4 digits of your phone number, through chat, voice, or this website." },
  { question: "How many locations do you have?", answer: "Three full-service locations, each with certified technicians and real-time booking." },
  { question: "Does the assistant know my vehicle's history?", answer: "Once you tell it your vehicle, it checks live recall and complaint data for that exact year, make, and model." },
];

export default function Home() {
  useDocumentHead({
    title: "Expert Service. Real Answers. Any Hour.",
    description: "Book service, check recalls, and get real answers 24/7 with Meridian Auto Group's AI-powered assistant.",
    path: "/",
  });
  const { locations } = useLocations();
  const [services, setServices] = useState<ServiceCatalogOut[] | null>(null);

  useEffect(() => {
    listServices().then((s) => setServices(s.slice(0, 8))).catch(() => setServices([]));
  }, []);

  return (
    <div>
      <section className="relative">
        <div className="relative h-[560px] w-full overflow-hidden sm:h-[620px]">
          <ResponsiveImage
            slug={IMAGES.carServiceTechnician[0]}
            alt="Certified technician servicing a customer's vehicle"
            className="h-full w-full object-cover"
            priority
          />
          <div className="absolute inset-0 bg-gradient-to-t from-navy via-navy/70 to-navy/20" />
        </div>
        <div className="container-page absolute inset-0 flex flex-col justify-center">
          <div className="max-w-xl text-white">
            <h1 className="font-display text-4xl font-extrabold leading-tight sm:text-6xl">
              Expert Service. Real Answers. Any Hour.
            </h1>
            <p className="mt-5 text-lg text-slate-200">
              AI-assisted booking, live recall checks, and certified technicians across every Meridian Auto Group
              location -- available by chat, voice, or web, 24/7.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link to="/book">
                <Button size="lg">Book Service</Button>
              </Link>
              <Link to="/recalls">
                <Button size="lg" variant="outline" className="border-white text-white hover:bg-white/10">
                  Check Your Vehicle's Recalls
                </Button>
              </Link>
            </div>
          </div>
        </div>

        <div className="container-page relative z-10 -mt-16 hidden max-w-md lg:block">
          <RecallQuickCheck />
        </div>
      </section>

      <div className="container-page -mt-8 block lg:hidden">
        <RecallQuickCheck />
      </div>

      <TrustBar />

      <FadeSection className="container-page py-20">
        <h2 className="font-display text-3xl font-bold text-navy">Our Services</h2>
        <p className="mt-2 max-w-xl text-slate-600">Real pricing, real duration estimates, and instant online booking.</p>
        <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {services === null && Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-72 w-full" />)}
          {services?.map((s) => (
            <ServiceCard key={s.code} service={s} imageSlug={imageForService(s.code)} />
          ))}
        </div>
        <div className="mt-8 text-center">
          <Link to="/services">
            <Button variant="outline">View All Services</Button>
          </Link>
        </div>
      </FadeSection>

      <FadeSection className="bg-slate-50 py-20">
        <div className="container-page">
          <h2 className="font-display text-3xl font-bold text-navy">How It Works</h2>
          <div className="mt-10 grid gap-8 sm:grid-cols-3">
            {HOW_IT_WORKS.map((step) => (
              <div key={step.title} className="text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 text-3xl" aria-hidden="true">
                  {step.icon}
                </div>
                <h3 className="mt-4 font-display text-xl font-bold text-navy">{step.title}</h3>
                <p className="mt-2 text-sm text-slate-600">{step.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </FadeSection>

      <FadeSection className="container-page py-20">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <h2 className="font-display text-3xl font-bold text-navy">Meet Meridian Assist</h2>
            <p className="mt-4 text-slate-600">
              Our AI assistant handles recall checks, pricing questions, and full bookings by chat or voice --
              available 24/7, and always backed by live data, never a script.
            </p>
            <ul className="mt-6 space-y-3 text-sm text-slate-700">
              <li className="flex gap-2"><span className="text-success">&#10003;</span> Live NHTSA recall and complaint lookups</li>
              <li className="flex gap-2"><span className="text-success">&#10003;</span> Real-time appointment availability, not a guess</li>
              <li className="flex gap-2"><span className="text-success">&#10003;</span> Seamless handoff to a human advisor when needed</li>
              <li className="flex gap-2"><span className="text-success">&#10003;</span> Talk naturally by voice, with barge-in support</li>
            </ul>
          </div>
          <div className="rounded-[var(--radius-card)] bg-navy p-6 text-white shadow-xl">
            <div className="flex items-center gap-2 border-b border-white/10 pb-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-xs font-bold">MA</div>
              <span className="text-sm font-semibold">Meridian Assist</span>
              <span className="ml-auto flex items-center gap-1 text-xs text-green-300">
                <span className="h-1.5 w-1.5 rounded-full bg-green-400" /> Online
              </span>
            </div>
            <div className="space-y-3 py-4 text-sm">
              <p className="w-fit max-w-[85%] rounded-2xl rounded-bl-sm bg-white/10 px-3.5 py-2">Does my 2020 Toyota Camry have any recalls?</p>
              <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-accent px-3.5 py-2">
                Checking live NHTSA data... You have 1 open recall for the fuel pump. Repairs are free of charge -- want me to book it?
              </p>
              <p className="w-fit max-w-[85%] rounded-2xl rounded-bl-sm bg-white/10 px-3.5 py-2">Yes, next Tuesday works</p>
            </div>
          </div>
        </div>
      </FadeSection>

      <FadeSection className="bg-slate-50 py-20">
        <div className="container-page grid items-center gap-10 lg:grid-cols-2">
          <ResponsiveImage
            slug={IMAGES.brakeRepairCloseUp[0]}
            alt="Close-up of a technician performing a brake repair"
            className="aspect-[4/3] w-full rounded-[var(--radius-card)] object-cover"
          />
          <div>
            <h2 className="font-display text-3xl font-bold text-navy">Recall &amp; Safety, Taken Seriously</h2>
            <p className="mt-4 text-slate-600">
              Every lookup on this site queries the National Highway Traffic Safety Administration's public APIs
              directly -- not a cached list. If your vehicle has an open recall, the repair is always free of charge.
            </p>
            <Link to="/recalls" className="mt-6 inline-block">
              <Button>Check Your Vehicle</Button>
            </Link>
          </div>
        </div>
      </FadeSection>

      <FadeSection className="container-page py-20">
        <Testimonials />
      </FadeSection>

      {locations.length > 0 && (
        <FadeSection className="bg-slate-50 py-20">
          <div className="container-page">
            <h2 className="font-display text-3xl font-bold text-navy">Find Us</h2>
            <div className="mt-8 overflow-hidden rounded-[var(--radius-card)] border border-slate-200">
              <Suspense fallback={<Skeleton className="h-96 w-full" />}>
                <LocationMap locations={locations} />
              </Suspense>
            </div>
          </div>
        </FadeSection>
      )}

      <FadeSection className="container-page py-20">
        <h2 className="font-display text-3xl font-bold text-navy">Frequently Asked Questions</h2>
        <div className="mt-8 max-w-3xl">
          <FaqAccordion items={FAQ} />
        </div>
      </FadeSection>

      <section className="bg-navy py-20 text-center text-white">
        <div className="container-page">
          <h2 className="font-display text-3xl font-bold">Ready when you are.</h2>
          <p className="mt-3 text-slate-300">Book in minutes, or ask Meridian Assist anything -- day or night.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <Link to="/book">
              <Button size="lg">Book Service</Button>
            </Link>
            <Link to="/recalls">
              <Button size="lg" variant="outline" className="border-white text-white hover:bg-white/10">
                Check Recalls
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function TrustBar() {
  const items = [
    { label: "Certified Technicians", value: "ASE Certified" },
    { label: "Genuine Parts", value: "OEM & OEM-Equivalent" },
    { label: "Locations", value: "3 Full-Service" },
    { label: "Customer Rating", value: "4.8 / 5" },
  ];
  return (
    <div className="border-b border-slate-200 bg-white py-8">
      <div className="container-page grid grid-cols-2 gap-6 sm:grid-cols-4">
        {items.map((item) => (
          <div key={item.label} className="text-center">
            <p className="font-display text-lg font-bold text-navy">{item.value}</p>
            <p className="text-xs text-slate-500">{item.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function FadeSection({ className, children }: { className?: string; children: React.ReactNode }) {
  const ref = useFadeUp<HTMLDivElement>();
  return (
    <div ref={ref} className={`fade-up ${className ?? ""}`}>
      {children}
    </div>
  );
}
