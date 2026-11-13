"use client";

import { useState } from "react";

import { IconBank, IconHospital, IconShield } from "@/components/icons";
import { Button, ErrorMessage, Field, LoadingSpinner } from "@/components/ui";
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

  const RoleIcon = role === "hospital" ? IconHospital : role === "bank_admin" ? IconBank : IconShield;

  return (
    <div className="mx-auto max-w-[25rem] pt-2 sm:pt-8">
      <div className="mb-6 text-center">
        <span aria-hidden="true" className="mx-auto mb-4 grid size-12 place-items-center rounded-[14px] bg-accent-soft text-accent ring-1 ring-inset ring-accent/15">
          <RoleIcon size={24} />
        </span>
        <h1 className="text-[26px] font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-[15px] text-muted">Log in with your staff account.</p>
      </div>
      {user && (
        <div className="mb-4 rounded-[var(--radius-control)] bg-surface px-3.5 py-2.5 text-sm text-ink-soft">
          You are logged in with a different kind of account.{" "}
          <Button variant="ghost" onClick={signOut}>
            Log out
          </Button>
        </div>
      )}
      <form onSubmit={submit} className="space-y-4 rounded-[var(--radius-panel)] border border-line bg-white p-5 shadow-[var(--shadow-float)] sm:p-6">
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
        <Button type="submit" size="lg" busy={busy} className="w-full">
          Log in
        </Button>
      </form>
      <div className="mt-4 rounded-[var(--radius-panel)] border border-dashed border-line-strong px-4 py-3 text-[13px] leading-relaxed text-muted">
        <p>
          Demo account: <span className="font-semibold text-ink-soft [overflow-wrap:anywhere]">{demoEmail}</span>, password{" "}
          <span className="font-semibold text-ink-soft">raktsetu123</span>.{" "}
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
        {note && <p className="mt-2">{note}</p>}
      </div>
    </div>
  );
}
