import { IconAlert, IconCheck } from "@/components/icons";
import type { Donor } from "@/lib/types";

export function EligibilityResult({ donor }: { donor: Donor }) {
  return donor.eligible ? (
    <div role="status" className="flex gap-3 rounded-[var(--radius-panel)] border border-ok/25 bg-[#f1f9f4] p-4">
      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-ok text-white">
        <IconCheck size={20} />
      </span>
      <div>
        <p className="font-semibold text-ink">You can donate today</p>
        <p className="text-sm text-muted">You meet the age, health and donation-gap rules.</p>
      </div>
    </div>
  ) : (
    <div role="status" className="flex gap-3 rounded-[var(--radius-panel)] border border-accent/25 bg-accent-soft p-4 text-accent-dark">
      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-white text-accent">
        <IconAlert size={20} />
      </span>
      <div>
        <p className="font-semibold">You cannot donate right now</p>
        <ul className="mt-1 space-y-0.5 text-sm">
          {donor.eligibility_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
