
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
      <div className="w-full min-w-0 space-y-5 px-3 py-3 sm:space-y-6 sm:px-5 sm:py-5 lg:px-8 lg:py-6">
        {/* Page Header */}
        <div className="mb-5 flex min-w-0 flex-col gap-4 sm:mb-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-[26px]">
              Dashboard
            </h1>
            <p className="mt-1 text-xs leading-relaxed text-ink-secondary sm:text-sm">
              Overview of your AutoExplainAI workspace
            </p>
          </div>

          <Link to={ROUTES.UPLOAD} className="w-full shrink-0 sm:w-auto">
            <Button icon={Plus} className="w-full justify-center sm:w-auto">
              New Experiment
            </Button>
          </Link>
        </div>

        {error && (
          <div
            role="alert"
            className="mb-4 flex min-w-0 flex-col items-start justify-between gap-2 rounded-lg border border-state-error/30 bg-[#FCEAEA] p-3 text-sm text-state-error sm:flex-row sm:items-center sm:gap-3"
          >
            <span className="min-w-0 break-words">{error}</span>
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
        <div className="mb-5 grid min-w-0 grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:gap-4 lg:mb-6 lg:grid-cols-4">
          {dashboardStats.map((stat, i) => {
            const Icon = STAT_ICONS[i];

            return (
              <Card key={stat.label} padding="p-3 sm:p-4">
                <div className="flex min-w-0 items-center justify-between gap-2">
                  <p className="min-w-0 text-xs leading-relaxed text-ink-secondary">
                    {stat.label}
                  </p>

                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-orange-50">
                    <Icon size={14} className="text-orange" />
                  </div>
                </div>

                <p className="mt-2 break-words text-2xl font-semibold text-ink sm:text-2xl">
                  {loading ? "—" : stat.value}
                </p>
              </Card>
            );
          })}
        </div>

        <div className="grid min-w-0 grid-cols-1 gap-5 lg:grid-cols-3 lg:gap-6">
          <div className="min-w-0 space-y-5 lg:col-span-2 lg:space-y-6">
            {/* Real workspace activity: use uploaded datasets instead of mock experiments */}
            <Card padding="p-0">
              <div className="px-4 pt-4 sm:px-5 sm:pt-5">
                <CardHeader
                  title="Continue your workflow"
                  subtitle="Pick up with a dataset already in your workspace"
                  action={
                    <button
                      type="button"
                      onClick={loadSummary}
                      disabled={loading}
                      className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-orange hover:text-orange-light disabled:opacity-50"
                    >
                      <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
                      Refresh
                    </button>
                  }
                />
              </div>

              <div className="space-y-3 p-3 sm:p-4">
                {loading ? (
                  <div className="py-8 text-center text-sm text-ink-muted">
                    Loading your datasets...
                  </div>
                ) : recentUploads.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-surface-border px-4 py-8 text-center sm:px-5">
                    <Database size={24} className="mx-auto mb-2 text-ink-muted" />
                    <p className="text-sm font-medium text-ink">
                      Your workspace is ready
                    </p>
                    <p className="mb-4 mt-1 text-xs leading-relaxed text-ink-secondary">
                      Upload a CSV to profile it and start preprocessing.
                    </p>
                    <Link to={ROUTES.UPLOAD}>
                      <Button size="sm" icon={Plus}>
                        Upload your first dataset
                      </Button>
                    </Link>
                  </div>
                ) : (
                  recentUploads.slice(0, 4).map((ds) => (
                    <div
                      key={ds.id}
                      className="flex min-w-0 flex-col justify-between gap-3 rounded-xl border border-surface-border p-3 transition-default hover:border-orange/40 hover:bg-surface-page/50 sm:flex-row sm:items-center sm:p-4"
                    >
                      <div className="flex min-w-0 items-start gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-orange-50">
                          <Database size={16} className="text-orange" />
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-ink">
                            {ds.name}
                          </p>
                          <p className="mt-1 text-xs text-ink-secondary">
                            {Number(ds.n_rows ?? 0).toLocaleString()} rows · {ds.n_cols ?? 0} columns
                          </p>
                          <p className="mt-1 text-xs text-ink-muted">
                            Uploaded {formatDate(ds.created_at)}
                          </p>
                        </div>
                      </div>
                      <Link to={ROUTES.UPLOAD} className="w-full shrink-0 sm:w-auto">
                        <Button
                          size="sm"
                          variant="outline"
                          icon={ArrowRight}
                          className="w-full justify-center sm:w-auto"
                        >
                          Start workflow
                        </Button>
                      </Link>
                    </div>
                  ))
                )}

                {recentUploads.length > 0 && (
                  <div className="flex flex-col items-start justify-between gap-2 pt-1 min-[420px]:flex-row min-[420px]:items-center">
                    <p className="text-xs text-ink-muted">
                      Showing {Math.min(recentUploads.length, 4)} of {recentUploads.length} recent datasets
                    </p>
                    <Link
                      to={ROUTES.UPLOAD}
                      className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-orange hover:text-orange-light"
                    >
                      Add dataset <ArrowRight size={12} />
                    </Link>
                  </div>
                )}
              </div>
            </Card>

            {/* Recent Datasets: live backend data */}
            <Card padding="p-0">
              <div className="px-4 pt-4 sm:px-5 sm:pt-5">
                <CardHeader
                  title="Recent Datasets"
                  subtitle="CSV files uploaded to your workspace"
                  action={
                    <button
                      type="button"
                      onClick={loadSummary}
                      disabled={loading}
                      className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-orange hover:text-orange-light disabled:opacity-50"
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

              <div className="w-full overflow-x-auto overscroll-x-contain">
                <table className="w-full min-w-[560px] text-sm">
                  <thead>
                    <tr className="border-t border-surface-border text-left text-[11px] uppercase tracking-wide text-ink-muted">
                      <th className="px-4 py-2.5 font-medium sm:px-5">Name</th>
                      <th className="px-4 py-2.5 font-medium sm:px-5">Rows</th>
                      <th className="px-4 py-2.5 font-medium sm:px-5">Columns</th>
                      <th className="px-4 py-2.5 font-medium sm:px-5">Uploaded</th>
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
                          className="border-t border-surface-border transition-default hover:bg-surface-page/60"
                        >
                          <td className="whitespace-nowrap px-4 py-3 font-medium text-ink sm:px-5">
                            {ds.name}
                          </td>
                          <td className="px-4 py-3 text-ink-secondary sm:px-5">
                            {Number(ds.n_rows ?? 0).toLocaleString()}
                          </td>
                          <td className="px-4 py-3 text-ink-secondary sm:px-5">
                            {ds.n_cols ?? 0}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 text-ink-muted sm:px-5">
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
          <div className="min-w-0 space-y-5 lg:space-y-6">
            <Card>
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-orange-50">
                <UploadCloud size={17} className="text-orange" />
              </div>

              <h3 className="text-sm font-semibold text-ink">
                Upload Dataset
              </h3>

              <p className="mt-1.5 text-xs leading-relaxed text-ink-secondary">
                Start a new AutoML experiment from a CSV dataset.
              </p>

              <Link to={ROUTES.UPLOAD} className="mt-4 block">
                <Button size="sm" className="w-full justify-center">
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
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-surface-border bg-surface-page text-[10px] font-medium text-ink-secondary">
                      {i + 1}
                    </span>
                    <span className="min-w-0 leading-relaxed">{step}</span>
                  </li>
                ))}
              </ol>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
