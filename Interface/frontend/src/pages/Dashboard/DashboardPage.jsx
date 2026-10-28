
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Plus,
  Database,
  Workflow,
  Rows3,
  Columns3,
  UploadCloud,
  ArrowRight,
  RefreshCw,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import Card, { CardHeader } from "../../components/common/Card";
import Button from "../../components/common/Button";
import { ROUTES } from "../../constants/routes";

import { getDashboardSummary } from "../../services/datasets";
import { getPreprocessingRuns } from "../../services/preprocessing";

const STAT_ICONS = [
  Database,
  Workflow,
  Rows3,
  Columns3,
];

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleDateString();
}

export default function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [preprocessingRunCount, setPreprocessingRunCount] = useState(null);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const data = await getDashboardSummary();
      setSummary(data);

      // Count real preprocessing runs for the datasets returned by the dashboard.
      const uploads = data?.recent_uploads ?? [];
      const runLists = await Promise.all(
        uploads.map(async (dataset) => {
          try {
            const result = await getPreprocessingRuns(dataset.id);
            if (Array.isArray(result)) return result;
            if (Array.isArray(result?.runs)) return result.runs;
            if (Array.isArray(result?.items)) return result.items;
            return [];
          } catch {
            return [];
          }
        })
      );
      setPreprocessingRunCount(runLists.reduce((total, runs) => total + runs.length, 0));
    } catch (err) {
      setError(err.message || "Unable to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const apiStats = summary?.stats;
  const recentUploads = summary?.recent_uploads ?? [];
  const recentRows = recentUploads.reduce(
    (total, dataset) => total + Number(dataset.n_rows ?? 0),
    0
  );
  const latestDatasetColumns = recentUploads[0]?.n_cols ?? 0;

  // All four cards use real workspace data; no mock project/experiment counts.
  const dashboardStats = [
    { label: "Datasets", value: apiStats?.total_datasets ?? recentUploads.length },
    {
      label: "Recent Preprocessing Runs",
      value: preprocessingRunCount === null ? "—" : preprocessingRunCount,
    },
    { label: "Rows in Recent Datasets", value: recentRows.toLocaleString() },
    { label: "Latest Dataset Columns", value: latestDatasetColumns },
  ];


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

      {error && (
        <div
          role="alert"
          className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-state-error/30 bg-[#FCEAEA] p-3 text-sm text-state-error"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={loadSummary}
            className="shrink-0 font-medium underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {dashboardStats.map((stat, i) => {
          const Icon = STAT_ICONS[i];

          return (
            <Card key={stat.label} padding="p-4">
              <div className="flex items-center justify-between">
                <p className="text-xs text-ink-secondary">
                  {stat.label}
                </p>

                <div className="w-7 h-7 rounded-lg bg-orange-50 flex items-center justify-center">
                  <Icon size={14} className="text-orange" />
                </div>
              </div>

              <p className="text-2xl font-semibold text-ink mt-2">
                {loading ? "—" : stat.value}
              </p>
            </Card>
          );
        })}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Real workspace activity: use uploaded datasets instead of mock experiments */}
          <Card padding="p-0">
            <div className="px-5 pt-5">
              <CardHeader
                title="Continue your workflow"
                subtitle="Pick up with a dataset already in your workspace"
                action={
                  <button
                    type="button"
                    onClick={loadSummary}
                    disabled={loading}
                    className="inline-flex items-center gap-1 text-xs font-medium text-orange hover:text-orange-light disabled:opacity-50"
                  >
                    <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
                    Refresh
                  </button>
                }
              />
            </div>

            <div className="p-4 space-y-3">
              {loading ? (
                <div className="py-8 text-center text-sm text-ink-muted">
                  Loading your datasets...
                </div>
              ) : recentUploads.length === 0 ? (
                <div className="rounded-xl border border-dashed border-surface-border px-5 py-8 text-center">
                  <Database size={24} className="mx-auto text-ink-muted mb-2" />
                  <p className="text-sm font-medium text-ink">Your workspace is ready</p>
                  <p className="text-xs text-ink-secondary mt-1 mb-4">
                    Upload a CSV to profile it and start preprocessing.
                  </p>
                  <Link to={ROUTES.UPLOAD}>
                    <Button size="sm" icon={Plus}>Upload your first dataset</Button>
                  </Link>
                </div>
              ) : (
                recentUploads.slice(0, 4).map((ds) => (
                  <div
                    key={ds.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-surface-border p-4 transition-default hover:border-orange/40 hover:bg-surface-page/50"
                  >
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="w-9 h-9 rounded-lg bg-orange-50 flex items-center justify-center shrink-0">
                        <Database size={16} className="text-orange" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink truncate">{ds.name}</p>
                        <p className="text-xs text-ink-secondary mt-1">
                          {Number(ds.n_rows ?? 0).toLocaleString()} rows · {ds.n_cols ?? 0} columns
                        </p>
                        <p className="text-xs text-ink-muted mt-1">
                          Uploaded {formatDate(ds.created_at)}
                        </p>
                      </div>
                    </div>
                    <Link to={ROUTES.UPLOAD} className="shrink-0">
                      <Button size="sm" variant="outline" icon={ArrowRight}>
                        Start workflow
                      </Button>
                    </Link>
                  </div>
                ))
              )}

              {recentUploads.length > 0 && (
                <div className="flex items-center justify-between pt-1">
                  <p className="text-xs text-ink-muted">
                    Showing {Math.min(recentUploads.length, 4)} of {recentUploads.length} recent datasets
                  </p>
                  <Link
                    to={ROUTES.UPLOAD}
                    className="inline-flex items-center gap-1 text-xs font-medium text-orange hover:text-orange-light"
                  >
                    Add dataset <ArrowRight size={12} />
                  </Link>
                </div>
              )}
            </div>
          </Card>

          {/* Recent Datasets: live backend data */}
          <Card padding="p-0">
            <div className="px-5 pt-5">
              <CardHeader
                title="Recent Datasets"
                subtitle="CSV files uploaded to your workspace"
                action={
                  <button
                    type="button"
                    onClick={loadSummary}
                    disabled={loading}
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-orange hover:text-orange-light disabled:opacity-50"
                  >
                    <RefreshCw
                      size={13}
                      className={loading ? "animate-spin" : ""}
                    />
                    Refresh
                  </button>
                }
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
                  {loading ? (
                    <tr>
                      <td
                        colSpan={4}
                        className="px-5 py-8 text-center text-ink-muted"
                      >
                        Loading datasets...
                      </td>
                    </tr>
                  ) : recentUploads.length === 0 ? (
                    <tr>
                      <td
                        colSpan={4}
                        className="px-5 py-8 text-center text-ink-muted"
                      >
                        No datasets uploaded yet.
                      </td>
                    </tr>
                  ) : (
                    recentUploads.map((ds) => (
                      <tr
                        key={ds.id}
                        className="border-t border-surface-border hover:bg-surface-page/60 transition-default"
                      >
                        <td className="px-5 py-3 font-medium text-ink whitespace-nowrap">
                          {ds.name}
                        </td>
                        <td className="px-5 py-3 text-ink-secondary">
                          {Number(ds.n_rows ?? 0).toLocaleString()}
                        </td>
                        <td className="px-5 py-3 text-ink-secondary">
                          {ds.n_cols ?? 0}
                        </td>
                        <td className="px-5 py-3 text-ink-muted whitespace-nowrap">
                          {formatDate(ds.created_at)}
                        </td>
                      </tr>
                    ))
                  )}
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
