
import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  Award,
  BarChart3,
  CheckCircle2,
  Clock3,
  Download,
  FileJson,
  FileSpreadsheet,
  FileText,
  RefreshCw,
  Search,
  Trophy,
} from "lucide-react";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ErrorBar,
  ScatterChart,
  Scatter,
  ZAxis,
} from "recharts";

import AppShell from "../../components/layout/AppShell";
import Card from "../../components/common/Card";

import {
  getTrainingRun,
  getTrainingLeaderboard,
  getTrainingArtifacts,
  downloadTrainingArtifact,
} from "../../services/training";

import { BASE_URL } from "../../services/api";

/* -------------------------------------------------------
   Helpers
------------------------------------------------------- */

const percentageMetrics = [
  "accuracy",
  "balanced_accuracy",
  "precision",
  "recall",
  "f1",
  "roc_auc",
  "average_precision",
];

const formatLabel = (value = "") =>
  String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());

const formatMetric = (value, metric = "") => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  return percentageMetrics.includes(metric.toLowerCase())
    ? `${(value * 100).toFixed(2)}%`
    : value.toFixed(4);
};

const formatDuration = (seconds) => {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) {
    return "—";
  }

  return seconds < 1
    ? `${(seconds * 1000).toFixed(0)} ms`
    : `${seconds.toFixed(2)} s`;
};

const formatGap = (value) => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  return `${(value * 100).toFixed(2)}%`;
};

const getScore = (row, metric, type = "cv") => {
  if (!row || !metric) return null;

  const value =
    type === "test"
      ? row.test?.[metric]
      : row[`cv_${metric}_mean`];

  return typeof value === "number" && Number.isFinite(value)
    ? value
    : null;
};

const getArtifactIcon = (filename) => {
  const extension = filename.split(".").pop()?.toLowerCase();

  if (extension === "json") return FileJson;
  if (extension === "csv") return FileSpreadsheet;
  if (extension === "joblib" || extension === "pkl") {
    return BarChart3;
  }

  return FileText;
};

const getArtifactGroup = (filename) => {
  if (filename.startsWith("models/") || filename.endsWith(".joblib")) {
    return "Trained models";
  }

  if (
    filename.includes("leaderboard") ||
    filename.includes("evaluation") ||
    filename.includes("results") ||
    filename.includes("selection")
  ) {
    return "Evaluation reports";
  }

  return "Run metadata";
};

/* -------------------------------------------------------
   Load a JSON artifact using the existing download route.
   No backend endpoint is added.
------------------------------------------------------- */

async function fetchArtifactJson(trainingRunId, filename) {
  const params = new URLSearchParams({
    artifact_path: filename,
  });

  const response = await fetch(
    `${BASE_URL}/training/runs/${encodeURIComponent(
      trainingRunId
    )}/artifacts/download?${params}`,
    {
      credentials: "include",
    }
  );

  if (!response.ok) {
    throw new Error(`Could not load ${filename}`);
  }

  return response.json();
}

/* -------------------------------------------------------
   Reusable UI
------------------------------------------------------- */

function MetricCard({ label, value, icon: Icon, description }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-ink-secondary">{label}</p>
        <Icon size={17} className="text-orange" />
      </div>

      <p className="text-xl font-semibold text-ink mt-2">
        {value}
      </p>

      {description && (
        <p className="text-[11px] text-ink-secondary mt-1">
          {description}
        </p>
      )}
    </Card>
  );
}

function SectionHeading({ title, description, action }) {
  return (
    <div className="flex flex-wrap justify-between items-start gap-3 mb-5">
      <div>
        <h2 className="text-sm font-semibold text-ink">{title}</h2>

        {description && (
          <p className="text-xs text-ink-secondary mt-1">
            {description}
          </p>
        )}
      </div>

      {action}
    </div>
  );
}

function ChartCard({ title, description, children, height = 300 }) {
  return (
    <Card className="p-5 min-w-0">
      <SectionHeading title={title} description={description} />

      <div style={{ height }} className="w-full min-w-0">
        {children}
      </div>
    </Card>
  );
}

function EmptyChart({ message = "No data available for this visualization." }) {
  return (
    <div className="h-full flex items-center justify-center text-xs text-ink-secondary">
      {message}
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-lg border border-border bg-surface p-3 shadow-lg">
      <p className="text-xs font-semibold text-ink mb-2">{label}</p>

      {payload.map((item, index) => (
        <p key={index} className="text-xs text-ink-secondary">
          {item.name}:{" "}
          {typeof item.value === "number"
            ? `${(item.value * 100).toFixed(2)}%`
            : item.value}
        </p>
      ))}
    </div>
  );
}

function ConfusionMatrix({ evaluation }) {
  const matrix = evaluation?.confusion_matrix;
  const classes = evaluation?.classes;

  if (
    !Array.isArray(matrix) ||
    matrix.length === 0 ||
    !Array.isArray(classes)
  ) {
    return <EmptyChart message="Confusion matrix artifact is unavailable." />;
  }

  const maxValue = Math.max(...matrix.flat(), 1);

  return (
    <div className="h-full flex flex-col items-center justify-center">
      <p className="text-[10px] text-ink-secondary mb-4">
        Predicted class
      </p>

      <div className="flex gap-3 items-center">
        <div className="[writing-mode:vertical-rl] rotate-180 text-[10px] text-ink-secondary">
          Actual class
        </div>

        <div>
          <div
            className="grid gap-2"
            style={{
              gridTemplateColumns: `repeat(${classes.length}, minmax(75px, 110px))`,
            }}
          >
            {classes.map((className) => (
              <div
                key={className}
                className="text-center text-xs text-ink-secondary pb-1"
              >
                {className}
              </div>
            ))}

            {matrix.map((row, rowIndex) =>
              row.map((value, colIndex) => {
                const intensity = value / maxValue;

                return (
                  <div
                    key={`${rowIndex}-${colIndex}`}
                    className="rounded-xl min-h-[85px] flex flex-col items-center justify-center border border-border"
                    style={{
                      backgroundColor:
                        intensity > 0.5
                          ? `rgba(34, 197, 94, ${0.15 + intensity * 0.45})`
                          : `rgba(249, 115, 22, ${0.08 + intensity * 0.3})`,
                    }}
                  >
                    <span className="text-xl font-semibold text-ink">
                      {value}
                    </span>

                    <span className="text-[10px] text-ink-secondary mt-1">
                      Actual {classes[rowIndex]}
                    </span>
                  </div>
                );
              })
            )}
          </div>

          <div className="flex justify-center gap-4 mt-4 text-[10px] text-ink-secondary">
            <span>Rows: actual</span>
            <span>Columns: predicted</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------
   Main page
------------------------------------------------------- */

export default function ModelComparisonPage() {
  const location = useLocation();

  const trainingRunId =
    location.state?.trainingRunId ||
    sessionStorage.getItem("latestTrainingRunId");

  const [run, setRun] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [evaluation, setEvaluation] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [downloading, setDownloading] = useState("");

  const [refreshKey, setRefreshKey] = useState(0);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("rank");

  /* -----------------------------------------------------
     Load run, leaderboard, artifacts and evaluation JSON
  ----------------------------------------------------- */

  useEffect(() => {
    let active = true;
    let pollTimer;

    async function loadResults(isPolling = false) {
      if (!trainingRunId) {
        setLoading(false);
        setError(
          "No training run was selected. Start training to view its results."
        );
        return;
      }

      if (!isPolling) setLoading(true);
      setError("");

      try {
        const runData = await getTrainingRun(trainingRunId);

        if (!active) return;

        setRun(runData);

        if (runData.status === "completed") {
          const [leaderboardData, artifactData] = await Promise.all([
            Array.isArray(runData.leaderboard)
              ? Promise.resolve({ leaderboard: runData.leaderboard })
              : getTrainingLeaderboard(trainingRunId),

            Array.isArray(runData.artifacts)
              ? Promise.resolve({ artifacts: runData.artifacts })
              : getTrainingArtifacts(trainingRunId),
          ]);

          if (!active) return;

          const rows = leaderboardData.leaderboard || [];
          const files = artifactData.artifacts || [];

          setLeaderboard(rows);
          setArtifacts(files);

          const evaluationArtifact = files.find((file) =>
            String(file).endsWith("test_evaluation.json")
          );

          if (evaluationArtifact) {
            try {
              const evaluationData = await fetchArtifactJson(
                trainingRunId,
                evaluationArtifact
              );

              if (active) setEvaluation(evaluationData);
            } catch {
              if (active) setEvaluation(null);
            }
          } else {
            setEvaluation(null);
          }
        } else {
          setLeaderboard([]);
          setArtifacts([]);
          setEvaluation(null);

          if (
            runData.status === "pending" ||
            runData.status === "running"
          ) {
            pollTimer = window.setTimeout(() => {
              if (active) loadResults(true);
            }, 2500);
          }
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
      if (pollTimer) window.clearTimeout(pollTimer);
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

  /* -----------------------------------------------------
     Derived values
  ----------------------------------------------------- */

  const summary = run?.summary || {};

  const primaryMetric =
    summary.primary_metric || run?.primary_metric || "accuracy";

  const bestModel =
    summary.best_model || run?.best_model || "—";

  const bestRow =
    leaderboard.find((row) => row.algorithm === bestModel) ||
    leaderboard[0];

  const bestTestRow = useMemo(() => {
    const validRows = leaderboard.filter((row) => {
      const score = getScore(row, primaryMetric, "test");
      return score !== null && !row.test_error;
    });

    return validRows.reduce((best, current) => {
      if (!best) return current;

      return getScore(current, primaryMetric, "test") >
        getScore(best, primaryMetric, "test")
        ? current
        : best;
    }, null);
  }, [leaderboard, primaryMetric]);

  const filteredLeaderboard = useMemo(() => {
    let rows = leaderboard.filter((row) =>
      String(row.algorithm || "")
        .toLowerCase()
        .includes(search.toLowerCase())
    );

    if (sortBy === "cv") {
      rows = [...rows].sort(
        (a, b) =>
          (getScore(b, primaryMetric) ?? -Infinity) -
          (getScore(a, primaryMetric) ?? -Infinity)
      );
    } else if (sortBy === "test") {
      rows = [...rows].sort(
        (a, b) =>
          (getScore(b, primaryMetric, "test") ?? -Infinity) -
          (getScore(a, primaryMetric, "test") ?? -Infinity)
      );
    } else if (sortBy === "time") {
      rows = [...rows].sort(
        (a, b) =>
          (a.train_time_s ?? Infinity) -
          (b.train_time_s ?? Infinity)
      );
    }

    return rows;
  }, [leaderboard, search, sortBy, primaryMetric]);

  const warnings = Array.isArray(summary.warnings)
    ? summary.warnings
    : [];

  const artifactGroups = useMemo(() => {
    return artifacts.reduce((groups, artifact) => {
      const group = getArtifactGroup(artifact);
      groups[group] = [...(groups[group] || []), artifact];
      return groups;
    }, {});
  }, [artifacts]);

  /* -----------------------------------------------------
     Chart data
  ----------------------------------------------------- */

  const performanceData = useMemo(
    () =>
      leaderboard.map((row) => ({
        model: row.algorithm,
        cv: getScore(row, primaryMetric),
        test: getScore(row, primaryMetric, "test"),
      })),
    [leaderboard, primaryMetric]
  );

  const stabilityData = useMemo(
    () =>
      leaderboard
        .filter((row) => getScore(row, primaryMetric) !== null)
        .map((row) => ({
          model: row.algorithm,
          mean: getScore(row, primaryMetric),
          std: row[`cv_${primaryMetric}_std`] || 0,
          error: [
            row[`cv_${primaryMetric}_std`] || 0,
            row[`cv_${primaryMetric}_std`] || 0,
          ],
        })),
    [leaderboard, primaryMetric]
  );

  const timeData = useMemo(
    () =>
      leaderboard.map((row) => ({
        model: row.algorithm,
        training: row.train_time_s ?? 0,
        inference: row.inference_time_s ?? 0,
      })),
    [leaderboard]
  );

  const rocData = useMemo(
    () =>
      leaderboard
        .filter((row) => typeof row.test?.roc_auc === "number")
        .map((row) => ({
          model: row.algorithm,
          auc: row.test.roc_auc,
        })),
    [leaderboard]
  );

  const diagnosticData = useMemo(
    () =>
      leaderboard
        .filter(
          (row) =>
            typeof row.train_accuracy_mean === "number" &&
            typeof row.cv_accuracy_mean === "number"
        )
        .map((row) => ({
          model: row.algorithm,
          train: row.train_accuracy_mean,
          cv: row.cv_accuracy_mean,
          gap: row.overfit_gap,
          warning: row.overfit_warning,
        })),
    [leaderboard]
  );

  const classReport = evaluation?.classification_report || {};

  const classMetricData = useMemo(
    () =>
      Object.entries(classReport)
        .filter(
          ([key, value]) =>
            key !== "accuracy" &&
            value &&
            typeof value === "object" &&
            typeof value.precision === "number"
        )
        .map(([className, values]) => ({
          className: `Class ${className}`,
          precision: values.precision,
          recall: values.recall,
          f1: values["f1-score"],
        })),
    [classReport]
  );

  /* -----------------------------------------------------
     Loading and error states
  ----------------------------------------------------- */

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
          <AlertTriangle
            size={24}
            className="mx-auto text-red-500 mb-3"
          />

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

  /* -----------------------------------------------------
     Render
  ----------------------------------------------------- */

  return (
    <AppShell>
      <div className="space-y-6">

        {/* Header */}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-ink">
                Model Results
              </h1>

              {run?.status === "completed" && (
                <span className="text-[10px] px-2 py-1 rounded-full bg-green-500/10 text-green-600">
                  Completed
                </span>
              )}
            </div>

            <p className="text-xs text-ink-secondary mt-1">
              Compare models, evaluate performance and inspect generalization.
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
                    : run?.status === "cancelled"
                      ? "This training run was cancelled."
                      : "Your results will appear here when training completes. This page checks automatically."}
                </p>
              </div>
            </div>
          </Card>
        )}

        {run?.status === "completed" && (
          <>

            {/* Model selection summary */}

            <div>
              <div className="flex items-center gap-2 mb-3">
                <Trophy size={17} className="text-orange" />
                <h2 className="text-sm font-semibold text-ink">
                  Model selection summary
                </h2>
              </div>

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                <Card className="p-5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-ink-secondary">
                      AutoML selected model
                    </span>

                    <span className="text-[10px] px-2 py-1 rounded-full bg-green-500/10 text-green-600">
                      Selected
                    </span>
                  </div>

                  <h2 className="text-2xl font-semibold text-ink mt-3">
                    {bestModel}
                  </h2>

                  <p className="text-xs text-ink-secondary mt-1">
                    Selected using {formatLabel(primaryMetric)} cross-validation performance.
                  </p>

                  <div className="mt-5">
                    <p className="text-xs text-ink-secondary">
                      Cross-validation score
                    </p>

                    <p className="text-3xl font-semibold text-orange mt-1">
                      {formatMetric(
                        summary.best_cv_score ??
                          getScore(bestRow, primaryMetric),
                        primaryMetric
                      )}
                    </p>
                  </div>
                </Card>

                <Card className="p-5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-ink-secondary">
                      Highest test performer
                    </span>

                    <span className="text-[10px] px-2 py-1 rounded-full bg-orange/10 text-orange">
                      Held-out test
                    </span>
                  </div>

                  <h2 className="text-2xl font-semibold text-ink mt-3">
                    {bestTestRow?.algorithm || "Unavailable"}
                  </h2>

                  <p className="text-xs text-ink-secondary mt-1">
                    Highest recorded test {formatLabel(primaryMetric)}.
                  </p>

                  <div className="mt-5">
                    <p className="text-xs text-ink-secondary">
                      Test score
                    </p>

                    <p className="text-3xl font-semibold text-orange mt-1">
                      {formatMetric(
                        getScore(bestTestRow, primaryMetric, "test"),
                        primaryMetric
                      )}
                    </p>
                  </div>
                </Card>
              </div>
            </div>

            {/* Overview cards */}

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
              <MetricCard
                label="Models screened"
                value={summary.models_screened ?? "—"}
                icon={BarChart3}
              />

              <MetricCard
                label="Finalists"
                value={summary.models_finalists ?? summary.finalists ?? "—"}
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

            {/* Dataset overview */}

            <Card className="p-5">
              <SectionHeading
                title="Training overview"
                description="Dataset and experiment information."
              />

              <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-5">
                {[
                  ["Task", formatLabel(run.task || summary.task || "—")],
                  ["Primary metric", formatLabel(primaryMetric)],
                  ["Training rows", summary.n_train ?? "—"],
                  ["Test rows", summary.n_test ?? "—"],
                  ["Features", summary.n_features ?? "—"],
                ].map(([label, value]) => (
                  <div key={label}>
                    <p className="text-xs text-ink-secondary">{label}</p>
                    <p className="text-sm font-semibold text-ink mt-1">
                      {value}
                    </p>
                  </div>
                ))}
              </div>
            </Card>

            {/* Performance analytics */}

            <div>
              <SectionHeading
                title="Performance analytics"
                description="Visual comparison of model scores across the evaluation pipeline."
              />

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">

                <ChartCard
                  title="CV vs test performance"
                  description={`Cross-validation and held-out test ${formatLabel(primaryMetric)}.`}
                >
                  {performanceData.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={performanceData}
                        margin={{ top: 10, right: 10, left: -15, bottom: 55 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis
                          dataKey="model"
                          angle={-25}
                          textAnchor="end"
                          interval={0}
                          tick={{ fontSize: 10 }}
                        />
                        <YAxis
                          domain={[0, 1]}
                          tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                          tick={{ fontSize: 10 }}
                        />
                        <Tooltip content={<ChartTooltip />} />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Bar
                          dataKey="cv"
                          name="CV mean"
                          fill="#f97316"
                          radius={[4, 4, 0, 0]}
                        />
                        <Bar
                          dataKey="test"
                          name="Test score"
                          fill="#3b82f6"
                          radius={[4, 4, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart />
                  )}
                </ChartCard>

                <ChartCard
                  title="Cross-validation stability"
                  description="Mean CV score with one standard deviation on either side."
                >
                  {stabilityData.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={stabilityData}
                        margin={{ top: 15, right: 15, left: -15, bottom: 55 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis
                          dataKey="model"
                          angle={-25}
                          textAnchor="end"
                          interval={0}
                          tick={{ fontSize: 10 }}
                        />
                        <YAxis
                          domain={[0, 1]}
                          tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                          tick={{ fontSize: 10 }}
                        />
                        <Tooltip content={<ChartTooltip />} />
                        <Bar
                          dataKey="mean"
                          name="CV mean"
                          fill="#f97316"
                          radius={[4, 4, 0, 0]}
                        >
                          <ErrorBar
                            dataKey="error"
                            width={5}
                            strokeWidth={1.5}
                            stroke="#64748b"
                            direction="y"
                          />
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart />
                  )}
                </ChartCard>

                <ChartCard
                  title="Training time comparison"
                  description="Time taken to train each finalist, in seconds."
                >
                  {timeData.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={timeData}
                        layout="vertical"
                        margin={{ top: 5, right: 25, left: 15, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                        <XAxis type="number" tick={{ fontSize: 10 }} />
                        <YAxis
                          type="category"
                          dataKey="model"
                          width={125}
                          tick={{ fontSize: 10 }}
                        />
                        <Tooltip />
                        <Bar
                          dataKey="training"
                          name="Training time (s)"
                          fill="#8b5cf6"
                          radius={[0, 4, 4, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart />
                  )}
                </ChartCard>

                <ChartCard
                  title="Inference time comparison"
                  description="Recorded inference time per model, in seconds."
                >
                  {timeData.some((item) => item.inference > 0) ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={timeData}
                        layout="vertical"
                        margin={{ top: 5, right: 25, left: 15, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                        <XAxis type="number" tick={{ fontSize: 10 }} />
                        <YAxis
                          type="category"
                          dataKey="model"
                          width={125}
                          tick={{ fontSize: 10 }}
                        />
                        <Tooltip />
                        <Bar
                          dataKey="inference"
                          name="Inference time (s)"
                          fill="#06b6d4"
                          radius={[0, 4, 4, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart message="Inference timing is not available." />
                  )}
                </ChartCard>

                <ChartCard
                  title="ROC-AUC comparison"
                  description="Held-out test ROC-AUC values. This is not an ROC curve."
                >
                  {rocData.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={rocData}
                        margin={{ top: 10, right: 10, left: -15, bottom: 55 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis
                          dataKey="model"
                          angle={-25}
                          textAnchor="end"
                          interval={0}
                          tick={{ fontSize: 10 }}
                        />
                        <YAxis
                          domain={[0, 1]}
                          tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                          tick={{ fontSize: 10 }}
                        />
                        <Tooltip content={<ChartTooltip />} />
                        <Bar
                          dataKey="auc"
                          name="Test ROC-AUC"
                          fill="#14b8a6"
                          radius={[4, 4, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart message="ROC-AUC metrics are unavailable." />
                  )}
                </ChartCard>

                <ChartCard
                  title="Generalization diagnostics"
                  description="Training accuracy compared with cross-validation accuracy."
                >
                  {diagnosticData.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={diagnosticData}
                        margin={{ top: 10, right: 10, left: -15, bottom: 55 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis
                          dataKey="model"
                          angle={-25}
                          textAnchor="end"
                          interval={0}
                          tick={{ fontSize: 10 }}
                        />
                        <YAxis
                          domain={[0, 1]}
                          tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                          tick={{ fontSize: 10 }}
                        />
                        <Tooltip content={<ChartTooltip />} />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Bar
                          dataKey="train"
                          name="Training accuracy"
                          fill="#8b5cf6"
                        />
                        <Bar
                          dataKey="cv"
                          name="CV accuracy"
                          fill="#f97316"
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart message="Training and CV accuracy are unavailable." />
                  )}
                </ChartCard>
              </div>
            </div>

            {/* Classification evaluation */}

            {run.task === "classification" && (
              <div>
                <SectionHeading
                  title="Classification evaluation"
                  description="Detailed test-set classification diagnostics."
                />

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">

                  <ChartCard
                    title="Confusion matrix"
                    description="Actual class versus predicted class for the evaluated model."
                    height={320}
                  >
                    <ConfusionMatrix evaluation={evaluation} />
                  </ChartCard>

                  <ChartCard
                    title="Class-wise performance"
                    description="Precision, recall and F1-score for each class."
                  >
                    {classMetricData.length ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={classMetricData}
                          margin={{ top: 10, right: 10, left: -15, bottom: 5 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" vertical={false} />
                          <XAxis dataKey="className" tick={{ fontSize: 11 }} />
                          <YAxis
                            domain={[0, 1]}
                            tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                            tick={{ fontSize: 10 }}
                          />
                          <Tooltip content={<ChartTooltip />} />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          <Bar dataKey="precision" name="Precision" fill="#3b82f6" />
                          <Bar dataKey="recall" name="Recall" fill="#f97316" />
                          <Bar dataKey="f1" name="F1-score" fill="#14b8a6" />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <EmptyChart message="Classification report artifact is unavailable." />
                    )}
                  </ChartCard>
                </div>

                {evaluation?.classification_report && (
                  <Card className="p-5 mt-4">
                    <SectionHeading
                      title="Classification report"
                      description="Per-class test-set metrics and sample counts."
                    />

                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[550px] text-xs text-left">
                        <thead>
                          <tr className="border-b border-border text-ink-secondary">
                            <th className="py-3 pr-4">Class</th>
                            <th className="py-3 pr-4">Precision</th>
                            <th className="py-3 pr-4">Recall</th>
                            <th className="py-3 pr-4">F1-score</th>
                            <th className="py-3">Support</th>
                          </tr>
                        </thead>

                        <tbody>
                          {Object.entries(evaluation.classification_report)
                            .filter(
                              ([key, value]) =>
                                key !== "accuracy" &&
                                value &&
                                typeof value === "object"
                            )
                            .map(([key, value]) => (
                              <tr
                                key={key}
                                className="border-b border-border last:border-0"
                              >
                                <td className="py-3 pr-4 font-medium text-ink">
                                  {formatLabel(key)}
                                </td>
                                <td className="py-3 pr-4 text-ink">
                                  {formatMetric(value.precision, "precision")}
                                </td>
                                <td className="py-3 pr-4 text-ink">
                                  {formatMetric(value.recall, "recall")}
                                </td>
                                <td className="py-3 pr-4 text-ink">
                                  {formatMetric(value["f1-score"], "f1")}
                                </td>
                                <td className="py-3 text-ink">
                                  {value.support ?? "—"}
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                )}
              </div>
            )}

            {/* Model leaderboard */}

            <Card className="p-5">
              <SectionHeading
                title="Model leaderboard"
                description="Models ranked by the AutoML selection process."
                action={
                  <span className="text-xs text-ink-secondary">
                    {leaderboard.length} models
                  </span>
                }
              />

              {leaderboard.length > 0 && (
                <div className="flex flex-col sm:flex-row gap-3 mb-4">
                  <div className="relative flex-1">
                    <Search
                      size={14}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-secondary"
                    />

                    <input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Search models..."
                      className="w-full pl-9 pr-3 py-2 rounded-lg border border-border bg-transparent text-xs text-ink outline-none focus:border-orange"
                    />
                  </div>

                  <select
                    value={sortBy}
                    onChange={(event) => setSortBy(event.target.value)}
                    className="px-3 py-2 rounded-lg border border-border bg-surface text-xs text-ink outline-none"
                  >
                    <option value="rank">Original ranking</option>
                    <option value="cv">CV score: highest first</option>
                    <option value="test">Test score: highest first</option>
                    <option value="time">Training time: fastest first</option>
                  </select>
                </div>
              )}

              {leaderboard.length === 0 ? (
                <p className="text-xs text-ink-secondary py-6 text-center">
                  No leaderboard data is available.
                </p>
              ) : filteredLeaderboard.length === 0 ? (
                <p className="text-xs text-ink-secondary py-6 text-center">
                  No models match your search.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs min-w-[850px]">
                    <thead>
                      <tr className="border-b border-border text-ink-secondary">
                        <th className="py-3 pr-4">Rank</th>
                        <th className="py-3 pr-4">Model</th>
                        <th className="py-3 pr-4">Family</th>
                        <th className="py-3 pr-4">CV {formatLabel(primaryMetric)}</th>
                        <th className="py-3 pr-4">Test score</th>
                        <th className="py-3 pr-4">Overfit gap</th>
                        <th className="py-3 pr-4">Training time</th>
                        <th className="py-3">Status</th>
                      </tr>
                    </thead>

                    <tbody>
                      {filteredLeaderboard.map((row, index) => {
                        const cvScore = getScore(row, primaryMetric);
                        const cvStd = row[`cv_${primaryMetric}_std`];
                        const testScore = getScore(
                          row,
                          primaryMetric,
                          "test"
                        );

                        const isSelected = row.algorithm === bestModel;
                        const isBestTest =
                          row.algorithm === bestTestRow?.algorithm;

                        return (
                          <tr
                            key={row.algorithm || index}
                            className={`border-b border-border last:border-0 ${
                              isSelected ? "bg-orange/[0.04]" : ""
                            }`}
                          >
                            <td className="py-3 pr-4 font-medium text-ink">
                              #{row.rank ?? index + 1}
                            </td>

                            <td className="py-3 pr-4">
                              <div className="font-medium text-ink">
                                {row.algorithm || "Unknown"}
                              </div>

                              <div className="flex flex-wrap gap-1 mt-1">
                                {isSelected && (
                                  <span className="text-[9px] text-green-600">
                                    Selected model
                                  </span>
                                )}

                                {isBestTest && (
                                  <span className="text-[9px] text-orange">
                                    Best test score
                                  </span>
                                )}

                                {row.tuned && (
                                  <span className="text-[9px] text-ink-secondary">
                                    Tuned
                                  </span>
                                )}
                              </div>
                            </td>

                            <td className="py-3 pr-4 text-ink-secondary">
                              {formatLabel(row.family || "—")}
                            </td>

                            <td className="py-3 pr-4 text-ink">
                              {formatMetric(cvScore, primaryMetric)}
                              <span className="block text-[10px] text-ink-secondary mt-1">
                                ± {formatMetric(cvStd, primaryMetric)}
                              </span>
                            </td>

                            <td className="py-3 pr-4 text-ink">
                              {formatMetric(testScore, primaryMetric)}
                            </td>

                            <td className="py-3 pr-4 text-ink">
                              {formatGap(row.overfit_gap)}
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

            {/* Selected model test evaluation */}

            <Card className="p-5">
              <SectionHeading
                title="Selected model test evaluation"
                description={`Held-out test metrics for ${bestRow?.algorithm || bestModel}.`}
              />

              {bestRow?.test ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
                  {Object.entries(bestRow.test).map(([metric, value]) => (
                    <div
                      key={metric}
                      className="rounded-lg border border-border p-3"
                    >
                      <p className="text-xs text-ink-secondary">
                        {formatLabel(metric)}
                      </p>

                      <p className="text-lg font-semibold text-ink mt-2">
                        {formatMetric(value, metric)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-ink-secondary">
                  Evaluation metrics are not available for this model.
                </p>
              )}
            </Card>

            {/* Diagnostics */}

            <Card className="p-5">
              <SectionHeading
                title="Training diagnostics"
                description="Warnings and observations reported by the training pipeline."
              />

              {warnings.length > 0 ? (
                <div className="space-y-3">
                  {warnings.map((warning, index) => (
                    <div
                      key={index}
                      className="flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3"
                    >
                      <AlertTriangle
                        size={16}
                        className="text-amber-500 mt-0.5 shrink-0"
                      />

                      <p className="text-xs text-ink-secondary leading-relaxed">
                        {warning}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-xs text-ink-secondary">
                  <CheckCircle2 size={16} className="text-green-600" />
                  No training warnings were reported.
                </div>
              )}

              {diagnosticData.length > 0 && (
                <div className="mt-4 rounded-lg bg-surface-secondary p-3">
                  <p className="text-xs font-semibold text-ink">
                    Generalization observations
                  </p>

                  <div className="mt-3 space-y-2">
                    {diagnosticData.map((item) => (
                      <div
                        key={item.model}
                        className="flex flex-wrap justify-between gap-2 text-xs"
                      >
                        <span className="text-ink-secondary">
                          {item.model}
                        </span>

                        <span
                          className={
                            item.warning
                              ? "text-amber-600 font-medium"
                              : "text-ink"
                          }
                        >
                          Gap: {formatGap(item.gap)}
                          {item.warning ? " · Warning" : ""}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {bestRow && bestTestRow && (
                <div className="mt-4 p-3 rounded-lg bg-surface-secondary">
                  <p className="text-xs font-semibold text-ink">
                    How to interpret these results
                  </p>

                  <p className="text-xs text-ink-secondary mt-2 leading-relaxed">
                    The selected model is chosen using cross-validation
                    performance. The highest test-scoring model is shown
                    separately. A higher test score does not automatically
                    make a model the AutoML selection winner. CV standard
                    deviations describe fold-to-fold variation; they are not
                    confidence intervals.
                  </p>
                </div>
              )}
            </Card>

            {/* Artifacts */}

            <Card className="p-5">
              <SectionHeading
                title="Training artifacts"
                description="Files generated during this training run."
                action={
                  <span className="text-xs text-ink-secondary">
                    {artifacts.length} files
                  </span>
                }
              />

              {artifacts.length === 0 ? (
                <p className="text-xs text-ink-secondary">
                  No artifacts are available.
                </p>
              ) : (
                <div className="space-y-5">
                  {Object.entries(artifactGroups).map(([group, files]) => (
                    <div key={group}>
                      <h3 className="text-xs font-semibold text-ink mb-2">
                        {group}
                      </h3>

                      <div className="space-y-2">
                        {files.map((artifact) => {
                          const Icon = getArtifactIcon(artifact);

                          return (
                            <div
                              key={artifact}
                              className="flex flex-wrap items-center justify-between gap-3 border border-border rounded-lg p-3"
                            >
                              <div className="flex items-center gap-3 min-w-0">
                                <div className="p-2 rounded-lg bg-surface-secondary">
                                  <Icon
                                    size={17}
                                    className="text-ink-secondary"
                                  />
                                </div>

                                <div className="min-w-0">
                                  <p className="text-xs font-medium text-ink break-all">
                                    {artifact.split("/").pop()}
                                  </p>

                                  <p className="text-[10px] text-ink-secondary mt-1 break-all">
                                    {artifact}
                                  </p>
                                </div>
                              </div>

                              <button
                                onClick={() => handleDownload(artifact)}
                                disabled={downloading === artifact}
                                className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-xs text-ink hover:bg-surface-secondary disabled:opacity-50 shrink-0"
                              >
                                {downloading === artifact ? (
                                  <RefreshCw
                                    size={14}
                                    className="animate-spin"
                                  />
                                ) : (
                                  <Download size={14} />
                                )}

                                {downloading === artifact
                                  ? "Downloading..."
                                  : "Download"}
                              </button>
                            </div>
                          );
                        })}
                      </div>
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
