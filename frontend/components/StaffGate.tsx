"use client";

import { useState } from "react";

import { Button, Card, ErrorMessage, Field, LoadingSpinner, PageTitle } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Role, TokenResponse } from "@/lib/types";

interface Props {
  role: Extract<Role, "hospital" | "bank_admin" | "admin">;
  title: string;
  demoEmail: string;
  /** Extra help shown under the demo account line. */
  note?: React.ReactNode;
  children: React.ReactNode;
}

/** Shows its children only to a logged-in account with the right role; otherwise the email + password form. */
export function StaffGate({ role, title, demoEmail, note, children }: Props) {
  const { ready, user, signIn, signOut } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!ready) return <LoadingSpinner />;
  if (user?.role === role) return <>{children}</>;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session = await api<TokenResponse>("/auth/login", { method: "POST", body: { email, password } });
      if (session.user.role !== role) setError(`That account cannot use this page (it is a ${session.user.role.replace("_", " ")} account).`);
      else signIn(session);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <PageTitle title={title}>Log in with your staff account.</PageTitle>
      {user && (
        <p className="mb-3 text-sm text-muted">
          You are logged in with a different kind of account.{" "}
          <Button variant="ghost" onClick={signOut}>
            Log out
          </Button>
        </p>
      )}
      <Card>
        <form onSubmit={submit} className="space-y-3">
          <Field label="Email">
            {(field) => (
              <input {...field} type="email" name="email" autoComplete="username" spellCheck={false} required value={email} onChange={(e) => setEmail(e.target.value)} />
            )}
          </Field>
          <Field label="Password">
            {(field) => (
              <input {...field} type="password" name="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            )}
          </Field>
          <ErrorMessage>{error}</ErrorMessage>
          <Button type="submit" busy={busy} className="w-full">
            Log in
          </Button>
        </form>
      </Card>
      <p className="mt-3 text-xs text-muted">
        Demo account: <span className="font-mono">{demoEmail}</span>, password <span className="font-mono">raktsetu123</span>.{" "}
        <Button
          variant="ghost"
          onClick={() => {
            setEmail(demoEmail);
            setPassword("raktsetu123");
          }}
        >
          Fill in
        </Button>
      </p>
      {note && <p className="mt-2 text-xs text-muted">{note}</p>}
    </div>
  );
}
