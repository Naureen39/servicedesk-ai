import { useDocumentHead } from "../lib/useDocumentHead";

export default function Privacy() {
  useDocumentHead({ title: "Privacy Policy", description: "How Meridian Auto Group collects, uses, and protects your information." });

  return (
    <div className="container-page max-w-3xl py-16">
      <h1 className="font-display text-3xl font-extrabold text-navy">Privacy Policy</h1>
      <p className="mt-2 text-sm text-slate-500">Last updated September 2026</p>

      <div className="prose-chat mt-8 space-y-6 text-slate-700">
        <section>
          <h2 className="text-lg font-bold text-navy">Information We Collect</h2>
          <p className="mt-2">
            When you book a service appointment, chat with our AI assistant, or contact us, we collect your name, phone
            number, email address, and vehicle information (year, make, model, and VIN when provided). Phone numbers and
            email addresses are encrypted at rest. We never ask for or store payment card details through the chat or
            voice assistant.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">How We Use It</h2>
          <p className="mt-2">
            We use your information to schedule and manage service appointments, look up open recalls on your vehicle
            against NHTSA's public database, and follow up on requests submitted through our contact form. Conversation
            transcripts with our AI assistant are retained to improve service quality and are reviewed by staff only
            when a conversation is escalated to a human advisor.
          </p>
        </section>
        <section id="cookies">
          <h2 className="text-lg font-bold text-navy">Cookies &amp; Tracking</h2>
          <p className="mt-2">
            This site uses a single functional cookie to remember whether you've accepted or declined our cookie
            banner. We do not use third-party advertising trackers, analytics pixels, or cross-site tracking of any
            kind. Voice assistant sessions use browser microphone access only while a call is active; raw audio is
            deleted immediately after transcription and never stored.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">Data Sharing</h2>
          <p className="mt-2">
            We do not sell customer data. Vehicle recall and complaint information shown on this site comes directly
            from the National Highway Traffic Safety Administration's public APIs and is not linked to your personal
            account unless you explicitly look up your own vehicle.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">Your Rights</h2>
          <p className="mt-2">
            You may request a copy of the information we hold about you, ask us to correct it, or ask us to delete it,
            by contacting us through the form on our <a href="/contact" className="text-accent underline">Contact page</a>.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">Contact</h2>
          <p className="mt-2">
            Questions about this policy can be sent through our Contact page or by phone at any of our locations
            listed on the <a href="/locations" className="text-accent underline">Locations page</a>.
          </p>
        </section>
        <p className="text-xs text-slate-400">
          This is a demonstration website. Meridian Auto Group is a fictional company created for a software
          development project; this policy describes how the demo application actually behaves, not a real
          commercial service.
        </p>
      </div>
    </div>
  );
}
