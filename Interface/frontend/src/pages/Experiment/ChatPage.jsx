import AppShell from "../../components/layout/AppShell";
import Card from "../../components/common/Card";
import { MessageSquare } from "lucide-react";

export default function ChatPage() {
  return (
    <AppShell>
      <Card className="flex flex-col items-center justify-center text-center py-16">
        <div className="w-10 h-10 rounded-lg bg-orange-50 flex items-center justify-center mb-3">
          <MessageSquare size={18} className="text-orange" />
        </div>
        <h2 className="text-sm font-semibold text-ink">AI Assistant</h2>
        <p className="text-xs text-ink-secondary mt-1 max-w-xs">
          The experiment-grounded chat assistant is being built next.
        </p>
      </Card>
    </AppShell>
  );
}
