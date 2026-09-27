import AppShell from "../../components/layout/AppShell";
import Card from "../../components/common/Card";
import { Cpu } from "lucide-react";

export default function TrainingPage() {
  return (
    <AppShell>
      <Card className="flex flex-col items-center justify-center text-center py-16">
        <div className="w-10 h-10 rounded-lg bg-orange-50 flex items-center justify-center mb-3">
          <Cpu size={18} className="text-orange" />
        </div>
        <h2 className="text-sm font-semibold text-ink">Model Training</h2>
        <p className="text-xs text-ink-secondary mt-1 max-w-xs">
          This pipeline stage is being built next — training configuration and
          live progress will appear here.
        </p>
      </Card>
    </AppShell>
  );
}
