import { Link } from "react-router-dom";
import ResponsiveImage from "./ResponsiveImage";
import Card from "./ui/Card";
import Badge from "./ui/Badge";
import { formatDuration, formatPriceRange } from "../lib/format";
import type { ServiceCatalogOut } from "../lib/api";

export default function ServiceCard({ service, imageSlug }: { service: ServiceCatalogOut; imageSlug: string }) {
  return (
    <Card className="group overflow-hidden transition-shadow hover:shadow-md">
      <Link to={`/services/${service.code}`}>
        <div className="aspect-[4/3] overflow-hidden bg-slate-100">
          <ResponsiveImage
            slug={imageSlug}
            alt={service.name}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
            sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
          />
        </div>
        <div className="p-4">
          {service.category && (
            <Badge tone="accent" className="mb-2">
              {service.category}
            </Badge>
          )}
          <h3 className="font-display text-base font-bold text-navy">{service.name}</h3>
          <div className="mt-2 flex items-center justify-between text-sm text-slate-500">
            <span>{formatDuration(service.duration_min)}</span>
            <span className="font-semibold text-slate-700">{formatPriceRange(service.parts_cost_min, service.parts_cost_max)}</span>
          </div>
        </div>
      </Link>
    </Card>
  );
}
