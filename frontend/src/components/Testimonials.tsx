import { useState } from "react";

interface Testimonial {
  quote: string;
  name: string;
  location: string;
  rating: number;
}

const TESTIMONIALS: Testimonial[] = [
  {
    quote: "I booked an oil change through the chat widget in under two minutes, and it texted me the confirmation code instantly. No hold music, no back and forth.",
    name: "Dana R.", location: "Riverside", rating: 5,
  },
  {
    quote: "The voice assistant caught an open recall on my Civic before I even asked. Had it fixed the same week, free of charge.",
    name: "Marcus T.", location: "Lakeside", rating: 5,
  },
  {
    quote: "Transparent pricing on the site matched exactly what I paid at checkout. That alone earned my repeat business.",
    name: "Priya S.", location: "Northgate", rating: 5,
  },
  {
    quote: "Rescheduled my brake appointment twice through the chat -- both times it just worked, no phone call needed.",
    name: "Owen C.", location: "Riverside", rating: 4,
  },
];

export default function Testimonials() {
  const [index, setIndex] = useState(0);
  const active = TESTIMONIALS[index];

  return (
    <div className="mx-auto max-w-2xl text-center">
      <div className="flex justify-center gap-1 text-amber-500" aria-hidden="true">
        {Array.from({ length: 5 }).map((_, i) => (
          <span key={i}>{i < active.rating ? "★" : "☆"}</span>
        ))}
      </div>
      <blockquote className="mt-4 text-xl font-medium leading-relaxed text-slate-800">&ldquo;{active.quote}&rdquo;</blockquote>
      <p className="mt-4 text-sm font-semibold text-slate-600">
        {active.name} &middot; {active.location}
      </p>
      <div className="mt-6 flex justify-center gap-2" role="tablist" aria-label="Testimonials">
        {TESTIMONIALS.map((_, i) => (
          <button
            key={i}
            role="tab"
            aria-selected={i === index}
            aria-label={`Testimonial ${i + 1}`}
            onClick={() => setIndex(i)}
            className={`h-2 w-2 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
              i === index ? "bg-accent" : "bg-slate-300"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
