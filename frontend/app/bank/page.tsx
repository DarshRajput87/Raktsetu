"use client";

import { useState } from "react";

import { StaffGate } from "@/components/StaffGate";
import {
  BloodGroupSelect, Button, Card, ComponentSelect, EmptyState, ErrorMessage, Field, LoadingSpinner, PageTitle,
  StatusBadge, UrgencyBadge, formatDate, formatTime,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { demoEmail, useApi } from "@/lib/hooks";
import {
  BLOOD_GROUPS, COMPONENTS, COMPONENT_LABELS, type BankRequest, type BloodGroup, type City, type Component,
  type Stock, type Transaction, type Unit,
} from "@/lib/types";

export default function BankPage() {
  const cities = useApi<City[]>("/cities");
  return (
    <StaffGate role="bank_admin" title="Blood bank" demoEmail={demoEmail(cities.data, "b001", "bank")}>
      <BankDashboard />
    </StaffGate>
  );
}

function BankDashboard() {
  const stock = useApi<Stock>("/bank/stock");
  const requests = useApi<BankRequest[]>("/bank/requests", 5000);
  const log = useApi<Transaction[]>("/bank/transactions?limit=50");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  /** Run one action, then refresh everything it can have changed. */
  async function act(name: string, action: () => Promise<string>) {
    setBusy(name);
    setError("");
    setNotice("");
    try {
      setNotice(await action());
      stock.reload();
      requests.reload();
      log.reload();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy("");
    }
  }

  const undo = () =>
    act("undo", async () => {
      const result = await api<{ undone: string }>("/bank/undo", { method: "POST" });
      return `Undone: ${result.undone}.`;
    });

  if (stock.loading && !stock.data) return <LoadingSpinner />;
  return (
    <div className="space-y-6">
      <PageTitle title={stock.data?.bank.name ?? "Blood bank"}>
        {stock.data ? `${stock.data.total_units} usable units in stock as of ${formatDate(stock.data.today)}.` : ""}
      </PageTitle>
      <ErrorMessage onRetry={stock.reload}>{stock.error}</ErrorMessage>

      <div className="sticky top-0 z-10 -mx-4 flex flex-wrap items-center gap-3 border-b border-line bg-white px-4 py-2">
        <Button variant="secondary" busy={busy === "undo"} onClick={undo}>
          Undo last action
        </Button>
        <p role="status" className="min-w-0 flex-1 text-sm">
          {notice}
        </p>
        <ErrorMessage>{error}</ErrorMessage>
      </div>

      {stock.data && <StockTable stock={stock.data} />}

      <div className="grid gap-4 md:grid-cols-2">
        <AddUnitForm busy={busy === "add"} onSubmit={(body) => act("add", async () => {
          const unit = await api<Unit>("/bank/units", { method: "POST", body });
          return `Added one ${unit.blood_group} ${COMPONENT_LABELS[unit.component].toLowerCase()} unit, expires ${formatDate(unit.expires_on)}.`;
        })} />
        <IssueForm busy={busy === "issue"} onSubmit={(body) => act("issue", async () => {
          const result = await api<{ issued: Unit[] }>("/bank/units/issue", { method: "POST", body });
          return `Issued ${result.issued.length} unit(s), earliest expiry first: ${result.issued.map((u) => formatDate(u.expires_on)).join(", ")}.`;
        })} />
      </div>

      <section aria-labelledby="incoming">
        <h2 id="incoming" className="mb-3 text-lg font-bold">
          Incoming hospital requests
        </h2>
        <ErrorMessage onRetry={requests.reload}>{requests.error}</ErrorMessage>
        {requests.data?.length === 0 && <EmptyState title="No requests">Hospital requests that reserve units here will appear in this list.</EmptyState>}
        <ul className="space-y-3">
          {requests.data?.map((request) => (
            <li key={`${request.request_id}-${request.status}`}>
              <Card>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold [overflow-wrap:anywhere]">{request.hospital_name}</h3>
                  <StatusBadge status={request.status} />
                  <UrgencyBadge condition={request.patient_condition} />
                </div>
                <p className="mt-1 text-sm">
                  {request.units.length} × {COMPONENT_LABELS[request.component].toLowerCase()} for a {request.blood_group} patient (
                  {request.units.map((u) => `${u.blood_group}, expires ${formatDate(u.expires_on)}`).join("; ")})
                </p>
                <p className="text-xs text-muted">
                  {request.distance_km.toFixed(1)} km away · raised {formatTime(request.created_at)}
                </p>
                {request.status === "pending" && (
                  <div className="mt-3 flex gap-2">
                    <Button
                      busy={busy === `accept-${request.request_id}`}
                      aria-label={`Accept request from ${request.hospital_name}`}
                      onClick={() => act(`accept-${request.request_id}`, async () => {
                        await api(`/bank/requests/${request.request_id}`, { method: "PATCH", body: { action: "accept" } });
                        return `Accepted: ${request.units.length} unit(s) issued to ${request.hospital_name}.`;
                      })}
                    >
                      Accept
                    </Button>
                    <Button
                      variant="secondary"
                      busy={busy === `reject-${request.request_id}`}
                      aria-label={`Reject request from ${request.hospital_name}`}
                      onClick={() => {
                        if (!window.confirm(`Reject the request from ${request.hospital_name}? The units return to your stock and the request moves to another bank.`)) return;
                        act(`reject-${request.request_id}`, async () => {
                          await api(`/bank/requests/${request.request_id}`, { method: "PATCH", body: { action: "reject" } });
                          return "Rejected: the units are back in stock.";
                        });
                      }}
                    >
                      Reject
                    </Button>
                  </div>
                )}
              </Card>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="log">
        <h2 id="log" className="mb-3 text-lg font-bold">
          Recent transactions
        </h2>
        <ErrorMessage onRetry={log.reload}>{log.error}</ErrorMessage>
        {log.data?.length === 0 && <EmptyState title="Nothing logged yet">Adding, issuing and expiring units is recorded here.</EmptyState>}
        {log.data && log.data.length > 0 && (
          <div className="relative overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[28rem] text-left text-sm">
              <thead className="bg-surface text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-3 py-2">When</th>
                  <th scope="col" className="px-3 py-2">Action</th>
                  <th scope="col" className="px-3 py-2">Units</th>
                </tr>
              </thead>
              <tbody>
                {log.data.map((entry) => (
                  <tr key={entry.id} className="border-t border-line">
                    <td className="tabular whitespace-nowrap px-3 py-2">{formatTime(entry.at)}</td>
                    <td className="px-3 py-2 font-medium capitalize">{entry.action}</td>
                    <td className="px-3 py-2 font-mono text-xs [overflow-wrap:anywhere]">
                      {entry.unit_ids.length} unit{entry.unit_ids.length === 1 ? "" : "s"}: {entry.unit_ids.slice(0, 3).join(", ")}
                      {entry.unit_ids.length > 3 ? ", …" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function StockTable({ stock }: { stock: Stock }) {
  const cell = (group: string, component: string) => stock.rows.find((r) => r.blood_group === group && r.component === component);
  return (
    <section aria-labelledby="stock">
      <h2 id="stock" className="mb-1 text-lg font-bold">
        Stock
      </h2>
      <p className="mb-3 text-sm text-muted">
        Usable units by group and component. Cells marked in red have units that expire within 3 days: issue those first.
      </p>
      <div className="relative overflow-x-auto rounded-xl border border-line">
        <table className="tabular w-full min-w-[26rem] text-center text-sm">
          <thead className="bg-surface text-xs uppercase tracking-wide text-muted">
            <tr>
              <th scope="col" className="px-3 py-2 text-left">Group</th>
              {COMPONENTS.map((component) => (
                <th key={component} scope="col" className="px-3 py-2">
                  {COMPONENT_LABELS[component]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {BLOOD_GROUPS.map((group) => (
              <tr key={group} className="border-t border-line">
                <th scope="row" className="px-3 py-2 text-left font-semibold">
                  {group}
                </th>
                {COMPONENTS.map((component) => {
                  const row = cell(group, component);
                  if (!row) return <td key={component} className="px-3 py-2 text-muted">0</td>;
                  return (
                    <td key={component} className={`px-3 py-2 ${row.expiring_soon ? "bg-accent-soft font-semibold text-accent-dark" : ""}`}>
                      {row.units}
                      {row.expiring_soon > 0 && <span className="block text-xs font-normal">{row.expiring_soon} expiring soon</span>}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {stock.expiring_soon.length > 0 && (
        <p className="mt-2 text-sm">
          <span className="font-medium">Expiring within 3 days:</span>{" "}
          {stock.expiring_soon.slice(0, 8).map((u) => `${u.blood_group} ${COMPONENT_LABELS[u.component].toLowerCase()} (${formatDate(u.expires_on)})`).join(", ")}
          {stock.expiring_soon.length > 8 ? `, and ${stock.expiring_soon.length - 8} more` : ""}.
        </p>
      )}
    </section>
  );
}

function AddUnitForm({ busy, onSubmit }: { busy: boolean; onSubmit: (body: object) => void }) {
  const [group, setGroup] = useState<BloodGroup>("O+");
  const [component, setComponent] = useState<Component>("whole_blood");
  const [donorId, setDonorId] = useState("");
  return (
    <Card>
      <h2 className="mb-3 font-semibold">Add a unit</h2>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(donorId.trim() ? { component, donor_id: donorId.trim() } : { component, blood_group: group });
        }}
      >
        <div className="grid grid-cols-2 gap-3">
          <BloodGroupSelect value={group} disabled={donorId.trim() !== ""} onChange={(e) => setGroup(e.target.value as BloodGroup)} />
          <ComponentSelect value={component} onChange={(e) => setComponent(e.target.value as Component)} />
        </div>
        <Field label="Donor ID (optional)" hint="Records this unit as the donor's donation and uses the donor's blood group.">
          {(field) => <input {...field} name="donor_id" autoComplete="off" spellCheck={false} placeholder="D00001…" value={donorId} onChange={(e) => setDonorId(e.target.value)} />}
        </Field>
        <Button type="submit" busy={busy}>
          Add unit
        </Button>
      </form>
    </Card>
  );
}

function IssueForm({ busy, onSubmit }: { busy: boolean; onSubmit: (body: object) => void }) {
  const [group, setGroup] = useState<BloodGroup>("O+");
  const [component, setComponent] = useState<Component>("whole_blood");
  const [count, setCount] = useState("1");
  return (
    <Card>
      <h2 className="mb-3 font-semibold">Issue units</h2>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit({ group, component, count: Number(count) });
        }}
      >
        <div className="grid grid-cols-2 gap-3">
          <BloodGroupSelect value={group} onChange={(e) => setGroup(e.target.value as BloodGroup)} />
          <ComponentSelect value={component} onChange={(e) => setComponent(e.target.value as Component)} />
        </div>
        <Field label="How many" hint="The units closest to expiry are issued first.">
          {(field) => <input {...field} type="number" name="count" inputMode="numeric" min={1} max={100} required value={count} onChange={(e) => setCount(e.target.value)} />}
        </Field>
        <Button type="submit" busy={busy}>
          Issue
        </Button>
      </form>
    </Card>
  );
}
