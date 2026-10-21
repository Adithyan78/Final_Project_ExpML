
import request from "./api";

export const signup = (payload) =>
  request("/auth/signup", {
    method: "POST",
    body: JSON.stringify({
      name: payload.name,
      email: payload.email,
      password: payload.password,
    }),
  });

export const login = (payload) =>
  request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: payload.email,
      password: payload.password,
    }),
  });

export const getCurrentUser = () =>
  request("/auth/me");

export const logout = () =>
  request("/auth/logout", {
    method: "POST",
  });
