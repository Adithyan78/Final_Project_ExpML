
import request from "./api";

export function uploadDataset(file, targetColumn = "") {
  const formData = new FormData();
  formData.append("file", file);

  if (targetColumn.trim()) {
    formData.append("target_column", targetColumn.trim());
  }

  return request("/datasets", {
    method: "POST",
    body: formData,
  });
}

export async function getDatasets() {
  const data = await request("/datasets");
  return data.datasets ?? [];
}

export function getDataset(datasetId) {
  return request(`/datasets/${encodeURIComponent(datasetId)}`);
}

export function deleteDataset(datasetId) {
  return request(`/datasets/${encodeURIComponent(datasetId)}`, {
    method: "DELETE",
  });
}

export function getDashboardSummary() {
  return request("/dashboard/summary");
}
