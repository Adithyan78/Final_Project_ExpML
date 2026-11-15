
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Boxes, Database, Cpu, Lightbulb } from "lucide-react";
import { ROUTES } from "../../constants/routes";
import Button from "../../components/common/Button";
import { login } from "../../services/auth";

const POINTS = [
  { icon: Database, text: "Profile any tabular CSV in seconds" },
  { icon: Cpu, text: "Train and compare models automatically" },
  { icon: Lightbulb, text: "Understand predictions with SHAP" },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await login(form);
      navigate(ROUTES.DASHBOARD, { replace: true });
    } catch (err) {
      setError(err.message || "Unable to sign in. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full bg-surface-page">
      {/* Left brand panel */}
      <div className="hidden w-1/2 flex-col justify-between border-r border-surface-border bg-white p-8 lg:flex xl:p-12">
        <Link to={ROUTES.HOME} className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-orange">
            <Boxes size={17} className="text-white" strokeWidth={2.25} />
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-ink">
            AutoExplainAI
          </span>
        </Link>

        <div className="w-full max-w-md">
          <h2 className="text-2xl font-semibold leading-snug tracking-tight text-ink xl:text-3xl">
            Explainable AutoML for tabular classification
          </h2>

          <div className="mt-7 space-y-4 xl:mt-8">
            {POINTS.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-orange-50">
                  <Icon size={16} className="text-orange" />
                </div>
                <span className="text-sm leading-relaxed text-ink-secondary">
                  {text}
                </span>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-ink-muted">
          &copy; 2026 AutoExplainAI
        </p>
      </div>

      {/* Right auth card */}
      <div className="flex min-w-0 flex-1 items-center justify-center px-4 py-8 sm:px-6 sm:py-10 lg:px-8 xl:px-12">
        <div className="w-full max-w-sm min-w-0">
          <div className="mb-7 flex items-center justify-center gap-2 lg:hidden sm:mb-8">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-orange">
              <Boxes size={17} className="text-white" strokeWidth={2.25} />
            </div>
            <span className="text-[15px] font-semibold text-ink">
              AutoExplainAI
            </span>
          </div>

          <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-[28px]">
            Welcome back
          </h1>
          <p className="mt-1.5 text-xs leading-relaxed text-ink-secondary sm:text-sm">
            Sign in to continue to your workspace.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4 sm:mt-8">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-ink">
                Email
              </label>
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) =>
                  setForm({ ...form, email: e.target.value })
                }
                placeholder="you@company.com"
                className="w-full rounded-lg border border-surface-border bg-white px-3.5 py-3 text-sm text-ink outline-none transition-default placeholder:text-ink-muted focus:border-orange focus:ring-1 focus:ring-orange sm:py-2.5"
              />
            </div>

            <div>
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <label className="block text-xs font-medium text-ink">
                  Password
                </label>
                <a
                  href="#"
                  className="shrink-0 text-xs text-orange hover:text-orange-light"
                >
                  Forgot password?
                </a>
              </div>
              <input
                type="password"
                required
                value={form.password}
                onChange={(e) =>
                  setForm({ ...form, password: e.target.value })
                }
                placeholder="••••••••"
                className="w-full rounded-lg border border-surface-border bg-white px-3.5 py-3 text-sm text-ink outline-none transition-default placeholder:text-ink-muted focus:border-orange focus:ring-1 focus:ring-orange sm:py-2.5"
              />
            </div>

            {error && (
              <p role="alert" className="break-words text-sm text-red-600">
                {error}
              </p>
            )}

            <Button
              type="submit"
              className="w-full justify-center"
              size="lg"
              disabled={loading}
            >
              {loading ? "Signing In..." : "Sign In"}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs leading-relaxed text-ink-secondary sm:text-sm">
            Don&apos;t have an account?{" "}
            <Link
              to={ROUTES.SIGNUP}
              className="font-medium text-orange hover:text-orange-light"
            >
              Create account
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
