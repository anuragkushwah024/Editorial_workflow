import axios from "axios";

// The backend URL comes from an environment variable so the same build works
// locally (http://localhost:8000) and on Vercel (the Render URL).
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

const TOKEN_KEY = "editorial_access_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Storage can be blocked (private mode); the user just has to log in again.
  }
}

// Attach the JWT to every request.
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = "Bearer " + token;
  }
  return config;
});

// Turn a DRF error response into one readable message for the UI.
export function errorMessage(error) {
  const data = error.response && error.response.data;
  if (!data) {
    return "Could not reach the server. It may be waking up, try again in a minute.";
  }
  if (typeof data === "string") {
    return data;
  }
  if (data.detail) {
    return data.detail;
  }
  // Field errors look like {"name": ["A section with this name already exists."]}.
  const parts = [];
  for (const field of Object.keys(data)) {
    const value = data[field];
    if (Array.isArray(value)) {
      parts.push(value.join(" "));
    } else {
      parts.push(String(value));
    }
  }
  return parts.join(" ");
}

export default api;
