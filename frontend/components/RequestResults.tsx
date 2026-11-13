"use client";

import { useState } from "react";

import { DonorCard } from "@/components/DonorCard";
import { ShowMoreList } from "@/components/ShowMoreList";
import { formatDate } from "@/components/ui";
import { COMPONENT_LABELS, type Allocation, type BloodRequest } from "@/lib/types";

const ALLOCATION_TEXT: Record<Allocation["status"], string> = {
  pending: "Units reserved. Waiting for the bank to accept.",
  accepted: "Accepted. The units are ready to collect.",
  rejected: "Declined by the bank. The request was sent on to the next bank.",
};

/** In this demo every bank has a login; show which one received the request. */
const SHOW_DEMO_LOGINS = process.env.NODE_ENV !== "production";
const demoBankLogin = (bankId: string) => `${bankId.toLowerCase().replace(":", ".")}@bank.raktsetu.test`;

/**
 * A request's two kinds of result, as tabs: the blood banks it was sent to,
 * and matching donors near the hospital. Opens on banks when any were found,
 * otherwise on donors.
 */
export function RequestResults({ request }: { request: BloodRequest }) {
  const hasBanks = request.allocations.length > 0;
  const [tab, setTab] = useState<"banks" | "donors" | null>(null);
  const current = tab ?? (hasBanks || request.status === "queued" ? "banks" : "donors");
  const what = `${request.blood_group} ${COMPONENT_LABELS[request.component].toLowerCase()}`;

  const tabButton = (id: "banks" | "donors", label: string) => (
    <button
      type="button"
      aria-pressed={current === id}
      onClick={() => setTab(id)}
      className={`min-h-11 flex-1 rounded-md px-3 text-sm font-semibold ${
        current === id ? "bg-white text-accent shadow-sm" : "text-muted hover:text-ink"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="mt-3">
      <div role="group" aria-label={`Results for request ${request.id}`} className="flex gap-1 rounded-lg bg-surface p-1">
        {tabButton("banks", `Blood banks (${request.allocations.length})`)}
        {tabButton("donors", `Donors (${request.donor_suggestions.length})`)}
      </div>

      <div className="mt-3">
        {current === "banks" ? (
          request.status === "queued" ? (
            <p className="text-sm text-muted">Finding the nearest blood banks with {what}…</p>
          ) : hasBanks ? (
            <ul className="space-y-2">
              {request.allocations.map((allocation, index) => (
                <li key={index} className="rounded-lg border border-line p-3 text-sm">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <span className="min-w-0 font-semibold [overflow-wrap:anywhere]">{allocation.bank_name}</span>
                    <span className="tabular text-muted">{allocation.distance_km.toFixed(1)} km</span>
                  </div>
                  <p className={allocation.status === "accepted" ? "font-medium" : "text-muted"}>{ALLOCATION_TEXT[allocation.status]}</p>
                  <p className="mt-1 text-muted">
                    {allocation.units.length} unit{allocation.units.length === 1 ? "" : "s"}:{" "}
                    {allocation.units.map((u) => `${u.blood_group} (expires ${formatDate(u.expires_on)})`).join(", ")}
                  </p>
                  {allocation.bank_phone && allocation.status !== "rejected" && (
                    <a
                      href={`tel:${allocation.bank_phone.replace(/[^+\d]/g, "")}`}
                      aria-label={`Call ${allocation.bank_name} on ${allocation.bank_phone}`}
                      className="mt-2 inline-flex min-h-11 items-center rounded-lg border border-line px-4 font-semibold hover:bg-surface"
                    >
                      Call {allocation.bank_phone}
                    </a>
                  )}
                  {SHOW_DEMO_LOGINS && allocation.status === "pending" && (
                    <p className="mt-2 text-xs text-muted">
                      Demo: to accept it, log in on the Blood bank page as{" "}
                      <span className="font-mono [overflow-wrap:anywhere]">{demoBankLogin(allocation.bank_id)}</span>.
                    </p>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div className="rounded-lg border border-accent bg-accent-soft px-3 py-2 text-sm text-accent-dark">
              <p className="font-semibold">No blood bank within 25 km has {what} or a compatible group.</p>
              <p>The request was not sent to any bank. Contact the matching donors in the Donors tab.</p>
            </div>
          )
        ) : request.donor_suggestions.length > 0 ? (
          <>
            <p className="mb-2 text-xs text-muted">Matching donors near your hospital, nearest first. Each number you open is recorded.</p>
            <ShowMoreList
              items={request.donor_suggestions}
              noun="donors"
              className="grid gap-2 sm:grid-cols-2"
              renderItem={(donor) => <DonorCard key={donor.donor_id} donor={donor} />}
            />
          </>
        ) : (
          <p className="text-sm text-muted">
            {request.status === "queued" ? "Finding matching donors…" : "No matching donors who agreed to be contacted are within 25 km."}
          </p>
        )}
      </div>
    </div>
  );
}
