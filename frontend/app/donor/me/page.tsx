"use client";

import Link from "next/link";
import { useState } from "react";

import { EligibilityResult } from "@/components/EligibilityResult";
import { IconDrop } from "@/components/icons";
import { EmptyState, ErrorMessage, LoadingSpinner, Notice, PageTitle, SectionTitle, Skeleton, formatDate } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { COMPONENT_LABELS, type Component, type Donor } from "@/lib/types";

export default function DonorProfilePage() {
  const { ready, user, requireLogin } = useAuth();
  const isDonor = user?.role === "donor";
  const profile = useApi<Donor>(isDonor ? "/donors/me" : null);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function toggle(field: "available" | "contact_consent", value: boolean) {
    const before = profile.data;
    if (!before) return;
    // Flip the switch at once; put it back if saving fails.
    profile.setData({ ...before, [field]: value });
    setSaving(field);
    setError("");
    setNotice("");
    try {
      profile.setData(await api<Donor>("/donors/me", { method: "PATCH", body: { [field]: value } }));
      setNotice(field === "available" ? `You are now marked ${value ? "available" : "not available"}.` : `Your phone number is now ${value ? "shared" : "hidden"}.`);
    } catch (e) {
      profile.setData(before);
      setError(`Could not save: ${errorMessage(e)}`);
    } finally {
      setSaving("");
    }
  }

  if (!ready) return <LoadingSpinner />;
  if (!isDonor) {
    return (
      <div className="mx-auto max-w-xl">
        <PageTitle title="My donor profile" />
        <EmptyState title={user ? "This account is not registered as a donor" : "Log in to see your donor profile"}>
          {user ? (
            <Link href="/donor/register" className="text-accent underline">
              Register as a donor
            </Link>
          ) : (
            <button type="button" className="text-accent underline" onClick={() => requireLogin()}>
              Log in with phone
            </button>
          )}
        </EmptyState>
      </div>
    );
  }
  if (profile.loading && !profile.data) {
    return (
      <div className="mx-auto max-w-xl space-y-4" role="status" aria-label="Loading your profile">
        <div className="flex items-center gap-4">
          <Skeleton className="size-16 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-7 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
        </div>
        <Skeleton className="h-20" />
        <Skeleton className="h-36" />
      </div>
    );
  }
  const donor = profile.data;
  if (!donor) return <ErrorMessage onRetry={profile.reload}>{profile.error}</ErrorMessage>;
  const sign = donor.blood_group.endsWith("-") ? "−" : "+";

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <header className="flex items-center gap-4">
        <span
          aria-hidden="true"
          className="grid size-16 shrink-0 place-items-center rounded-full bg-accent text-[22px] font-semibold text-white shadow-[var(--shadow-accent)]"
        >
          {donor.blood_group.slice(0, -1)}
          {sign}
        </span>
        <div className="min-w-0">
          <h1 className="text-[26px] font-semibold leading-tight tracking-tight [overflow-wrap:anywhere]">{donor.name}</h1>
          <p className="mt-0.5 text-sm text-muted">
            Blood group {donor.blood_group}. Donor ID <span className="font-semibold text-ink-soft">{donor.id}</span>
          </p>
        </div>
      </header>

      <EligibilityResult donor={donor} />
      <ErrorMessage>{error}</ErrorMessage>

      <section aria-label="Settings" className="divide-y divide-line rounded-[var(--radius-panel)] border border-line bg-white shadow-[var(--shadow-raise)]">
        <Switch
          label="Available to donate"
          hint="Switch off when you are travelling or unwell. You will not appear in searches."
          checked={donor.available}
          busy={saving === "available"}
          onChange={(value) => toggle("available", value)}
        />
        <Switch
          label="Share my phone number"
          hint="Only logged-in users can see it, and every view is recorded."
          checked={donor.contact_consent}
          busy={saving === "contact_consent"}
          onChange={(value) => toggle("contact_consent", value)}
        />
      </section>
      <Notice>{notice}</Notice>

      <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-[var(--radius-panel)] border border-line bg-line shadow-[var(--shadow-raise)] sm:grid-cols-3">
        <div className="bg-white px-4 py-3.5">
          <dt className="text-[13px] text-muted">Your blood bank</dt>
          <dd className="mt-0.5 font-semibold [overflow-wrap:anywhere]">{donor.linked_bank_name ?? "None yet"}</dd>
        </div>
        <div className="bg-white px-4 py-3.5">
          <dt className="text-[13px] text-muted">Last donation</dt>
          <dd className="mt-0.5 font-semibold">{donor.last_donation_date ? formatDate(donor.last_donation_date) : "Never"}</dd>
        </div>
        <div className="bg-white px-4 py-3.5">
          <dt className="text-[13px] text-muted">Can donate again from</dt>
          <dd className="mt-0.5 font-semibold">{donor.next_eligible_date ? formatDate(donor.next_eligible_date) : "Any time"}</dd>
        </div>
      </dl>

      <section aria-labelledby="history">
        <SectionTitle id="history" title="Donation history" />
        {donor.donations.length === 0 ? (
          <EmptyState title="No donations recorded yet" icon={<IconDrop size={20} />}>
            When you donate at a blood bank, give them your donor ID and it will appear here.
          </EmptyState>
        ) : (
          <ol className="relative space-y-4 border-l-2 border-accent-tint-2 pl-5">
            {donor.donations.map((donation) => (
              <li key={donation.unit_id} className="relative">
                <span aria-hidden="true" className="absolute -left-[27px] top-1 size-3 rounded-full border-2 border-white bg-accent shadow-[0_0_0_2px_var(--color-accent-tint-2)]" />
                <p className="font-semibold">{formatDate(donation.date)}</p>
                <p className="text-sm text-muted [overflow-wrap:anywhere]">
                  {COMPONENT_LABELS[donation.component as Component] ?? donation.component} at {donation.bank_name ?? donation.bank_id}
                </p>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function Switch({ label, hint, checked, busy, onChange }: { label: string; hint: string; checked: boolean; busy: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 px-4 py-4">
      <span>
        <span className="block font-semibold">{label}</span>
        <span className="mt-0.5 block text-sm text-muted">{hint}</span>
      </span>
      <span className="relative inline-flex shrink-0">
        <input
          type="checkbox"
          role="switch"
          className="peer absolute inset-0 z-10 size-full cursor-pointer opacity-0 disabled:cursor-wait"
          checked={checked}
          disabled={busy}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span
          aria-hidden="true"
          className="h-7 w-12 rounded-full bg-line-strong transition-colors duration-200 peer-checked:bg-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent"
        />
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-0.5 top-0.5 size-6 rounded-full bg-white shadow-[0_1px_3px_rgb(27_35_51/0.3)] transition-transform duration-200 peer-checked:translate-x-5"
        />
      </span>
    </label>
  );
}
