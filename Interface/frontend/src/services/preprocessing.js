
import request, { BASE_URL } from "./api";

export function preprocessDataset(datasetId, options) {
  return request(`/preprocessing/${encodeURIComponent(datasetId)}`, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export async function getPreprocessingRuns(datasetId) {
  const data = await request(
    `/preprocessing/${encodeURIComponent(datasetId)}/runs`
  );
  return data.runs ?? [];
}

export function getPreprocessingRun(runId) {
  return request(`/preprocessing/runs/${encodeURIComponent(runId)}`);
}

export async function downloadPreprocessedCSV(runId, split) {
  const response = await fetch(
    `${BASE_URL}/preprocessing/runs/${encodeURIComponent(runId)}/download/${split}`,
    { credentials: "include" }
  );

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Download failed (${response.status})`);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `preprocessed_${split}_${runId}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
