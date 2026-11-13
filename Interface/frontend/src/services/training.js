
import request, { BASE_URL } from "./api";

export const startTraining = (preprocessingRunId, config = {}) =>
  request(`/training/${encodeURIComponent(preprocessingRunId)}`, {
    method: "POST",
    body: JSON.stringify({ config }),
  });

export const getTrainingRun = (trainingRunId) =>
  request(`/training/runs/${encodeURIComponent(trainingRunId)}`);

export const getTrainingLeaderboard = (trainingRunId) =>
  request(
    `/training/runs/${encodeURIComponent(trainingRunId)}/leaderboard`
  );

export const getTrainingArtifacts = (trainingRunId) =>
  request(
    `/training/runs/${encodeURIComponent(trainingRunId)}/artifacts`
  );

export async function downloadTrainingArtifact(trainingRunId, filename) {
  const params = new URLSearchParams({ artifact_path: filename });

  const response = await fetch(
    `${BASE_URL}/training/runs/${encodeURIComponent(trainingRunId)}/artifacts/download?${params}`,
    { credentials: "include" }
  );

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      data.detail || `Artifact download failed (${response.status})`
    );
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename.split("/").pop() || filename;
  document.body.appendChild(link);
  link.click();
  link.remove();

  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
