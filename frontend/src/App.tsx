import { Suspense, lazy } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { useEffect } from "react";
import Header from "./components/layout/Header";
import Footer from "./components/layout/Footer";
import UtilityBar from "./components/layout/UtilityBar";
import CookieConsent from "./components/layout/CookieConsent";
import { LocationsProvider } from "./lib/LocationsContext";
import { ToastProvider } from "./components/ui/Toast";
import { TooltipProvider } from "./components/ui/Tooltip";
import ChatWidget from "./components/ChatWidget";
import Skeleton from "./components/ui/Skeleton";

const Home = lazy(() => import("./pages/Home"));
const Services = lazy(() => import("./pages/Services"));
const ServiceDetail = lazy(() => import("./pages/ServiceDetail"));
const Recalls = lazy(() => import("./pages/Recalls"));
const Book = lazy(() => import("./pages/Book"));
const Warranty = lazy(() => import("./pages/Warranty"));
const Locations = lazy(() => import("./pages/Locations"));
const About = lazy(() => import("./pages/About"));
const Contact = lazy(() => import("./pages/Contact"));
const Privacy = lazy(() => import("./pages/Privacy"));
const Terms = lazy(() => import("./pages/Terms"));
const Accessibility = lazy(() => import("./pages/Accessibility"));
const Login = lazy(() => import("./pages/Login"));
const NotFound = lazy(() => import("./pages/NotFound"));
const ServerError = lazy(() => import("./pages/ServerError"));

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function PageFallback() {
  return (
    <div className="container-page py-24">
      <Skeleton className="mx-auto h-8 w-64" />
    </div>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <UtilityBar />
      <Header />
      <main id="main-content" className="flex-1">
        {children}
      </main>
      <Footer />
      <CookieConsent />
      <ChatWidget />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <LocationsProvider>
        <ToastProvider>
          <TooltipProvider>
            <ScrollToTop />
            <Layout>
              <Suspense fallback={<PageFallback />}>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/services" element={<Services />} />
                  <Route path="/services/:slug" element={<ServiceDetail />} />
                  <Route path="/recalls" element={<Recalls />} />
                  <Route path="/book" element={<Book />} />
                  <Route path="/warranty" element={<Warranty />} />
                  <Route path="/locations" element={<Locations />} />
                  <Route path="/about" element={<About />} />
                  <Route path="/contact" element={<Contact />} />
                  <Route path="/privacy" element={<Privacy />} />
                  <Route path="/terms" element={<Terms />} />
                  <Route path="/accessibility" element={<Accessibility />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/500" element={<ServerError />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </Layout>
          </TooltipProvider>
        </ToastProvider>
      </LocationsProvider>
    </BrowserRouter>
  );
}
