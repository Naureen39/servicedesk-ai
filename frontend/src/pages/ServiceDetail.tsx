import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getService, type ServiceCatalogOut } from "../lib/api";
import { imageForService } from "../lib/imageSlugs";
import { formatDuration, formatPriceRange } from "../lib/format";
import { useDocumentHead } from "../lib/useDocumentHead";
import ResponsiveImage from "../components/ResponsiveImage";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import Skeleton from "../components/ui/Skeleton";

const INCLUDED_BY_CATEGORY: Record<string, string[]> = {
  Maintenance: ["Multi-point inspection", "Fluid top-off", "Digital service report"],
  Brakes: ["Pad and rotor inspection", "Brake fluid check", "Road test"],
  Tires: ["Tread depth check", "Pressure calibration", "Visual sidewall inspection"],
  Diagnostics: ["Computer diagnostic scan", "Technician review", "Written findings summary"],
  Electrical: ["Battery and charging system test", "Wiring inspection", "Component testing"],
  Suspension: ["Alignment check", "Shock and strut inspection", "Road test"],
  Transmission: ["Fluid level and condition check", "Filter inspection", "Road test"],
  "Climate Control": ["Refrigerant level check", "System pressure test", "Cabin filter inspection"],
  Inspection: ["Full multi-point inspection", "Written report", "Photo documentation where applicable"],
  Recall: ["Manufacturer-specified remedy", "Parts and labor at no cost", "VIN status confirmation"],
};

export default function ServiceDetail() {
  useDocumentHead({ title: "Service Details", description: "Service details, pricing, and duration." });
  const { slug } = useParams<{ slug: string }>();
  const [service, setService] = useState<ServiceCatalogOut | null | "error">(null);

  useEffect(() => {
    if (!slug) return;
    getService(slug)
      .then(setService)
      .catch(() => setService("error"));
  }, [slug]);

  if (service === "error") {
    return (
      <div className="container-page py-24 text-center">
        <h1 className="text-2xl font-bold text-navy">Service not found</h1>
        <Link to="/services" className="mt-4 inline-block text-accent underline">Back to all services</Link>
      </div>
    );
  }

  if (!service) {
    return (
      <div className="container-page py-16">
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  const included = (service.category && INCLUDED_BY_CATEGORY[service.category]) || ["Technician inspection", "Written summary of findings"];

  return (
    <div className="container-page py-16">
      <Link to="/services" className="text-sm font-semibold text-accent">&larr; All Services</Link>
      <div className="mt-6 grid gap-10 lg:grid-cols-2">
        <div className="aspect-[4/3] overflow-hidden rounded-[var(--radius-card)] bg-slate-100">
          <ResponsiveImage slug={imageForService(service.code)} alt={service.name} className="h-full w-full object-cover" priority />
        </div>
        <div>
          {service.category && <Badge tone="accent">{service.category}</Badge>}
          <h1 className="mt-3 font-display text-3xl font-extrabold text-navy">{service.name}</h1>
          <div className="mt-4 flex items-center gap-6 text-sm text-slate-600">
            <span>
              <span className="font-semibold text-navy">{formatDuration(service.duration_min)}</span> typical duration
            </span>
            <span>
              <span className="font-semibold text-navy">{formatPriceRange(service.parts_cost_min, service.parts_cost_max)}</span> estimated
            </span>
          </div>
          {!service.parts_available && (
            <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Parts for this service are temporarily out of stock; booking will flag this for follow-up.
            </p>
          )}
          <p className="mt-5 text-slate-700">
            Our certified technicians perform this service using genuine or OEM-equivalent parts, backed by our
            standard warranty coverage. Final pricing depends on your vehicle's specific needs, confirmed before any
            work begins.
          </p>
          <h2 className="mt-6 text-sm font-bold uppercase tracking-wide text-slate-500">What's Included</h2>
          <ul className="mt-2 space-y-1.5 text-sm text-slate-700">
            {included.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="text-success" aria-hidden="true">&#10003;</span> {item}
              </li>
            ))}
          </ul>
          <Link to="/book" state={{ serviceCode: service.code }} className="mt-8 block">
            <Button size="lg" className="w-full sm:w-auto">Book this Service</Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
