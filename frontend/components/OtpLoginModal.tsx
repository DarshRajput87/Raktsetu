"use client";

import { useEffect, useRef, useState } from "react";

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
      setStep("code");
    } catch (e) {
      setError(errorMessage(e).replace(/^phone: .*/, "Enter a valid phone number, for example +91-00000-12345."));
    } finally {
      setBusy(false);
    }
  }

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
      className="m-auto w-[calc(100%-2rem)] max-w-sm rounded-xl border border-line p-5 text-ink"
    >
      <h2 id="otp-title" className="text-lg font-bold">
        Log in with your phone
      </h2>
      <p className="mt-1 text-sm text-muted">
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
        <form onSubmit={verify} className="mt-4 space-y-3">
          <Field
            label={`Code sent to ${phone}`}
            hint={devOtp ? `Development mode, no SMS is sent. Your code is ${devOtp}.` : "The code is valid for 5 minutes."}
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
