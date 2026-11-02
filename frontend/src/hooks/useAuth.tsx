import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { auth as authApi } from "@/api/endpoints";
import { setUnauthorizedHandler, tokenStore } from "@/api/client";
import type { Me } from "@/types";

interface AuthCtx { user: Me | null; loading: boolean; login: (e: string, p: string) => Promise<void>; logout: () => Promise<void>; can: (perm: string) => boolean; }
const Ctx = createContext<AuthCtx>(null as never);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(!!tokenStore.get());
  const qc = useQueryClient();

  useEffect(() => { setUnauthorizedHandler(() => { setUser(null); qc.clear(); }); }, [qc]);
  useEffect(() => {
    if (!tokenStore.get()) return;
    authApi.me().then(setUser).catch(() => tokenStore.clear()).finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const r = await authApi.login(email, password);
    tokenStore.set(r.access_token);
    setUser(r.user);
  }, []);
  const logout = useCallback(async () => {
    try { await authApi.logout(); } catch { /* token may already be invalid */ }
    tokenStore.clear(); setUser(null); qc.clear();
  }, [qc]);
  const can = useCallback((perm: string) => !!user?.permissions.includes(perm), [user]);
  return <Ctx.Provider value={{ user, loading, login, logout, can }}>{children}</Ctx.Provider>;
}
export const useAuth = () => useContext(Ctx);
