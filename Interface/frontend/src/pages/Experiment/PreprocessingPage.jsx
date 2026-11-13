
import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ROUTES } from "../../constants/routes";
import {
  Workflow,
  Play,
  RefreshCw,
  Download,
  CheckCircle2,
  AlertCircle,
  Database,
  LoaderCircle,
  ArrowRight,
  AlertTriangle,
  Settings2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import Card from "../../components/common/Card";
import Button from "../../components/common/Button";

import { getDatasets, getDataset } from "../../services/datasets";
import request, { BASE_URL } from "../../services/api";

import {
  preprocessDataset,
  getPreprocessingRuns,
  downloadPreprocessedCSV,
} from "../../services/preprocessing";

import {
  startTraining,
  getTrainingRun,
} from "../../services/training";

const TRAINING_TERMINAL_STATUSES = [
  "completed",
  "failed",
  "cancelled",
];

const DEFAULT_TRAINING_CONFIG = {
  task: "auto",
  primary_metric: null,
  cv_splits: 5,
  cv_repeats: 1,
  random_state: 42,
  n_jobs: -1,
  max_candidates: 10,
  exclude: [],
  include_only: [],
  screening_max_rows: 5000,
  screening_folds: 3,
  keep_fraction: 0.5,
  keep_min: 3,
  time_budget_s: null,
  tune: false,
  tune_top_n: 3,
  tune_iterations: 30,
  ensemble: true,
  ensemble_top_k: 3,
  ensemble_min_gain: 0.005,
  refit_on_all: false,
  overfit_gap_warn: 0.10,
};

const MODEL_OPTIONS = [
  "RandomForest",
  "GradientBoosting",
  "HistGradientBoosting",
  "LogisticRegression",
  "ExtraTrees",
  "DecisionTree",
  "GaussianNB",
  "SVC",
  "AdaBoost",
  "KNN",
];

function DonutChart({
  segments,
  total,
  centerLabel = "Total",
  centerValue,
}) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  const colors = [
    "#ff6534",
    "#cbd5e1",
    "#16a34a",
    "#8b5cf6",
    "#0ea5e9",
  ];

  return (
    <div className="flex flex-wrap items-center gap-5">
      <div className="relative h-36 w-36 shrink-0">
        <svg
          viewBox="0 0 100 100"
          className="h-full w-full -rotate-90"
          role="img"
          aria-label={`${centerLabel}: ${centerValue ?? total}`}
        >
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="#f1f5f9"
            strokeWidth="13"
          />

          {segments
            .filter((segment) => segment.value > 0)
            .map((segment, index) => {
              const length =
                (segment.value / Math.max(total, 1)) *
                circumference;

              const circle = (
                <circle
                  key={segment.label}
                  cx="50"
                  cy="50"
                  r={radius}
                  fill="none"
                  stroke={
                    segment.color ||
                    colors[index % colors.length]
                  }
                  strokeWidth="13"
                  strokeDasharray={`${length} ${circumference - length}`}
                  strokeDashoffset={-offset}
                />
              );

              offset += length;
              return circle;
            })}
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-xs text-ink-muted">
            {centerLabel}
          </span>
          <span className="text-xl font-semibold text-ink">
            {centerValue ?? total}
          </span>
        </div>
      </div>

      <div className="min-w-[150px] flex-1 space-y-3">
        {segments.map((segment, index) => (
          <div
            key={segment.label}
            className="flex items-center justify-between gap-4 text-sm"
          >
            <span className="flex items-center gap-2 text-ink-secondary">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{
                  backgroundColor:
                    segment.color ||
                    colors[index % colors.length],
                }}
              />
              {segment.label}
            </span>

            <span className="font-medium text-ink">
              {segment.value}{" "}
              <span className="text-ink-muted">
                (
                {total
                  ? Math.round((segment.value / total) * 100)
                  : 0}
                %)
              </span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  help,
}) {
  return (
    <label className="space-y-2 text-sm">
      <span className="font-medium text-ink">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => {
          const next = event.target.value;
          onChange(next === "" ? "" : Number(next));
        }}
        className="w-full rounded-lg border border-surface-border bg-white p-3 text-ink outline-none focus:border-orange"
      />
      {help && (
        <span className="block text-xs text-ink-muted">
          {help}
        </span>
      )}
    </label>
  );
}

export default function PreprocessingPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const initialDatasetId = location.state?.datasetId || "";

  const [datasets, setDatasets] = useState([]);
  const [datasetId, setDatasetId] = useState(initialDatasetId);
  const [profile, setProfile] = useState(null);
  const [target, setTarget] = useState("");
  const [testSize, setTestSize] = useState("0.2");
  const [runs, setRuns] = useState([]);
  const [result, setResult] = useState(null);

  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [logSearch, setLogSearch] = useState("");
  const [logFilter, setLogFilter] = useState("All");
  const [expandedLogs, setExpandedLogs] = useState({});

  const [reports, setReports] = useState({});
  const [activeReport, setActiveReport] = useState(
    "preprocessing_summary.json"
  );
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsError, setReportsError] = useState("");
  const [insightTab, setInsightTab] = useState("overview");

  // AutoML configuration
  const [trainingConfig, setTrainingConfig] = useState({
    ...DEFAULT_TRAINING_CONFIG,
  });

  const [advancedSettingsOpen, setAdvancedSettingsOpen] =
    useState(false);

  const [startingTraining, setStartingTraining] = useState(false);
  const [trainingRunId, setTrainingRunId] = useState("");
  const [trainingStatus, setTrainingStatus] = useState("");
  const [trainingError, setTrainingError] = useState("");

  const columns = Object.keys(profile?.columns ?? {});

  const preprocessingLogs = Array.isArray(
    result?.preprocessing_log
  )
    ? result.preprocessing_log
    : [];

  const visiblePreprocessingLogs = preprocessingLogs.filter(
    (item) => {
      const log =
        item && typeof item === "object"
          ? item
          : { message: item };

      const action = String(log.action ?? "").toLowerCase();

      const text = [
        log.column,
        log.stage,
        log.action,
        log.reason,
        log.rule_id,
        log.source,
        log.message,
        typeof item === "string" ? item : "",
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      let category = "Other";

      if (action.includes("drop")) {
        category = "Dropped";
      } else if (action.includes("imput")) {
        category = "Missing values";
      } else if (action.includes("encod")) {
        category = "Encoding";
      } else if (action.includes("scal")) {
        category = "Scaling";
      } else if (
        action === "skipped" ||
        log.source === "system"
      ) {
        category = "System";
      }

      return (
        (logFilter === "All" || category === logFilter) &&
        text.includes(logSearch.trim().toLowerCase())
      );
    }
  );

  const logSummary = {
    columns: new Set(
      preprocessingLogs
        .filter((item) => item && typeof item === "object")
        .map((item) => item.column)
        .filter(Boolean)
    ).size,

    dropped: preprocessingLogs.filter(
      (item) =>
        item &&
        typeof item === "object" &&
        String(item.action ?? "").toLowerCase().includes("drop")
    ).length,

    imputed: preprocessingLogs.filter(
      (item) =>
        item &&
        typeof item === "object" &&
        String(item.action ?? "").toLowerCase().includes("imput")
    ).length,

    encoded: preprocessingLogs.filter(
      (item) =>
        item &&
        typeof item === "object" &&
        String(item.action ?? "").toLowerCase().includes("encod")
    ).length,

    scaled: preprocessingLogs.filter(
      (item) =>
        item &&
        typeof item === "object" &&
        String(item.action ?? "").toLowerCase().includes("scal")
    ).length,
  };

  const updateTrainingConfig = (key, value) => {
    setTrainingConfig((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const toggleModel = (key, model) => {
    setTrainingConfig((current) => ({
      ...current,
      [key]: current[key].includes(model)
        ? current[key].filter((item) => item !== model)
        : [...current[key], model],
    }));
  };

  const loadRuns = useCallback(async (id) => {
    if (!id) {
      setRuns([]);
      return;
    }

    const data = await getPreprocessingRuns(id);
    setRuns(data);
  }, []);

  const loadDataset = useCallback(
    async (id) => {
      setProfile(null);
      setResult(null);
      setReports({});
      setReportsError("");
      setTarget("");
      setError("");
      setNotice("");

      setTrainingRunId("");
      setTrainingStatus("");
      setTrainingError("");
      setTrainingConfig({ ...DEFAULT_TRAINING_CONFIG });

      if (!id) {
        setRuns([]);
        return;
      }

      try {
        const [response] = await Promise.all([
          getDataset(id),
          loadRuns(id),
        ]);

        const dataset =
          response?.dataset ??
          response?.data?.dataset ??
          response?.data ??
          response;

        const nextProfile = dataset?.profile ?? null;
        setProfile(nextProfile);

        const availableColumns = Object.keys(
          nextProfile?.columns ?? {}
        );

        const savedTarget = dataset?.target_column;

        setTarget(
          savedTarget && availableColumns.includes(savedTarget)
            ? savedTarget
            : nextProfile?.target?.name &&
                availableColumns.includes(nextProfile.target.name)
              ? nextProfile.target.name
              : ""
        );
      } catch (err) {
        setError(err.message || "Could not load this dataset.");
      }
    },
    [loadRuns]
  );

  useEffect(() => {
    let active = true;

    async function initialise() {
      setLoading(true);

      try {
        const data = await getDatasets();

        if (!active) return;

        setDatasets(data);

        const selected =
          initialDatasetId &&
          data.some((item) => item.id === initialDatasetId)
            ? initialDatasetId
            : data[0]?.id || "";

        setDatasetId(selected);

        if (selected) {
          await loadDataset(selected);
        }
      } catch (err) {
        if (active) {
          setError(err.message || "Could not load datasets.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    initialise();

    return () => {
      active = false;
    };
  }, [initialDatasetId, loadDataset]);

  async function handleDatasetChange(id) {
    setDatasetId(id);
    await loadDataset(id);
  }

  async function loadReports(runId) {
    if (!runId) {
      setReports({});
      return;
    }

    setReportsLoading(true);
    setReportsError("");

    try {
      const data = await request(
        `/preprocessing/runs/${encodeURIComponent(runId)}/reports`
      );

      setReports(data?.reports ?? {});

      const names = Object.keys(data?.reports ?? {});

      if (names.length && !names.includes(activeReport)) {
        setActiveReport(names[0]);
      }
    } catch (err) {
      setReports({});
      setReportsError(
        err.message ||
          "Could not load JSON reports for this run."
      );
    } finally {
      setReportsLoading(false);
    }
  }

  async function handleDownloadReport(filename) {
    if (!result?.run_id || !filename) return;

    setError("");

    try {
      const response = await fetch(
        `${BASE_URL}/preprocessing/runs/${encodeURIComponent(result.run_id)}/reports/${encodeURIComponent(filename)}`,
        { credentials: "include" }
      );

      if (!response.ok) {
        let message = `Download failed (${response.status})`;

        try {
          const data = await response.json();
          if (typeof data.detail === "string") {
            message = data.detail;
          }
        } catch {
          // Keep HTTP status message.
        }

        throw new Error(message);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();

      URL.revokeObjectURL(url);
    } catch (err) {
      setError(
        err.message || "Could not download the JSON report."
      );
    }
  }

  async function handlePreprocess() {
    if (!datasetId) {
      setError("Choose a dataset first.");
      return;
    }

    if (!target) {
      setError("Choose a target column first.");
      return;
    }

    setRunning(true);
    setError("");
    setNotice("");
    setResult(null);
    setReports({});

    setTrainingRunId("");
    setTrainingStatus("");
    setTrainingError("");

    try {
      const response = await preprocessDataset(datasetId, {
        target_column: target,
        test_size: Number(testSize),
      });

      setResult(response);

      await Promise.all([
        loadReports(response.run_id),
        loadRuns(datasetId),
      ]);

      setNotice(
        "Preprocessing completed. Your CSV artifacts are ready."
      );
    } catch (err) {
      setError(err.message || "Preprocessing failed.");
    } finally {
      setRunning(false);
    }
  }

  async function handleDownload(runId, split) {
    setError("");

    try {
      await downloadPreprocessedCSV(runId, split);
    } catch (err) {
      setError(err.message || "Could not download the CSV.");
    }
  }

  // Start AutoML using the existing backend TrainingConfig.
  async function handleStartTraining() {
    const preprocessingRunId =
      result?.run_id ?? result?.preprocessing_run_id;

    if (!datasetId || !preprocessingRunId) {
      setError(
        "A completed preprocessing run is required before training."
      );
      return;
    }

    if (
      startingTraining ||
      (trainingRunId &&
        !["failed", "cancelled"].includes(trainingStatus))
    ) {
      return;
    }

    setError("");
    setTrainingError("");
    setTrainingStatus("submitting");
    setStartingTraining(true);

    try {
      const config = {
        ...trainingConfig,
        primary_metric: trainingConfig.primary_metric || null,
        time_budget_s:
          trainingConfig.time_budget_s === "" ||
          trainingConfig.time_budget_s === null
            ? null
            : Number(trainingConfig.time_budget_s),
      };

      const response = await startTraining(
        preprocessingRunId,
        config
      );

      const id =
        response?.training_run_id ??
        response?.run_id ??
        response?.id;

      if (!id) {
        throw new Error(
          "The backend did not return a training run ID."
        );
      }

      setTrainingRunId(id);

      window.sessionStorage.setItem(
        "autoexplainai:lastTrainingRunId",
        id
      );

      setTrainingStatus(
        String(response?.status ?? "pending").toLowerCase()
      );
    } catch (err) {
      setTrainingStatus("failed");
      setTrainingError(
        err.message || "Could not start AutoML training."
      );
    } finally {
      setStartingTraining(false);
    }
  }

  // Poll backend training status.
  useEffect(() => {
    if (!trainingRunId) return undefined;

    let cancelled = false;
    let timeoutId;

    async function pollTraining() {
      try {
        const response = await getTrainingRun(trainingRunId);

        if (cancelled) return;

        const status = String(
          response?.status ?? "running"
        ).toLowerCase();

        setTrainingStatus(status);

        if (TRAINING_TERMINAL_STATUSES.includes(status)) {
          setTrainingError(
            status === "failed"
              ? response?.error || "Training failed."
              : ""
          );
          return;
        }

        setTrainingError("");
      } catch (err) {
        if (!cancelled) {
          setTrainingError(
            err.message ||
              "Could not retrieve training status."
          );
        }
      }

      if (!cancelled) {
        timeoutId = window.setTimeout(pollTraining, 2500);
      }
    }

    pollTraining();

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [trainingRunId]);

  function handleContinueToComparison() {
    const preprocessingRunId =
      result?.run_id ?? result?.preprocessing_run_id;

    if (!datasetId || !preprocessingRunId || !trainingRunId) {
      setError(
        "A completed training run is required before opening model comparison."
      );
      return;
    }

    navigate(ROUTES.COMPARISON, {
      state: {
        datasetId,
        preprocessingRunId,
        trainingRunId,
      },
    });
  }

  const activeDataset = datasets.find(
    (item) => item.id === datasetId
  );

  const trainingIsActive = [
    "submitting",
    "pending",
    "queued",
    "running",
    "in_progress",
  ].includes(trainingStatus);

  const metricOptions =
    trainingConfig.task === "classification"
      ? [
          ["accuracy", "Accuracy"],
          ["f1", "F1"],
          ["roc_auc", "ROC-AUC"],
          ["precision", "Precision"],
          ["recall", "Recall"],
        ]
      : trainingConfig.task === "regression"
        ? [
            ["r2", "R²"],
            ["neg_mean_squared_error", "Mean squared error"],
            ["neg_mean_absolute_error", "Mean absolute error"],
          ]
        : [];

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-6xl space-y-6 p-5 md:p-8">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm text-orange">
            <Workflow size={17} />
            Data pipeline
          </div>

          <h1 className="text-2xl font-semibold text-ink">
            Preprocessing workspace
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-secondary">
            Prepare your dataset, select a target, review feature
            selection, and download the processed training and
            testing data.
          </p>
        </div>

        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <AlertCircle size={18} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {notice && (
          <div className="flex items-start gap-2 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">
            <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
            <span>{notice}</span>
          </div>
        )}

        <Card>
          <div className="space-y-5 p-5">
            <div className="flex items-center gap-2">
              <Database size={18} className="text-orange" />
              <h2 className="font-semibold text-ink">
                Configure preprocessing
              </h2>
            </div>

            {loading ? (
              <p className="flex items-center gap-2 text-sm text-ink-secondary">
                <LoaderCircle size={16} className="animate-spin" />
                Loading datasets...
              </p>
            ) : datasets.length === 0 ? (
              <p className="text-sm text-ink-secondary">
                No datasets found. Upload a dataset before continuing.
              </p>
            ) : (
              <div className="grid gap-5 md:grid-cols-3">
                <label className="space-y-2 text-sm">
                  <span className="font-medium text-ink">Dataset</span>
                  <select
                    value={datasetId}
                    onChange={(event) =>
                      handleDatasetChange(event.target.value)
                    }
                    className="w-full rounded-lg border border-surface-border bg-white p-3 text-ink outline-none focus:border-orange"
                  >
                    {datasets.map((dataset) => (
                      <option key={dataset.id} value={dataset.id}>
                        {dataset.filename || dataset.name || dataset.id}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-2 text-sm">
                  <span className="font-medium text-ink">
                    Target column
                  </span>
                  <select
                    value={target}
                    onChange={(event) => setTarget(event.target.value)}
                    className="w-full rounded-lg border border-surface-border bg-white p-3 text-ink outline-none focus:border-orange"
                  >
                    <option value="">Select target</option>
                    {columns.map((column) => (
                      <option key={column} value={column}>
                        {column}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-2 text-sm">
                  <span className="font-medium text-ink">Test split</span>
                  <select
                    value={testSize}
                    onChange={(event) => setTestSize(event.target.value)}
                    className="w-full rounded-lg border border-surface-border bg-white p-3 text-ink outline-none focus:border-orange"
                  >
                    <option value="0.1">10% test / 90% train</option>
                    <option value="0.2">20% test / 80% train</option>
                    <option value="0.25">25% test / 75% train</option>
                    <option value="0.3">30% test / 70% train</option>
                    <option value="0.4">40% test / 60% train</option>
                  </select>
                </label>
              </div>
            )}

            {activeDataset && profile && (
              <p className="text-xs text-ink-muted">
                {activeDataset.n_rows ?? "—"} rows · {columns.length} columns
              </p>
            )}

            <div className="flex flex-wrap gap-3">
              <Button
                onClick={handlePreprocess}
                disabled={loading || running || !datasetId || !target}
              >
                {running ? (
                  <LoaderCircle size={16} className="mr-2 animate-spin" />
                ) : (
                  <Play size={16} className="mr-2" />
                )}
                {running ? "Preprocessing..." : "Run preprocessing"}
              </Button>

              <Button
                variant="secondary"
                onClick={() => loadDataset(datasetId)}
                disabled={loading || running || !datasetId}
              >
                <RefreshCw size={16} className="mr-2" />
                Refresh dataset
              </Button>
            </div>
          </div>
        </Card>

        {result && (
          <section className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold text-ink">
                Latest preprocessing results
              </h2>
              <p className="mt-1 text-sm text-ink-secondary">
                Run ID: {result.run_id}
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Training rows", result.train_rows],
                ["Testing rows", result.test_rows],
                ["Selected features", result.feature_count],
                ["Removed missing targets", result.rows_removed_missing_target],
              ].map(([label, value]) => (
                <Card key={label}>
                  <div className="p-5">
                    <p className="text-sm text-ink-secondary">{label}</p>
                    <p className="mt-2 text-2xl font-semibold text-ink">
                      {value ?? "—"}
                    </p>
                  </div>
                </Card>
              ))}
            </div>

            <Card>
              <div className="space-y-5 p-5">
                <div>
                  <h3 className="text-lg font-semibold text-ink">
                    Preprocessing insights
                  </h3>
                  <p className="mt-1 text-sm text-ink-secondary">
                    A visual explanation of the transformations and outputs for this run.
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  {[
                    ["overview", "Overview"],
                    ["features", "Features"],
                    ["pipeline", "Pipeline"],
                  ].map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setInsightTab(key)}
                      className={`rounded-lg border px-4 py-2 text-sm font-medium transition ${
                        insightTab === key
                          ? "border-orange bg-orange-50 text-orange"
                          : "border-surface-border bg-white text-ink-secondary hover:bg-surface-page"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {insightTab === "overview" && (
                  <div className="space-y-5">
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="rounded-xl border border-surface-border p-4">
                        <p className="text-sm text-ink-secondary">Input dataset</p>
                        <p className="mt-2 text-2xl font-semibold text-ink">
                          {profile?.row_count ?? profile?.rows ?? "—"}
                        </p>
                        <p className="text-xs text-ink-muted">
                          Rows reported by the dataset profile
                        </p>
                      </div>

                      <div className="rounded-xl border border-surface-border p-4">
                        <p className="text-sm text-ink-secondary">Output features</p>
                        <p className="mt-2 text-2xl font-semibold text-ink">
                          {result.feature_count ??
                            result.selected_features?.length ??
                            0}
                        </p>
                        <p className="text-xs text-ink-muted">
                          Features available for model training
                        </p>
                      </div>

                      <div className="rounded-xl border border-surface-border p-4">
                        <p className="text-sm text-ink-secondary">
                          Logged transformations
                        </p>
                        <p className="mt-2 text-2xl font-semibold text-ink">
                          {preprocessingLogs.length}
                        </p>
                        <p className="text-xs text-ink-muted">
                          Recorded preprocessing events
                        </p>
                      </div>
                    </div>

                    <div className="grid gap-5 lg:grid-cols-2">
                      <div className="rounded-xl border border-surface-border p-4">
                        <h4 className="mb-4 font-medium text-ink">
                          Train/test split
                        </h4>
                        <DonutChart
                          segments={[
                            {
                              label: "Training",
                              value: Number(result.train_rows || 0),
                              color: "#ff6534",
                            },
                            {
                              label: "Testing",
                              value: Number(result.test_rows || 0),
                              color: "#cbd5e1",
                            },
                          ]}
                          total={
                            Number(result.train_rows || 0) +
                            Number(result.test_rows || 0)
                          }
                          centerLabel="Total rows"
                        />
                      </div>

                      <div className="rounded-xl border border-surface-border p-4">
                        <h4 className="mb-4 font-medium text-ink">
                          Transformation activity
                        </h4>
                        <DonutChart
                          segments={[
                            {
                              label: "Dropped",
                              value: logSummary.dropped,
                              color: "#ff6534",
                            },
                            {
                              label: "Imputed",
                              value: logSummary.imputed,
                              color: "#0ea5e9",
                            },
                            {
                              label: "Encoded",
                              value: logSummary.encoded,
                              color: "#16a34a",
                            },
                            {
                              label: "Scaled",
                              value: logSummary.scaled,
                              color: "#8b5cf6",
                            },
                          ]}
                          total={
                            logSummary.dropped +
                            logSummary.imputed +
                            logSummary.encoded +
                            logSummary.scaled
                          }
                          centerLabel="Actions"
                        />
                        <p className="mt-3 text-xs text-ink-muted">
                          Counts reflect logged actions; one column may have multiple events.
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {insightTab === "features" && (
                  <div className="space-y-3">
                    <p className="text-sm text-ink-secondary">
                      These are the features returned by the preprocessing run.
                    </p>

                    {result.selected_features?.length ? (
                      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                        {result.selected_features.map((feature) => (
                          <div
                            key={feature}
                            className="flex items-center gap-2 rounded-lg border border-surface-border bg-surface-page px-3 py-2 text-sm text-ink"
                          >
                            <CheckCircle2
                              size={15}
                              className="shrink-0 text-emerald-600"
                            />
                            <span className="break-all">{feature}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-ink-secondary">
                        No selected features were returned for this run.
                      </p>
                    )}
                  </div>
                )}

                {insightTab === "pipeline" && (
                  <div className="space-y-3">
                    {[
                      ["1", "Inspect dataset", "Review the input columns and selected target."],
                      ["2", "Handle missing values", `${logSummary.imputed} imputation actions recorded.`],
                      ["3", "Transform features", `${logSummary.encoded} encoding and ${logSummary.scaled} scaling actions recorded.`],
                      ["4", "Prepare model splits", `${result.train_rows ?? 0} training rows and ${result.test_rows ?? 0} testing rows created.`],
                    ].map(([step, title, description]) => (
                      <div
                        key={step}
                        className="flex gap-3 rounded-xl border border-surface-border p-4"
                      >
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-orange-50 text-sm font-semibold text-orange">
                          {step}
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-ink">{title}</p>
                          <p className="mt-1 text-sm text-ink-secondary">
                            {description}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>

            {/* Selected features and AutoML */}
            <Card>
              <div className="space-y-5 p-5">
                <div>
                  <h3 className="font-semibold text-ink">
                    Selected features
                  </h3>

                  {result.selected_features?.length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {result.selected_features.map((feature) => (
                        <span
                          key={feature}
                          className="rounded-full bg-orange-50 px-3 py-1 text-sm text-orange"
                        >
                          {feature}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-ink-secondary">
                      No selected features were returned.
                    </p>
                  )}
                </div>

                <div className="flex flex-wrap gap-3">
                  <Button
                    onClick={() => handleDownload(result.run_id, "train")}
                  >
                    <Download size={16} className="mr-2" />
                    Download training CSV
                  </Button>

                  <Button
                    variant="secondary"
                    onClick={() => handleDownload(result.run_id, "test")}
                  >
                    <Download size={16} className="mr-2" />
                    Download testing CSV
                  </Button>
                </div>

                <div className="border-t border-surface-border pt-5">
                  <div className="mb-5">
                    <div className="flex items-center gap-2">
                      <Workflow size={19} className="text-orange" />
                      <h3 className="font-semibold text-ink">
                        AutoML configuration
                      </h3>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-ink-secondary">
                      Configure how AutoExplainAI evaluates candidate models,
                      tunes hyperparameters, and selects an appropriate model.
                    </p>
                  </div>

                  {/* Basic settings */}
                  <div className="space-y-5">
                    <div className="grid gap-5 md:grid-cols-2">
                      <label className="space-y-2 text-sm">
                        <span className="font-medium text-ink">
                          Learning objective
                        </span>
                        <select
                          value={trainingConfig.task}
                          onChange={(event) => {
                            const task = event.target.value;
                            updateTrainingConfig("task", task);
                            updateTrainingConfig("primary_metric", null);
                          }}
                          disabled={startingTraining || Boolean(trainingRunId)}
                          className="w-full rounded-lg border border-surface-border bg-white p-3 text-ink outline-none focus:border-orange disabled:opacity-50"
                        >
                          <option value="auto">Auto-detect</option>
                          <option value="classification">Classification</option>
                          <option value="regression">Regression</option>
                        </select>
                        <span className="block text-xs text-ink-muted">
                          Automatically infer the task from the target column or select it manually.
                        </span>
                      </label>

                      <label className="space-y-2 text-sm">
                        <span className="font-medium text-ink">
                          Primary evaluation metric
                        </span>
                        <select
                          value={trainingConfig.primary_metric ?? ""}
                          onChange={(event) =>
                            updateTrainingConfig(
                              "primary_metric",
                              event.target.value || null
                            )
                          }
                          disabled={
                            startingTraining ||
                            Boolean(trainingRunId) ||
                            trainingConfig.task === "auto"
                          }
                          className="w-full rounded-lg border border-surface-border bg-white p-3 text-ink outline-none focus:border-orange disabled:opacity-50"
                        >
                          <option value="">Automatic selection</option>
                          {metricOptions.map(([value, label]) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                        <span className="block text-xs text-ink-muted">
                          Metric options depend on the selected learning objective.
                        </span>
                      </label>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <label className="flex items-start gap-3 rounded-xl border border-surface-border p-4">
                        <input
                          type="checkbox"
                          checked={trainingConfig.tune}
                          onChange={(event) =>
                            updateTrainingConfig("tune", event.target.checked)
                          }
                          disabled={startingTraining || Boolean(trainingRunId)}
                          className="mt-1 accent-orange"
                        />
                        <span>
                          <span className="block text-sm font-medium text-ink">
                            Hyperparameter tuning
                          </span>
                          <span className="mt-1 block text-xs text-ink-muted">
                            Search for better model configurations.
                          </span>
                        </span>
                      </label>

                      <label className="flex items-start gap-3 rounded-xl border border-surface-border p-4">
                        <input
                          type="checkbox"
                          checked={trainingConfig.ensemble}
                          onChange={(event) =>
                            updateTrainingConfig("ensemble", event.target.checked)
                          }
                          disabled={startingTraining || Boolean(trainingRunId)}
                          className="mt-1 accent-orange"
                        />
                        <span>
                          <span className="block text-sm font-medium text-ink">
                            Ensemble evaluation
                          </span>
                          <span className="mt-1 block text-xs text-ink-muted">
                            Evaluate combinations of top-performing models.
                          </span>
                        </span>
                      </label>
                    </div>

                    <div className="grid gap-5 md:grid-cols-2">
                      <NumberField
                        label="Time budget (seconds)"
                        value={trainingConfig.time_budget_s ?? ""}
                        min={1}
                        onChange={(value) =>
                          updateTrainingConfig("time_budget_s", value)
                        }
                        help="Leave empty for no time limit."
                      />
                    </div>
                  </div>

                  {/* Advanced settings */}
                  <div className="mt-6 overflow-hidden rounded-xl border border-surface-border">
                    <button
                      type="button"
                      onClick={() =>
                        setAdvancedSettingsOpen((value) => !value)
                      }
                      aria-expanded={advancedSettingsOpen}
                      className="flex w-full items-center justify-between gap-3 bg-surface-page p-4 text-left"
                    >
                      <span className="flex items-center gap-2">
                        <Settings2 size={18} className="text-orange" />
                        <span>
                          <span className="block text-sm font-semibold text-ink">
                            Advanced settings
                          </span>
                          <span className="mt-1 block text-xs text-ink-muted">
                            Fine-tune model selection and evaluation.
                          </span>
                        </span>
                      </span>
                      {advancedSettingsOpen ? (
                        <ChevronUp size={18} />
                      ) : (
                        <ChevronDown size={18} />
                      )}
                    </button>

                    {advancedSettingsOpen && (
                      <div className="space-y-6 p-4">
                        <div>
                          <h4 className="mb-3 text-sm font-semibold text-ink">
                            Cross-validation and candidate selection
                          </h4>
                          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                            <NumberField
                              label="CV folds"
                              value={trainingConfig.cv_splits}
                              min={2}
                              onChange={(value) =>
                                updateTrainingConfig("cv_splits", value)
                              }
                            />
                            <NumberField
                              label="CV repeats"
                              value={trainingConfig.cv_repeats}
                              min={1}
                              onChange={(value) =>
                                updateTrainingConfig("cv_repeats", value)
                              }
                            />
                            <NumberField
                              label="Maximum candidates"
                              value={trainingConfig.max_candidates}
                              min={1}
                              onChange={(value) =>
                                updateTrainingConfig("max_candidates", value)
                              }
                            />
                          </div>
                        </div>

                        <div>
                          <h4 className="mb-3 text-sm font-semibold text-ink">
                            Hyperparameter tuning
                          </h4>
                          <div className="grid gap-4 sm:grid-cols-2">
                            <NumberField
                              label="Top models to tune"
                              value={trainingConfig.tune_top_n}
                              min={0}
                              onChange={(value) =>
                                updateTrainingConfig("tune_top_n", value)
                              }
                            />
                            <NumberField
                              label="Tuning iterations"
                              value={trainingConfig.tune_iterations}
                              min={1}
                              onChange={(value) =>
                                updateTrainingConfig("tune_iterations", value)
                              }
                            />
                          </div>
                        </div>

                        <div>
                          <h4 className="mb-3 text-sm font-semibold text-ink">
                            Ensemble configuration
                          </h4>
                          <div className="grid gap-4 sm:grid-cols-2">
                            <NumberField
                              label="Ensemble top K"
                              value={trainingConfig.ensemble_top_k}
                              min={1}
                              onChange={(value) =>
                                updateTrainingConfig("ensemble_top_k", value)
                              }
                            />
                            <NumberField
                              label="Minimum ensemble gain"
                              value={trainingConfig.ensemble_min_gain}
                              min={0}
                              step={0.001}
                              onChange={(value) =>
                                updateTrainingConfig("ensemble_min_gain", value)
                              }
                            />
                          </div>
                        </div>

                        <div>
                          <h4 className="mb-3 text-sm font-semibold text-ink">
                            Reproducibility and safeguards
                          </h4>
                          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                            <NumberField
                              label="Random state"
                              value={trainingConfig.random_state}
                              min={0}
                              onChange={(value) =>
                                updateTrainingConfig("random_state", value)
                              }
                            />
                            <NumberField
                              label="Parallel jobs"
                              value={trainingConfig.n_jobs}
                              min={-1}
                              onChange={(value) =>
                                updateTrainingConfig("n_jobs", value)
                              }
                              help="-1 uses all available CPU cores."
                            />
                            <NumberField
                              label="Overfit warning threshold"
                              value={trainingConfig.overfit_gap_warn}
                              min={0}
                              max={1}
                              step={0.01}
                              onChange={(value) =>
                                updateTrainingConfig("overfit_gap_warn", value)
                              }
                            />
                          </div>

                          <label className="mt-4 flex items-start gap-3 rounded-xl border border-surface-border p-4">
                            <input
                              type="checkbox"
                              checked={trainingConfig.refit_on_all}
                              onChange={(event) =>
                                updateTrainingConfig(
                                  "refit_on_all",
                                  event.target.checked
                                )
                              }
                              disabled={startingTraining || Boolean(trainingRunId)}
                              className="mt-1 accent-orange"
                            />
                            <span>
                              <span className="block text-sm font-medium text-ink">
                                Refit selected model on all available data
                              </span>
                              <span className="mt-1 block text-xs text-ink-muted">
                                Enable only if you understand how this affects the held-out test evaluation.
                              </span>
                            </span>
                          </label>
                        </div>

                        <div>
                          <h4 className="mb-3 text-sm font-semibold text-ink">
                            Model selection
                          </h4>

                          <p className="mb-3 text-xs text-ink-muted">
                            Exclude specific models or restrict evaluation to selected models. Leave both empty to use the default candidate set.
                          </p>

                          <div className="grid gap-5 md:grid-cols-2">
                            {[
                              ["exclude", "Exclude models"],
                              ["include_only", "Include only these models"],
                            ].map(([key, label]) => (
                              <div key={key}>
                                <p className="mb-2 text-sm font-medium text-ink">
                                  {label}
                                </p>
                                <div className="max-h-48 space-y-2 overflow-y-auto rounded-lg border border-surface-border p-3">
                                  {MODEL_OPTIONS.map((model) => (
                                    <label
                                      key={model}
                                      className="flex items-center gap-2 text-sm text-ink-secondary"
                                    >
                                      <input
                                        type="checkbox"
                                        checked={trainingConfig[key].includes(model)}
                                        onChange={() => toggleModel(key, model)}
                                        disabled={
                                          startingTraining ||
                                          Boolean(trainingRunId)
                                        }
                                        className="accent-orange"
                                      />
                                      {model}
                                    </label>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        <Button
                          variant="secondary"
                          onClick={() =>
                            setTrainingConfig({
                              ...DEFAULT_TRAINING_CONFIG,
                            })
                          }
                          disabled={startingTraining || Boolean(trainingRunId)}
                        >
                          <RefreshCw size={15} className="mr-2" />
                          Reset configuration
                        </Button>
                      </div>
                    )}
                  </div>

                  {trainingError && (
                    <div className="mt-5 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                      <AlertTriangle size={17} className="mt-0.5 shrink-0" />
                      <span>{trainingError}</span>
                    </div>
                  )}

                  {trainingRunId && (
                    <div className="mt-5 rounded-xl border border-surface-border p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-ink">
                            AutoML training run
                          </p>
                          <p className="mt-1 break-all text-xs text-ink-secondary">
                            {trainingRunId}
                          </p>
                        </div>

                        <span
                          className={`rounded-full px-3 py-1 text-xs font-medium ${
                            trainingStatus === "completed"
                              ? "bg-emerald-100 text-emerald-800"
                              : trainingStatus === "failed"
                                ? "bg-red-100 text-red-800"
                                : trainingStatus === "cancelled"
                                  ? "bg-gray-100 text-gray-700"
                                  : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {trainingStatus
                            .replaceAll("_", " ")
                            .replace(/\b\w/g, (character) =>
                              character.toUpperCase()
                            )}
                        </span>
                      </div>

                      {trainingIsActive && (
                        <div className="mt-4 flex items-center gap-3 text-sm text-ink-secondary">
                          <LoaderCircle size={18} className="animate-spin" />
                          AutoML is evaluating candidate models. This section updates automatically.
                        </div>
                      )}

                      {trainingStatus === "completed" && (
                        <div className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
                          <div className="flex items-center gap-2 font-medium">
                            <CheckCircle2 size={17} />
                            Training completed successfully.
                          </div>
                          <p className="mt-1">
                            Your model evaluation results are ready.
                          </p>
                        </div>
                      )}

                      {trainingStatus === "failed" && (
                        <p className="mt-3 text-sm text-red-700">
                          {trainingError || "Training failed. Check the backend logs."}
                        </p>
                      )}

                      {trainingStatus === "cancelled" && (
                        <p className="mt-3 text-sm text-ink-secondary">
                          This training run was cancelled.
                        </p>
                      )}
                    </div>
                  )}

                  <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
                    <p className="text-xs text-ink-muted">
                      Preprocessing run:{" "}
                      <span className="font-medium text-ink-secondary">
                        {result.run_id || result.preprocessing_run_id}
                      </span>
                    </p>

                    {trainingStatus === "completed" ? (
                      <Button onClick={handleContinueToComparison}>
                        View Model Comparison
                        <ArrowRight size={16} className="ml-2" />
                      </Button>
                    ) : (
                      <Button
                        onClick={handleStartTraining}
                        disabled={
                          startingTraining ||
                          trainingIsActive ||
                          Boolean(
                            trainingRunId &&
                              !["failed", "cancelled"].includes(trainingStatus)
                          ) ||
                          !(result?.run_id || result?.preprocessing_run_id)
                        }
                      >
                        {startingTraining || trainingIsActive ? (
                          <>
                            <LoaderCircle
                              size={16}
                              className="mr-2 animate-spin"
                            />
                            {startingTraining
                              ? "Starting AutoML..."
                              : "Training..."}
                          </>
                        ) : (
                          <>
                            {["failed", "cancelled"].includes(trainingStatus)
                              ? "Retry AutoML Training"
                              : "Start AutoML Training"}
                            <ArrowRight size={16} className="ml-2" />
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </Card>

            {/* JSON reports */}
            <Card>
              <div className="space-y-5 p-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h3 className="font-semibold text-ink">JSON reports</h3>
                    <p className="mt-1 text-sm text-ink-secondary">
                      Inspect and download the JSON artifacts saved for this run.
                    </p>
                  </div>

                  <Button
                    variant="secondary"
                    onClick={() => loadReports(result.run_id)}
                    disabled={reportsLoading}
                  >
                    <RefreshCw
                      size={16}
                      className={`mr-2 ${reportsLoading ? "animate-spin" : ""}`}
                    />
                    Refresh reports
                  </Button>
                </div>

                {reportsLoading ? (
                  <p className="flex items-center gap-2 text-sm text-ink-secondary">
                    <LoaderCircle size={16} className="animate-spin" />
                    Loading JSON reports...
                  </p>
                ) : reportsError ? (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                    <p>{reportsError}</p>
                    <p className="mt-1 text-xs">
                      This may happen for runs created before JSON report storage was added.
                    </p>
                  </div>
                ) : Object.keys(reports).length ? (
                  <>
                    <div className="flex flex-wrap gap-2">
                      {Object.keys(reports).map((filename) => (
                        <button
                          key={filename}
                          type="button"
                          onClick={() => setActiveReport(filename)}
                          className={`rounded-lg border px-3 py-2 text-sm transition ${
                            activeReport === filename
                              ? "border-orange bg-orange-50 text-orange"
                              : "border-surface-border bg-white text-ink-secondary hover:bg-surface-page"
                          }`}
                        >
                          {filename}
                        </button>
                      ))}
                    </div>

                    <div className="overflow-hidden rounded-xl border border-surface-border">
                      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-border bg-surface-page px-4 py-3">
                        <p className="break-all text-sm font-medium text-ink">
                          {activeReport}
                        </p>
                        <Button
                          variant="secondary"
                          onClick={() => handleDownloadReport(activeReport)}
                        >
                          <Download size={15} className="mr-2" />
                          Download JSON
                        </Button>
                      </div>

                      <pre className="max-h-[520px] overflow-auto bg-white p-4 text-xs leading-6 text-ink">
                        {JSON.stringify(reports[activeReport] ?? {}, null, 2)}
                      </pre>
                    </div>
                  </>
                ) : (
                  <div className="rounded-lg bg-surface-page p-4 text-sm text-ink-secondary">
                    No JSON reports are available for this run yet.
                  </div>
                )}
              </div>
            </Card>

            {/* Preprocessing log */}
            <Card>
              <div className="space-y-5 p-5">
                <div>
                  <h3 className="font-semibold text-ink">
                    Preprocessing log
                  </h3>
                  <p className="mt-1 text-sm text-ink-secondary">
                    Review the transformations recorded for this preprocessing run.
                  </p>
                </div>

                {preprocessingLogs.length > 0 ? (
                  <>
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      {[
                        ["Columns affected", logSummary.columns, "Unique columns in the log"],
                        ["Drop actions", logSummary.dropped, "Logged column-removal actions"],
                        ["Imputation", logSummary.imputed, "Missing-value handling actions"],
                        [
                          "Encoding / scaling",
                          `${logSummary.encoded} / ${logSummary.scaled}`,
                          "Encoding actions / scaling actions",
                        ],
                      ].map(([label, value, detail]) => (
                        <div
                          key={label}
                          className="rounded-xl border border-surface-border bg-surface-page p-4"
                        >
                          <p className="text-sm text-ink-secondary">{label}</p>
                          <p className="mt-2 text-2xl font-semibold text-ink">
                            {value}
                          </p>
                          <p className="mt-1 text-xs text-ink-muted">
                            {detail}
                          </p>
                        </div>
                      ))}
                    </div>

                    <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_190px]">
                      <input
                        value={logSearch}
                        onChange={(event) => setLogSearch(event.target.value)}
                        placeholder="Search column, action, reason or rule..."
                        aria-label="Search preprocessing logs"
                        className="w-full rounded-lg border border-surface-border bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-orange"
                      />

                      <select
                        value={logFilter}
                        onChange={(event) => setLogFilter(event.target.value)}
                        aria-label="Filter preprocessing logs"
                        className="w-full rounded-lg border border-surface-border bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-orange"
                      >
                        {[
                          "All",
                          "Dropped",
                          "Missing values",
                          "Encoding",
                          "Scaling",
                          "System",
                          "Other",
                        ].map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-3">
                      {visiblePreprocessingLogs.map((item, index) => {
                        const log =
                          item && typeof item === "object"
                            ? item
                            : { message: String(item) };

                        const action = String(log.action ?? "Log event")
                          .replaceAll("_", " ")
                          .replace(/\b\w/g, (character) =>
                            character.toUpperCase()
                          );

                        const title = log.column || log.message || action;
                        const isExpanded = Boolean(expandedLogs[index]);

                        const details = [
                          ["Stage", log.stage],
                          ["Action", log.action],
                          ["Reason", log.reason],
                          ["Rule ID", log.rule_id],
                          ["Source", log.source],
                        ].filter(
                          ([, value]) =>
                            value !== undefined &&
                            value !== null &&
                            value !== ""
                        );

                        return (
                          <div
                            key={`${log.column ?? "dataset"}-${log.action ?? "event"}-${index}`}
                            className="overflow-hidden rounded-xl border border-surface-border"
                          >
                            <button
                              type="button"
                              onClick={() =>
                                setExpandedLogs((current) => ({
                                  ...current,
                                  [index]: !current[index],
                                }))
                              }
                              aria-expanded={isExpanded}
                              className="flex w-full items-center justify-between gap-4 p-4 text-left transition hover:bg-surface-page"
                            >
                              <div className="min-w-0">
                                <p className="truncate font-medium text-ink">
                                  {title}
                                </p>
                                <p className="mt-1 text-sm text-ink-secondary">
                                  {log.reason || log.stage || (log.message ? "Recorded event" : action)}
                                </p>
                              </div>
                              <span className="shrink-0 rounded-full border border-surface-border bg-surface-page px-2.5 py-1 text-xs text-ink-secondary">
                                {action}
                              </span>
                            </button>

                            {isExpanded && (
                              <div className="space-y-3 border-t border-surface-border bg-surface-page p-4">
                                {details.length > 0 && (
                                  <dl className="grid gap-3 sm:grid-cols-2">
                                    {details.map(([label, value]) => (
                                      <div
                                        key={label}
                                        className="rounded-lg bg-white p-3"
                                      >
                                        <dt className="text-xs text-ink-muted">
                                          {label}
                                        </dt>
                                        <dd className="mt-1 break-words text-sm text-ink">
                                          {String(value)}
                                        </dd>
                                      </div>
                                    ))}
                                  </dl>
                                )}

                                {log.message && (
                                  <p className="whitespace-pre-wrap break-words text-sm text-ink-secondary">
                                    {String(log.message)}
                                  </p>
                                )}

                                {details.length === 0 && !log.message && (
                                  <pre className="overflow-x-auto whitespace-pre-wrap break-words text-xs text-ink-secondary">
                                    {JSON.stringify(item, null, 2)}
                                  </pre>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}

                      {visiblePreprocessingLogs.length === 0 && (
                        <p className="rounded-lg bg-surface-page p-5 text-center text-sm text-ink-secondary">
                          No log events match your search or filter.
                        </p>
                      )}
                    </div>

                    <p className="text-xs text-ink-muted">
                      Showing {visiblePreprocessingLogs.length} of{" "}
                      {preprocessingLogs.length} log events.
                    </p>
                  </>
                ) : (
                  <p className="rounded-lg bg-surface-page p-4 text-sm text-ink-secondary">
                    No preprocessing log was returned for this run.
                  </p>
                )}
              </div>
            </Card>
          </section>
        )}

        {/* Recent preprocessing runs */}
        <Card>
          <div className="p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold text-ink">Recent runs</h2>
                <p className="mt-1 text-sm text-ink-secondary">
                  Previous preprocessing runs for the selected dataset.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  loadRuns(datasetId).catch((err) =>
                    setError(err.message)
                  )
                }
                disabled={!datasetId}
                className="rounded-lg p-2 text-ink-secondary hover:bg-surface-page"
                aria-label="Refresh run history"
              >
                <RefreshCw size={16} />
              </button>
            </div>

            {runs.length === 0 ? (
              <p className="text-sm text-ink-secondary">
                No preprocessing runs yet.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-surface-border text-ink-muted">
                      <th className="py-3 pr-4 font-medium">Target</th>
                      <th className="py-3 pr-4 font-medium">Train rows</th>
                      <th className="py-3 pr-4 font-medium">Test rows</th>
                      <th className="py-3 pr-4 font-medium">Features</th>
                      <th className="py-3 pr-4 font-medium">Status</th>
                      <th className="py-3 font-medium">Downloads</th>
                    </tr>
                  </thead>

                  <tbody>
                    {runs.map((run) => (
                      <tr
                        key={run.run_id}
                        className="border-b border-surface-border last:border-0"
                      >
                        <td className="py-3 pr-4 text-ink">
                          {run.target_column}
                        </td>
                        <td className="py-3 pr-4">{run.train_rows}</td>
                        <td className="py-3 pr-4">{run.test_rows}</td>
                        <td className="py-3 pr-4">{run.feature_count}</td>
                        <td className="py-3 pr-4">
                          <span className="rounded-full bg-green-50 px-2 py-1 text-xs text-green-700">
                            {run.status}
                          </span>
                        </td>
                        <td className="py-3">
                          <div className="flex gap-2">
                            {run.artifacts?.train_available && (
                              <button
                                type="button"
                                onClick={() =>
                                  handleDownload(run.run_id, "train")
                                }
                                className="text-orange hover:underline"
                              >
                                Train
                              </button>
                            )}
                            {run.artifacts?.test_available && (
                              <button
                                type="button"
                                onClick={() =>
                                  handleDownload(run.run_id, "test")
                                }
                                className="text-orange hover:underline"
                              >
                                Test
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
