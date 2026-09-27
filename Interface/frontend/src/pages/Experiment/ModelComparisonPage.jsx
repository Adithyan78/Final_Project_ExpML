import AppShell from "../../components/layout/AppShell";
import Card from "../../components/common/Card";
import { BarChart3 } from "lucide-react";

export default function ModelComparisonPage() {
  return (
    <AppShell>
      <Card className="flex flex-col items-center justify-center text-center py-16">
        <div className="w-10 h-10 rounded-lg bg-orange-50 flex items-center justify-center mb-3">
          <BarChart3 size={18} className="text-orange" />
        </div>
        <h2 className="text-sm font-semibold text-ink">Model Results</h2>
        <p className="text-xs text-ink-secondary mt-1 max-w-xs">
          Model comparison and feature importance charts are being built
          next.
        </p>
      </Card>
    </AppShell>
  );
}
