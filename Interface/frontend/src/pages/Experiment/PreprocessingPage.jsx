
import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  Workflow,
  Play,
  RefreshCw,
  Download,
  CheckCircle2,
  AlertCircle,
  Database,
  LoaderCircle,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import Card from "../../components/common/Card";
import Button from "../../components/common/Button";
import { getDatasets, getDataset } from "../../services/datasets";
import {
  preprocessDataset,
  getPreprocessingRuns,
  downloadPreprocessedCSV,
} from "../../services/preprocessing";


export default function PreprocessingPage() {
  const location = useLocation();
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

  const columns = Object.keys(profile?.columns ?? {});
  const preprocessingLogs = Array.isArray(result?.preprocessing_log)
    ? result.preprocessing_log
    : [];
  const visiblePreprocessingLogs = preprocessingLogs.filter((item) => {
    const log = item && typeof item === "object" ? item : { message: item };
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
    if (action.includes("drop")) category = "Dropped";
    else if (action.includes("imput")) category = "Missing values";
    else if (action.includes("encod")) category = "Encoding";
    else if (action.includes("scal")) category = "Scaling";
    else if (action === "skipped" || log.source === "system") category = "System";

    return (
      (logFilter === "All" || category === logFilter) &&
      text.includes(logSearch.trim().toLowerCase())
    );
  });

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

  const loadRuns = useCallback(async (id) => {
    if (!id) {
      setRuns([]);
      return;
    }

    const data = await getPreprocessingRuns(id);
    setRuns(data);
  }, []);

  const loadDataset = useCallback(async (id) => {
    setProfile(null);
    setResult(null);
    setTarget("");
    setError("");
    setNotice("");

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

      const availableColumns = Object.keys(nextProfile?.columns ?? {});
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
  }, [loadRuns]);

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

        if (selected) await loadDataset(selected);
      } catch (err) {
        if (active) setError(err.message || "Could not load datasets.");
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

    try {
      const response = await preprocessDataset(datasetId, {
        target_column: target,
        test_size: Number(testSize),
      });

      setResult(response);
      await loadRuns(datasetId);
      setNotice("Preprocessing completed. Your CSV artifacts are ready.");
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

  const activeDataset = datasets.find((item) => item.id === datasetId);

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
            Prepare your dataset, select a target, review feature selection,
            and download the processed training and testing data.
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
              <h2 className="font-semibold text-ink">Configure preprocessing</h2>
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
                    onChange={(event) => handleDatasetChange(event.target.value)}
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
                  <span className="font-medium text-ink">Target column</span>
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
              <div className="space-y-4 p-5">
                <h3 className="font-semibold text-ink">Selected features</h3>
                {result.selected_features?.length ? (
                  <div className="flex flex-wrap gap-2">
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
                  <p className="text-sm text-ink-secondary">
                    No selected features were returned.
                  </p>
                )}

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
              </div>
            </Card>

            <Card>
              <div className="space-y-5 p-5">
                <div>
                  <h3 className="font-semibold text-ink">Preprocessing log</h3>
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
                        ["Encoding / scaling", `${logSummary.encoded} / ${logSummary.scaled}`, "Encoding actions / scaling actions"],
                      ].map(([label, value, detail]) => (
                        <div
                          key={label}
                          className="rounded-xl border border-surface-border bg-surface-page p-4"
                        >
                          <p className="text-sm text-ink-secondary">{label}</p>
                          <p className="mt-2 text-2xl font-semibold text-ink">{value}</p>
                          <p className="mt-1 text-xs text-ink-muted">{detail}</p>
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
                        {["All", "Dropped", "Missing values", "Encoding", "Scaling", "System", "Other"].map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-3">
                      {visiblePreprocessingLogs.map((item, index) => {
                        const log = item && typeof item === "object"
                          ? item
                          : { message: String(item) };
                        const action = String(log.action ?? "Log event")
                          .replaceAll("_", " ")
                          .replace(/\b\w/g, (character) => character.toUpperCase());
                        const title = log.column || log.message || action;
                        const isExpanded = Boolean(expandedLogs[index]);
                        const details = [
                          ["Stage", log.stage],
                          ["Action", log.action],
                          ["Reason", log.reason],
                          ["Rule ID", log.rule_id],
                          ["Source", log.source],
                        ].filter(([, value]) => value !== undefined && value !== null && value !== "");

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
                                <p className="truncate font-medium text-ink">{title}</p>
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
                                {details.length > 0 ? (
                                  <dl className="grid gap-3 sm:grid-cols-2">
                                    {details.map(([label, value]) => (
                                      <div key={label} className="rounded-lg bg-white p-3">
                                        <dt className="text-xs text-ink-muted">{label}</dt>
                                        <dd className="mt-1 break-words text-sm text-ink">
                                          {String(value)}
                                        </dd>
                                      </div>
                                    ))}
                                  </dl>
                                ) : null}
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
                      Showing {visiblePreprocessingLogs.length} of {preprocessingLogs.length} log events.
                      Expand any event to inspect its recorded details.
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
                onClick={() => loadRuns(datasetId).catch((err) => setError(err.message))}
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
                                onClick={() => handleDownload(run.run_id, "train")}
                                className="text-orange hover:underline"
                              >
                                Train
                              </button>
                            )}
                            {run.artifacts?.test_available && (
                              <button
                                type="button"
                                onClick={() => handleDownload(run.run_id, "test")}
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
