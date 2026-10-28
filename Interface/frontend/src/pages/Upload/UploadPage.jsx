
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Trash2, Eye, RefreshCw, Check } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import Card, { CardHeader } from "../../components/common/Card";
import DropzoneUploader from "../../components/upload/DropzoneUploader";
import Button from "../../components/common/Button";
import { ROUTES } from "../../constants/routes";

import {
  uploadDataset,
  getDatasets,
  deleteDataset,
} from "../../services/datasets";

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

function formatSize(bytes) {
  if (typeof bytes !== "number") return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;

  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function UploadPage() {
  const navigate = useNavigate();

  const [uploads, setUploads] = useState([]);
  const [targetColumn, setTargetColumn] = useState("");
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadDatasets = useCallback(async () => {
    setError("");
    setLoading(true);

    try {
      const datasets = await getDatasets();

      setUploads(datasets);

      setSelectedDatasetId((currentId) => {
        if (currentId && datasets.some((ds) => ds.id === currentId)) {
          return currentId;
        }

        return datasets[0]?.id ?? "";
      });
    } catch (err) {
      setError(err.message || "Unable to load datasets.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDatasets();
  }, [loadDatasets]);

  const handleFileSelected = async (file) => {
    if (!file) return;

    setError("");
    setSuccess("");

    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Please select a CSV file.");
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setError("The maximum file size is 50 MB.");
      return;
    }

    setUploading(true);

    try {
      const dataset = await uploadDataset(file, targetColumn);

      setUploads((current) => [
        dataset,
        ...current.filter((item) => item.id !== dataset.id),
      ]);

      setSelectedDatasetId(dataset.id);
      setTargetColumn("");
      setSuccess(`${dataset.name} uploaded and analyzed successfully.`);
    } catch (err) {
      setError(err.message || "Dataset upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (dataset) => {
    const confirmed = window.confirm(
      `Delete "${dataset.name}"? This will permanently delete the stored CSV and its analysis profile.`
    );

    if (!confirmed) return;

    setError("");
    setSuccess("");
    setDeletingId(dataset.id);

    try {
      await deleteDataset(dataset.id);

      setUploads((current) =>
        current.filter((item) => item.id !== dataset.id)
      );

      setSelectedDatasetId((currentId) =>
        currentId === dataset.id
          ? uploads.find((item) => item.id !== dataset.id)?.id ?? ""
          : currentId
      );

      setSuccess(`${dataset.name} was deleted.`);
    } catch (err) {
      setError(err.message || "Unable to delete this dataset.");
    } finally {
      setDeletingId(null);
    }
  };

  const continueToPreprocessing = () => {
    if (!selectedDatasetId) {
      setError("Please select a dataset first.");
      return;
    }

    navigate(ROUTES.TRAINING, {
      state: { datasetId: selectedDatasetId },
    });
  };

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-[26px] font-semibold text-ink tracking-tight">
          Upload Dataset
        </h1>
        <p className="text-sm text-ink-secondary mt-1">
          Upload a CSV file to analyze its quality and prepare your AutoML pipeline.
        </p>
      </div>

      <Card className="mb-4">
        <label
          htmlFor="target-column"
          className="block text-sm font-medium text-ink mb-2"
        >
          Target column
        </label>

        <input
          id="target-column"
          type="text"
          value={targetColumn}
          onChange={(event) => setTargetColumn(event.target.value)}
          placeholder="e.g. Survived"
          disabled={uploading}
          className="w-full sm:max-w-md rounded-lg border border-surface-border bg-white px-3 py-2 text-sm text-ink outline-none focus:border-orange disabled:opacity-60"
        />

        <p className="text-xs text-ink-muted mt-2">
          Enter the exact column name you want to predict. Leave blank for
          profiling without a target. You can also choose an objective later.
        </p>
      </Card>

      <DropzoneUploader onFileSelected={handleFileSelected} />

      {uploading && (
        <div
          role="status"
          className="mt-4 rounded-lg border border-surface-border bg-surface-page p-4 text-sm text-ink-secondary"
        >
          Uploading and analyzing your dataset. Larger files may take a little
          longer...
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-state-error/30 bg-[#FCEAEA] p-3 text-sm text-state-error"
        >
          {error}
        </div>
      )}

      {success && (
        <div
          role="status"
          className="mt-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800"
        >
          {success}
        </div>
      )}

      <Card className="mt-6" padding="p-0">
        <div className="px-5 pt-5">
          <CardHeader
            title="Recent Uploads"
            subtitle="Select a dataset to analyze in your workspace"
            action={
              <button
                type="button"
                onClick={loadDatasets}
                disabled={loading || uploading}
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
                <th className="font-medium px-5 py-2.5">Select</th>
                <th className="font-medium px-5 py-2.5">Name</th>
                <th className="font-medium px-5 py-2.5">Rows</th>
                <th className="font-medium px-5 py-2.5">Columns</th>
                <th className="font-medium px-5 py-2.5">Uploaded At</th>
                <th className="font-medium px-5 py-2.5 text-right">Action</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-ink-muted">
                    Loading datasets...
                  </td>
                </tr>
              ) : uploads.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-ink-muted">
                    No datasets yet. Upload a CSV to get started.
                  </td>
                </tr>
              ) : (
                uploads.map((ds) => {
                  const selected = selectedDatasetId === ds.id;

                  return (
                    <tr
                      key={ds.id}
                      onClick={() => setSelectedDatasetId(ds.id)}
                      className={`border-t border-surface-border cursor-pointer transition-default ${
                        selected
                          ? "bg-orange-50/70"
                          : "hover:bg-surface-page/60"
                      }`}
                    >
                      <td className="px-5 py-3">
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedDatasetId(ds.id);
                          }}
                          aria-label={`Select ${ds.name}`}
                          aria-pressed={selected}
                          className={`flex h-6 w-6 items-center justify-center rounded-full border ${
                            selected
                              ? "border-orange bg-orange text-white"
                              : "border-surface-border text-transparent"
                          }`}
                        >
                          <Check size={13} />
                        </button>
                      </td>

                      <td className="px-5 py-3 font-medium text-ink whitespace-nowrap">
                        <div>{ds.name}</div>
                        {typeof ds.size_bytes === "number" && (
                          <div className="text-xs font-normal text-ink-muted mt-0.5">
                            {formatSize(ds.size_bytes)}
                          </div>
                        )}
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

                      <td className="px-5 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              navigate(ROUTES.TRAINING, {
                                state: { datasetId: ds.id },
                              });
                            }}
                            className="p-1.5 rounded-md text-ink-secondary hover:text-orange hover:bg-orange-50 transition-default"
                            aria-label={`Analyze ${ds.name}`}
                            title="Analyze this dataset"
                          >
                            <Eye size={15} />
                          </button>

                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDelete(ds);
                            }}
                            disabled={deletingId === ds.id || uploading}
                            className="p-1.5 rounded-md text-ink-secondary hover:text-state-error hover:bg-[#FCEAEA] transition-default disabled:opacity-40"
                            aria-label={`Delete ${ds.name}`}
                            title="Delete dataset"
                          >
                            {deletingId === ds.id ? (
                              <RefreshCw size={15} className="animate-spin" />
                            ) : (
                              <Trash2 size={15} />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="mt-6 flex flex-col items-end gap-2">
        <p className="text-xs text-ink-muted">
          {selectedDatasetId
            ? `Selected: ${uploads.find((ds) => ds.id === selectedDatasetId)?.name ?? "Dataset"}`
            : "Select a dataset to continue."}
        </p>

        <Button
          onClick={continueToPreprocessing}
          disabled={!selectedDatasetId || loading || uploading || Boolean(deletingId)}
        >
          Continue to Dataset Analyzer
        </Button>
      </div>
    </AppShell>
  );
}
