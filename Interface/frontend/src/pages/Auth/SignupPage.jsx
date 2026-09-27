import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Boxes } from "lucide-react";
import { ROUTES } from "../../constants/routes";
import Button from "../../components/common/Button";

export default function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirm: "",
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    navigate(ROUTES.DASHBOARD);
  };

  const field = (key, label, type = "text", placeholder = "") => (
    <div>
      <label className="block text-xs font-medium text-ink mb-1.5">
        {label}
      </label>
      <input
        type={type}
        required
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        placeholder={placeholder}
        className="w-full text-sm px-3.5 py-2.5 rounded-lg border border-surface-border bg-white text-ink placeholder:text-ink-muted outline-none focus:border-orange focus:ring-1 focus:ring-orange transition-default"
      />
    </div>
  );

  return (
    <div className="min-h-screen bg-surface-page flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <Link
          to={ROUTES.HOME}
          className="flex items-center gap-2 mb-8 justify-center"
        >
          <div className="w-7 h-7 rounded-md bg-orange flex items-center justify-center">
            <Boxes size={16} className="text-white" strokeWidth={2.25} />
          </div>
          <span className="text-[15px] font-semibold text-ink">
            AutoExplainAI
          </span>
        </Link>

        <div className="bg-white border border-surface-border rounded-card shadow-card p-7">
          <h1 className="text-2xl font-semibold text-ink tracking-tight">
            Create your account
          </h1>
          <p className="text-sm text-ink-secondary mt-1.5 leading-relaxed">
            Create your workspace and start your first explainable ML
            experiment.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {field("name", "Name", "text", "Ada Lovelace")}
            {field("email", "Email", "email", "you@company.com")}
            {field("password", "Password", "password", "••••••••")}
            {field("confirm", "Confirm Password", "password", "••••••••")}
            <Button type="submit" className="w-full" size="lg">
              Create Account
            </Button>
          </form>
        </div>

        <p className="text-sm text-ink-secondary text-center mt-6">
          Already have an account?{" "}
          <Link
            to={ROUTES.LOGIN}
            className="text-orange font-medium hover:text-orange-light"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
