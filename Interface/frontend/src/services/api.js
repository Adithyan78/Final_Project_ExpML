// Base API client. No real network calls are made yet — the app runs
// entirely on mock data (see src/mock/mockData.js). Once the FastAPI
// backend is live, point BASE_URL at it and swap mock imports in pages
// for calls into services/*.

export const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed with status ${res.status}`);
  }
  return res.json();
}

export default request;
