"use client";

import { useEffect, useState } from "react";

import { IconAlert, IconCheck, IconUndo } from "@/components/icons";
import { StaffGate } from "@/components/StaffGate";
import {
  BloodGroupPicker, Button, ComponentPicker, EmptyState, ErrorMessage, Field, PageTitle, SectionTitle, Skeleton,
  SkeletonList, Stat, StatusBadge, UrgencyBadge, formatDate, formatShortDate, formatTime,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { demoEmail, useApi } from "@/lib/hooks";
import {
  BLOOD_GROUPS, COMPONENTS, COMPONENT_LABELS, type BankRequest, type BloodGroup, type City, type Component,
  type Stock, type StockRow, type Transaction, type Unit,
} from "@/lib/types";

export default function BankPage() {
  const cities = useApi<City[]>("/cities");
  return (
    <StaffGate
      role="bank_admin"
      title="Blood bank"
      demoEmail={demoEmail(cities.data, "b001", "bank")}
      note="A hospital request goes only to the nearest bank(s) with that blood in stock, not to every bank. The request card on the Hospital page shows which bank's login to use."
    >
      <BankDashboard />
    </StaffGate>
  );
}

const ACTION_LABELS: Record<string, { text: string; tone: string }> = {
  added: { text: "Added", tone: "bg-ok" },
  issued: { text: "Issued", tone: "bg-accent" },
  reserved: { text: "Reserved for a hospital", tone: "bg-accent-tint-4" },
  released: { text: "Released back to stock", tone: "bg-faint" },
  returned: { text: "Returned to stock (undo)", tone: "bg-faint" },
  removed: { text: "Removed (undo)", tone: "bg-faint" },
  expired: { text: "Expired", tone: "bg-ink-soft" },
  transferred: { text: "Transferred", tone: "bg-you" },
};

type Feedback = { kind: "ok" | "error"; text: string } | null;

function BankDashboard() {
  const stock = useApi<Stock>("/bank/stock");
  const requests = useApi<BankRequest[]>("/bank/requests", 5000);
  const log = useApi<Transaction[]>("/bank/transactions?limit=50");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState("");

  /** Run one action, then refresh everything it can have changed. */
  async function act(name: string, action: () => Promise<string>) {
    setBusy(name);
    setFeedback(null);
    try {
      setFeedback({ kind: "ok", text: await action() });
      stock.reload();
      requests.reload();
      log.reload();
    } catch (e) {
      setFeedback({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy("");
    }
  }

  const undo = () =>
    act("undo", async () => {
      const result = await api<{ undone: string }>("/bank/undo", { method: "POST" });
      return `Undone: ${result.undone}.`;
    });

  if (stock.loading && !stock.data) {
    return (
      <div className="space-y-6" role="status" aria-label="Loading stock">
        <Skeleton className="h-9 w-72" />
        <div className="grid grid-cols-3 gap-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }
  const pending = requests.data?.filter((r) => r.status === "pending").length ?? 0;

  return (
    <>
      <PageTitle
        title={stock.data?.bank.name ?? "Blood bank"}
        actions={
          <Button variant="secondary" busy={busy === "undo"} onClick={undo}>
            {busy !== "undo" && <IconUndo size={18} />}
            Undo last action
          </Button>
        }
      >
        {stock.data ? `${stock.data.bank.area}. Stock as of ${formatDate(stock.data.today)}.` : ""}
      </PageTitle>
      <ErrorMessage onRetry={stock.reload}>{stock.error}</ErrorMessage>

      {stock.data && (
        <div className="mb-8 grid grid-cols-3 gap-2 sm:gap-3">
          <Stat label="Usable units" value={stock.data.total_units} />
          <Stat label="Expire within 3 days" value={stock.data.expiring_soon.length} tone={stock.data.expiring_soon.length ? "accent" : "neutral"} />
          <Stat label="Requests waiting" value={requests.data ? pending : "–"} tone={pending ? "accent" : "neutral"} />
        </div>
      )}

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <div className="min-w-0 space-y-10">
          {stock.data && <StockMap stock={stock.data} />}

          <section aria-labelledby="incoming">
            <SectionTitle id="incoming" title="Incoming hospital requests">
              Units are already reserved for these. Accept to issue them, or decline to send the request to the next bank.
            </SectionTitle>
            <ErrorMessage onRetry={requests.reload}>{requests.error}</ErrorMessage>
            {requests.loading && !requests.data && <SkeletonList rows={1} />}
            {requests.data?.length === 0 && (
              <EmptyState title="No requests">When a nearby hospital needs blood you have, its request appears here.</EmptyState>
            )}
            <ul className="space-y-3">
              {requests.data?.map((request) => (
                <li
                  key={`${request.request_id}-${request.status}`}
                  className={`rounded-[var(--radius-panel)] border bg-white p-4 shadow-[var(--shadow-raise)] sm:p-5 ${
                    request.status === "pending" ? "border-accent/30" : "border-line"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                    <h3 className="font-semibold [overflow-wrap:anywhere]">{request.hospital_name}</h3>
                    <StatusBadge status={request.status} />
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[13px] text-muted">
                    <UrgencyBadge condition={request.patient_condition} />
                    <span className="tabular">{request.distance_km.toFixed(1)} km away</span>
                    <span>Raised {formatTime(request.created_at)}</span>
                  </div>
                  <p className="mt-3 text-sm">
                    {request.units.length} unit{request.units.length === 1 ? "" : "s"} of {COMPONENT_LABELS[request.component].toLowerCase()} for a{" "}
                    {request.blood_group} patient
                  </p>
                  <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Reserved units">
                    {request.units.map((u) => (
                      <li key={u.unit_id} className="rounded-md bg-surface px-2 py-0.5 text-xs ring-1 ring-inset ring-line">
                        <span className="font-semibold">{u.blood_group}</span> <span className="text-muted">expires {formatShortDate(u.expires_on)}</span>
                      </li>
                    ))}
                  </ul>
                  {request.status === "pending" && (
                    <div className="mt-4 flex gap-2">
                      <Button
                        busy={busy === `accept-${request.request_id}`}
                        aria-label={`Accept request from ${request.hospital_name}`}
                        onClick={() =>
                          act(`accept-${request.request_id}`, async () => {
                            await api(`/bank/requests/${request.request_id}`, { method: "PATCH", body: { action: "accept" } });
                            return `Accepted: ${request.units.length} unit(s) issued to ${request.hospital_name}.`;
                          })
                        }
                      >
                        Accept and issue
                      </Button>
                      <Button
                        variant="secondary"
                        busy={busy === `reject-${request.request_id}`}
                        aria-label={`Reject request from ${request.hospital_name}`}
                        onClick={() => {
                          if (!window.confirm(`Decline the request from ${request.hospital_name}? The units return to your stock and the request moves to another bank.`)) return;
                          act(`reject-${request.request_id}`, async () => {
                            await api(`/bank/requests/${request.request_id}`, { method: "PATCH", body: { action: "reject" } });
                            return "Declined: the units are back in stock.";
                          });
                        }}
                      >
                        Decline
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="log">
            <SectionTitle id="log" title="Recent activity">
              Everything that changed this bank&apos;s stock, newest first.
            </SectionTitle>
            <ErrorMessage onRetry={log.reload}>{log.error}</ErrorMessage>
            {log.data?.length === 0 && <EmptyState title="Nothing recorded yet">Adding, issuing and expiring units is recorded here.</EmptyState>}
            {log.data && log.data.length > 0 && (
              <div className="relative overflow-x-auto rounded-[var(--radius-panel)] border border-line bg-white shadow-[var(--shadow-raise)]">
                <table className="w-full min-w-[30rem] text-left text-sm">
                  <thead className="border-b border-line bg-canvas text-[13px] text-muted">
                    <tr>
                      <th scope="col" className="px-4 py-2.5 font-medium">When</th>
                      <th scope="col" className="px-4 py-2.5 font-medium">What happened</th>
                      <th scope="col" className="px-4 py-2.5 font-medium">Units</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {log.data.map((entry) => {
                      const action = ACTION_LABELS[entry.action] ?? { text: entry.action, tone: "bg-faint" };
                      return (
                        <tr key={entry.id} className="hover:bg-canvas">
                          <td className="tabular whitespace-nowrap px-4 py-2.5 text-muted">{formatTime(entry.at)}</td>
                          <td className="px-4 py-2.5">
                            <span className="inline-flex items-center gap-2 font-medium">
                              <span aria-hidden="true" className={`size-2 rounded-full ${action.tone}`} />
                              {action.text}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-muted [overflow-wrap:anywhere]">
                            <span className="tabular font-medium text-ink">{entry.unit_ids.length}</span>{" "}
                            <span className="text-xs">
                              ({entry.unit_ids.slice(0, 2).join(", ")}
                              {entry.unit_ids.length > 2 ? ` and ${entry.unit_ids.length - 2} more` : ""})
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        <aside className="min-w-0 space-y-4 xl:sticky xl:top-[5.5rem] xl:self-start" aria-label="Stock actions">
          <AddUnitForm
            busy={busy === "add"}
            onSubmit={(body) =>
              act("add", async () => {
                const unit = await api<Unit>("/bank/units", { method: "POST", body });
                return `Added one ${unit.blood_group} ${COMPONENT_LABELS[unit.component].toLowerCase()} unit, expires ${formatDate(unit.expires_on)}.`;
              })
            }
          />
          <IssueForm
            busy={busy === "issue"}
            onSubmit={(body) =>
              act("issue", async () => {
                const result = await api<{ issued: Unit[] }>("/bank/units/issue", { method: "POST", body });
                return `Issued ${result.issued.length} unit(s), earliest expiry first: ${result.issued.map((u) => formatDate(u.expires_on)).join(", ")}.`;
              })
            }
          />
        </aside>
      </div>

      <Toast feedback={feedback} onClose={() => setFeedback(null)} />
    </>
  );
}

/** Feedback for the last action, pinned to the bottom of the screen. Successes fade after a while; errors stay. */
function Toast({ feedback, onClose }: { feedback: Feedback; onClose: () => void }) {
  useEffect(() => {
    if (feedback?.kind !== "ok") return;
    const timer = window.setTimeout(onClose, 8000);
    return () => window.clearTimeout(timer);
  }, [feedback, onClose]);

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-[calc(4.25rem+env(safe-area-inset-bottom))] z-[1200] flex justify-center px-4 md:bottom-6">
      <div role={feedback?.kind === "error" ? "alert" : "status"} data-toast="" className="pointer-events-auto w-full max-w-md">
        {feedback && (
          <div
            className={`flex items-start gap-3 rounded-[var(--radius-panel)] px-4 py-3 text-sm shadow-[var(--shadow-float)] ring-1 ${
              feedback.kind === "ok" ? "bg-ink text-white ring-black/10" : "bg-white text-accent-dark ring-accent/30"
            }`}
          >
            {feedback.kind === "ok" ? <IconCheck size={18} className="mt-px text-[#7fd6a3]" /> : <IconAlert size={18} className="mt-px" />}
            <p className="min-w-0 flex-1">{feedback.text}</p>
            <button type="button" onClick={onClose} className="-my-1 -mr-1 rounded-md px-2 py-1 text-xs font-semibold opacity-80 hover:opacity-100">
              Dismiss
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

const TINTS = ["bg-white", "bg-accent-tint-1", "bg-accent-tint-2", "bg-accent-tint-3", "bg-accent-tint-4"];

/** Stock as a heat map: deeper red means more units; a red edge marks units that expire within 3 days. */
function StockMap({ stock }: { stock: Stock }) {
  const byKey = new Map<string, StockRow>(stock.rows.map((r) => [`${r.blood_group}|${r.component}`, r]));
  const max = Math.max(1, ...stock.rows.map((r) => r.units));
  const tint = (units: number) => TINTS[units === 0 ? 0 : Math.min(4, 1 + Math.floor((units / max) * 3.999))];

  return (
    <section aria-labelledby="stock">
      <SectionTitle id="stock" title="Stock">
        Usable units by blood group and component. A red edge means some expire within 3 days: issue those first.
      </SectionTitle>
      <div className="relative overflow-x-auto rounded-[var(--radius-panel)] border border-line bg-white shadow-[var(--shadow-raise)]">
        <table className="tabular w-full min-w-[30rem] border-separate border-spacing-1.5 text-center text-sm">
          <thead>
            <tr className="text-[13px] text-muted">
              <th scope="col" className="w-14 px-2 py-1.5 text-left font-medium">Group</th>
              {COMPONENTS.map((component) => (
                <th key={component} scope="col" className="px-2 py-1.5 font-medium">
                  {COMPONENT_LABELS[component]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {BLOOD_GROUPS.map((group) => (
              <tr key={group}>
                <th scope="row" className="px-2 text-left text-[15px] font-semibold">
                  {group}
                </th>
                {COMPONENTS.map((component) => {
                  const row = byKey.get(`${group}|${component}`);
                  const units = row?.units ?? 0;
                  const soon = row?.expiring_soon ?? 0;
                  return (
                    <td
                      key={component}
                      className={`h-14 rounded-[8px] px-2 align-middle ${tint(units)} ${units === 0 ? "text-faint ring-1 ring-inset ring-line" : "text-ink"} ${
                        soon ? "shadow-[inset_3px_0_0_var(--color-accent)]" : ""
                      }`}
                    >
                      <span className="block text-[17px] font-semibold leading-tight">{units}</span>
                      {soon > 0 && <span className="block text-[11px] font-medium leading-tight text-accent-dark">{soon} {soon === 1 ? "expires" : "expire"} soon</span>}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line px-4 py-2.5 text-xs text-muted" aria-hidden="true">
          <span className="flex items-center gap-1.5">
            Fewer
            {TINTS.slice(1).map((t) => (
              <span key={t} className={`size-3 rounded-[3px] ${t}`} />
            ))}
            More units
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-[3px] rounded-full bg-accent" />
            Expire within 3 days
          </span>
        </div>
      </div>
      {stock.expiring_soon.length > 0 && (
        <p className="mt-3 text-sm leading-relaxed text-muted">
          <span className="font-medium text-ink">Expire soonest:</span>{" "}
          {stock.expiring_soon
            .slice(0, 6)
            .map((u) => `${u.blood_group} ${COMPONENT_LABELS[u.component].toLowerCase()} (${formatShortDate(u.expires_on)})`)
            .join(", ")}
          {stock.expiring_soon.length > 6 ? `, and ${stock.expiring_soon.length - 6} more` : ""}.
        </p>
      )}
    </section>
  );
}

function AddUnitForm({ busy, onSubmit }: { busy: boolean; onSubmit: (body: object) => void }) {
  const [group, setGroup] = useState<BloodGroup>("O+");
  const [component, setComponent] = useState<Component>("whole_blood");
  const [donorId, setDonorId] = useState("");
  const fromDonor = donorId.trim() !== "";
  return (
    <form
      aria-labelledby="add-unit"
      className="space-y-4 rounded-[var(--radius-panel)] border border-line bg-white p-4 shadow-[var(--shadow-raise)] sm:p-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(fromDonor ? { component, donor_id: donorId.trim() } : { component, blood_group: group });
      }}
    >
      <h2 id="add-unit" className="text-[17px] font-semibold tracking-tight">
        Add a unit
      </h2>
      <Field label="Donor ID (optional)" hint="Records this unit as that donor's donation, with the donor's blood group.">
        {(field) => (
          <input {...field} name="donor_id" autoComplete="off" spellCheck={false} placeholder="For example D-3EDBDC71FB" value={donorId} onChange={(e) => setDonorId(e.target.value)} />
        )}
      </Field>
      <BloodGroupPicker value={group} onChange={setGroup} disabled={fromDonor} label={fromDonor ? "Blood group (from the donor)" : "Blood group"} name="add-group" />
      <ComponentPicker value={component} onChange={setComponent} name="add-component" />
      <Button type="submit" busy={busy} className="w-full">
        Add unit
      </Button>
    </form>
  );
}

function IssueForm({ busy, onSubmit }: { busy: boolean; onSubmit: (body: object) => void }) {
  const [group, setGroup] = useState<BloodGroup>("O+");
  const [component, setComponent] = useState<Component>("whole_blood");
  const [count, setCount] = useState("1");
  return (
    <form
      aria-labelledby="issue-units"
      className="space-y-4 rounded-[var(--radius-panel)] border border-line bg-white p-4 shadow-[var(--shadow-raise)] sm:p-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({ group, component, count: Number(count) });
      }}
    >
      <h2 id="issue-units" className="text-[17px] font-semibold tracking-tight">
        Issue units
      </h2>
      <BloodGroupPicker value={group} onChange={setGroup} name="issue-group" />
      <ComponentPicker value={component} onChange={setComponent} name="issue-component" />
      <Field label="How many" hint="The units closest to expiry go first.">
        {(field) => <input {...field} type="number" name="count" inputMode="numeric" min={1} max={100} required value={count} onChange={(e) => setCount(e.target.value)} />}
      </Field>
      <Button type="submit" busy={busy} className="w-full">
        Issue
      </Button>
    </form>
  );
}
