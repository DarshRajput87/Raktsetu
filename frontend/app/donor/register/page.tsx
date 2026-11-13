"use client";

import Link from "next/link";
import { useRef, useState } from "react";

import { EligibilityResult } from "@/components/EligibilityResult";
import MapView from "@/components/MapView";
import { BloodGroupSelect, Button, Card, EmptyState, ErrorMessage, Field, LoadingSpinner, PageTitle } from "@/components/ui";
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
        <PageTitle title="You are registered">Thank you, {registered.name}.</PageTitle>
        <EligibilityResult donor={registered} />
        <p className="mt-4 text-sm">
          Your blood bank: <span className="font-semibold">{registered.linked_bank_name ?? "none"}</span>. Your donor ID is{" "}
          <span className="font-mono">{registered.id}</span>: give it to the bank when you donate.
        </p>
        <Link href="/donor/me" className="mt-4 inline-flex min-h-11 items-center rounded-lg bg-accent px-4 text-sm font-semibold text-white hover:bg-accent-dark">
          Go to my donor profile
        </Link>
      </div>
    );
  }

  if (user?.role === "donor") {
    return (
      <div className="mx-auto max-w-xl">
        <PageTitle title="Become a donor" />
        <EmptyState title="You are already registered as a donor">
          <Link href="/donor/me" className="text-accent underline">
            Open my donor profile
          </Link>
        </EmptyState>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="mx-auto max-w-xl">
        <PageTitle title="Become a donor">Register once. A blood bank or a patient nearby can reach you when your group is needed.</PageTitle>
        <Card>
          <p className="text-sm">First confirm your phone number. It becomes your contact number, shown only to logged-in users and only if you agree.</p>
          <Button className="mt-3" onClick={() => requireLogin()}>
            Log in with phone
          </Button>
        </Card>
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
    <div className="mx-auto max-w-xl">
      <PageTitle title="Become a donor">Signed in as {user.phone}.</PageTitle>
      <ol className="mb-4 flex gap-1" aria-label="Progress">
        {STEPS.map((label, index) => (
          <li key={label} aria-current={index === step ? "step" : undefined} className={`h-1.5 flex-1 rounded-full ${index <= step ? "bg-accent" : "bg-line"}`}>
            <span className="sr-only">
              Step {index + 1}: {label}
              {index < step ? " (done)" : ""}
            </span>
          </li>
        ))}
      </ol>

      <form onSubmit={next} className="space-y-4">
        <h2 ref={heading} tabIndex={-1} className="text-lg font-bold">
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
              <BloodGroupSelect value={group} onChange={(e) => setGroup(e.target.value as BloodGroup)} />
              <Field label="Last donation (if any)">
                {(field) => <input {...field} type="date" name="last_donation" value={lastDonation} onChange={(e) => setLastDonation(e.target.value)} />}
              </Field>
            </div>
            <fieldset>
              <legend className="mb-1 text-sm font-medium">Where you live</legend>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  onClick={() =>
                    navigator.geolocation?.getCurrentPosition(
                      (place) => setPosition([place.coords.latitude, place.coords.longitude]),
                      () => setError("Could not get your location. Tap the map instead."),
                    )
                  }
                >
                  Use my location
                </Button>
                <Button variant="secondary" onClick={() => setPosition(center)}>
                  Use city centre
                </Button>
              </div>
              <p className="mb-2 text-xs text-muted" aria-live="polite">
                {position ? `Location set: ${position[0].toFixed(4)}, ${position[1].toFixed(4)}.` : "Or tap the map to drop a pin."}
              </p>
              <MapView label="Map to choose where you live" className="h-64" center={center} user={position} fit={position ? [position] : []} onPick={(lat, lng) => setPosition([lat, lng])} />
            </fieldset>
          </>
        )}

        {step === 1 && (
          <fieldset className="space-y-2">
            <legend className="mb-2 text-sm text-muted">Tick everything that applies to you. If none apply, leave all unticked.</legend>
            {HEALTH.map(({ key, label }) => (
              <label key={key} className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border border-line p-3 text-sm">
                <input type="checkbox" name={key} className="mt-0.5 size-5 accent-accent" checked={health[key] ?? false} onChange={(e) => setHealth({ ...health, [key]: e.target.checked })} />
                {label}
              </label>
            ))}
          </fieldset>
        )}

        {step === 2 && (
          <fieldset className="space-y-2">
            <legend className="sr-only">Consent</legend>
            <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-line p-3 text-sm">
              <input type="checkbox" name="consent" className="mt-0.5 size-5 accent-accent" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>
                <span className="font-medium">Share my phone number when my blood group is needed.</span>
                <span className="block text-muted">Only logged-in users can see it, each view is recorded, and you can turn this off at any time.</span>
              </span>
            </label>
            <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-line p-3 text-sm">
              <input type="checkbox" name="available" className="mt-0.5 size-5 accent-accent" checked={available} onChange={(e) => setAvailable(e.target.checked)} />
              <span>
                <span className="font-medium">I am available to donate now.</span>
                <span className="block text-muted">Switch this off when you are travelling or unwell.</span>
              </span>
            </label>
          </fieldset>
        )}

        {step === 3 && (
          <fieldset className="space-y-2">
            <legend className="mb-2 text-sm text-muted">The blood banks nearest to you by road. Choose the one you would donate at.</legend>
            {banks?.length === 0 && <EmptyState title="No blood bank found near you">You can still register; a bank can be linked later.</EmptyState>}
            {banks?.map((bank, index) => (
              <label key={bank.id} className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-line p-3 text-sm has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
                <input type="radio" name="bank" className="size-5 accent-accent" value={bank.id} checked={bankId === bank.id} onChange={() => setBankId(bank.id)} />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium [overflow-wrap:anywhere]">{bank.name}</span>
                  <span className="text-muted">
                    {bank.area}
                    {index === 0 ? " · nearest" : ""}
                  </span>
                </span>
                <span className="tabular font-semibold">{bank.distance_km.toFixed(1)} km</span>
              </label>
            ))}
          </fieldset>
        )}

        <ErrorMessage>{error}</ErrorMessage>
        <div className="flex gap-2">
          {step > 0 && (
            <Button variant="secondary" onClick={() => go(step - 1)}>
              Back
            </Button>
          )}
          <Button type="submit" busy={busy} className="flex-1">
            {step === 3 ? "Register as a donor" : "Continue"}
          </Button>
        </div>
      </form>
    </div>
  );
}
