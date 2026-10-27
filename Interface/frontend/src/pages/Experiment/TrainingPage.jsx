
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Database,
  FileSpreadsheet,
  LoaderCircle,
  RefreshCw,
  Settings2,
  Target,
  Trash2,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import Card, { CardHeader } from "../../components/common/Card";
import Button from "../../components/common/Button";
import { ROUTES } from "../../constants/routes";
import { getDataset } from "../../services/datasets";

const OBJECTIVES = [
  { value: "classification", label: "Classification" },
  { value: "regression", label: "Regression" },
  { value: "clustering", label: "Clustering" },
  { value: "exploration", label: "Exploratory analysis" },
];

const PIPELINES = [
  { value: "auto", label: "Automatic selection" },
  { value: "linear", label: "Linear models" },
  { value: "tree", label: "Tree-based models" },
];

function formatNumber(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 2,
  });
}

function formatPercent(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "—";
  }

  return `${Number(value).toFixed(2)}%`;
}

function formatDate(value) {
  if (!value) return "Recently uploaded";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "Recently uploaded"
    : date.toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
}

function titleCase(value = "") {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function StatCard({ label, value, hint, icon: Icon }) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-ink-secondary">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-ink">
            {value}
          </p>
          {hint && (
            <p className="mt-1 text-xs text-ink-muted">{hint}</p>
          )}
        </div>

        {Icon && (
          <div className="rounded-xl bg-surface-page p-3">
            <Icon size={19} className="text-ink-secondary" />
          </div>
        )}
      </div>
    </Card>
  );
}

function EmptyPanel({ children }) {
  return (
    <div className="rounded-xl border border-dashed border-surface-border p-6 text-center text-sm text-ink-secondary">
      {children}
    </div>
  );
}

function BarList({ items, labelKey = "label", valueKey = "value", suffix = "" }) {
  if (!items?.length) {
    return <EmptyPanel>No data available for this chart.</EmptyPanel>;
  }

  const max = Math.max(
    1,
    ...items.map((item) => Number(item[valueKey]) || 0)
  );

  return (
    <div className="space-y-4">
      {items.map((item, index) => {
        const value = Number(item[valueKey]) || 0;
        const width = Math.max(0, Math.min(100, (value / max) * 100));

        return (
          <div key={`${item[labelKey]}-${index}`}>
            <div className="mb-1.5 flex items-center justify-between gap-3 text-xs">
              <span
                className="min-w-0 truncate text-ink-secondary"
                title={String(item[labelKey])}
              >
                {item[labelKey]}
              </span>
              <span className="shrink-0 font-medium text-ink">
                {formatNumber(value)}{suffix}
              </span>
            </div>

            <div className="h-2 overflow-hidden rounded-full bg-surface-page">
              <div
                className="h-full rounded-full bg-orange-500"
                style={{ width: `${width}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Histogram({ items }) {
  if (!items?.length) {
    return <EmptyPanel>No numeric distribution available.</EmptyPanel>;
  }

  const max = Math.max(1, ...items.map((item) => item.count));

  return (
    <div className="flex h-56 items-end gap-1.5 border-b border-surface-border px-1 pt-4">
      {items.map((item, index) => (
        <div
          key={`${item.label}-${index}`}
          className="flex h-full min-w-0 flex-1 flex-col justify-end"
          title={`${item.label}: ${item.count} observations`}
        >
          <span className="mb-1 truncate text-center text-[10px] text-ink-secondary">
            {item.count}
          </span>
          <div
            className="w-full rounded-t bg-orange-500"
            style={{
              height: `${Math.max(2, (item.count / max) * 80)}%`,
            }}
          />
          {items.length <= 8 && (
            <span className="mt-2 truncate text-center text-[9px] text-ink-muted">
              {item.label}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function CorrelationHeatmap({ matrix }) {
  const labels = matrix?.labels ?? [];
  const values = matrix?.values ?? [];

  if (!labels.length || !values.length) {
    return (
      <EmptyPanel>
        Not enough numeric columns to calculate a correlation matrix.
      </EmptyPanel>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table
        className="w-full border-separate text-xs"
        style={{ borderSpacing: "3px" }}
      >
        <thead>
          <tr>
            <th />
            {labels.map((label) => (
              <th
                key={label}
                className="max-w-24 px-1 py-2 font-medium text-ink-secondary"
              >
                <span className="block truncate" title={label}>
                  {label}
                </span>
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {labels.map((label, rowIndex) => (
            <tr key={label}>
              <th className="max-w-28 pr-2 text-left font-medium text-ink-secondary">
                <span className="block truncate" title={label}>
                  {label}
                </span>
              </th>

              {labels.map((otherLabel, colIndex) => {
                const value = values[rowIndex]?.[colIndex];
                const valid = Number.isFinite(value);
                const strength = valid ? Math.abs(value) : 0;

                const background = !valid
                  ? "#f3f4f6"
                  : value >= 0
                    ? `rgba(234, 88, 12, ${0.10 + strength * 0.75})`
                    : `rgba(37, 99, 235, ${0.10 + strength * 0.75})`;

                return (
                  <td
                    key={`${label}-${otherLabel}`}
                    title={`${label} × ${otherLabel}: ${
                      valid ? value.toFixed(3) : "Unavailable"
                    }`}
                    className="h-10 min-w-10 rounded text-center"
                    style={{
                      backgroundColor: background,
                      color:
                        valid && strength > 0.55
                          ? "#ffffff"
                          : "#374151",
                    }}
                  >
                    {valid ? value.toFixed(2) : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <p className="mt-3 text-xs text-ink-muted">
        Orange = positive correlation. Blue = negative correlation.
        Correlation does not establish causation.
      </p>
    </div>
  );
}

function SectionHeading({ title, subtitle }) {
  return (
    <div className="mb-5">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      {subtitle && (
        <p className="mt-1 text-sm text-ink-secondary">{subtitle}</p>
      )}
    </div>
  );
}

export default function TrainingPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const datasetId = location.state?.datasetId;

  const [dataset, setDataset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const [objective, setObjective] = useState("classification");
  const [targetColumn, setTargetColumn] = useState("");
  const [pipeline, setPipeline] = useState("auto");
  const [testSize, setTestSize] = useState("20");
  const [includeFeatureSelection, setIncludeFeatureSelection] =
    useState(true);

  const [selectedNumericColumn, setSelectedNumericColumn] = useState("");
  const [selectedCategoryColumn, setSelectedCategoryColumn] = useState("");

  async function loadDataset(isRefresh = false) {
    if (!datasetId) {
      setError("No dataset was selected. Return to your datasets and select one.");
      setLoading(false);
      return;
    }

    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    setError("");

    try {
      const result = await getDataset(datasetId);
      const loaded = result?.dataset ?? result?.data?.dataset ?? result?.data ?? result;

      setDataset(loaded);

      const profile = loaded?.profile;
      const targetName = profile?.target?.name;

      if (targetName) {
        setTargetColumn(targetName);
      } else if (!targetColumn && loaded?.columns?.length) {
        setTargetColumn("");
      }
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Could not load this dataset."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadDataset();
    // Dataset ID identifies the resource being loaded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]);

  const profile = dataset?.profile ?? {};
  const overview = profile?.overview ?? {};
  const columns = profile?.columns ?? {};
  const visualizations = profile?.visualizations ?? {};
  const summaryMetrics = visualizations?.summary_metrics ?? {};

  const columnNames = useMemo(() => Object.keys(columns), [columns]);

  const columnRows = useMemo(
    () =>
      columnNames.map((name) => ({
        name,
        ...(columns[name] ?? {}),
      })),
    [columnNames, columns]
  );

  const missingColumns = useMemo(
    () =>
      (visualizations?.missing_by_column ?? [])
        .filter((item) => Number(item.missing_count) > 0)
        .slice(0, 12)
        .map((item) => ({
          label: item.column,
          value: Number(item.missing_pct) || 0,
          count: Number(item.missing_count) || 0,
        })),
    [visualizations]
  );

  const typeCounts = [
    { label: "Numeric", value: Number(overview.numeric_columns) || 0 },
    { label: "Categorical", value: Number(overview.categorical_columns) || 0 },
    { label: "Datetime", value: Number(overview.datetime_columns) || 0 },
    { label: "Text", value: Number(overview.text_columns) || 0 },
  ].filter((item) => item.value > 0);

  const numericDistributions = visualizations?.numeric_distributions ?? {};
  const categoryCounts = visualizations?.category_counts ?? {};

  const numericColumnNames = Object.keys(numericDistributions);
  const categoryColumnNames = Object.keys(categoryCounts);

  const activeNumericColumn = numericDistributions[selectedNumericColumn]
    ? selectedNumericColumn
    : numericColumnNames[0] ?? "";

  const activeCategoryColumn = categoryCounts[selectedCategoryColumn]
    ? selectedCategoryColumn
    : categoryColumnNames[0] ?? "";

  const activeNumericData = numericDistributions[activeNumericColumn];
  const activeCategoryData = categoryCounts[activeCategoryColumn];

  const histogramItems = (activeNumericData?.histogram ?? []).map(
    (bin, index) => ({
      label: `${bin.bin_start ?? "?"}–${bin.bin_end ?? "?"}`,
      count: Number(bin.count) || 0,
      index,
    })
  );

  const categoryItems = (activeCategoryData?.categories ?? []).map(
    (item) => ({
      label: item.category,
      count: Number(item.count) || 0,
    })
  );

  const correlationMatrix = visualizations?.correlation_matrix ?? {
    labels: [],
    values: [],
  };

  const correlationPairs = useMemo(() => {
    const labels = correlationMatrix.labels ?? [];
    const values = correlationMatrix.values ?? [];

    return labels.flatMap((featureA, rowIndex) =>
      labels
        .slice(rowIndex + 1)
        .map((featureB, offset) => ({
          featureA,
          featureB,
          value: values[rowIndex]?.[rowIndex + offset + 1],
        }))
        .filter((pair) => Number.isFinite(pair.value))
    );
  }, [correlationMatrix]);

  const strongCorrelations = correlationPairs
    .filter((pair) => Math.abs(pair.value) >= 0.85)
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

  const qualityFlags = profile?.quality_flags ?? [];
  const warnings = profile?.warnings ?? [];

  const targetInfo = profile?.target;
  const classBalance = targetInfo?.class_balance ?? {};

  const targetDistribution = Object.entries(classBalance).map(
    ([label, proportion]) => ({
      label: String(label),
      value: Number(proportion) * 100,
    })
  );

  const targetProfile = columns?.[targetColumn];
  const targetType = targetProfile?.inferred_type;

  const hasTarget = Boolean(targetColumn);
  const targetIsIdLike = Boolean(targetProfile?.id_like);
  const targetHasHighMissing = Number(targetProfile?.missing_pct) >= 60;

  const targetWarning =
    hasTarget && targetIsIdLike
      ? "The selected target appears identifier-like. Verify that it represents the outcome you want to predict."
      : hasTarget && targetHasHighMissing
        ? "The selected target has substantial missing values. Training may require removing rows with missing targets."
        : hasTarget && objective === "classification" && targetType === "text"
          ? "Text targets are not supported as ordinary classification labels without additional processing."
          : hasTarget && objective === "regression" && targetType !== "numeric"
            ? "Regression generally requires a numeric target."
            : hasTarget && objective === "clustering"
              ? "Clustering is unsupervised and normally does not require a target column."
              : "";

  const constantColumns =
    summaryMetrics.constant_columns ?? [];

  const highCardinalityColumns =
    summaryMetrics.high_cardinality_columns ?? [];

  const datasetName =
    dataset?.name ??
    dataset?.filename ??
    dataset?.original_filename ??
    "Uploaded dataset";

  const rowCount = overview.n_rows ?? dataset?.n_rows ?? dataset?.row_count;
  const columnCount = overview.n_cols ?? dataset?.n_cols ?? dataset?.column_count;

  function handleContinue() {
    if (!datasetId) {
      setError("Select a dataset before continuing.");
      return;
    }

    if (objective !== "clustering" && objective !== "exploration" && !targetColumn) {
      setError("Choose a target column before continuing.");
      return;
    }

    setError(
      "Pipeline settings are ready, but the training endpoint has not yet been connected. No model has been trained."
    );
  }

  if (loading) {
    return (
      <AppShell>
        <div className="flex min-h-[55vh] items-center justify-center">
          <div className="text-center">
            <LoaderCircle className="mx-auto animate-spin text-ink-secondary" size={30} />
            <p className="mt-4 text-sm text-ink-secondary">
              Loading dataset profile…
            </p>
          </div>
        </div>
      </AppShell>
    );
  }

  if (error && !dataset) {
    return (
      <AppShell>
        <div className="mx-auto max-w-2xl py-12">
          <Card>
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-1 shrink-0 text-red-500" size={22} />
              <div>
                <h2 className="font-semibold text-ink">
                  Could not load dataset
                </h2>
                <p className="mt-2 text-sm text-ink-secondary">{error}</p>
                <div className="mt-5 flex flex-wrap gap-3">
                  <Button onClick={() => loadDataset()}>
                    <RefreshCw size={16} className="mr-2" />
                    Try again
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => navigate(ROUTES.UPLOAD)}
                  >
                    Back to datasets
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-7xl space-y-6 pb-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <button
              type="button"
              onClick={() => navigate(ROUTES.UPLOAD)}
              className="mb-4 inline-flex items-center gap-2 text-sm text-ink-secondary hover:text-ink"
            >
              <ArrowLeft size={16} />
              Back to datasets
            </button>

            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-surface-page p-3">
                <FileSpreadsheet size={24} className="text-ink" />
              </div>
              <div>
                <h1 className="text-2xl font-semibold text-ink">
                  Dataset analysis
                </h1>
                <p className="mt-1 text-sm text-ink-secondary">
                  Explore data quality and configure your ML pipeline.
                </p>
              </div>
            </div>
          </div>

          <Button
            variant="secondary"
            onClick={() => loadDataset(true)}
            disabled={refreshing}
          >
            <RefreshCw
              size={16}
              className={`mr-2 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh profile
          </Button>
        </div>

        <Card>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex min-w-0 items-center gap-3">
              <Database size={22} className="shrink-0 text-ink-secondary" />
              <div className="min-w-0">
                <h2 className="truncate font-semibold text-ink">
                  {datasetName}
                </h2>
                <p className="mt-1 text-xs text-ink-secondary">
                  Uploaded {formatDate(dataset?.created_at ?? dataset?.uploaded_at)}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-4 text-sm text-ink-secondary">
              <span>{formatNumber(rowCount)} rows</span>
              <span>{formatNumber(columnCount)} columns</span>
            </div>
          </div>
        </Card>

        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <AlertTriangle size={18} className="mt-0.5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        <section>
          <SectionHeading
            title="Dataset overview"
            subtitle="A quick snapshot of the uploaded dataset."
          />

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Total rows"
              value={formatNumber(overview.n_rows ?? rowCount)}
              hint="Observations in the dataset"
              icon={Database}
            />
            <StatCard
              label="Total columns"
              value={formatNumber(overview.n_cols ?? columnCount)}
              hint="Features and potential target"
              icon={BarChart3}
            />
            <StatCard
              label="Missing cells"
              value={formatNumber(
                summaryMetrics.missing_cells ?? overview.missing_cells
              )}
              hint={formatPercent(
                summaryMetrics.missing_cells_pct ?? overview.missing_cells_pct
              ) + " of all cells"}
              icon={AlertTriangle}
            />
            <StatCard
              label="Duplicate rows"
              value={formatNumber(
                summaryMetrics.duplicate_rows ?? overview.n_duplicate_rows
              )}
              hint={formatPercent(
                summaryMetrics.duplicate_rows_pct ?? overview.duplicate_rows_pct
              ) + " of all rows"}
              icon={RefreshCw}
            />
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-2">
          <Card>
            <CardHeader
              title="Missing values by column"
              subtitle="Columns with the highest missing-value percentages."
            />
            <BarList
              items={missingColumns.map((item) => ({
                label: `${item.label} (${item.count})`,
                value: item.value,
              }))}
              suffix="%"
            />
          </Card>

          <Card>
            <CardHeader
              title="Column type distribution"
              subtitle="How the analyzer classified your columns."
            />
            <BarList items={typeCounts} />
            <p className="mt-4 text-xs text-ink-muted">
              Type inference is a profile estimate; review columns before training.
            </p>
          </Card>
        </section>

        <section className="grid gap-6 xl:grid-cols-2">
          <Card>
            <CardHeader
              title="Target class distribution"
              subtitle={
                targetInfo?.name
                  ? `Selected target: ${targetInfo.name}`
                  : "Choose a target column below to inspect class balance."
              }
            />

            {targetDistribution.length ? (
              <>
                <BarList items={targetDistribution} suffix="%" />
                {targetInfo?.imbalance_flag && (
                  <div className="mt-4 flex gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                    <AlertTriangle size={17} className="mt-0.5 shrink-0" />
                    The analyzer flagged potential class imbalance.
                  </div>
                )}
              </>
            ) : (
              <EmptyPanel>
                No class-balance data is available for the selected target.
                The target must have been passed to the backend analyzer.
              </EmptyPanel>
            )}
          </Card>

          <Card>
            <CardHeader
              title="Strong correlations"
              subtitle="Numeric feature pairs with absolute Pearson correlation ≥ 0.85."
            />

            {strongCorrelations.length ? (
              <div className="space-y-3">
                {strongCorrelations.slice(0, 10).map((pair) => (
                  <div
                    key={`${pair.featureA}-${pair.featureB}`}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-surface-page p-3 text-sm"
                  >
                    <span className="text-ink">
                      {pair.featureA}
                      <span className="mx-2 text-ink-muted">↔</span>
                      {pair.featureB}
                    </span>
                    <span className="font-semibold text-ink">
                      {pair.value.toFixed(3)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyPanel>
                No feature pairs crossed the 0.85 correlation threshold.
              </EmptyPanel>
            )}
          </Card>
        </section>

        <section>
          <SectionHeading
            title="Distribution explorer"
            subtitle="Inspect real numeric histograms and frequent categorical values."
          />

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader
                title="Numeric distribution"
                subtitle="Frequency histogram and summary statistics."
              />

              {numericColumnNames.length ? (
                <>
                  <label
                    htmlFor="numeric-column"
                    className="mb-2 block text-xs font-medium text-ink-secondary"
                  >
                    Select numeric column
                  </label>
                  <select
                    id="numeric-column"
                    value={activeNumericColumn}
                    onChange={(event) =>
                      setSelectedNumericColumn(event.target.value)
                    }
                    className="mb-5 w-full rounded-lg border border-surface-border bg-white px-3 py-2 text-sm text-ink"
                  >
                    {numericColumnNames.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>

                  <Histogram items={histogramItems} />

                  {activeNumericData?.statistics && (
                    <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
                      {["min", "max", "mean", "median"].map((key) => (
                        <div
                          key={key}
                          className="rounded-lg bg-surface-page p-3"
                        >
                          <p className="text-xs text-ink-secondary">
                            {titleCase(key)}
                          </p>
                          <p className="mt-1 font-semibold text-ink">
                            {formatNumber(
                              activeNumericData.statistics[key]
                            )}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}

                  {activeNumericData?.statistics && (
                    <p className="mt-4 text-xs text-ink-muted">
                      Standard deviation: {formatNumber(activeNumericData.statistics.std)}
                      {" · "}Skewness: {formatNumber(activeNumericData.statistics.skewness)}
                      {" · "}Q1: {formatNumber(activeNumericData.statistics.q1)}
                      {" · "}Q3: {formatNumber(activeNumericData.statistics.q3)}
                    </p>
                  )}
                </>
              ) : (
                <EmptyPanel>
                  No numeric histogram data was returned by the analyzer.
                </EmptyPanel>
              )}
            </Card>

            <Card>
              <CardHeader
                title="Category frequency"
                subtitle="Most frequent values for a categorical, text, or datetime column."
              />

              {categoryColumnNames.length ? (
                <>
                  <label
                    htmlFor="category-column"
                    className="mb-2 block text-xs font-medium text-ink-secondary"
                  >
                    Select column
                  </label>
                  <select
                    id="category-column"
                    value={activeCategoryColumn}
                    onChange={(event) =>
                      setSelectedCategoryColumn(event.target.value)
                    }
                    className="mb-5 w-full rounded-lg border border-surface-border bg-white px-3 py-2 text-sm text-ink"
                  >
                    {categoryColumnNames.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>

                  <BarList
                    items={categoryItems}
                    labelKey="label"
                    valueKey="count"
                  />

                  <p className="mt-4 text-xs text-ink-muted">
                    Showing up to 12 values out of{" "}
                    {formatNumber(activeCategoryData?.total_categories)} distinct categories.
                  </p>
                </>
              ) : (
                <EmptyPanel>
                  No category-frequency data was returned by the analyzer.
                </EmptyPanel>
              )}
            </Card>
          </div>
        </section>

        <Card>
          <CardHeader
            title="Correlation matrix"
            subtitle="Pearson correlation across inferred numeric columns."
          />
          <CorrelationHeatmap matrix={correlationMatrix} />
        </Card>

        <section className="grid gap-6 xl:grid-cols-2">
          <Card>
            <CardHeader
              title="Data quality flags"
              subtitle="Potential issues detected by the analyzer."
            />

            {qualityFlags.length ? (
              <div className="space-y-2">
                {qualityFlags.map((flag, index) => (
                  <div
                    key={`${flag}-${index}`}
                    className="flex items-start gap-3 rounded-lg bg-surface-page p-3 text-sm"
                  >
                    <AlertTriangle
                      size={17}
                      className="mt-0.5 shrink-0 text-amber-600"
                    />
                    <span className="break-words text-ink">
                      {String(flag).replaceAll("_", " ")}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyPanel>No quality flags were returned.</EmptyPanel>
            )}

            {!!warnings.length && (
              <div className="mt-5 space-y-2">
                {warnings.map((warning, index) => (
                  <p
                    key={index}
                    className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
                  >
                    {typeof warning === "string"
                      ? warning
                      : JSON.stringify(warning)}
                  </p>
                ))}
              </div>
            )}
          </Card>

          <Card>
            <CardHeader
              title="Additional quality metrics"
              subtitle="Structural issues and columns worth reviewing."
            />

            <div className="space-y-4">
              <div>
                <p className="text-sm font-medium text-ink">
                  Constant columns
                </p>
                <p className="mt-1 text-xs text-ink-secondary">
                  {formatNumber(summaryMetrics.constant_column_count ?? overview.constant_columns)}
                  {" "}column(s) have one distinct value.
                </p>
                {constantColumns.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {constantColumns.map((name) => (
                      <span
                        key={name}
                        className="rounded-md bg-surface-page px-2 py-1 text-xs text-ink-secondary"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="border-t border-surface-border pt-4">
                <p className="text-sm font-medium text-ink">
                  High-cardinality columns
                </p>
                <p className="mt-1 text-xs text-ink-secondary">
                  Columns with many distinct values, which may include IDs or names.
                </p>

                {highCardinalityColumns.length ? (
                  <div className="mt-3 space-y-2">
                    {highCardinalityColumns.slice(0, 8).map((item) => (
                      <div
                        key={item.column}
                        className="flex items-center justify-between gap-3 text-sm"
                      >
                        <span className="truncate text-ink">
                          {item.column}
                        </span>
                        <span className="shrink-0 text-ink-secondary">
                          {formatPercent(item.unique_pct)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-ink-secondary">
                    No high-cardinality columns were flagged.
                  </p>
                )}
              </div>
            </div>
          </Card>
        </section>

        <Card>
          <CardHeader
            title="Column profile"
            subtitle="Inspect inferred types, missing values, cardinality, and numeric outliers."
          />

          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-xs text-ink-secondary">
                  <th className="py-3 pr-4 font-medium">Column</th>
                  <th className="py-3 pr-4 font-medium">Type</th>
                  <th className="py-3 pr-4 font-medium">Missing</th>
                  <th className="py-3 pr-4 font-medium">Unique</th>
                  <th className="py-3 pr-4 font-medium">Outliers</th>
                  <th className="py-3 font-medium">Flags</th>
                </tr>
              </thead>

              <tbody>
                {columnRows.map((column) => (
                  <tr
                    key={column.name}
                    className="border-b border-surface-border last:border-0"
                  >
                    <td className="max-w-52 truncate py-3 pr-4 font-medium text-ink">
                      {column.name}
                    </td>
                    <td className="py-3 pr-4 text-ink-secondary">
                      {titleCase(column.inferred_type ?? "unknown")}
                    </td>
                    <td className="py-3 pr-4 text-ink-secondary">
                      {formatNumber(column.missing_count)}
                      {" "}({formatPercent(column.missing_pct)})
                    </td>
                    <td className="py-3 pr-4 text-ink-secondary">
                      {formatNumber(column.n_unique)}
                    </td>
                    <td className="py-3 pr-4 text-ink-secondary">
                      {column.outlier_count === undefined
                        ? "—"
                        : `${formatNumber(column.outlier_count)} (${formatPercent(column.outlier_pct)})`}
                    </td>
                    <td className="py-3">
                      <div className="flex flex-wrap gap-1">
                        {(column.flags ?? []).length ? (
                          column.flags.map((flag) => (
                            <span
                              key={flag}
                              className="rounded-md bg-surface-page px-2 py-1 text-[10px] text-ink-secondary"
                            >
                              {titleCase(flag)}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-ink-muted">None</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}

                {!columnRows.length && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-ink-secondary">
                      No column profile is available.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Configure pipeline"
            subtitle="Set the intended task and training preferences. Training is not triggered from this screen yet."
          />

          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <label
                htmlFor="objective"
                className="mb-2 block text-sm font-medium text-ink"
              >
                ML objective
              </label>
              <select
                id="objective"
                value={objective}
                onChange={(event) => setObjective(event.target.value)}
                className="w-full rounded-lg border border-surface-border bg-white px-3 py-2.5 text-sm text-ink"
              >
                {OBJECTIVES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="target-column"
                className="mb-2 block text-sm font-medium text-ink"
              >
                Target column
              </label>
              <select
                id="target-column"
                value={targetColumn}
                onChange={(event) => setTargetColumn(event.target.value)}
                disabled={objective === "clustering" || objective === "exploration"}
                className="w-full rounded-lg border border-surface-border bg-white px-3 py-2.5 text-sm text-ink disabled:opacity-50"
              >
                <option value="">Select a target</option>
                {columnNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="pipeline"
                className="mb-2 block text-sm font-medium text-ink"
              >
                Model family
              </label>
              <select
                id="pipeline"
                value={pipeline}
                onChange={(event) => setPipeline(event.target.value)}
                className="w-full rounded-lg border border-surface-border bg-white px-3 py-2.5 text-sm text-ink"
              >
                {PIPELINES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="test-size"
                className="mb-2 block text-sm font-medium text-ink"
              >
                Test set size
              </label>
              <select
                id="test-size"
                value={testSize}
                onChange={(event) => setTestSize(event.target.value)}
                className="w-full rounded-lg border border-surface-border bg-white px-3 py-2.5 text-sm text-ink"
              >
                <option value="10">10%</option>
                <option value="20">20%</option>
                <option value="25">25%</option>
                <option value="30">30%</option>
              </select>
            </div>
          </div>

          <label className="mt-5 flex items-start gap-3 rounded-xl bg-surface-page p-4">
            <input
              type="checkbox"
              checked={includeFeatureSelection}
              onChange={(event) =>
                setIncludeFeatureSelection(event.target.checked)
              }
              className="mt-1"
            />
            <span>
              <span className="block text-sm font-medium text-ink">
                Enable feature selection
              </span>
              <span className="mt-1 block text-xs text-ink-secondary">
                Allow the future training pipeline to select useful features.
                This setting is not applied until training is implemented.
              </span>
            </span>
          </label>

          {targetWarning && (
            <div className="mt-5 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <AlertTriangle size={18} className="mt-0.5 shrink-0" />
              <p>{targetWarning}</p>
            </div>
          )}

          {hasTarget && !targetWarning && (
            <div className="mt-5 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
              <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
              <p>
                Target selected: <strong>{targetColumn}</strong>.
                Confirm that this is the outcome you intend to predict.
              </p>
            </div>
          )}

          <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t border-surface-border pt-5">
            <div className="text-xs text-ink-secondary">
              <Settings2 size={15} className="mr-1 inline" />
              Objective: {titleCase(objective)} · Test set: {testSize}%
              {" · "}Pipeline: {titleCase(pipeline)}
            </div>

            <Button onClick={handleContinue}>
              Continue to training
              <ArrowRight size={16} className="ml-2" />
            </Button>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
