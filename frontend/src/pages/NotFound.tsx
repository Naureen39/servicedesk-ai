import { Link } from "react-router-dom";
import Button from "../components/ui/Button";
import { useDocumentHead } from "../lib/useDocumentHead";

export default function NotFound() {
  useDocumentHead({ title: "Page Not Found", description: "The page you're looking for doesn't exist." });

  return (
    <div className="container-page flex flex-col items-center justify-center py-32 text-center">
      <p className="font-display text-6xl font-extrabold text-accent">404</p>
      <h1 className="mt-4 text-2xl font-bold text-navy">We couldn't find that page</h1>
      <p className="mt-2 max-w-md text-slate-600">
        The page may have moved, or the link might be outdated. Try heading back home, or book a service appointment.
      </p>
      <div className="mt-8 flex gap-3">
        <Link to="/">
          <Button>Back to Home</Button>
        </Link>
        <Link to="/book">
          <Button variant="outline">Book Service</Button>
        </Link>
      </div>
    </div>
  );
}
