"use client";

import { useState } from "react";

import { IconPlus } from "@/components/icons";
import { RequestResults } from "@/components/RequestResults";
import { StaffGate } from "@/components/StaffGate";
import {
  BloodGroupPicker, Button, ComponentPicker, EmptyState, ErrorMessage, Notice, PageTitle, SectionTitle, SkeletonList,
  Stat, StatusBadge, UrgencyBadge, formatTime,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
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
  queued: "In the priority queue. Banks are usually found within a few seconds.",
  allocated: "Units are reserved. Waiting for the blood bank to accept.",
  partial: "Only some units were found in blood banks. Contact donors for the rest.",
  unfulfilled: "No blood bank within 25 km has stock. Contact donors instead.",
  completed: "Every bank accepted. The units are ready to collect.",
};

const LEVELS: [number, string][] = [
  [100, "Critical"],
  [65, "High"],
  [40, "Medium"],
  [0, "Low"],
];
const levelOf = (score: number) => LEVELS.find(([min]) => score >= min)![1];

function HospitalDashboard() {
  const { user } = useAuth();
  const [group, setGroup] = useState<BloodGroup>("O+");
  const [component, setComponent] = useState<Component>("red_cells");
  const [units, setUnits] = useState(1);
  const [condition, setCondition] = useState<Condition>("accident");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Poll while the page is open: queued requests are allocated within seconds.
  const requests = useApi<BloodRequest[]>("/hospital/requests", 3000);
  const list = requests.data ?? [];
  const active = list.filter((r) => r.status !== "completed").length;
  const waiting = list.filter((r) => r.allocations.some((a) => a.status === "pending")).length;
  const done = list.filter((r) => r.status === "completed").length;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api<BloodRequest>("/hospital/requests", {
        method: "POST",
        body: { group, component, units_needed: units, patient_condition: condition },
      });
      setNotice(`Request raised for ${units} unit${units === 1 ? "" : "s"} of ${group} ${COMPONENT_LABELS[component].toLowerCase()}.`);
      requests.reload();
    } catch (e) {
      setError(errorMessage(e).replace(/^units_needed: .*/, "Units must be a number from 1 to 50."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageTitle title="Blood requests">
        {user?.name ? `${user.name}. ` : ""}Requests are served most urgent first, from the nearest blood banks with stock.
      </PageTitle>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,23rem)_minmax(0,1fr)] lg:gap-8">
        <section aria-labelledby="new-request" className="min-w-0 lg:sticky lg:top-[5.5rem] lg:self-start">
          <form
            onSubmit={submit}
            className="space-y-5 rounded-[var(--radius-panel)] border border-line bg-white p-4 shadow-[var(--shadow-float)] sm:p-5"
          >
            <h2 id="new-request" className="text-[17px] font-semibold tracking-tight">
              New request
            </h2>
            <BloodGroupPicker value={group} onChange={setGroup} label="Patient's blood group" name="request-group" />
            <ComponentPicker value={component} onChange={setComponent} name="request-component" />

            <div>
              <label htmlFor="units" className="mb-1.5 block text-[13px] font-medium text-ink-soft">
                Units needed
              </label>
              <div className="flex items-stretch gap-2">
                <button
                  type="button"
                  aria-label="One unit fewer"
                  disabled={units <= 1}
                  onClick={() => setUnits((u) => Math.max(1, u - 1))}
                  className="grid w-11 place-items-center rounded-[var(--radius-control)] border border-line bg-white text-lg font-semibold shadow-[var(--shadow-raise)] hover:border-line-strong disabled:opacity-40"
                >
                  −
                </button>
                <input
                  id="units"
                  type="number"
                  name="units"
                  inputMode="numeric"
                  min={1}
                  max={50}
                  required
                  value={Number.isNaN(units) ? "" : units}
                  onChange={(e) => setUnits(e.target.valueAsNumber)}
                  className="control tabular text-center text-[17px] font-semibold"
                />
                <button
                  type="button"
                  aria-label="One unit more"
                  disabled={units >= 50}
                  onClick={() => setUnits((u) => Math.min(50, (u || 0) + 1))}
                  className="grid w-11 place-items-center rounded-[var(--radius-control)] border border-line bg-white text-lg font-semibold shadow-[var(--shadow-raise)] hover:border-line-strong disabled:opacity-40"
                >
                  +
                </button>
              </div>
            </div>

            <fieldset>
              <legend className="mb-1.5 text-[13px] font-medium text-ink-soft">Patient condition</legend>
              <p className="-mt-0.5 mb-2 text-xs text-muted">Sets the urgency. Waiting requests also gain priority over time.</p>
              <div className="overflow-hidden rounded-[var(--radius-control)] border border-line">
                {(Object.entries(CONDITIONS) as [Condition, { label: string; score: number }][]).map(([value, { label, score }]) => (
                  <label
                    key={value}
                    className="flex min-h-11 cursor-pointer items-center gap-3 border-b border-line px-3 text-sm last:border-b-0 has-[:checked]:bg-accent-tint-1 has-[:focus-visible]:outline-2 has-[:focus-visible]:-outline-offset-2 has-[:focus-visible]:outline-accent"
                  >
                    <input
                      type="radio"
                      name="condition"
                      value={value}
                      checked={condition === value}
                      onChange={() => setCondition(value)}
                      className="size-4 accent-accent focus-visible:outline-none"
                    />
                    <span className="flex-1 font-medium">{label}</span>
                    <span className={`text-xs font-semibold ${score >= 100 ? "text-accent" : score >= 65 ? "text-accent-dark/80" : "text-muted"}`}>
                      {levelOf(score)}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            <ErrorMessage>{error}</ErrorMessage>
            <Button type="submit" size="lg" busy={busy} className="w-full">
              {!busy && <IconPlus size={18} />}
              Raise request
            </Button>
            <Notice>{notice}</Notice>
          </form>
        </section>

        <section aria-labelledby="my-requests" className="min-w-0">
          <div className="mb-5 grid grid-cols-3 gap-2 sm:gap-3">
            <Stat label="In progress" value={requests.data ? active : "–"} />
            <Stat label="Waiting for a bank" value={requests.data ? waiting : "–"} tone={waiting ? "accent" : "neutral"} />
            <Stat label="Completed" value={requests.data ? done : "–"} />
          </div>

          <SectionTitle id="my-requests" title="Your requests">
            Newest first. This list refreshes every few seconds.
          </SectionTitle>
          {requests.loading && !requests.data && <SkeletonList rows={2} />}
          <ErrorMessage onRetry={requests.reload}>{requests.error}</ErrorMessage>
          {requests.data?.length === 0 && (
            <EmptyState title="No requests yet">Raise a request and it will appear here, with the banks and donors that can help.</EmptyState>
          )}
          <ul className="space-y-3">
            {list.map((request) => (
              <li key={request.id}>
                <RequestCard request={request} />
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}

function RequestCard({ request }: { request: BloodRequest }) {
  const share = Math.min(1, request.units_allocated / request.units_needed);
  return (
    <article className="rounded-[var(--radius-panel)] border border-line bg-white p-4 shadow-[var(--shadow-raise)] sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <h3 className="text-[17px] font-semibold tracking-tight">
          {request.units_needed} × {request.blood_group} {COMPONENT_LABELS[request.component].toLowerCase()}
        </h3>
        <StatusBadge status={request.status} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[13px] text-muted">
        <UrgencyBadge condition={request.patient_condition} />
        <span>Raised {formatTime(request.created_at)}</span>
        <span className="tabular">Priority {request.priority}</span>
      </div>

      <div className="mt-4">
        <div className="mb-1.5 flex justify-between text-[13px]">
          <span className="text-ink-soft">{STATUS_HELP[request.status]}</span>
          <span className="tabular shrink-0 pl-3 font-semibold">
            {request.units_allocated} of {request.units_needed}
          </span>
        </div>
        <div
          role="progressbar"
          aria-label="Units found in blood banks"
          aria-valuemin={0}
          aria-valuemax={request.units_needed}
          aria-valuenow={request.units_allocated}
          className="h-1.5 overflow-hidden rounded-full bg-surface"
        >
          <div
            className={`h-full rounded-full transition-[width] duration-500 ${request.status === "completed" ? "bg-ok" : "bg-accent"}`}
            style={{ width: `${share * 100}%` }}
          />
        </div>
      </div>

      <RequestResults request={request} />
      <p className="mt-3 text-xs text-faint">Request {request.id}</p>
    </article>
  );
}
