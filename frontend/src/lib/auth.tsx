import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, session, setUnauthorizedHandler, type User } from "./api";

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const generation = useRef(0);

  const logout = useCallback(() => {
    ++generation.current;
    session.token = null;
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    let active = true;
    const current = generation.current;
    const token = session.token;
    const isCurrent = () => active && generation.current === current && session.token === token;
    if (!session.token) {
      setReady(true);
      return () => { active = false; };
    }
    api.me().then(user => { if (isCurrent()) setUser(user); })
      .catch(() => { if (isCurrent()) logout(); })
      .finally(() => { if (active) setReady(true); });
    return () => { active = false; };
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const current = ++generation.current;
    const r = await api.login(email, password);
    if (current !== generation.current) throw new Error("Запрос входа уже неактуален. Повторите вход.");
    session.token = r.access_token;
    setUser(r.user);
    setReady(true);
    return r.user;
  }, []);

  return <AuthContext.Provider value={{ user, ready, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside provider");
  return ctx;
}
