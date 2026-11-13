"use client";

import { useState } from "react";

import { StaffGate } from "@/components/StaffGate";
import { Button, EmptyState, ErrorMessage, Field, LoadingSpinner, PageTitle, StatusBadge, formatTime } from "@/components/ui";
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

function AdminDashboard() {
  const places = useApi<Place[]>("/admin/places");
  const reports = useApi<Report[]>("/admin/reports");
  const [query, setQuery] = useState("");
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
  const shown = (places.data ?? []).filter((p) => !needle || `${p.name} ${p.area} ${p.kind}`.toLowerCase().includes(needle));

  return (
    <div className="space-y-8">
      <section aria-labelledby="places">
        <PageTitle title="System admin">Verify hospitals and blood banks, and review misuse reports.</PageTitle>
        <h2 id="places" className="mb-3 text-lg font-bold">
          Hospitals and blood banks
        </h2>
        <div className="mb-3 max-w-sm">
          <Field label="Filter by name, area or type">
            {(field) => <input {...field} type="search" name="filter" autoComplete="off" value={query} onChange={(e) => setQuery(e.target.value)} />}
          </Field>
        </div>
        <p role="status" className="mb-2 text-sm">
          {notice}
        </p>
        <ErrorMessage>{error}</ErrorMessage>
        {places.loading && <LoadingSpinner />}
        <ErrorMessage onRetry={places.reload}>{places.error}</ErrorMessage>
        {places.data && shown.length === 0 && (
          <EmptyState title={`Nothing matches "${query}"`}>
            <Button variant="ghost" onClick={() => setQuery("")}>
              Clear the filter
            </Button>
          </EmptyState>
        )}
        {shown.length > 0 && (
          <div className="relative overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[34rem] text-left text-sm">
              <thead className="bg-surface text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-3 py-2">Name</th>
                  <th scope="col" className="px-3 py-2">Type</th>
                  <th scope="col" className="px-3 py-2">Status</th>
                  <th scope="col" className="px-3 py-2">
                    <span className="sr-only">Action</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((place) => (
                  <tr key={`${place.kind}-${place.id}`} className="border-t border-line">
                    <td className="px-3 py-2">
                      <span className="font-medium [overflow-wrap:anywhere]">{place.name}</span>
                      <span className="block text-xs text-muted">{place.id}</span>
                    </td>
                    <td className="px-3 py-2 capitalize">{place.kind === "bank" ? "Blood bank" : "Hospital"}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={place.verified ? "verified" : "pending"} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Button
                        variant="secondary"
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
        )}
      </section>

      <section aria-labelledby="reports">
        <h2 id="reports" className="mb-3 text-lg font-bold">
          Misuse reports
        </h2>
        {reports.loading && <LoadingSpinner />}
        <ErrorMessage onRetry={reports.reload}>{reports.error}</ErrorMessage>
        {reports.data?.length === 0 && <EmptyState title="No reports">Reports about misuse of donor contact details will appear here.</EmptyState>}
        <ul className="space-y-2">
          {reports.data?.map((report) => (
            <li key={report.id} className="rounded-xl border border-line p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={report.status} />
                <span className="text-muted">
                  {formatTime(report.at)} · donor {report.donor_id} · reported by a {report.reporter_role.replace("_", " ")} account
                </span>
              </div>
              <p className="mt-1 [overflow-wrap:anywhere]">{report.reason}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
