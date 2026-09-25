import { useDocumentHead } from "../lib/useDocumentHead";

export default function Accessibility() {
  useDocumentHead({ title: "Accessibility Statement", description: "Our commitment to an accessible website for all customers." });

  return (
    <div className="container-page max-w-3xl py-16">
      <h1 className="font-display text-3xl font-extrabold text-navy">Accessibility Statement</h1>
      <p className="mt-2 text-sm text-slate-500">Last updated September 2026</p>

      <div className="mt-8 space-y-6 text-slate-700">
        <section>
          <h2 className="text-lg font-bold text-navy">Our Commitment</h2>
          <p className="mt-2">
            Meridian Auto Group is committed to making this website usable by everyone, including customers who use
            assistive technology such as screen readers, keyboard-only navigation, or voice control. We aim to
            conform to WCAG 2.1 Level AA.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">What We've Built In</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>A skip-to-content link at the top of every page for keyboard users.</li>
            <li>Visible focus outlines on every interactive element, not just a color change.</li>
            <li>Sufficient color contrast between text and its background throughout the site.</li>
            <li>Descriptive labels on every form field, button, and icon-only control.</li>
            <li>Full keyboard operability for the chat widget, voice modal, and booking wizard.</li>
            <li>Motion and animation that respects your operating system's "reduce motion" setting.</li>
            <li>Live-region announcements for dynamic content like recall lookup results and the assistant's typing indicator.</li>
          </ul>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">Alternative Ways to Reach Us</h2>
          <p className="mt-2">
            If any part of this site is difficult to use with your assistive technology, you can also reach us by
            phone at any of our locations listed on the <a href="/locations" className="text-accent underline">Locations page</a>,
            or by voice through the microphone button on our chat widget.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-bold text-navy">Feedback</h2>
          <p className="mt-2">
            We welcome feedback on the accessibility of this site. Please let us know through our{" "}
            <a href="/contact" className="text-accent underline">Contact page</a> if you encounter a barrier.
          </p>
        </section>
      </div>
    </div>
  );
}
