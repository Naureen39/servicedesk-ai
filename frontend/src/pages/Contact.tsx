import { useState } from "react";
import { useDocumentHead } from "../lib/useDocumentHead";
import { useLocations } from "../lib/LocationsContext";
import { Input, Textarea, Select, Label } from "../components/ui/Input";
import Button from "../components/ui/Button";
import { submitContact } from "../lib/api";

interface FormState {
  name: string;
  email: string;
  phone: string;
  locationId: string;
  subject: string;
  message: string;
}

const EMPTY: FormState = { name: "", email: "", phone: "", locationId: "", subject: "", message: "" };

export default function Contact() {
  useDocumentHead({ title: "Contact Us", description: "Get in touch with Meridian Auto Group.", path: "/contact" });
  const { locations } = useLocations();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ messageId: string } | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const update = (field: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const validate = (): boolean => {
    const next: Partial<Record<keyof FormState, string>> = {};
    if (!form.name.trim()) next.name = "Please enter your name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) next.email = "Please enter a valid email address.";
    if (!form.subject.trim()) next.subject = "Please enter a subject.";
    if (form.message.trim().length < 10) next.message = "Please tell us a bit more (at least 10 characters).";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError(null);
    if (!validate()) return;
    setSubmitting(true);
    try {
      const res = await submitContact({
        name: form.name,
        email: form.email,
        phone: form.phone || undefined,
        location_id: form.locationId ? Number(form.locationId) : undefined,
        subject: form.subject,
        message: form.message,
      });
      setResult({ messageId: res.message_id });
      setForm(EMPTY);
    } catch {
      setServerError("We couldn't submit your message. Please try again in a moment.");
    } finally {
      setSubmitting(false);
    }
  };

  if (result) {
    return (
      <div className="container-page max-w-lg py-24 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-3xl text-success" aria-hidden="true">
          &#10003;
        </div>
        <h1 className="mt-6 font-display text-2xl font-bold text-navy">Message received</h1>
        <p className="mt-2 text-slate-600">
          Thanks for reaching out. Your ticket reference is <strong>{result.messageId}</strong>. A team member will
          follow up by email shortly.
        </p>
        <Button className="mt-6" onClick={() => setResult(null)}>
          Send Another Message
        </Button>
      </div>
    );
  }

  return (
    <div className="container-page max-w-2xl py-16">
      <h1 className="font-display text-3xl font-extrabold text-navy sm:text-4xl">Contact Us</h1>
      <p className="mt-3 text-slate-600">Questions about a service, an estimate, or anything else -- we're here to help.</p>

      <form className="mt-10 space-y-5" onSubmit={handleSubmit} noValidate>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <Label htmlFor="contact-name">Name</Label>
            <Input id="contact-name" value={form.name} onChange={update("name")} aria-invalid={!!errors.name} aria-describedby={errors.name ? "contact-name-error" : undefined} />
            {errors.name && <p id="contact-name-error" className="mt-1 text-xs text-danger">{errors.name}</p>}
          </div>
          <div>
            <Label htmlFor="contact-email">Email</Label>
            <Input id="contact-email" type="email" value={form.email} onChange={update("email")} aria-invalid={!!errors.email} aria-describedby={errors.email ? "contact-email-error" : undefined} />
            {errors.email && <p id="contact-email-error" className="mt-1 text-xs text-danger">{errors.email}</p>}
          </div>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <Label htmlFor="contact-phone">Phone (optional)</Label>
            <Input id="contact-phone" type="tel" value={form.phone} onChange={update("phone")} />
          </div>
          <div>
            <Label htmlFor="contact-location">Location (optional)</Label>
            <Select id="contact-location" value={form.locationId} onChange={update("locationId")}>
              <option value="">Any location</option>
              {locations.map((loc) => (
                <option key={loc.location_id} value={loc.location_id}>{loc.name}</option>
              ))}
            </Select>
          </div>
        </div>
        <div>
          <Label htmlFor="contact-subject">Subject</Label>
          <Input id="contact-subject" value={form.subject} onChange={update("subject")} aria-invalid={!!errors.subject} aria-describedby={errors.subject ? "contact-subject-error" : undefined} />
          {errors.subject && <p id="contact-subject-error" className="mt-1 text-xs text-danger">{errors.subject}</p>}
        </div>
        <div>
          <Label htmlFor="contact-message">Message</Label>
          <Textarea id="contact-message" rows={5} value={form.message} onChange={update("message")} aria-invalid={!!errors.message} aria-describedby={errors.message ? "contact-message-error" : undefined} />
          {errors.message && <p id="contact-message-error" className="mt-1 text-xs text-danger">{errors.message}</p>}
        </div>
        {serverError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-danger" role="alert">{serverError}</p>
        )}
        <Button type="submit" disabled={submitting} className="w-full sm:w-auto">
          {submitting ? "Sending..." : "Send Message"}
        </Button>
      </form>
    </div>
  );
}
