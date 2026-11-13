"use client";

import { useState } from "react";

import { StaffGate } from "@/components/StaffGate";
import { IconShield } from "@/components/icons";
import { Badge, Button, EmptyState, ErrorMessage, Field, Notice, PageTitle, SectionTitle, SkeletonList, Stat, StatusBadge, formatTime } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Place, Report } from "@/lib/types";

export default function AdminPage() {
  return (
    <StaffGate role="admin" title="System admin" demoEmail="admin@raktsetu.test">
      <AdminDashboard />
    </StaffGate>
  );
}

const PAGE = 25;

function AdminDashboard() {
  const places = useApi<Place[]>("/admin/places");
  const reports = useApi<Report[]>("/admin/reports");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"all" | "hospital" | "bank" | "unverified">("all");
  const [limit, setLimit] = useState(PAGE);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function setVerified(place: Place, verified: boolean) {
    if (!verified && !window.confirm(`Remove verification from ${place.name}? It will be hidden from search and its account cannot log in.`)) return;
    setBusyId(place.id);
    setError("");
    try {
      const path = place.kind === "bank" ? `/admin/banks/${place.id}/verify` : `/admin/hospitals/${place.id}/verify`;
      const updated = await api<Place>(path, { method: "PATCH", body: { verified } });
      places.setData((places.data ?? []).map((p) => (p.id === place.id && p.kind === place.kind ? updated : p)));
      setNotice(`${place.name} is now ${verified ? "verified" : "not verified"}.`);
    } catch (e) {
      setError(`${place.name}: ${errorMessage(e)}`);
    } finally {
      setBusyId("");
    }
  }

  const needle = query.trim().toLowerCase();
  const all = places.data ?? [];
  const shown = all.filter(
    (p) =>
      (kind === "all" || (kind === "unverified" ? !p.verified : p.kind === kind)) &&
      (!needle || `${p.name} ${p.area} ${p.kind} ${p.city_id}`.toLowerCase().includes(needle)),
  );
  const visible = shown.slice(0, limit);
  const unverified = all.filter((p) => !p.verified).length;
  const openReports = reports.data?.filter((r) => r.status === "open").length ?? 0;
  const cityName = (id: string) => id.charAt(0).toUpperCase() + id.slice(1);
  const KINDS: { id: typeof kind; label: string }[] = [
    { id: "all", label: "All" },
    { id: "hospital", label: "Hospitals" },
    { id: "bank", label: "Blood banks" },
    { id: "unverified", label: "Not verified" },
  ];

  return (
    <div className="space-y-10">
      <div>
        <PageTitle title="System admin">Verify hospitals and blood banks, and review reports of misused donor contact details.</PageTitle>
        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          <Stat label="Hospitals and banks" value={places.data ? all.length : "–"} />
          <Stat label="Not verified" value={places.data ? unverified : "–"} tone={unverified ? "accent" : "neutral"} />
          <Stat label="Open reports" value={reports.data ? openReports : "–"} tone={openReports ? "accent" : "neutral"} />
        </div>
      </div>

      <section aria-labelledby="places">
        <SectionTitle id="places" title="Hospitals and blood banks">
          Unverified places are hidden from search, and their staff cannot log in.
        </SectionTitle>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="min-w-0 sm:w-80">
            <Field label="Filter by name, area or city">
              {(field) => (
                <input
                  {...field}
                  type="search"
                  name="filter"
                  autoComplete="off"
                  placeholder="For example Anand or Surat"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setLimit(PAGE);
                  }}
                />
              )}
            </Field>
          </div>
          <div role="group" aria-label="Show" className="grid grid-cols-4 gap-1 rounded-[var(--radius-control)] bg-surface p-1 sm:flex">
            {KINDS.map((k) => (
              <button
                key={k.id}
                type="button"
                aria-pressed={kind === k.id}
                onClick={() => {
                  setKind(k.id);
                  setLimit(PAGE);
                }}
                className={`min-h-9 whitespace-nowrap rounded-[8px] px-3 text-[13px] font-semibold transition-colors ${
                  kind === k.id ? "bg-white text-ink shadow-[var(--shadow-raise)]" : "text-muted hover:text-ink"
                }`}
              >
                {k.label}
              </button>
            ))}
          </div>
        </div>
        <Notice>{notice}</Notice>
        <ErrorMessage>{error}</ErrorMessage>
        {places.loading && <SkeletonList rows={2} />}
        <ErrorMessage onRetry={places.reload}>{places.error}</ErrorMessage>
        {places.data && shown.length === 0 && (
          <EmptyState title={query ? `Nothing matches "${query}"` : "Nothing to show"}>
            <Button
              variant="ghost"
              onClick={() => {
                setQuery("");
                setKind("all");
              }}
            >
              Clear the filter
            </Button>
          </EmptyState>
        )}
        {shown.length > 0 && (
          <>
            <div className="relative mt-2 overflow-x-auto rounded-[var(--radius-panel)] border border-line bg-white shadow-[var(--shadow-raise)]">
              <table className="w-full min-w-[40rem] text-left text-sm">
                <thead className="border-b border-line bg-canvas text-[13px] text-muted">
                  <tr>
                    <th scope="col" className="px-4 py-2.5 font-medium">Name</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Type</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">City</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
                    <th scope="col" className="px-4 py-2.5">
                      <span className="sr-only">Action</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {visible.map((place) => (
                    <tr key={`${place.kind}-${place.id}`} className="hover:bg-canvas">
                      <td className="px-4 py-2.5">
                        <span className="font-semibold [overflow-wrap:anywhere]">{place.name}</span>
                        <span className="block text-xs text-muted">{place.id}</span>
                      </td>
                      <td className="px-4 py-2.5 text-ink-soft">{place.kind === "bank" ? "Blood bank" : "Hospital"}</td>
                      <td className="px-4 py-2.5 text-ink-soft">{cityName(place.city_id)}</td>
                      <td className="px-4 py-2.5">
                        <Badge tone={place.verified ? "ok" : "accent"} dot>
                          {place.verified ? "Verified" : "Not verified"}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <Button
                          variant={place.verified ? "quiet" : "primary"}
                          size="sm"
                          busy={busyId === place.id}
                          aria-label={`${place.verified ? "Remove verification from" : "Verify"} ${place.name}`}
                          onClick={() => setVerified(place, !place.verified)}
                        >
                          {place.verified ? "Unverify" : "Verify"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex flex-col items-center gap-2">
              {visible.length < shown.length && (
                <Button variant="secondary" className="w-full sm:w-auto" onClick={() => setLimit((n) => n + PAGE)}>
                  Show {Math.min(PAGE, shown.length - visible.length)} more
                </Button>
              )}
              <p className="tabular text-xs text-muted" aria-live="polite">
                Showing {visible.length} of {shown.length}
              </p>
            </div>
          </>
        )}
      </section>

      <section aria-labelledby="reports">
        <SectionTitle id="reports" title="Misuse reports">
          Filed by donors who were contacted unfairly, or by users about a donor listing.
        </SectionTitle>
        {reports.loading && <SkeletonList rows={1} />}
        <ErrorMessage onRetry={reports.reload}>{reports.error}</ErrorMessage>
        {reports.data?.length === 0 && (
          <EmptyState title="No reports" icon={<IconShield size={20} />}>
            Reports about misuse of donor contact details will appear here.
          </EmptyState>
        )}
        <ul className="space-y-2">
          {reports.data?.map((report) => (
            <li key={report.id} className="rounded-[var(--radius-panel)] border border-line bg-white p-4 text-sm shadow-[var(--shadow-raise)]">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                <StatusBadge status={report.status} />
                <span className="text-muted">{formatTime(report.at)}</span>
                <span className="text-muted">Donor {report.donor_id}</span>
                <span className="text-muted">Reported by a {report.reporter_role.replace("_", " ")} account</span>
              </div>
              <p className="mt-2 [overflow-wrap:anywhere]">{report.reason}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
