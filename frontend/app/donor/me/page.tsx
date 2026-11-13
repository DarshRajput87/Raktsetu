"use client";

import Link from "next/link";
import { useState } from "react";

import { EligibilityResult } from "@/components/EligibilityResult";
import { Card, EmptyState, ErrorMessage, LoadingSpinner, PageTitle, formatDate } from "@/components/ui";
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
    setSaving(field);
    setError("");
    try {
      profile.setData(await api<Donor>("/donors/me", { method: "PATCH", body: { [field]: value } }));
      setNotice(field === "available" ? `You are now marked ${value ? "available" : "not available"}.` : `Your phone number is now ${value ? "shared" : "hidden"}.`);
    } catch (e) {
      setError(errorMessage(e));
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
  if (profile.loading && !profile.data) return <LoadingSpinner />;
  const donor = profile.data;
  if (!donor) return <ErrorMessage onRetry={profile.reload}>{profile.error}</ErrorMessage>;

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <PageTitle title={donor.name}>
        Blood group {donor.blood_group} · donor ID <span className="font-mono">{donor.id}</span>
      </PageTitle>
      <EligibilityResult donor={donor} />
      <ErrorMessage>{error}</ErrorMessage>

      <Card>
        <Switch
          label="Available to donate"
          hint="Switch off when you are travelling or unwell. You will not appear in searches."
          checked={donor.available}
          busy={saving === "available"}
          onChange={(value) => toggle("available", value)}
        />
        <hr className="my-3 border-line" />
        <Switch
          label="Share my phone number"
          hint="Only logged-in users can see it, and every view is recorded."
          checked={donor.contact_consent}
          busy={saving === "contact_consent"}
          onChange={(value) => toggle("contact_consent", value)}
        />
        <p role="status" className="mt-2 text-sm text-muted">
          {notice}
        </p>
      </Card>

      <Card>
        <h2 className="font-semibold">Linked blood bank</h2>
        <p className="mt-1 text-sm [overflow-wrap:anywhere]">{donor.linked_bank_name ?? "No bank linked yet."}</p>
        <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
          <div>
            <dt className="text-muted">Last donation</dt>
            <dd className="font-medium">{donor.last_donation_date ? formatDate(donor.last_donation_date) : "Never"}</dd>
          </div>
          <div>
            <dt className="text-muted">Can donate again from</dt>
            <dd className="font-medium">{donor.next_eligible_date ? formatDate(donor.next_eligible_date) : "Any time"}</dd>
          </div>
        </dl>
      </Card>

      <section aria-labelledby="history">
        <h2 id="history" className="mb-2 font-semibold">
          Donation history
        </h2>
        {donor.donations.length === 0 ? (
          <EmptyState title="No donations recorded yet">When you donate at a blood bank, give them your donor ID and it will appear here.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {donor.donations.map((donation) => (
              <li key={donation.unit_id} className="flex flex-wrap justify-between gap-2 rounded-lg border border-line px-3 py-2 text-sm">
                <span className="font-medium">{formatDate(donation.date)}</span>
                <span className="text-muted [overflow-wrap:anywhere]">
                  {COMPONENT_LABELS[donation.component as Component] ?? donation.component} at {donation.bank_name ?? donation.bank_id}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Switch({ label, hint, checked, busy, onChange }: { label: string; hint: string; checked: boolean; busy: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4">
      <span>
        <span className="block font-medium">{label}</span>
        <span className="block text-sm text-muted">{hint}</span>
      </span>
      <input
        type="checkbox"
        role="switch"
        className="mt-1 size-6 shrink-0 accent-accent"
        checked={checked}
        disabled={busy}
        onChange={(e) => onChange(e.target.checked)}
      />
    </label>
  );
}
