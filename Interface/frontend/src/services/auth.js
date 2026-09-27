import request from "./api";

// POST /auth/signup
export const signup = (payload) =>
  request("/auth/signup", { method: "POST", body: JSON.stringify(payload) });

// POST /auth/login
export const login = (payload) =>
  request("/auth/login", { method: "POST", body: JSON.stringify(payload) });
