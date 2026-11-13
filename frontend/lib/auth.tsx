"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { OtpLoginModal } from "@/components/OtpLoginModal";
import { api, getToken, setToken } from "@/lib/api";
import type { TokenResponse, User } from "@/lib/types";

interface AuthValue {
  /** False until the saved session has been checked (avoids a login flash). */
  ready: boolean;
  user: User | null;
  /** Save a session returned by a login or register call. */
  signIn: (session: TokenResponse) => void;
  signOut: () => void;
  /** Resolves true once someone is logged in, opening the OTP dialog if needed. */
  requireLogin: () => Promise<boolean>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [otpOpen, setOtpOpen] = useState(false);
  const waiting = useRef<((ok: boolean) => void)[]>([]);

  useEffect(() => {
    let ignore = false;
    if (!getToken()) {
      queueMicrotask(() => !ignore && setReady(true));
      return;
    }
    api<User>("/auth/me")
      .then((me) => !ignore && setUser(me))
      .catch(() => setToken(null))
      .finally(() => !ignore && setReady(true));
    return () => {
      ignore = true;
    };
  }, []);

  const signIn = useCallback((session: TokenResponse) => {
    setToken(session.token);
    setUser(session.user);
  }, []);

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const settle = useCallback((ok: boolean) => {
    setOtpOpen(false);
    waiting.current.forEach((resolve) => resolve(ok));
    waiting.current = [];
  }, []);

  const requireLogin = useCallback(() => {
    if (user) return Promise.resolve(true);
    setOtpOpen(true);
    return new Promise<boolean>((resolve) => waiting.current.push(resolve));
  }, [user]);

  const value = useMemo(
    () => ({ ready, user, signIn, signOut, requireLogin }),
    [ready, user, signIn, signOut, requireLogin],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
      {otpOpen && (
        <OtpLoginModal
          onSuccess={(session) => {
            signIn(session);
            settle(true);
          }}
          onClose={() => settle(false)}
        />
      )}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
