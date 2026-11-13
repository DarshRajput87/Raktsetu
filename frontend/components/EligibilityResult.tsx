import type { Donor } from "@/lib/types";

export function EligibilityResult({ donor }: { donor: Donor }) {
  return donor.eligible ? (
    <div role="status" className="rounded-xl border border-ink p-4">
      <p className="text-lg font-bold">✓ You can donate today</p>
      <p className="text-sm text-muted">You meet the age, health and donation-gap rules.</p>
    </div>
  ) : (
    <div role="status" className="rounded-xl border border-accent bg-accent-soft p-4 text-accent-dark">
      <p className="text-lg font-bold">You cannot donate right now</p>
      <ul className="mt-1 list-disc pl-5 text-sm">
        {donor.eligibility_reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
  );
}
