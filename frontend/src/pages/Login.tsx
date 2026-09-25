import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import ResponsiveImage from "../components/ResponsiveImage";
import { IMAGES } from "../lib/imageSlugs";
import { Input, Label } from "../components/ui/Input";
import Button from "../components/ui/Button";
import { useDocumentHead } from "../lib/useDocumentHead";
import { staffLogin, staffMfaVerify } from "../lib/api";
import { useAuth } from "../lib/auth";

type Step = "credentials" | "mfa";

export default function Login() {
  useDocumentHead({ title: "Staff Login", description: "Sign in to the Meridian Auto Group staff portal." });
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/portal";

  const [step, setStep] = useState<Step>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberDevice, setRememberDevice] = useState(false);
  const [mfaCode, setMfaCode] = useState("");
  const [challengeToken, setChallengeToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [lockoutMessage, setLockoutMessage] = useState<string | null>(null);

  const handleCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLockoutMessage(null);
    setLoading(true);
    try {
      const result = await staffLogin(email, password);
      if (result.mfa_required && result.mfa_challenge_token) {
        setChallengeToken(result.mfa_challenge_token);
        setStep("mfa");
      } else {
        await login(result.access_token);
        navigate(redirectTo, { replace: true });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Invalid email or password.";
      if (/locked/i.test(message)) setLockoutMessage(message);
      else setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleMfa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!challengeToken) return;
    setError(null);
    setLoading(true);
    try {
      const result = await staffMfaVerify(challengeToken, mfaCode);
      await login(result.access_token);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid code. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-[calc(100vh-4rem)] grid-cols-1 lg:grid-cols-2">
      <div className="relative hidden lg:block">
        <ResponsiveImage
          slug={IMAGES.serviceAdvisorDesk[0]}
          alt="Meridian Auto Group service advisor at work"
          className="h-full w-full object-cover"
          priority
        />
        <div className="absolute inset-0 bg-gradient-to-t from-navy/80 via-navy/20 to-transparent" />
        <div className="absolute bottom-10 left-10 right-10 text-white">
          <h2 className="font-display text-2xl font-bold">Run every location from one portal.</h2>
          <p className="mt-2 text-sm text-slate-200">Appointments, escalations, and revenue -- all in real time.</p>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-sm">
          <h1 className="font-display text-2xl font-bold text-navy">Staff Login</h1>
          <p className="mt-1 text-sm text-slate-500">Sign in to manage appointments, escalations, and reporting.</p>

          {step === "credentials" && (
            <form className="mt-8 space-y-4" onSubmit={handleCredentials}>
              <div>
                <Label htmlFor="login-email">Email</Label>
                <Input id="login-email" type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="login-password">Password</Label>
                <div className="relative">
                  <Input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pr-16"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute inset-y-0 right-3 text-xs font-semibold text-accent focus-visible:outline-none"
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input type="checkbox" checked={rememberDevice} onChange={(e) => setRememberDevice(e.target.checked)} className="rounded" />
                Remember this device
              </label>
              {lockoutMessage && (
                <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
                  {lockoutMessage}
                </p>
              )}
              {error && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-danger" role="alert">
                  {error}
                </p>
              )}
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Signing in..." : "Sign In"}
              </Button>
            </form>
          )}

          {step === "mfa" && (
            <form className="mt-8 space-y-4" onSubmit={handleMfa}>
              <div>
                <Label htmlFor="mfa-code">6-digit authentication code</Label>
                <Input id="mfa-code" inputMode="numeric" maxLength={6} required value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} />
              </div>
              {error && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-danger" role="alert">
                  {error}
                </p>
              )}
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Verifying..." : "Verify"}
              </Button>
            </form>
          )}


          <p className="mt-8 text-center text-sm text-slate-500">
            <Link to="/" className="font-semibold text-accent hover:underline">
              &larr; Back to website
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
