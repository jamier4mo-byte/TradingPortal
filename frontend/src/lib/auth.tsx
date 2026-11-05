import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { api, ApiError, type User, unauthorised } from "./api.ts";

interface AuthState {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<unknown>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api.get<User>("/api/auth/me");
      } catch (err) {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) return null;
        throw err;
      }
    },
    staleTime: 60_000,
    retry: false,
  });

  useEffect(() => {
    const onUnauthorised = () => {
      qc.setQueryData(["me"], null);
    };
    unauthorised.addEventListener("unauthorised", onUnauthorised);
    return () => unauthorised.removeEventListener("unauthorised", onUnauthorised);
  }, [qc]);

  const user = query.data ?? null;
  useEffect(() => {
    document.documentElement.dataset.motion = user?.motion_pref ?? "full";
  }, [user?.motion_pref]);

  const value: AuthState = {
    user,
    loading: query.isPending,
    refresh: () => qc.invalidateQueries({ queryKey: ["me"] }),
    signOut: async () => {
      await api.post("/api/auth/logout");
      qc.setQueryData(["me"], null);
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
    },
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}

/** Wraps routes that need a signed-in user. Remembers where they were going. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (!user) return null;
  if (user.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}
