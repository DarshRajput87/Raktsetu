import { IconArrowOut, IconClock, IconPhone, IconRoute } from "@/components/icons";
import type { BankHit } from "@/lib/types";

const telHref = (phone: string) => `tel:${phone.replace(/[^+\d]/g, "")}`;
const directionsHref = (bank: BankHit) => `https://www.google.com/maps/dir/?api=1&destination=${bank.lat},${bank.lng}`;
const minutes = (m: number) => `${Math.max(1, Math.round(m))} min`;

function UnitChips({ byGroup }: { byGroup: Record<string, number> }) {
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Units by blood group">
      {Object.entries(byGroup).map(([group, count]) => (
        <li key={group} className="inline-flex items-baseline gap-1 rounded-md bg-surface px-2 py-0.5 text-xs ring-1 ring-inset ring-line">
          <span className="font-semibold text-ink">{group}</span>
          <span className="tabular text-muted">{count}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * A blood bank in the results. The nearest one is the hero: its distance is the
 * headline and it gets the full set of actions. The rest are compact rows.
 */
export function BankCard({
  bank,
  nearest,
  routeShown,
  onShowRoute,
}: {
  bank: BankHit;
  nearest: boolean;
  routeShown: boolean;
  onShowRoute: () => void;
}) {
  const units = `${bank.units} unit${bank.units === 1 ? "" : "s"}`;

  if (nearest) {
    return (
      <li className="overflow-hidden rounded-[var(--radius-panel)] border border-accent/30 bg-white shadow-[var(--shadow-float)]">
        <div className="border-b border-accent/15 bg-gradient-to-b from-accent-tint-1 to-white px-4 pb-4 pt-3.5 sm:px-5">
          <p className="text-[13px] font-semibold text-accent">Nearest with stock</p>
          <div className="mt-2 flex items-end justify-between gap-4">
            <p className="tabular text-[44px] font-semibold leading-none tracking-tight text-ink">
              {bank.distance_km.toFixed(1)}
              <span className="ml-1 text-xl font-medium text-muted">km</span>
            </p>
            <p className="flex items-center gap-1.5 pb-1 text-sm text-muted">
              <IconClock size={16} />
              about {minutes(bank.est_travel_min)} by road
            </p>
          </div>
        </div>
        <div className="space-y-3 px-4 py-4 sm:px-5">
          <div className="min-w-0">
            <h3 className="text-[17px] font-semibold leading-snug [overflow-wrap:anywhere]">{bank.name}</h3>
            <p className="text-sm text-muted">
              {bank.area}, {units} available
            </p>
          </div>
          <UnitChips byGroup={bank.units_by_group} />
          <div className="grid grid-cols-2 gap-2 pt-1">
            <a
              href={telHref(bank.phone)}
              aria-label={`Call ${bank.name} on ${bank.phone}`}
              className="col-span-2 inline-flex min-h-12 items-center justify-center gap-2 rounded-[var(--radius-control)] bg-accent px-4 text-[15px] font-semibold text-white shadow-[var(--shadow-accent)] transition-colors hover:bg-accent-dark active:translate-y-px"
            >
              <IconPhone size={18} />
              Call {bank.phone}
            </a>
            <a
              href={directionsHref(bank)}
              target="_blank"
              rel="noreferrer"
              aria-label={`Directions to ${bank.name} in Google Maps (opens in a new tab)`}
              className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-[var(--radius-control)] border border-line bg-white px-3 text-sm font-semibold shadow-[var(--shadow-raise)] transition-colors hover:border-line-strong"
            >
              Directions
              <IconArrowOut size={16} className="text-muted" />
            </a>
            <button
              type="button"
              onClick={onShowRoute}
              disabled={routeShown}
              aria-label={routeShown ? `Route to ${bank.name} is on the map` : `Show route to ${bank.name} on the map`}
              className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-[var(--radius-control)] border border-line bg-white px-3 text-sm font-semibold shadow-[var(--shadow-raise)] transition-colors hover:border-line-strong disabled:border-transparent disabled:bg-surface disabled:text-muted disabled:shadow-none"
            >
              <IconRoute size={16} />
              {routeShown ? "On the map" : "Show route"}
            </button>
          </div>
        </div>
      </li>
    );
  }

  return (
    <li className="rounded-[var(--radius-panel)] border border-line bg-white px-4 py-3 shadow-[var(--shadow-raise)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold leading-snug [overflow-wrap:anywhere]">{bank.name}</h3>
          <p className="text-[13px] text-muted">
            {bank.area}, {units}
          </p>
        </div>
        <p className="tabular shrink-0 text-right">
          <span className="block text-[17px] font-semibold leading-tight">{bank.distance_km.toFixed(1)} km</span>
          <span className="block text-xs text-muted">{minutes(bank.est_travel_min)}</span>
        </p>
      </div>
      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2">
        <UnitChips byGroup={bank.units_by_group} />
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={onShowRoute}
            disabled={routeShown}
            aria-label={routeShown ? `Route to ${bank.name} is on the map` : `Show route to ${bank.name} on the map`}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-2.5 text-[13px] font-semibold text-ink-soft transition-colors hover:bg-surface disabled:text-muted"
          >
            <IconRoute size={16} />
            {routeShown ? "On the map" : "Route"}
          </button>
          <a
            href={telHref(bank.phone)}
            aria-label={`Call ${bank.name} on ${bank.phone}`}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-accent-soft px-3 text-[13px] font-semibold text-accent-dark transition-colors hover:bg-accent-tint-2"
          >
            <IconPhone size={16} />
            Call
          </a>
        </div>
      </div>
    </li>
  );
}
