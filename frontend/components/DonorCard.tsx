"use client";

import { useState } from "react";

import { IconPhone, IconWhatsApp } from "@/components/icons";
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

  const digits = contact?.phone.replace(/D/g, "");
  const sign = donor.blood_group.endsWith("-") ? "−" : "+";
  return (
    <li className="rounded-[var(--radius-panel)] border border-line bg-white px-4 py-3 shadow-[var(--shadow-raise)]">
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="grid size-11 shrink-0 place-items-center rounded-full bg-accent-soft text-[15px] font-semibold text-accent-dark ring-1 ring-inset ring-accent/15"
        >
          {donor.blood_group.slice(0, -1)}
          {sign}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold leading-snug [overflow-wrap:anywhere]">{donor.name}</h3>
          <p className="text-[13px] text-muted">
            Blood group {donor.blood_group}, <span className="tabular">{donor.distance_km.toFixed(1)} km</span> away
          </p>
        </div>
        {!contact && (
          <Button variant="secondary" size="sm" busy={busy} onClick={showNumber} aria-label={`Show phone number of ${donor.name}`} className="shrink-0">
            Show number
          </Button>
        )}
      </div>
      <div aria-live="polite">
        {contact && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
            <p className="tabular mr-auto text-[17px] font-semibold tracking-tight">{contact.phone}</p>
            <a
              href={`tel:+${digits}`}
              aria-label={`Call ${donor.name}`}
              className="inline-flex min-h-10 items-center gap-1.5 rounded-[var(--radius-control)] bg-accent px-4 text-sm font-semibold text-white shadow-[var(--shadow-accent)] hover:bg-accent-dark"
            >
              <IconPhone size={16} />
              Call
            </a>
            <a
              href={`https://wa.me/${digits}`}
              target="_blank"
              rel="noreferrer"
              aria-label={`Message ${donor.name} on WhatsApp (opens in a new tab)`}
              className="inline-flex min-h-10 items-center gap-1.5 rounded-[var(--radius-control)] border border-line bg-white px-3.5 text-sm font-semibold shadow-[var(--shadow-raise)] hover:border-line-strong"
            >
              <IconWhatsApp size={16} />
              WhatsApp
            </a>
            <p className="w-full text-xs text-muted">{contact.views_left_today} contact views left today. Each view is recorded.</p>
          </div>
        )}
        {error && (
          <div className="mt-3">
            <ErrorMessage>{error}</ErrorMessage>
          </div>
        )}
      </div>
    </li>
  );
}
