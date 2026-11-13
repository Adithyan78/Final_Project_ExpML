
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Clock3,
  Download,
  RefreshCw,
  Trophy,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import Card from "../../components/common/Card";

import {
  getTrainingRun,
  getTrainingLeaderboard,
  getTrainingArtifacts,
  downloadTrainingArtifact,
} from "../../services/training";

const formatLabel = (value = "") =>
  String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());

const formatMetric = (value, metric = "") => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  const percentageMetrics = [
    "accuracy",
    "balanced_accuracy",
    "precision",
    "recall",
    "f1",
    "roc_auc",
  ];

  return percentageMetrics.includes(metric.toLowerCase())
    ? `${(value * 100).toFixed(2)}%`
    : value.toFixed(4);
};

const formatDuration = (seconds) => {
  if (typeof seconds !== "number") return "—";
  return seconds < 1
    ? `${(seconds * 1000).toFixed(0)} ms`
    : `${seconds.toFixed(2)} s`;
};

function MetricCard({ label, value, icon: Icon }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-ink-secondary">{label}</p>
        <Icon size={16} className="text-orange" />
      </div>
      <p className="text-xl font-semibold text-ink mt-2">{value}</p>
    </Card>
  );
}

export default function ModelComparisonPage() {
  const location = useLocation();
  const trainingRunId = location.state?.trainingRunId;

  const [run, setRun] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [artifacts, setArtifacts] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [downloading, setDownloading] = useState("");

  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;

    async function loadResults() {
      if (!trainingRunId) {
        setLoading(false);
        setError("No training run was selected. Start training to view its results.");
        return;
      }

      setLoading(true);
      setError("");

      try {
        const runData = await getTrainingRun(trainingRunId);

        if (!active) return;

        setRun(runData);

        if (runData.status === "completed") {
          const [leaderboardData, artifactData] = await Promise.all([
            getTrainingLeaderboard(trainingRunId),
            getTrainingArtifacts(trainingRunId),
          ]);

          if (!active) return;

          setLeaderboard(leaderboardData.leaderboard || []);
          setArtifacts(artifactData.artifacts || []);
        } else {
          setLeaderboard([]);
          setArtifacts([]);
        }
      } catch (err) {
        if (active) {
          setError(err.message || "Could not load training results.");
        }
      } finally {
        if (active) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    }

    loadResults();

    return () => {
      active = false;
    };
  }, [trainingRunId, refreshKey]);

  const handleRefresh = () => {
    setRefreshing(true);
    setRefreshKey((previous) => previous + 1);
  };

  const handleDownload = async (artifact) => {
    try {
      setDownloading(artifact);
      await downloadTrainingArtifact(trainingRunId, artifact);
    } catch (err) {
      setError(err.message || "Artifact download failed.");
    } finally {
      setDownloading("");
    }
  };

  const summary = run?.summary || {};
  const primaryMetric = summary.primary_metric || run?.primary_metric || "";
  const bestModel = summary.best_model || run?.best_model || "—";

  const bestRow =
    leaderboard.find((row) => row.algorithm === bestModel) ||
    leaderboard[0];

  const warnings = Array.isArray(summary.warnings)
    ? summary.warnings
    : [];

  if (loading) {
    return (
      <AppShell>
        <Card className="flex flex-col items-center justify-center py-16">
          <RefreshCw size={22} className="animate-spin text-orange mb-3" />
          <p className="text-sm font-medium text-ink">
            Loading model results...
          </p>
          <p className="text-xs text-ink-secondary mt-1">
            Retrieving your training run.
          </p>
        </Card>
      </AppShell>
    );
  }

  if (error && !run) {
    return (
      <AppShell>
        <Card className="p-6 text-center">
          <AlertTriangle size={24} className="mx-auto text-red-500 mb-3" />
          <h2 className="text-sm font-semibold text-ink">
            Unable to load results
          </h2>
          <p className="text-xs text-ink-secondary mt-2">{error}</p>
          <button
            onClick={handleRefresh}
            className="mt-4 px-4 py-2 rounded-lg bg-orange text-white text-xs"
          >
            Try again
          </button>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-ink">
              Model Results
            </h1>
            <p className="text-xs text-ink-secondary mt-1">
              Compare model performance and inspect your AutoML run.
            </p>
          </div>

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-xs text-ink hover:bg-surface-secondary disabled:opacity-50"
          >
            <RefreshCw
              size={14}
              className={refreshing ? "animate-spin" : ""}
            />
            Refresh
          </button>
        </div>

        {/* Training status */}
        {run?.status !== "completed" && (
          <Card className="p-5">
            <div className="flex items-start gap-3">
              <Activity size={20} className="text-orange mt-1" />
              <div>
                <h2 className="text-sm font-semibold text-ink">
                  Training {run?.status || "unknown"}
                </h2>
                <p className="text-xs text-ink-secondary mt-1">
                  {run?.status === "failed"
                    ? run.error || "Training failed."
                    : "Your model results will appear here when training completes. Refresh to check the latest status."}
                </p>
              </div>
            </div>
          </Card>
        )}

        {run?.status === "completed" && (
          <>
            {/* Best model */}
            <Card className="p-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 text-xs text-ink-secondary">
                    <Trophy size={15} className="text-orange" />
                    Best performing model
                  </div>

                  <h2 className="text-2xl font-semibold text-ink mt-2">
                    {bestModel}
                  </h2>

                  <p className="text-xs text-ink-secondary mt-1">
                    {formatLabel(run.task || summary.task || "Model")} ·{" "}
                    {formatLabel(primaryMetric || "Primary metric")}
                  </p>
                </div>

                <div className="text-left sm:text-right">
                  <p className="text-xs text-ink-secondary">
                    Best cross-validation score
                  </p>
                  <p className="text-3xl font-semibold text-orange mt-1">
                    {formatMetric(
                      summary.best_cv_score ??
                        bestRow?.[`cv_${primaryMetric}_mean`],
                      primaryMetric
                    )}
                  </p>
                </div>
              </div>
            </Card>

            {/* Overview metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
              <MetricCard
                label="Models screened"
                value={summary.models_screened ?? "—"}
                icon={BarChart3}
              />
              <MetricCard
                label="Finalists"
                value={summary.finalists ?? "—"}
                icon={Trophy}
              />
              <MetricCard
                label="Training duration"
                value={formatDuration(summary.total_time_s)}
                icon={Clock3}
              />
              <MetricCard
                label="Features"
                value={summary.n_features ?? "—"}
                icon={Activity}
              />
            </div>

            {/* Dataset information */}
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-ink mb-4">
                Training overview
              </h2>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-ink-secondary">Task</p>
                  <p className="text-sm font-medium text-ink mt-1">
                    {formatLabel(run.task || summary.task || "—")}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-ink-secondary">Primary metric</p>
                  <p className="text-sm font-medium text-ink mt-1">
                    {formatLabel(primaryMetric || "—")}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-ink-secondary">Training rows</p>
                  <p className="text-sm font-medium text-ink mt-1">
                    {summary.n_train ?? "—"}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-ink-secondary">Test rows</p>
                  <p className="text-sm font-medium text-ink mt-1">
                    {summary.n_test ?? "—"}
                  </p>
                </div>
              </div>
            </Card>

            {/* Leaderboard */}
            <Card className="p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-sm font-semibold text-ink">
                    Model leaderboard
                  </h2>
                  <p className="text-xs text-ink-secondary mt-1">
                    Models ranked by the AutoML selection process.
                  </p>
                </div>

                <span className="text-xs text-ink-secondary">
                  {leaderboard.length} models
                </span>
              </div>

              {leaderboard.length === 0 ? (
                <p className="text-xs text-ink-secondary py-6 text-center">
                  No leaderboard data is available.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs min-w-[760px]">
                    <thead>
                      <tr className="border-b border-border text-ink-secondary">
                        <th className="py-3 pr-4">Rank</th>
                        <th className="py-3 pr-4">Model</th>
                        <th className="py-3 pr-4">Family</th>
                        <th className="py-3 pr-4">
                          CV {formatLabel(primaryMetric)}
                        </th>
                        <th className="py-3 pr-4">Test score</th>
                        <th className="py-3 pr-4">Overfit gap</th>
                        <th className="py-3 pr-4">Training time</th>
                        <th className="py-3">Status</th>
                      </tr>
                    </thead>

                    <tbody>
                      {leaderboard.map((row, index) => {
                        const cvScore =
                          row[`cv_${primaryMetric}_mean`];

                        const testScore =
                          row.test?.[primaryMetric];

                        return (
                          <tr
                            key={row.algorithm || index}
                            className="border-b border-border last:border-0"
                          >
                            <td className="py-3 pr-4 font-medium text-ink">
                              #{row.rank ?? index + 1}
                            </td>

                            <td className="py-3 pr-4 font-medium text-ink">
                              {row.algorithm || "Unknown"}
                              {row.tuned && (
                                <span className="ml-2 text-[10px] text-orange">
                                  Tuned
                                </span>
                              )}
                            </td>

                            <td className="py-3 pr-4 text-ink-secondary">
                              {formatLabel(row.family || "—")}
                            </td>

                            <td className="py-3 pr-4 text-ink">
                              {formatMetric(cvScore, primaryMetric)}
                              <span className="block text-[10px] text-ink-secondary mt-1">
                                ±{" "}
                                {formatMetric(
                                  row[`cv_${primaryMetric}_std`],
                                  primaryMetric
                                )}
                              </span>
                            </td>

                            <td className="py-3 pr-4 text-ink">
                              {formatMetric(testScore, primaryMetric)}
                            </td>

                            <td className="py-3 pr-4 text-ink">
                              {formatMetric(row.overfit_gap)}
                            </td>

                            <td className="py-3 pr-4 text-ink">
                              {formatDuration(row.train_time_s)}
                            </td>

                            <td className="py-3">
                              {row.overfit_warning ? (
                                <span className="text-amber-600">
                                  Overfit warning
                                </span>
                              ) : row.test_error ? (
                                <span className="text-red-500">
                                  Test failed
                                </span>
                              ) : (
                                <span className="text-green-600">
                                  Completed
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            {/* Best model evaluation */}
            {bestRow?.test && (
              <Card className="p-5">
                <h2 className="text-sm font-semibold text-ink">
                  Best model evaluation
                </h2>
                <p className="text-xs text-ink-secondary mt-1 mb-4">
                  Held-out test metrics for {bestRow.algorithm}.
                </p>

                <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
                  {Object.entries(bestRow.test).map(([metric, value]) => (
                    <div key={metric}>
                      <p className="text-xs text-ink-secondary">
                        {formatLabel(metric)}
                      </p>
                      <p className="text-lg font-semibold text-ink mt-1">
                        {formatMetric(value, metric)}
                      </p>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Warnings */}
            {warnings.length > 0 && (
              <Card className="p-5">
                <div className="flex items-center gap-2 mb-3">
                  <AlertTriangle size={17} className="text-amber-500" />
                  <h2 className="text-sm font-semibold text-ink">
                    Training diagnostics
                  </h2>
                </div>

                <div className="space-y-2">
                  {warnings.map((warning, index) => (
                    <p
                      key={index}
                      className="text-xs text-ink-secondary"
                    >
                      • {warning}
                    </p>
                  ))}
                </div>
              </Card>
            )}

            {/* Artifacts */}
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-ink">
                Training artifacts
              </h2>
              <p className="text-xs text-ink-secondary mt-1 mb-4">
                Download files generated during this training run.
              </p>

              {artifacts.length === 0 ? (
                <p className="text-xs text-ink-secondary">
                  No artifacts are available.
                </p>
              ) : (
                <div className="space-y-2">
                  {artifacts.map((artifact) => (
                    <div
                      key={artifact}
                      className="flex flex-wrap items-center justify-between gap-3 border border-border rounded-lg p-3"
                    >
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-ink break-all">
                          {artifact}
                        </p>
                      </div>

                      <button
                        onClick={() => handleDownload(artifact)}
                        disabled={downloading === artifact}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-xs text-ink hover:bg-surface-secondary disabled:opacity-50"
                      >
                        <Download size={14} />
                        {downloading === artifact
                          ? "Downloading..."
                          : "Download"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </>
        )}

        {error && run && (
          <p className="text-xs text-red-500">{error}</p>
        )}
      </div>
    </AppShell>
  );
}
