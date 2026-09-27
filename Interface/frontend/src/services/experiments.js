import request from "./api";

export const listProjects = () => request("/projects");
export const listExperiments = () => request("/experiments");

export const analyzeExperiment = (id) =>
  request(`/experiments/${id}/analyze`, { method: "POST" });

export const preprocessExperiment = (id, config) =>
  request(`/experiments/${id}/preprocess`, {
    method: "POST",
    body: JSON.stringify(config),
  });

export const selectFeatures = (id) =>
  request(`/experiments/${id}/select-features`, { method: "POST" });

export const trainExperiment = (id, config) =>
  request(`/experiments/${id}/train`, {
    method: "POST",
    body: JSON.stringify(config),
  });

export const getMetrics = (id) => request(`/experiments/${id}/metrics`);

export const explainExperiment = (id) =>
  request(`/experiments/${id}/explain`, { method: "POST" });

export const chatWithExperiment = (id, message) =>
  request(`/experiments/${id}/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });

export const getSummary = (id) => request(`/experiments/${id}/summary`);
export const getReport = (id) => request(`/experiments/${id}/report`);
