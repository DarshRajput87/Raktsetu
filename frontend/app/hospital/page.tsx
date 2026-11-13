"use client";

import { useState } from "react";

import { DonorCard } from "@/components/DonorCard";
import { ShowMoreList } from "@/components/ShowMoreList";
import { StaffGate } from "@/components/StaffGate";
import {
  BloodGroupSelect, Button, Card, ComponentSelect, EmptyState, ErrorMessage, Field, LoadingSpinner, PageTitle,
  StatusBadge, UrgencyBadge, formatDate, formatTime,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { demoEmail, useApi } from "@/lib/hooks";
import { COMPONENT_LABELS, CONDITIONS, type BloodGroup, type BloodRequest, type City, type Component, type Condition } from "@/lib/types";

export default function HospitalPage() {
  const cities = useApi<City[]>("/cities");
  return (
    <StaffGate role="hospital" title="Hospital requests" demoEmail={demoEmail(cities.data, "h001", "hospital")}>
      <HospitalDashboard />
    </StaffGate>
  );
}

const STATUS_HELP: Record<BloodRequest["status"], string> = {
  queued: "Waiting in the priority queue. This usually takes a few seconds.",
  allocated: "Units are reserved. Waiting for the blood bank(s) to accept.",
  partial: "Only some units were found in blood banks. Contact the donors below for the rest.",
  unfulfilled: "No blood bank within 25 km has stock. Contact the donors below.",
  completed: "All blood banks accepted. The units are ready to collect.",
};

function HospitalDashboard() {
  const [group, setGroup] = useState<BloodGroup>("O+");
  const [component, setComponent] = useState<Component>("red_cells");
  const [units, setUnits] = useState("1");
  const [condition, setCondition] = useState<Condition>("accident");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Poll while the page is open: queued requests are allocated within seconds.
  const requests = useApi<BloodRequest[]>("/hospital/requests", 3000);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api<BloodRequest>("/hospital/requests", {
        method: "POST",
        body: { group, component, units_needed: Number(units), patient_condition: condition },
      });
      setNotice("Request raised. It is in the priority queue and will be allocated shortly.");
      requests.reload();
    } catch (e) {
      setError(errorMessage(e).replace(/^units_needed: .*/, "Units must be a number from 1 to 50."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
      <section aria-labelledby="new-request">
        <PageTitle title="Hospital requests">Requests are served most urgent first, from the nearest blood banks.</PageTitle>
        <Card>
          <h2 id="new-request" className="mb-3 font-semibold">
            Raise a request
          </h2>
          <form onSubmit={submit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <BloodGroupSelect value={group} onChange={(e) => setGroup(e.target.value as BloodGroup)} />
              <ComponentSelect value={component} onChange={(e) => setComponent(e.target.value as Component)} />
            </div>
            <Field label="Units needed">
              {(field) => (
                <input {...field} type="number" name="units" inputMode="numeric" min={1} max={50} required value={units} onChange={(e) => setUnits(e.target.value)} />
              )}
            </Field>
            <Field label="Patient condition" hint="Sets the urgency. Waiting requests also gain priority over time.">
              {(field) => (
                <select {...field} name="condition" value={condition} onChange={(e) => setCondition(e.target.value as Condition)}>
                  {Object.entries(CONDITIONS).map(([value, { label }]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <ErrorMessage>{error}</ErrorMessage>
            <Button type="submit" busy={busy} className="w-full">
              Raise request
            </Button>
            <p role="status" className="text-sm text-muted">
              {notice}
            </p>
          </form>
        </Card>
      </section>

      <section aria-labelledby="my-requests" className="min-w-0">
        <h2 id="my-requests" className="mb-3 text-lg font-bold">
          Your requests
        </h2>
        {requests.loading && !requests.data && <LoadingSpinner />}
        <ErrorMessage onRetry={requests.reload}>{requests.error}</ErrorMessage>
        {requests.data?.length === 0 && <EmptyState title="No requests yet">Raise a request and it will appear here with its status.</EmptyState>}
        <ul className="space-y-3">
          {requests.data?.map((request) => (
            <li key={request.id}>
              <Card>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold">
                    {request.units_needed} × {request.blood_group} {COMPONENT_LABELS[request.component].toLowerCase()}
                  </h3>
                  <StatusBadge status={request.status} />
                  <UrgencyBadge condition={request.patient_condition} />
                </div>
                <p className="mt-1 text-xs text-muted">
                  Raised {formatTime(request.created_at)} · priority {request.priority} · {request.id}
                </p>
                <p className="mt-2 text-sm">{STATUS_HELP[request.status]}</p>

                {request.allocations.length > 0 && (
                  <ul className="mt-3 space-y-2">
                    {request.allocations.map((allocation, index) => (
                      <li key={index} className="rounded-lg bg-surface px-3 py-2 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-medium [overflow-wrap:anywhere]">{allocation.bank_name}</span>
                          <span className="tabular text-muted">{allocation.distance_km.toFixed(1)} km</span>
                        </div>
                        <p className="text-muted">
                          {allocation.units.length} unit{allocation.units.length === 1 ? "" : "s"} (
                          {allocation.units.map((u) => `${u.blood_group}, expires ${formatDate(u.expires_on)}`).join("; ")}) ·{" "}
                          <span className="font-medium text-ink">{allocation.status}</span>
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
                {request.donor_suggestions.length > 0 && (
                  <details className="mt-3" open={request.status === "unfulfilled"}>
                    <summary className="flex min-h-11 cursor-pointer items-center text-sm font-medium">
                      {request.donor_suggestions.length} matching donor{request.donor_suggestions.length === 1 ? "" : "s"} near your hospital
                    </summary>
                    <p className="mb-2 text-xs text-muted">Nearest first. Each number you open is recorded.</p>
                    <ShowMoreList
                      items={request.donor_suggestions}
                      noun="donors"
                      className="grid gap-2 sm:grid-cols-2"
                      renderItem={(donor) => <DonorCard key={donor.donor_id} donor={donor} />}
                    />
                  </details>
                )}
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
