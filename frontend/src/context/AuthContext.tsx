import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, tokenStore } from "../api/client";
import type { AppConfig, User } from "../api/types";

interface AuthState {
  user: User | null;
  config: AppConfig | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { name: string; email: string; password: string; phone?: string; city?: string }) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    if (!tokenStore.get()) return setUser(null);
    try {
      setUser(await api<User>("/auth/me"));
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    Promise.all([refreshUser(), api<AppConfig>("/meta/config").then(setConfig)]).finally(() => setLoading(false));
  }, [refreshUser]);

  const handleToken = (res: { access_token: string; user: User }) => {
    tokenStore.set(res.access_token);
    setUser(res.user);
  };

  const value: AuthState = {
    user,
    config,
    loading,
    refreshUser,
    login: async (email, password) =>
      handleToken(await api("/auth/login", { method: "POST", json: { email, password } })),
    register: async (data) => handleToken(await api("/auth/register", { method: "POST", json: data })),
    logout: () => {
      tokenStore.clear();
      setUser(null);
    },
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function useCountries() {
  const { config } = useAuth();
  const countries = config?.countries ?? [];
  const name = (code: string) => countries.find((c) => c.code === code)?.name ?? code;
  return { countries, abroad: countries.filter((c) => c.code !== "IN"), name };
}
