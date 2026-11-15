
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Boxes } from "lucide-react";
import { ROUTES } from "../../constants/routes";
import Button from "../../components/common/Button";
import { signup } from "../../services/auth";

export default function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (form.password !== form.confirm) {
      setError("Passwords do not match.");
      return;
    }

    if (form.password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setLoading(true);

    try {
      await signup(form);
      navigate(ROUTES.DASHBOARD, { replace: true });
    } catch (err) {
      setError(err.message || "Unable to create your account. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const field = (key, label, type = "text", placeholder = "") => (
    <div className="min-w-0">
      <label className="mb-1.5 block text-xs font-medium text-ink">
        {label}
      </label>
      <input
        type={type}
        required
        minLength={key === "password" ? 8 : undefined}
        maxLength={key === "password" || key === "confirm" ? 128 : undefined}
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        placeholder={placeholder}
        className="w-full rounded-lg border border-surface-border bg-white px-3.5 py-3 text-sm text-ink outline-none transition-default placeholder:text-ink-muted focus:border-orange focus:ring-1 focus:ring-orange sm:py-2.5"
      />
    </div>
  );

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-surface-page px-4 py-6 sm:px-6 sm:py-10">
      <div className="w-full max-w-sm min-w-0">
        <Link
          to={ROUTES.HOME}
          className="mb-6 flex items-center justify-center gap-2 sm:mb-8"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-orange">
            <Boxes size={17} className="text-white" strokeWidth={2.25} />
          </div>
          <span className="text-[15px] font-semibold text-ink">
            AutoExplainAI
          </span>
        </Link>

        <div className="rounded-card border border-surface-border bg-white p-5 shadow-card sm:p-7">
          <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">
            Create your account
          </h1>
          <p className="mt-1.5 text-xs leading-relaxed text-ink-secondary sm:text-sm">
            Create your workspace and start your first explainable ML
            experiment.
          </p>

          <form onSubmit={handleSubmit} className="mt-5 space-y-4 sm:mt-6">
            {field("name", "Name", "text", "Ada Lovelace")}
            {field("email", "Email", "email", "you@company.com")}
            {field("password", "Password", "password", "••••••••")}
            {field("confirm", "Confirm Password", "password", "••••••••")}

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
              {loading ? "Creating Account..." : "Create Account"}
            </Button>
          </form>
        </div>

        <p className="mt-5 text-center text-xs leading-relaxed text-ink-secondary sm:mt-6 sm:text-sm">
          Already have an account?{" "}
          <Link
            to={ROUTES.LOGIN}
            className="font-medium text-orange hover:text-orange-light"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
