"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { EligibilityResult } from "@/components/EligibilityResult";
import { IconCheck, IconDrop, IconLocate, IconPin } from "@/components/icons";
import MapView from "@/components/MapView";
import { BloodGroupPicker, Button, EmptyState, ErrorMessage, Field, LoadingSpinner, PageTitle } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import type { BloodGroup, City, Donor, LatLng, SuggestedBank, TokenResponse } from "@/lib/types";

const STEPS = ["Your details", "Health checklist", "Consent", "Choose a blood bank"];
const HEALTH = [
  { key: "recent_illness", label: "I have been ill (fever, infection) in the last 2 weeks" },
  { key: "recent_surgery", label: "I had surgery or a major procedure in the last 6 months" },
  { key: "on_medication", label: "I am taking antibiotics or other regular medication" },
  { key: "chronic_condition", label: "I have a chronic condition (heart disease, diabetes on insulin, hepatitis, HIV)" },
] as const;
const FALLBACK_CENTER: LatLng = [23.0225, 72.5714];
const INTRO_STEPS = [
  "Confirm your phone number",
  "Tell us your details and where you live",
  "Answer four health questions",
  "Pick the blood bank you would donate at",
];
const CHECK_CARD =
  "flex min-h-12 cursor-pointer items-start gap-3 rounded-[var(--radius-control)] border border-line bg-white p-3.5 text-sm shadow-[var(--shadow-raise)] transition-colors hover:border-line-strong has-[:checked]:border-accent/40 has-[:checked]:bg-accent-tint-1";

export default function DonorRegisterPage() {
  const { ready, user, requireLogin, signIn } = useAuth();
  const cities = useApi<City[]>("/cities");

  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState<"M" | "F">("M");
  const [group, setGroup] = useState<BloodGroup>("O+");
  const [lastDonation, setLastDonation] = useState("");
  const [position, setPosition] = useState<LatLng | null>(null);
  const [health, setHealth] = useState<Record<string, boolean>>({});
  const [consent, setConsent] = useState(true);
  const [available, setAvailable] = useState(true);
  const [banks, setBanks] = useState<SuggestedBank[] | null>(null);
  const [bankId, setBankId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [registered, setRegistered] = useState<Donor | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);

  // After the phone login the dialog closes and the button that opened it is gone,
  // so put keyboard focus on the first step instead of the top of the page.
  const canRegister = user?.role === "public";
  useEffect(() => {
    if (canRegister) heading.current?.focus();
  }, [canRegister]);

  function go(next: number) {
    setError("");
    setStep(next);
    requestAnimationFrame(() => heading.current?.focus());
  }

  async function next(event: React.FormEvent) {
    event.preventDefault();
    if (step === 0 && !position) {
      setError("Choose where you live: use your location or tap the map.");
      return;
    }
    if (step < 2) return go(step + 1);
    if (step === 2) {
      // The nearest banks by road distance, from the chosen location.
      setBusy(true);
      setError("");
      try {
        const found = await api<SuggestedBank[]>("/donors/me/suggested-banks", { params: { lat: position![0], lng: position![1] } });
        setBanks(found);
        setBankId(found[0]?.id ?? "");
        go(3);
      } catch (e) {
        setError(errorMessage(e));
      } finally {
        setBusy(false);
      }
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await api<TokenResponse & { donor: Donor }>("/donors/register", {
        method: "POST",
        body: {
          name: name.trim(), age: Number(age), gender, blood_group: group, lat: position![0], lng: position![1],
          health_checklist: health, last_donation_date: lastDonation || null, contact_consent: consent, available,
          linked_bank_id: bankId || null,
        },
      });
      signIn(result);
      setRegistered(result.donor);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (!ready) return <LoadingSpinner />;

  if (registered) {
    return (
      <div className="mx-auto max-w-xl">
        <div className="mb-5 grid size-12 place-items-center rounded-full bg-[#eaf6ef] text-ok">
          <IconCheck size={26} />
        </div>
        <PageTitle title="You are registered">Thank you, {registered.name}. Your blood can now reach someone nearby when it is needed most.</PageTitle>
        <EligibilityResult donor={registered} />
        <dl className="mt-4 divide-y divide-line rounded-[var(--radius-panel)] border border-line bg-white text-sm shadow-[var(--shadow-raise)]">
          <div className="flex justify-between gap-4 px-4 py-3">
            <dt className="text-muted">Your blood bank</dt>
            <dd className="text-right font-semibold">{registered.linked_bank_name ?? "None yet"}</dd>
          </div>
          <div className="flex justify-between gap-4 px-4 py-3">
            <dt className="text-muted">Your donor ID</dt>
            <dd className="text-right font-semibold" data-testid="donor-id">
              {registered.id}
            </dd>
          </div>
        </dl>
        <p className="mt-3 text-sm text-muted">Give your donor ID to the blood bank when you donate, so the donation is recorded against your name.</p>
        <Link
          href="/donor/me"
          className="mt-6 inline-flex min-h-11 items-center rounded-[var(--radius-control)] bg-accent px-5 text-sm font-semibold text-white shadow-[var(--shadow-accent)] hover:bg-accent-dark"
        >
          Go to my donor profile
        </Link>
      </div>
    );
  }

  if (user?.role === "donor") {
    return (
      <div className="mx-auto max-w-xl">
        <PageTitle title="Become a donor" />
        <EmptyState title="You are already registered as a donor" icon={<IconDrop size={20} />}>
          <Link href="/donor/me" className="font-semibold text-accent underline underline-offset-2">
            Open my donor profile
          </Link>
        </EmptyState>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="mx-auto grid max-w-4xl gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] md:items-center">
        <div>
          <h1 className="text-[34px] font-semibold leading-[1.1] tracking-tight sm:text-[40px]">Become a blood donor</h1>
          <p className="mt-3 max-w-prose text-[16px] leading-relaxed text-muted">
            Register once. When a hospital or a family nearby needs your blood group and no blood bank has it, RaktSetu can show them your number, but only if
            you agree.
          </p>
          <ol className="mt-6 space-y-3 text-sm">
            {INTRO_STEPS.map((item, index) => (
              <li key={item} className="flex items-center gap-3">
                <span className="tabular grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-[13px] font-semibold text-accent-dark">
                  {index + 1}
                </span>
                {item}
              </li>
            ))}
          </ol>
        </div>
        <div className="rounded-[var(--radius-panel)] border border-line bg-white p-5 shadow-[var(--shadow-float)]">
          <p className="font-semibold">Start with your phone number</p>
          <p className="mt-1 text-sm leading-relaxed text-muted">It becomes your contact number. It is shown only to logged-in users, and every view is recorded.</p>
          <Button size="lg" className="mt-4 w-full" onClick={() => requireLogin()}>
            Log in with phone
          </Button>
        </div>
      </div>
    );
  }

  if (user.role !== "public") {
    return (
      <div className="mx-auto max-w-xl">
        <PageTitle title="Become a donor" />
        <EmptyState title="This is a staff account">Log out and log in with your phone number to register as a donor.</EmptyState>
      </div>
    );
  }

  const center = cities.data?.[0]?.center ?? FALLBACK_CENTER;
  return (
    <div className="mx-auto max-w-2xl">
      <PageTitle title="Become a donor">Signed in as {user.phone}.</PageTitle>

      <ol className="mb-6 grid grid-cols-4 gap-2" aria-label="Progress">
        {STEPS.map((label, index) => (
          <li key={label} aria-current={index === step ? "step" : undefined} className="min-w-0">
            <span aria-hidden="true" className={`block h-1 rounded-full transition-colors duration-300 ${index <= step ? "bg-accent" : "bg-line"}`} />
            <span aria-hidden="true" className={`mt-2 hidden text-xs sm:block ${index === step ? "font-semibold text-ink" : "text-muted"}`}>
              {index + 1}. {label}
            </span>
            <span className="sr-only">
              Step {index + 1}: {label}
              {index < step ? " (done)" : ""}
            </span>
          </li>
        ))}
      </ol>

      <form onSubmit={next} className="space-y-5 rounded-[var(--radius-panel)] border border-line bg-white p-4 shadow-[var(--shadow-float)] sm:p-6">
        <h2 ref={heading} tabIndex={-1} className="text-[19px] font-semibold tracking-tight">
          Step {step + 1} of {STEPS.length}: {STEPS[step]}
        </h2>

        {step === 0 && (
          <>
            <Field label="Full name">
              {(field) => <input {...field} name="name" autoComplete="name" required minLength={2} maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />}
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Age" hint="Donors must be 18 to 65.">
                {(field) => <input {...field} type="number" name="age" inputMode="numeric" min={1} max={120} required value={age} onChange={(e) => setAge(e.target.value)} />}
              </Field>
              <Field label="Gender" hint="Sets the gap between donations.">
                {(field) => (
                  <select {...field} name="gender" value={gender} onChange={(e) => setGender(e.target.value as "M" | "F")}>
                    <option value="M">Male</option>
                    <option value="F">Female</option>
                  </select>
                )}
              </Field>
            </div>
            <BloodGroupPicker value={group} onChange={setGroup} label="Your blood group" name="donor-group" />
            <Field label="Last donation, if any">
              {(field) => <input {...field} type="date" name="last_donation" value={lastDonation} onChange={(e) => setLastDonation(e.target.value)} />}
            </Field>
            <fieldset className="space-y-2">
              <legend className="mb-1.5 text-[13px] font-medium text-ink-soft">Where you live</legend>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="secondary"
                  onClick={() =>
                    navigator.geolocation?.getCurrentPosition(
                      (place) => setPosition([place.coords.latitude, place.coords.longitude]),
                      () => setError("Could not get your location. Tap the map instead."),
                    )
                  }
                >
                  <IconLocate size={18} className="text-you" />
                  Use my location
                </Button>
                <Button variant="secondary" onClick={() => setPosition(center)}>
                  <IconPin size={18} className="text-muted" />
                  Use city centre
                </Button>
              </div>
              <p className="text-[13px] text-muted" aria-live="polite">
                {position ? (
                  <>
                    Location set at{" "}
                    <span className="tabular">
                      {position[0].toFixed(4)}, {position[1].toFixed(4)}
                    </span>
                    .
                  </>
                ) : (
                  "Or tap the map to drop a pin."
                )}
              </p>
              <MapView label="Map to choose where you live" className="h-64" center={center} user={position} fit={position ? [position] : []} onPick={(lat, lng) => setPosition([lat, lng])} />
            </fieldset>
          </>
        )}

        {step === 1 && (
          <fieldset className="space-y-2">
            <legend className="mb-3 text-sm leading-relaxed text-muted">Tick everything that applies to you. If none apply, leave them all unticked.</legend>
            {HEALTH.map(({ key, label }) => (
              <label key={key} className={CHECK_CARD}>
                <input
                  type="checkbox"
                  name={key}
                  className="mt-0.5 size-5 shrink-0 accent-accent"
                  checked={health[key] ?? false}
                  onChange={(e) => setHealth({ ...health, [key]: e.target.checked })}
                />
                {label}
              </label>
            ))}
          </fieldset>
        )}

        {step === 2 && (
          <fieldset className="space-y-2">
            <legend className="sr-only">Consent</legend>
            <label className={CHECK_CARD}>
              <input type="checkbox" name="consent" className="mt-0.5 size-5 shrink-0 accent-accent" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>
                <span className="font-semibold">Share my phone number when my blood group is needed.</span>
                <span className="mt-0.5 block text-muted">Only logged-in users can see it, each view is recorded, and you can turn this off at any time.</span>
              </span>
            </label>
            <label className={CHECK_CARD}>
              <input type="checkbox" name="available" className="mt-0.5 size-5 shrink-0 accent-accent" checked={available} onChange={(e) => setAvailable(e.target.checked)} />
              <span>
                <span className="font-semibold">I am available to donate now.</span>
                <span className="mt-0.5 block text-muted">Switch this off when you are travelling or unwell.</span>
              </span>
            </label>
          </fieldset>
        )}

        {step === 3 && (
          <fieldset className="space-y-2">
            <legend className="mb-3 text-sm leading-relaxed text-muted">The blood banks nearest to you by road. Choose the one you would donate at.</legend>
            {banks?.length === 0 && <EmptyState title="No blood bank found near you">You can still register; a bank can be linked later.</EmptyState>}
            {banks?.map((bank, index) => (
              <label key={bank.id} className={`${CHECK_CARD} items-center`}>
                <input type="radio" name="bank" className="size-5 shrink-0 accent-accent" value={bank.id} checked={bankId === bank.id} onChange={() => setBankId(bank.id)} />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold [overflow-wrap:anywhere]">{bank.name}</span>
                  <span className="text-muted">
                    {bank.area}
                    {index === 0 ? ", the nearest" : ""}
                  </span>
                </span>
                <span className="tabular font-semibold">{bank.distance_km.toFixed(1)} km</span>
              </label>
            ))}
          </fieldset>
        )}

        <ErrorMessage>{error}</ErrorMessage>
        <div className="flex gap-2 border-t border-line pt-5">
          {step > 0 && (
            <Button variant="secondary" size="lg" onClick={() => go(step - 1)}>
              Back
            </Button>
          )}
          <Button type="submit" size="lg" busy={busy} className="flex-1">
            {step === 3 ? "Register as a donor" : "Continue"}
          </Button>
        </div>
      </form>
    </div>
  );
}
