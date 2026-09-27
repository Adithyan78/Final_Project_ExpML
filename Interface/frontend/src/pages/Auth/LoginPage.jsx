import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Boxes, Database, Cpu, Lightbulb } from "lucide-react";
import { ROUTES } from "../../constants/routes";
import Button from "../../components/common/Button";

const POINTS = [
  { icon: Database, text: "Profile any tabular CSV in seconds" },
  { icon: Cpu, text: "Train and compare models automatically" },
  { icon: Lightbulb, text: "Understand predictions with SHAP" },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });

  const handleSubmit = (e) => {
    e.preventDefault();
    // No backend yet — route straight to the dashboard.
    navigate(ROUTES.DASHBOARD);
  };

  return (
    <div className="min-h-screen bg-surface-page flex">
      {/* Left brand panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-white border-r border-surface-border flex-col justify-between p-12">
        <Link to={ROUTES.HOME} className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-orange flex items-center justify-center">
            <Boxes size={16} className="text-white" strokeWidth={2.25} />
          </div>
          <span className="text-[15px] font-semibold text-ink tracking-tight">
            AutoExplainAI
          </span>
        </Link>

        <div className="max-w-sm">
          <h2 className="text-2xl font-semibold text-ink tracking-tight leading-snug">
            Explainable AutoML for tabular classification
          </h2>
          <div className="mt-8 space-y-4">
            {POINTS.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-orange-50 flex items-center justify-center shrink-0">
                  <Icon size={15} className="text-orange" />
                </div>
                <span className="text-sm text-ink-secondary">{text}</span>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-ink-muted">
          &copy; 2026 AutoExplainAI
        </p>
      </div>

      {/* Right auth card */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8 justify-center">
            <div className="w-7 h-7 rounded-md bg-orange flex items-center justify-center">
              <Boxes size={16} className="text-white" strokeWidth={2.25} />
            </div>
            <span className="text-[15px] font-semibold text-ink">
              AutoExplainAI
            </span>
          </div>

          <h1 className="text-2xl font-semibold text-ink tracking-tight">
            Welcome back
          </h1>
          <p className="text-sm text-ink-secondary mt-1.5">
            Sign in to continue to your workspace.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            <div>
              <label className="block text-xs font-medium text-ink mb-1.5">
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
                className="w-full text-sm px-3.5 py-2.5 rounded-lg border border-surface-border bg-white text-ink placeholder:text-ink-muted outline-none focus:border-orange focus:ring-1 focus:ring-orange transition-default"
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-medium text-ink">
                  Password
                </label>
                <a
                  href="#"
                  className="text-xs text-orange hover:text-orange-light"
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
                className="w-full text-sm px-3.5 py-2.5 rounded-lg border border-surface-border bg-white text-ink placeholder:text-ink-muted outline-none focus:border-orange focus:ring-1 focus:ring-orange transition-default"
              />
            </div>
            <Button type="submit" className="w-full" size="lg">
              Sign In
            </Button>
          </form>

          <p className="text-sm text-ink-secondary text-center mt-6">
            Don&apos;t have an account?{" "}
            <Link
              to={ROUTES.SIGNUP}
              className="text-orange font-medium hover:text-orange-light"
            >
              Create account
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
