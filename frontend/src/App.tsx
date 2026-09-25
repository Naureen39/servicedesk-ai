import { Suspense, lazy, useEffect } from "react";
import { BrowserRouter, Outlet, Route, Routes, useLocation } from "react-router-dom";
import Header from "./components/layout/Header";
import Footer from "./components/layout/Footer";
import UtilityBar from "./components/layout/UtilityBar";
import CookieConsent from "./components/layout/CookieConsent";
import { LocationsProvider } from "./lib/LocationsContext";
import { AuthProvider } from "./lib/auth";
import { ToastProvider } from "./components/ui/Toast";
import { TooltipProvider } from "./components/ui/Tooltip";
import ChatWidget from "./components/ChatWidget";
import Skeleton from "./components/ui/Skeleton";
import PortalLayout, { RequireAuth } from "./components/portal/PortalLayout";

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

const ExecutiveOverview = lazy(() => import("./pages/portal/ExecutiveOverview"));
const RevenueAnalytics = lazy(() => import("./pages/portal/RevenueAnalytics"));
const ServiceOperations = lazy(() => import("./pages/portal/ServiceOperations"));
const TechnicianPerformance = lazy(() => import("./pages/portal/TechnicianPerformance"));
const AssistantPerformance = lazy(() => import("./pages/portal/AssistantPerformance"));
const RecallInsights = lazy(() => import("./pages/portal/RecallInsights"));
const LiveConversations = lazy(() => import("./pages/portal/LiveConversations"));
const PortalEscalations = lazy(() => import("./pages/portal/Escalations"));
const PortalAppointments = lazy(() => import("./pages/portal/Appointments"));
const PortalKnowledgeBase = lazy(() => import("./pages/portal/KnowledgeBase"));
const PortalTestConsole = lazy(() => import("./pages/portal/TestConsole"));
const PortalAdmin = lazy(() => import("./pages/portal/Admin"));

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

function MarketingLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <UtilityBar />
      <Header />
      <main id="main-content" className="flex-1">
        <Suspense fallback={<PageFallback />}>
          <Outlet />
        </Suspense>
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
      <AuthProvider>
        <LocationsProvider>
          <ToastProvider>
            <TooltipProvider>
              <ScrollToTop />
              <Routes>
                <Route element={<MarketingLayout />}>
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
                </Route>

                <Route element={<RequireAuth />}>
                  <Route element={<PortalLayout />}>
                    <Route path="/portal" element={<Suspense fallback={<PageFallback />}><ExecutiveOverview /></Suspense>} />
                    <Route path="/portal/revenue" element={<Suspense fallback={<PageFallback />}><RevenueAnalytics /></Suspense>} />
                    <Route path="/portal/operations" element={<Suspense fallback={<PageFallback />}><ServiceOperations /></Suspense>} />
                    <Route path="/portal/technicians" element={<Suspense fallback={<PageFallback />}><TechnicianPerformance /></Suspense>} />
                    <Route path="/portal/assistant" element={<Suspense fallback={<PageFallback />}><AssistantPerformance /></Suspense>} />
                    <Route path="/portal/recalls" element={<Suspense fallback={<PageFallback />}><RecallInsights /></Suspense>} />
                    <Route path="/portal/live" element={<Suspense fallback={<PageFallback />}><LiveConversations /></Suspense>} />
                    <Route path="/portal/escalations" element={<Suspense fallback={<PageFallback />}><PortalEscalations /></Suspense>} />
                    <Route path="/portal/appointments" element={<Suspense fallback={<PageFallback />}><PortalAppointments /></Suspense>} />
                    <Route path="/portal/kb" element={<Suspense fallback={<PageFallback />}><PortalKnowledgeBase /></Suspense>} />
                    <Route path="/portal/test-console" element={<Suspense fallback={<PageFallback />}><PortalTestConsole /></Suspense>} />
                    <Route path="/portal/admin" element={<Suspense fallback={<PageFallback />}><PortalAdmin /></Suspense>} />
                  </Route>
                </Route>
              </Routes>
            </TooltipProvider>
          </ToastProvider>
        </LocationsProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
