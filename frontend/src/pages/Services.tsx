import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { listServices, type ServiceCatalogOut } from "../lib/api";
import { imageForService } from "../lib/imageSlugs";
import { useDocumentHead } from "../lib/useDocumentHead";
import ServiceCard from "../components/ServiceCard";
import Skeleton from "../components/ui/Skeleton";

export default function Services() {
  useDocumentHead({ title: "Services", description: "Browse our full service menu with real pricing and typical duration.", path: "/services" });
  const [services, setServices] = useState<ServiceCatalogOut[] | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const activeCategory = searchParams.get("category");

  useEffect(() => {
    listServices()
      .then(setServices)
      .catch(() => setServices([]));
  }, []);

  const categories = useMemo(() => {
    if (!services) return [];
    return Array.from(new Set(services.map((s) => s.category).filter((c): c is string => !!c))).sort();
  }, [services]);

  const filtered = services?.filter((s) => !activeCategory || s.category === activeCategory) ?? null;

  return (
    <div className="container-page py-16">
      <h1 className="font-display text-3xl font-extrabold text-navy sm:text-4xl">Services</h1>
      <p className="mt-3 max-w-2xl text-slate-600">
        Every service we offer, with typical duration and real pricing pulled straight from our live service catalog.
      </p>

      {categories.length > 0 && (
        <div className="mt-8 flex flex-wrap gap-2" role="group" aria-label="Filter by category">
          <button
            onClick={() => setSearchParams({})}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${!activeCategory ? "bg-accent text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSearchParams({ category: cat })}
              className={`rounded-full px-4 py-2 text-sm font-semibold ${activeCategory === cat ? "bg-accent text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {filtered === null && Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-80 w-full" />)}
        {filtered?.length === 0 && <p className="col-span-full text-slate-500">No services found in this category.</p>}
        {filtered?.map((service) => (
          <ServiceCard key={service.code} service={service} imageSlug={imageForService(service.code)} />
        ))}
      </div>
    </div>
  );
}
