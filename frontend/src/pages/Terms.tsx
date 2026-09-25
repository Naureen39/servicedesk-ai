import { useDocumentHead } from "../lib/useDocumentHead";

export default function Terms() {
  useDocumentHead({ title: "Terms of Use", description: "Terms governing use of the Meridian Auto Group website and services." });

  return (
    <div className="container-page max-w-3xl py-16">
      <h1 className="font-display text-3xl font-extrabold text-navy">Terms of Use</h1>
      <p className="mt-2 text-sm text-slate-500">Last updated September 2026</p>

      <div className="mt-8 space-y-6 text-slate-700">
        <section>
          <h2 className="text-lg font-bold text-navy">Acceptance of Terms</h2>
          <p className="mt-2">
            By using this website, the chat assistant, the voice assistant, or booking a service appointment, you agree
            to these terms. This is a demonstration website built for a software development project; Meridian Auto
            Group is a fictional company, and no real commercial transactions occur here.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">Appointment Bookings</h2>
          <p className="mt-2">
            Appointments booked through this site, the chat widget, or the voice assistant are held for the requested
            time slot subject to real-time availability. Same-day bookings require at least 2 hours' notice.
            Appointments can be rescheduled or cancelled using your confirmation code and the last 4 digits of the
            phone number on file.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">Pricing</h2>
          <p className="mt-2">
            Prices shown on the Services page are estimated ranges based on typical labor and parts costs and may vary
            based on your vehicle's condition, the technician's assessment, and parts availability at the time of
            service.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">AI Assistant Disclaimer</h2>
          <p className="mt-2">
            Our chat and voice assistant provides recall information sourced directly from NHTSA's public APIs and
            general guidance about our services. It is not a substitute for a technician's in-person diagnosis. For
            any safety concern, stop driving and contact a service advisor directly.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">Limitation of Liability</h2>
          <p className="mt-2">
            This site and its assistant are provided as a demonstration "as is," without warranties of any kind,
            express or implied.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">Changes to These Terms</h2>
          <p className="mt-2">We may update these terms from time to time; continued use of the site constitutes acceptance of the revised terms.</p>
        </section>
      </div>
    </div>
  );
}
