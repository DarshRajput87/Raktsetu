"use client";

import { useEffect, useRef, useState } from "react";

import { IconPhone } from "@/components/icons";
import { Button, ErrorMessage, Field } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { TokenResponse } from "@/lib/types";

interface Props {
  onSuccess: (session: TokenResponse) => void;
  onClose: () => void;
}

/** Phone number, then the 6-digit code. Uses <dialog> so focus stays inside and Esc closes it. */
export function OtpLoginModal({ onSuccess, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [devOtp, setDevOtp] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal();
  }, []);

  async function sendCode(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const sent = await api<{ dev_otp: string | null }>("/auth/otp/send", { method: "POST", body: { phone } });
      setDevOtp(sent.dev_otp);
      // Development: no SMS is sent, so fill the code in. Real SMS codes are filled by the
      // browser (WebOTP on Android, the keyboard suggestion on iOS), see the effect below.
      setOtp(sent.dev_otp ?? "");
      setStep("code");
    } catch (e) {
      setError(errorMessage(e).replace(/^phone: .*/, "Enter a valid phone number, for example +91-00000-12345."));
    } finally {
      setBusy(false);
    }
  }

  // WebOTP (Chrome on Android): read the code from the incoming SMS and log in with it.
  // Needs an SMS whose last line is "@<site> #<code>", which the backend sends.
  const codeForm = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (step !== "code" || devOtp || !("OTPCredential" in window)) return;
    const controller = new AbortController();
    navigator.credentials
      .get({ otp: { transport: ["sms"] }, signal: controller.signal } as CredentialRequestOptions)
      .then((credential) => {
        const code = (credential as (Credential & { code?: string }) | null)?.code;
        if (!code) return;
        setOtp(code);
        requestAnimationFrame(() => codeForm.current?.requestSubmit());
      })
      .catch(() => {
        /* aborted, or the user typed the code instead */
      });
    return () => controller.abort();
  }, [step, devOtp]);

  async function verify(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSuccess(await api<TokenResponse>("/auth/otp/verify", { method: "POST", body: { phone, otp } }));
    } catch (e) {
      setError(errorMessage(e).replace(/^otp: .*/, "The code has 6 digits."));
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      aria-labelledby="otp-title"
      className="m-auto w-[calc(100%-2rem)] max-w-sm rounded-[var(--radius-panel)] border border-line bg-white p-6 text-ink shadow-[0_24px_64px_-12px_rgb(27_35_51/0.35)]"
    >
      <span aria-hidden="true" className="mb-4 grid size-11 place-items-center rounded-[13px] bg-accent-soft text-accent ring-1 ring-inset ring-accent/15">
        <IconPhone size={22} />
      </span>
      <h2 id="otp-title" className="text-[20px] font-semibold tracking-tight">
        Log in with your phone
      </h2>
      <p className="mt-1.5 text-sm leading-relaxed text-muted">
        Donor phone numbers are shown only to logged-in users, and every view is recorded.
      </p>

      {step === "phone" ? (
        <form onSubmit={sendCode} className="mt-4 space-y-3">
          <Field label="Phone number">
            {(field) => (
              <input
                {...field}
                type="tel"
                name="phone"
                autoComplete="tel"
                inputMode="tel"
                required
                autoFocus
                placeholder="+91-00000-12345"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            )}
          </Field>
          <ErrorMessage>{error}</ErrorMessage>
          <div className="flex gap-2">
            <Button type="submit" busy={busy} className="flex-1">
              Send code
            </Button>
            <Button variant="secondary" onClick={() => dialog.current?.close()}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <form ref={codeForm} onSubmit={verify} className="mt-4 space-y-3">
          <Field
            label={`Code sent to ${phone}`}
            hint={devOtp ? "Development mode: no SMS is sent, so the code was filled in for you." : "The code is valid for 5 minutes. On most phones it fills in by itself when the SMS arrives."}
          >
            {(field) => (
              <input
                {...field}
                name="otp"
                inputMode="numeric"
                autoComplete="one-time-code"
                required
                autoFocus
                maxLength={6}
                placeholder="6 digits"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
              />
            )}
          </Field>
          <ErrorMessage>{error}</ErrorMessage>
          <div className="flex gap-2">
            <Button type="submit" busy={busy} className="flex-1">
              Log in
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setStep("phone");
                setOtp("");
                setError("");
              }}
            >
              Back
            </Button>
          </div>
        </form>
      )}
    </dialog>
  );
}
