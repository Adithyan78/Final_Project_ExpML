import { Link } from "react-router-dom";
import {
  Plus,
  FolderKanban,
  Database,
  FlaskConical,
  CheckCircle2,
  UploadCloud,
  ArrowRight,
} from "lucide-react";
import AppShell from "../../components/layout/AppShell";
import Card, { CardHeader } from "../../components/common/Card";
import Button from "../../components/common/Button";
import Badge from "../../components/common/Badge";
import { ROUTES } from "../../constants/routes";
import {
  dashboardStats,
  recentExperiments,
  recentUploads,
} from "../../mock/mockData";

const STAT_ICONS = [FolderKanban, Database, FlaskConical, CheckCircle2];

function statusTone(status) {
  if (status === "Completed") return "success";
  if (status === "Training") return "info";
  if (status === "Failed") return "error";
  return "neutral";
}

export default function DashboardPage() {
  return (
    <AppShell>
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-[26px] font-semibold text-ink tracking-tight">
            Dashboard
          </h1>
          <p className="text-sm text-ink-secondary mt-1">
            Overview of your AutoExplainAI workspace
          </p>
        </div>
        <Link to={ROUTES.UPLOAD}>
          <Button icon={Plus}>New Experiment</Button>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {dashboardStats.map((stat, i) => {
          const Icon = STAT_ICONS[i];
          return (
            <Card key={stat.label} padding="p-4">
              <div className="flex items-center justify-between">
                <p className="text-xs text-ink-secondary">{stat.label}</p>
                <div className="w-7 h-7 rounded-lg bg-orange-50 flex items-center justify-center">
                  <Icon size={14} className="text-orange" />
                </div>
              </div>
              <p className="text-2xl font-semibold text-ink mt-2">
                {stat.value}
              </p>
            </Card>
          );
        })}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Recent Experiments */}
        <div className="lg:col-span-2 space-y-6">
          <Card padding="p-0">
            <div className="px-5 pt-5">
              <CardHeader
                title="Recent Experiments"
                subtitle="Your latest AutoML runs"
                action={
                  <Link
                    to={ROUTES.HISTORY}
                    className="text-xs font-medium text-orange hover:text-orange-light inline-flex items-center gap-1"
                  >
                    View all <ArrowRight size={12} />
                  </Link>
                }
              />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-t border-surface-border text-left text-[11px] uppercase tracking-wide text-ink-muted">
                    <th className="font-medium px-5 py-2.5">Experiment</th>
                    <th className="font-medium px-5 py-2.5">Dataset</th>
                    <th className="font-medium px-5 py-2.5">Status</th>
                    <th className="font-medium px-5 py-2.5">Best Model</th>
                    <th className="font-medium px-5 py-2.5">F1 Score</th>
                    <th className="font-medium px-5 py-2.5">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {recentExperiments.map((exp) => (
                    <tr
                      key={exp.id}
                      className="border-t border-surface-border hover:bg-surface-page/60 transition-default"
                    >
                      <td className="px-5 py-3 font-medium text-ink whitespace-nowrap">
                        {exp.name}
                      </td>
                      <td className="px-5 py-3 text-ink-secondary whitespace-nowrap">
                        {exp.dataset}
                      </td>
                      <td className="px-5 py-3">
                        <Badge tone={statusTone(exp.status)}>
                          {exp.status}
                        </Badge>
                      </td>
                      <td className="px-5 py-3 text-ink-secondary whitespace-nowrap">
                        {exp.bestModel}
                      </td>
                      <td className="px-5 py-3 text-ink whitespace-nowrap">
                        {exp.f1 ? exp.f1.toFixed(3) : "—"}
                      </td>
                      <td className="px-5 py-3 text-ink-muted whitespace-nowrap">
                        {exp.updated}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Recent Datasets */}
          <Card padding="p-0">
            <div className="px-5 pt-5">
              <CardHeader
                title="Recent Datasets"
                subtitle="CSV files uploaded to your workspace"
              />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-t border-surface-border text-left text-[11px] uppercase tracking-wide text-ink-muted">
                    <th className="font-medium px-5 py-2.5">Name</th>
                    <th className="font-medium px-5 py-2.5">Rows</th>
                    <th className="font-medium px-5 py-2.5">Columns</th>
                    <th className="font-medium px-5 py-2.5">Uploaded</th>
                  </tr>
                </thead>
                <tbody>
                  {recentUploads.map((ds) => (
                    <tr
                      key={ds.id}
                      className="border-t border-surface-border hover:bg-surface-page/60 transition-default"
                    >
                      <td className="px-5 py-3 font-medium text-ink whitespace-nowrap">
                        {ds.name}
                      </td>
                      <td className="px-5 py-3 text-ink-secondary">
                        {ds.rows.toLocaleString()}
                      </td>
                      <td className="px-5 py-3 text-ink-secondary">
                        {ds.columns}
                      </td>
                      <td className="px-5 py-3 text-ink-muted whitespace-nowrap">
                        {ds.uploadedAt}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        {/* Quick start */}
        <div className="space-y-6">
          <Card>
            <div className="w-9 h-9 rounded-lg bg-orange-50 flex items-center justify-center mb-3">
              <UploadCloud size={17} className="text-orange" />
            </div>
            <h3 className="text-sm font-semibold text-ink">
              Upload Dataset
            </h3>
            <p className="text-xs text-ink-secondary mt-1.5 leading-relaxed">
              Start a new AutoML experiment from a CSV dataset.
            </p>
            <Link to={ROUTES.UPLOAD} className="block mt-4">
              <Button size="sm" className="w-full">
                Upload CSV
              </Button>
            </Link>
          </Card>

          <Card>
            <CardHeader title="Pipeline Stage Guide" />
            <ol className="space-y-2.5 text-xs text-ink-secondary">
              {[
                "Upload & profile your dataset",
                "Configure preprocessing",
                "Train candidate models",
                "Compare evaluation metrics",
                "Explain predictions with SHAP",
              ].map((step, i) => (
                <li key={step} className="flex items-start gap-2.5">
                  <span className="w-4 h-4 rounded-full bg-surface-page border border-surface-border text-[10px] font-medium text-ink-secondary flex items-center justify-center shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
