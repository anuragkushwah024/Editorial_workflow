import { createContext, useContext, useEffect, useState } from "react";
import api, { getToken, setToken } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // On page load, if we still have a token, ask the server who we are.
  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .get("/api/auth/me/")
      .then((response) => setUser(response.data))
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  async function login(email, password) {
    const response = await api.post("/api/auth/login/", { email, password });
    setToken(response.data.access);
    setUser(response.data.user);
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  const value = { user, loading, login, logout, isEditor: user !== null && user.role === "EDITOR" };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
