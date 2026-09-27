import request from "./api";

// POST /datasets/upload
export const uploadDataset = (formData) =>
  request("/datasets/upload", { method: "POST", body: formData, headers: {} });
