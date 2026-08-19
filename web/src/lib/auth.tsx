"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, getToken, setToken } from "@/lib/api";

export type HiitUser = {
  id: string;
  username?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  photo_url?: string | null;
  is_admin?: boolean;
};

type Quota = {
  tier: string;
  allowed: boolean;
  used: number;
  limit: number | null;
  day: string;
  topup_amount: number;
};

type AuthState = {
  ready: boolean;
  token: string | null;
  user: HiitUser | null;
  quota: Quota | null;
  botUsername: string;
  inTelegram: boolean;
  accessAllowed: boolean | null;
  channelJoinUrl: string | null;
  login: (token: string, user: HiitUser) => void;
  logout: () => void;
  refreshMe: () => Promise<void>;
  refreshAccess: () => Promise<void>;
  authWithInitData: (initData: string) => Promise<void>;
  authWithLoginWidget: (payload: Record<string, unknown>) => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [token, setTok] = useState<string | null>(null);
  const [user, setUser] = useState<HiitUser | null>(null);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [botUsername, setBotUsername] = useState("HiiTRadioBot");
  const [inTelegram, setInTelegram] = useState(false);
  const [accessAllowed, setAccessAllowed] = useState<boolean | null>(null);
  const [channelJoinUrl, setChannelJoinUrl] = useState<string | null>(null);

  const login = useCallback((t: string, u: HiitUser) => {
    setToken(t);
    setTok(t);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setTok(null);
    setUser(null);
    setQuota(null);
    setAccessAllowed(null);
  }, []);

  const refreshMe = useCallback(async () => {
    const me = await api<{
      user: HiitUser;
      quota: Quota;
      bot_username: string;
    }>("/me");
    setUser(me.user);
    setQuota(me.quota);
    setBotUsername(me.bot_username);
  }, []);

  const refreshAccess = useCallback(async () => {
    const a = await api<{
      allowed: boolean;
      join_url?: string;
    }>("/access");
    setAccessAllowed(a.allowed);
    setChannelJoinUrl(a.join_url || null);
  }, []);

  const authWithInitData = useCallback(
    async (initData: string) => {
      const res = await api<{ token: string; user: HiitUser }>(
        "/auth/telegram-webapp",
        {
          method: "POST",
          body: JSON.stringify({ initData }),
          auth: false,
        },
      );
      login(res.token, res.user);
    },
    [login],
  );

  const authWithLoginWidget = useCallback(
    async (payload: Record<string, unknown>) => {
      const res = await api<{ token: string; user: HiitUser }>(
        "/auth/telegram-login",
        {
          method: "POST",
          body: JSON.stringify(payload),
          auth: false,
        },
      );
      login(res.token, res.user);
    },
    [login],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const tg = typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;
      const hasTg = Boolean(tg?.initData);
      setInTelegram(hasTg);
      if (tg) {
        try {
          tg.ready();
          tg.expand();
        } catch {
          /* ignore */
        }
      }

      try {
        if (hasTg && tg?.initData) {
          await authWithInitData(tg.initData);
        } else {
          const existing = getToken();
          if (existing) {
            setTok(existing);
            await refreshMe();
          }
        }
        if (getToken()) {
          await refreshMe();
          await refreshAccess();
        }
      } catch (e) {
        console.error(e);
        logout();
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authWithInitData, logout, refreshAccess, refreshMe]);

  const value = useMemo(
    () => ({
      ready,
      token,
      user,
      quota,
      botUsername,
      inTelegram,
      accessAllowed,
      channelJoinUrl,
      login,
      logout,
      refreshMe,
      refreshAccess,
      authWithInitData,
      authWithLoginWidget,
    }),
    [
      ready,
      token,
      user,
      quota,
      botUsername,
      inTelegram,
      accessAllowed,
      channelJoinUrl,
      login,
      logout,
      refreshMe,
      refreshAccess,
      authWithInitData,
      authWithLoginWidget,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside provider");
  return ctx;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        ready: () => void;
        expand: () => void;
        openInvoice?: (url: string, cb?: (status: string) => void) => void;
        openTelegramLink?: (url: string) => void;
        openLink?: (url: string) => void;
        themeParams?: Record<string, string>;
        colorScheme?: string;
      };
    };
    onTelegramAuth?: (user: Record<string, unknown>) => void;
  }
}
