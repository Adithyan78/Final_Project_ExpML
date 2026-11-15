
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
    <div className="relative w-full min-w-0 bg-white border border-surface-border rounded-card shadow-card p-4 sm:p-6">
      <p className="text-[11px] font-medium text-ink-muted mb-4 break-words">
        churn_dataset.csv &middot; 7,043 rows &middot; 21 columns
      </p>

      <div className="space-y-2.5">
        {PIPELINE_STAGES.map((stage, i) => {
          const isDone = i < 3;
          const isActive = i === 3;

          return (
            <div key={stage} className="flex items-center gap-3 min-w-0">
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
                <div className="flex items-center justify-between gap-2">
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
                    <span className="text-[11px] text-orange font-medium shrink-0">
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

      <div className="mt-5 pt-4 border-t border-surface-border grid grid-cols-3 gap-2 sm:gap-3 text-center">
        <div className="min-w-0">
          <p className="text-base sm:text-lg font-semibold text-ink">0.853</p>
          <p className="text-[10px] sm:text-[11px] text-ink-muted">F1-Score</p>
        </div>

        <div className="min-w-0">
          <p className="text-base sm:text-lg font-semibold text-ink">0.911</p>
          <p className="text-[10px] sm:text-[11px] text-ink-muted">ROC-AUC</p>
        </div>

        <div className="min-w-0">
          <p className="text-base sm:text-lg font-semibold text-ink truncate">
            XGBoost
          </p>
          <p className="text-[10px] sm:text-[11px] text-ink-muted">Best Model</p>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-surface-page overflow-x-hidden">
      {/* Top nav */}
      <header className="border-b border-surface-border bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 min-h-16 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-md bg-orange flex items-center justify-center shrink-0">
              <Boxes size={16} className="text-white" strokeWidth={2.25} />
            </div>

            <span className="text-[15px] font-semibold text-ink tracking-tight whitespace-nowrap">
              AutoExplainAI
            </span>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
            <Link
              to={ROUTES.LOGIN}
              className="text-xs sm:text-sm text-ink-secondary hover:text-ink transition-default px-2 sm:px-3 py-2 whitespace-nowrap"
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
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pt-12 sm:pt-16 lg:pt-20 pb-14 sm:pb-20 grid grid-cols-1 lg:grid-cols-2 gap-9 sm:gap-12 items-center">
        <div className="min-w-0">
          <p className="text-xs font-medium text-orange mb-4">
            Automated machine learning
          </p>

          <h1 className="text-[clamp(2.25rem,6vw,2.5rem)] leading-[1.1] font-semibold text-ink tracking-tight">
            Turn your data into
            <br className="hidden sm:block" />
            <span className="sm:hidden"> </span>
            insights
          </h1>

          <p className="text-sm sm:text-base text-ink-secondary mt-5 max-w-md leading-relaxed">
            Upload a CSV, and AutoExplainAI profiles it, preprocesses it,
            trains and compares candidate models, then explains every
            prediction with SHAP.
          </p>

          <div className="flex flex-col min-[400px]:flex-row items-stretch min-[400px]:items-center gap-3 mt-7 sm:mt-8">
            <Link to={ROUTES.SIGNUP} className="w-full min-[400px]:w-auto">
              <Button size="lg" icon={ArrowRight} iconPosition="right">
                Get Started
              </Button>
            </Link>

            <Link to={ROUTES.LOGIN} className="w-full min-[400px]:w-auto">
              <Button size="lg" variant="secondary">
                Sign In
              </Button>
            </Link>
          </div>
        </div>

        <div className="w-full min-w-0">
          <PipelineVisual />
        </div>
      </section>

      {/* Feature cards */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pb-14 sm:pb-20 lg:pb-24">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="min-w-0 bg-white border border-surface-border rounded-card p-4 sm:p-5"
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

      {/* Footer */}
      <footer className="border-t border-surface-border">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-5 sm:py-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-4 text-xs text-ink-muted">
          <span>AutoExplainAI</span>
          <span className="leading-relaxed">
            Explainable AutoML for tabular classification
          </span>
        </div>
      </footer>
    </div>
  );
}
