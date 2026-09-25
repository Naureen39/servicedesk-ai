import { Link } from "react-router-dom";
import Button from "../components/ui/Button";
import { useDocumentHead } from "../lib/useDocumentHead";

export default function ServerError() {
  useDocumentHead({ title: "Something Went Wrong", description: "We're having trouble loading this page." });

  return (
    <div className="container-page flex flex-col items-center justify-center py-32 text-center">
      <p className="font-display text-6xl font-extrabold text-danger">500</p>
      <h1 className="mt-4 text-2xl font-bold text-navy">Something went wrong on our end</h1>
      <p className="mt-2 max-w-md text-slate-600">
        Our team has been notified. Please try again in a moment, or reach us directly if you need help right away.
      </p>
      <div className="mt-8 flex gap-3">
        <Link to="/">
          <Button>Back to Home</Button>
        </Link>
        <Link to="/contact">
          <Button variant="outline">Contact Us</Button>
        </Link>
      </div>
    </div>
  );
}
