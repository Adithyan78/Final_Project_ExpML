
import AppShell from "../../components/layout/AppShell";
import Card from "../../components/common/Card";
import { Lightbulb } from "lucide-react";

export default function ExplainabilityPage() {
  return (
    <AppShell>
      <div className="mx-auto flex min-h-[calc(100vh-120px)] w-full min-w-0 max-w-7xl items-center justify-center p-3 sm:p-5 md:p-8">
        <Card className="flex w-full max-w-lg flex-col items-center justify-center px-5 py-12 text-center sm:px-8 sm:py-16">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-orange/10">
            <Lightbulb size={21} className="text-orange" />
          </div>

          <h2 className="text-base font-semibold text-ink">
            Explainability
          </h2>

          <p className="mt-2 max-w-xs text-xs leading-relaxed text-ink-secondary sm:text-sm">
            SHAP-based global and per-prediction explanations are being built
            next.
          </p>

          <span className="mt-5 rounded-full border border-border bg-surface-secondary px-3 py-1.5 text-[10px] font-medium text-ink-secondary">
            Coming soon
          </span>
        </Card>
      </div>
    </AppShell>
  );
}
