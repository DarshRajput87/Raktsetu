"use client";

import { useState } from "react";

import { Button, ErrorMessage } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Contact, DonorHit } from "@/lib/types";

/**
 * A matching donor. The phone number is not in the search result at all: it is
 * fetched from /donors/{id}/contact only after login, when "Show number" is used.
 */
export function DonorCard({ donor }: { donor: Pick<DonorHit, "donor_id" | "name" | "blood_group" | "distance_km"> }) {
  const { requireLogin } = useAuth();
  const [contact, setContact] = useState<Contact | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function showNumber() {
    setError("");
    if (!(await requireLogin())) return;
    setBusy(true);
    try {
      setContact(await api<Contact>(`/donors/${encodeURIComponent(donor.donor_id)}/contact`));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const digits = contact?.phone.replace(/\D/g, "");
  return (
    <li className="rounded-xl border border-line bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold [overflow-wrap:anywhere]">{donor.name}</h3>
          <p className="text-sm text-muted">Blood group {donor.blood_group}</p>
        </div>
        <p className="tabular shrink-0 text-lg font-bold">{donor.distance_km.toFixed(1)} km</p>
      </div>
      <div className="mt-3 space-y-2" aria-live="polite">
        {contact ? (
          <>
            <p className="tabular text-sm font-semibold">{contact.phone}</p>
            <div className="flex flex-wrap gap-2">
              <a
                href={`tel:+${digits}`}
                aria-label={`Call ${donor.name}`}
                className="inline-flex min-h-11 items-center rounded-lg bg-accent px-4 text-sm font-semibold text-white hover:bg-accent-dark"
              >
                Call
              </a>
              <a
                href={`https://wa.me/${digits}`}
                target="_blank"
                rel="noreferrer"
                aria-label={`Message ${donor.name} on WhatsApp`}
                className="inline-flex min-h-11 items-center rounded-lg border border-line px-4 text-sm font-semibold hover:bg-surface"
              >
                WhatsApp
              </a>
            </div>
            <p className="text-xs text-muted">{contact.views_left_today} contact views left today.</p>
          </>
        ) : (
          <Button variant="secondary" busy={busy} onClick={showNumber} aria-label={`Show phone number of ${donor.name}`}>
            Show number
          </Button>
        )}
        <ErrorMessage>{error}</ErrorMessage>
      </div>
    </li>
  );
}
