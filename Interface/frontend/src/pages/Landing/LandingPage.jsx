import { Link } from "react-router-dom";
import { ArrowRight, Boxes, Workflow, Trophy, Sparkles } from "lucide-react";
import { ROUTES } from "../../constants/routes";
import Button from "../../components/common/Button";

const FEATURES = [
  {
    icon: Workflow,
    title: "Automated Pipeline",
    description:
      "From missing-value handling to encoding and scaling — configured automatically or by hand.",
  },
  {
    icon: Trophy,
    title: "Best Model Selection",
    description:
      "Train Logistic Regression, Random Forest, and XGBoost in parallel, then compare on F1 and ROC-AUC.",
  },
  {
    icon: Sparkles,
    title: "Explainable Results",
    description:
      "See exactly why a model predicted what it did with SHAP-based feature contributions.",
  },
];

const PIPELINE_STAGES = [
  "Dataset",
  "Preprocessing",
  "Model Selection",
  "Evaluation",
  "Explainability",
];

function PipelineVisual() {
  return (
    <div className="relative bg-white border border-surface-border rounded-card shadow-card p-6">
      <p className="text-[11px] font-medium text-ink-muted mb-4">
        churn_dataset.csv &middot; 7,043 rows &middot; 21 columns
      </p>
      <div className="space-y-2.5">
        {PIPELINE_STAGES.map((stage, i) => {
          const isDone = i < 3;
          const isActive = i === 3;
          return (
            <div key={stage} className="flex items-center gap-3">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-semibold shrink-0 ${
                  isDone
                    ? "bg-state-success/15 text-state-success"
                    : isActive
                    ? "bg-orange text-white"
                    : "bg-surface-page text-ink-muted border border-surface-border"
                }`}
              >
                {isDone ? "✓" : i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span
                    className={`text-sm ${
                      isDone || isActive
                        ? "text-ink font-medium"
                        : "text-ink-muted"
                    }`}
                  >
                    {stage}
                  </span>
                  {isActive && (
                    <span className="text-[11px] text-orange font-medium">
                      Running
                    </span>
                  )}
                </div>
                {isActive && (
                  <div className="mt-1.5 h-1.5 bg-surface-border rounded-full overflow-hidden">
                    <div className="h-full w-[58%] bg-orange rounded-full" />
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-5 pt-4 border-t border-surface-border grid grid-cols-3 gap-3 text-center">
        <div>
          <p className="text-lg font-semibold text-ink">0.853</p>
          <p className="text-[11px] text-ink-muted">F1-Score</p>
        </div>
        <div>
          <p className="text-lg font-semibold text-ink">0.911</p>
          <p className="text-[11px] text-ink-muted">ROC-AUC</p>
        </div>
        <div>
          <p className="text-lg font-semibold text-ink">XGBoost</p>
          <p className="text-[11px] text-ink-muted">Best Model</p>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-surface-page">
      {/* Top nav */}
      <header className="border-b border-surface-border bg-white">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-md bg-orange flex items-center justify-center">
              <Boxes size={16} className="text-white" strokeWidth={2.25} />
            </div>
            <span className="text-[15px] font-semibold text-ink tracking-tight">
              AutoExplainAI
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to={ROUTES.LOGIN}
              className="text-sm text-ink-secondary hover:text-ink transition-default px-3 py-1.5"
            >
              Sign in
            </Link>
            <Link to={ROUTES.SIGNUP}>
              <Button size="sm">Get Started</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-16 pb-20 grid lg:grid-cols-2 gap-12 items-center">
        <div>
          <p className="text-xs font-medium text-orange mb-4">
            Automated machine learning
          </p>
          <h1 className="text-[40px] leading-[1.1] font-semibold text-ink tracking-tight">
            Turn your data into
            <br />
            insights
          </h1>
          <p className="text-base text-ink-secondary mt-5 max-w-md leading-relaxed">
            Upload a CSV, and AutoExplainAI profiles it, preprocesses it,
            trains and compares candidate models, then explains every
            prediction with SHAP.
          </p>
          <div className="flex items-center gap-3 mt-8">
            <Link to={ROUTES.SIGNUP}>
              <Button size="lg" icon={ArrowRight} iconPosition="right">
                Get Started
              </Button>
            </Link>
            <Link to={ROUTES.LOGIN}>
              <Button size="lg" variant="secondary">
                Sign In
              </Button>
            </Link>
          </div>
        </div>
        <PipelineVisual />
      </section>

      {/* Feature cards */}
      <section className="max-w-6xl mx-auto px-6 pb-24">
        <div className="grid sm:grid-cols-3 gap-4">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="bg-white border border-surface-border rounded-card p-5"
            >
              <div className="w-9 h-9 rounded-lg bg-orange-50 flex items-center justify-center mb-4">
                <Icon size={17} className="text-orange" strokeWidth={2} />
              </div>
              <h3 className="text-sm font-semibold text-ink mb-1.5">
                {title}
              </h3>
              <p className="text-[13px] text-ink-secondary leading-relaxed">
                {description}
              </p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-surface-border">
        <div className="max-w-6xl mx-auto px-6 py-6 flex items-center justify-between text-xs text-ink-muted">
          <span>AutoExplainAI</span>
          <span>Explainable AutoML for tabular classification</span>
        </div>
      </footer>
    </div>
  );
}
