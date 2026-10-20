import { createContext, useContext, useEffect, useState } from "react";
import { api, clearToken, getToken, setToken } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // If a token is saved, check it's still valid before showing anything
  const [checking, setChecking] = useState(Boolean(getToken()));

  useEffect(() => {
    if (!getToken()) return;
    api
      .me()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => {
    const handleLogout = () => setUser(null);
    window.addEventListener("auth:logout", handleLogout);
    return () => window.removeEventListener("auth:logout", handleLogout);
  }, []);

  async function login(username, password) {
    clearToken(); // an old, invalid token would make the login request fail
    const { token } = await api.login(username, password);
    setToken(token);
    setUser(await api.me());
  }

  async function register(username, email, password) {
    clearToken();
    const data = await api.register(username, email, password);
    setToken(data.token);
    setUser(data.user);
  }

  async function logout() {
    try {
      await api.logout();
    } catch {
      // Even if the server call fails, log out locally
    }
    clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, checking, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
