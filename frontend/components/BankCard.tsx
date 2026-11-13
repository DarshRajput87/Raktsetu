import type { BankHit } from "@/lib/types";

export function BankCard({ bank, nearest, onShowRoute }: { bank: BankHit; nearest: boolean; onShowRoute?: () => void }) {
  const groups = Object.entries(bank.units_by_group)
    .map(([group, count]) => `${group} × ${count}`)
    .join(", ");
  return (
    <li className={`rounded-xl border p-4 ${nearest ? "border-accent bg-accent-soft" : "border-line bg-white"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {nearest && <p className="text-xs font-bold uppercase tracking-wide text-accent-dark">Nearest with stock</p>}
          <h3 className="font-semibold [overflow-wrap:anywhere]">{bank.name}</h3>
          <p className="text-sm text-muted">{bank.area}</p>
        </div>
        <p className="tabular shrink-0 text-right">
          <span className="block text-lg font-bold">{bank.distance_km.toFixed(1)} km</span>
          <span className="block text-xs text-muted">about {Math.max(1, Math.round(bank.est_travel_min))} min</span>
        </p>
      </div>
      <p className="mt-2 text-sm">
        <span className="font-semibold">
          {bank.units} unit{bank.units === 1 ? "" : "s"}
        </span>{" "}
        <span className="text-muted">({groups})</span>
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <a
          href={`tel:${bank.phone.replace(/[^+\d]/g, "")}`}
          aria-label={`Call ${bank.name} on ${bank.phone}`}
          className="inline-flex min-h-11 items-center rounded-lg bg-accent px-4 text-sm font-semibold text-white hover:bg-accent-dark"
        >
          Call {bank.phone}
        </a>
        {onShowRoute && (
          <button
            type="button"
            onClick={onShowRoute}
            aria-label={`Show route to ${bank.name}`}
            className="inline-flex min-h-11 items-center rounded-lg border border-line bg-white px-4 text-sm font-semibold hover:bg-surface"
          >
            Show route
          </button>
        )}
      </div>
    </li>
  );
}
