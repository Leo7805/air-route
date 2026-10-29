import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { api } from "../lib/api";
import type { Account } from "../types/api";

const TOKEN_KEY = "airroute_access_token";

interface AuthContextValue {
  account: Account | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  );
  const [account, setAccount] = useState<Account | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(token));
  const sessionVersion = useRef(0);
  const validatedToken = useRef<string | null>(null);

  const logout = useCallback(() => {
    sessionVersion.current += 1;
    validatedToken.current = null;
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setAccount(null);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    return () => {
      // Invalidate login requests too, even when no restoration is running.
      sessionVersion.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!token) {
      return;
    }

    if (validatedToken.current === token) {
      return;
    }

    const version = ++sessionVersion.current;
    const controller = new AbortController();
    setIsLoading(true);
    api
      .me(token, controller.signal)
      .then((currentAccount) => {
        if (
          version === sessionVersion.current &&
          token === localStorage.getItem(TOKEN_KEY)
        ) {
          validatedToken.current = token;
          setAccount(currentAccount);
        }
      })
      .catch((reason: unknown) => {
        if (
          reason instanceof DOMException &&
          reason.name === "AbortError"
        ) {
          return;
        }
        if (
          version === sessionVersion.current &&
          token === localStorage.getItem(TOKEN_KEY)
        ) {
          logout();
        }
      })
      .finally(() => {
        if (version === sessionVersion.current) {
          setIsLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [logout, token]);

  const login = useCallback(async (username: string, password: string) => {
    // A replacement login must never retain the previous account on failure.
    logout();
    const version = sessionVersion.current;
    setIsLoading(true);
    try {
      const { access_token } = await api.login(username, password);
      if (version !== sessionVersion.current) {
        return;
      }
      const currentAccount = await api.me(access_token);

      if (version !== sessionVersion.current) {
        return;
      }

      localStorage.setItem(TOKEN_KEY, access_token);
      validatedToken.current = access_token;
      setToken(access_token);
      setAccount(currentAccount);
      setIsLoading(false);
    } catch (reason) {
      if (version === sessionVersion.current) {
        setIsLoading(false);
      }
      throw reason;
    }
  }, [logout]);

  const value = useMemo(
    () => ({
      account,
      token,
      isLoading,
      isAuthenticated: Boolean(account && token),
      login,
      logout,
    }),
    [account, isLoading, login, logout, token],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
