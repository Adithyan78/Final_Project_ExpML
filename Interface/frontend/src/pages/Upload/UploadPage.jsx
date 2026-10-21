
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Trash2, Eye, RefreshCw } from "lucide-react";

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

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleString();
}

function formatSize(bytes) {
  if (typeof bytes !== "number") return "";

  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function UploadPage() {
  const navigate = useNavigate();

  const [uploads, setUploads] = useState([]);
  const [targetColumn, setTargetColumn] = useState("");
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

      setTargetColumn("");
      setSuccess(
        `${dataset.name} uploaded and analyzed successfully.`
      );
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

      setSuccess(`${dataset.name} was deleted.`);
    } catch (err) {
      setError(err.message || "Unable to delete this dataset.");
    } finally {
      setDeletingId(null);
    }
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
          Target column (optional)
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
          Enter the exact column name you want to predict. Leave blank for profiling only.
        </p>
      </Card>

      <DropzoneUploader onFileSelected={handleFileSelected} />

      {uploading && (
        <div
          role="status"
          className="mt-4 rounded-lg border border-surface-border bg-surface-page p-4 text-sm text-ink-secondary"
        >
          Uploading and analyzing your dataset. Larger files may take a little longer...
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
            subtitle="Datasets saved to your workspace"
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
                  <td
                    colSpan={5}
                    className="px-5 py-8 text-center text-ink-muted"
                  >
                    Loading datasets...
                  </td>
                </tr>
              ) : uploads.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-5 py-8 text-center text-ink-muted"
                  >
                    No datasets yet. Upload a CSV to get started.
                  </td>
                </tr>
              ) : (
                uploads.map((ds) => (
                  <tr
                    key={ds.id}
                    className="border-t border-surface-border hover:bg-surface-page/60 transition-default"
                  >
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
                          onClick={() =>
                            navigate(ROUTES.TRAINING, {
                              state: { datasetId: ds.id },
                            })
                          }
                          className="p-1.5 rounded-md text-ink-secondary hover:text-orange hover:bg-orange-50 transition-default"
                          aria-label={`Use ${ds.name}`}
                          title="Continue with this dataset"
                        >
                          <Eye size={15} />
                        </button>

                        <button
                          type="button"
                          onClick={() => handleDelete(ds)}
                          disabled={deletingId === ds.id || uploading}
                          className="p-1.5 rounded-md text-ink-secondary hover:text-state-error hover:bg-[#FCEAEA] transition-default disabled:opacity-40"
                          aria-label={`Delete ${ds.name}`}
                          title="Delete dataset"
                        >
                          {deletingId === ds.id ? (
                            <RefreshCw
                              size={15}
                              className="animate-spin"
                            />
                          ) : (
                            <Trash2 size={15} />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="flex justify-end mt-6">
        <Button
          onClick={() => navigate(ROUTES.TRAINING)}
          disabled={uploads.length === 0 || uploading}
        >
          Continue to Preprocessing
        </Button>
      </div>
    </AppShell>
  );
}
