"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { BankCard } from "@/components/BankCard";
import { DonorCard } from "@/components/DonorCard";
import { IconDrop, IconLocate, IconPin, IconPlay, IconSearch } from "@/components/icons";
import type { MapAnimation, MapBank } from "@/components/Map";
import MapView from "@/components/MapView";
import { ShowMoreList } from "@/components/ShowMoreList";
import { BloodGroupPicker, Button, ComponentPicker, EmptyState, ErrorMessage, Field, SkeletonList } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import {
  BLOOD_GROUPS,
  COMPONENT_LABELS,
  COMPONENTS,
  type Bank,
  type BloodGroup,
  type City,
  type Component,
  type LatLng,
  type SearchResult,
} from "@/lib/types";

const DEFAULT_RADIUS = 25;
const WIDE_RADIUS = 50;
const FALLBACK_CENTER: LatLng = [23.0225, 72.5714];

/** A search shared as a link, e.g. /?group=O-&component=platelets&lat=22.8021&lng=72.3275 (used by the demo script). */
function searchFromUrl(): { group?: BloodGroup; component?: Component; position?: LatLng } {
  const params = new URLSearchParams(window.location.search);
  const group = params.get("group");
  const component = params.get("component");
  const lat = Number(params.get("lat"));
  const lng = Number(params.get("lng"));
  return {
    group: BLOOD_GROUPS.find((g) => g === group),
    component: COMPONENTS.find((c) => c === component),
    position: params.has("lat") && params.has("lng") && Math.abs(lat) <= 90 && Math.abs(lng) <= 180 ? [lat, lng] : undefined,
  };
}

export default function SearchPage() {
  const cities = useApi<City[]>("/cities");
  const allBanks = useApi<Bank[]>("/banks");

  const [group, setGroup] = useState<BloodGroup>("B+");
  const [component, setComponent] = useState<Component>("red_cells");
  const [cityId, setCityId] = useState("");
  const [position, setPosition] = useState<LatLng | null>(null);
  const [locating, setLocating] = useState(false);

  const [result, setResult] = useState<SearchResult | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  // After a search the form folds into a one-line summary, so the results start near the top.
  const [collapsed, setCollapsed] = useState(false);
  const [route, setRoute] = useState<{ bankId: string; points: LatLng[] } | null>(null);

  const [animation, setAnimation] = useState<MapAnimation | null>(null);
  const [animating, setAnimating] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [skip, setSkip] = useState(false);
  const resultsRef = useRef<HTMLHeadingElement>(null);
  const runId = useRef(0);
  const mapRef = useRef<HTMLDivElement>(null);

  // Fill the form from a shared link once, after the first render (the URL is not known while prerendering).
  useEffect(() => {
    const shared = searchFromUrl();
    /* eslint-disable react-hooks/set-state-in-effect -- one-time read of the URL on mount */
    if (shared.group) setGroup(shared.group);
    if (shared.component) setComponent(shared.component);
    if (shared.position) setPosition(shared.position);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  const city = cities.data?.find((c) => c.id === cityId) ?? cities.data?.[0];
  const center = city?.center ?? FALLBACK_CENTER;

  function pick(lat: number, lng: number) {
    setPosition([lat, lng]);
    setResult(null);
    setRoute(null);
    setAnimation(null);
    setError("");
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      setError("This browser cannot share its location. Tap the map to choose where you are.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (place) => {
        setLocating(false);
        pick(place.coords.latitude, place.coords.longitude);
      },
      () => {
        setLocating(false);
        setError("Could not get your location. Allow location access, or tap the map to choose where you are.");
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  async function runSearch(radius: number, trace = false) {
    if (!position) {
      setError("Choose your location first: use your location, the city centre, or tap the map.");
      return;
    }
    setSearching(true);
    setError("");
    setAnimation(null);
    setRoute(null);
    try {
      const found = await api<SearchResult>("/search", {
        params: { group, component, lat: position[0], lng: position[1], radius, trace, city: cityId || undefined },
      });
      setResult(found);
      setCollapsed(true);
      if (trace && found.trace) {
        runId.current += 1;
        setSkip(false);
        setAnimating(true);
        // On a phone the map is below the results: bring it into view.
        mapRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        setAnimation({
          runId: runId.current,
          trace: found.trace,
          banksReached: found.banks_reached ?? [],
          route: found.route,
          bestBankId: found.route_bank_id,
        });
      } else {
        // Move focus to the results so keyboard and screen-reader users land on them.
        requestAnimationFrame(() => resultsRef.current?.focus());
      }
    } catch (e) {
      setResult(null);
      setError(
        e instanceof ApiError && e.code === "area_not_supported"
          ? "RaktSetu is not available in this area yet. Tap the map inside a covered city to search there."
          : errorMessage(e),
      );
    } finally {
      setSearching(false);
    }
  }

  async function showRoute(bankId: string) {
    if (!position) return;
    try {
      const found = await api<{ route: LatLng[] }>("/route", { params: { lat: position[0], lng: position[1], bank_id: bankId } });
      setAnimation(null);
      setRoute({ bankId, points: found.route });
      mapRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  const routeBankId = route?.bankId ?? result?.route_bank_id;
  // A new search (or a new location) starts the lists again at 5.
  const searchKey = result ? [result.city_id, result.group, result.component, result.radius_km, ...result.start].join("|") : "";
  const mapBanks = useMemo<MapBank[]>(() => {
    const hits = new Map(result?.banks.map((b) => [b.bank_id, b]) ?? []);
    // Only the selected city's banks: names repeat across cities, and the other cities are off-screen.
    return (allBanks.data ?? [])
      .filter((bank) => bank.city_id === city?.id)
      .map((bank) => {
        const hit = hits.get(bank.id);
        return {
          id: bank.id,
          name: bank.name,
          lat: bank.lat,
          lng: bank.lng,
          state: !hit ? "idle" : bank.id === routeBankId ? "best" : "hit",
          label: hit ? `${hit.distance_km.toFixed(1)} km, ${hit.units} units` : undefined,
        };
      });
  }, [allBanks.data, result, routeBankId, city?.id]);

  const shownRoute = animating ? [] : (route?.points ?? result?.route ?? []);
  const fit = useMemo<LatLng[]>(() => {
    if (!position) return [];
    if (!result) return [position];
    if (animating) {
      const dLat = result.radius_km / 111;
      const dLng = result.radius_km / (111 * Math.cos((position[0] * Math.PI) / 180));
      return [
        [position[0] - dLat, position[1] - dLng],
        [position[0] + dLat, position[1] + dLng],
      ];
    }
    const points = route?.points ?? result.route;
    if (points.length) return points;
    return [position, ...result.donors.slice(0, 10).map((d): LatLng => [d.lat, d.lng])];
  }, [position, result, route, animating]);

  const radius = result?.radius_km ?? DEFAULT_RADIUS;
  const label = `${group} ${COMPONENT_LABELS[component].toLowerCase()}`;
  const cityCount = cities.data?.length ?? 0;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,27rem)_minmax(0,1fr)] lg:gap-8">
      <div className="min-w-0">
        <header className="mb-6">
          <h1 className="text-[30px] font-semibold leading-[1.1] tracking-tight sm:text-[34px]">Find blood near you</h1>
          <p className="mt-2 text-[15px] leading-relaxed text-muted">
            The nearest blood banks with compatible stock, measured along real roads. If none has stock, donors nearby who agreed to help.
          </p>
        </header>

        {collapsed && result ? (
          <div className="flex items-center gap-3 rounded-[var(--radius-panel)] border border-line bg-white p-3 pl-3.5 shadow-[var(--shadow-float)]">
            <span aria-hidden="true" className="grid size-11 shrink-0 place-items-center rounded-full bg-accent text-[15px] font-semibold text-white shadow-[var(--shadow-accent)]">
              {group.slice(0, -1)}
              {group.endsWith("-") ? "−" : "+"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-semibold leading-snug">
                {group} {COMPONENT_LABELS[component].toLowerCase()}
              </p>
              <p className="truncate text-[13px] text-muted">
                Within {result.radius_km} km{city ? `, ${city.name}` : ""}
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              className="shrink-0"
              onClick={() => {
                setCollapsed(false);
                requestAnimationFrame(() => document.querySelector<HTMLInputElement>('input[name="search-group"]:checked')?.focus());
              }}
            >
              Change search
            </Button>
          </div>
        ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            runSearch(DEFAULT_RADIUS);
          }}
          className="space-y-5 rounded-[var(--radius-panel)] border border-line bg-white p-4 shadow-[var(--shadow-float)] sm:p-5"
        >
          <BloodGroupPicker value={group} onChange={setGroup} label="Patient's blood group" name="search-group" />
          <ComponentPicker value={component} onChange={setComponent} name="search-component" />

          <fieldset className="min-w-0 space-y-3">
            <legend className="mb-1.5 text-[13px] font-medium text-ink-soft">Where you are</legend>
            {cities.data && cityCount > 1 && (
              <Field label="City">
                {(field) => (
                  <select {...field} name="city" value={city?.id ?? ""} onChange={(e) => setCityId(e.target.value)}>
                    {cities.data!.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
            )}
            <div className="grid grid-cols-2 gap-2">
              <Button variant="secondary" busy={locating} onClick={useMyLocation}>
                {!locating && <IconLocate size={18} className="text-you" />}
                Use my location
              </Button>
              <Button variant="secondary" onClick={() => pick(center[0], center[1])}>
                <IconPin size={18} className="text-muted" />
                Use city centre
              </Button>
            </div>
            <p className="flex items-center gap-2 text-[13px] text-muted" aria-live="polite">
              {position ? (
                <>
                  <span aria-hidden="true" className="size-2 shrink-0 rounded-full bg-you shadow-[0_0_0_3px_rgb(29_100_216/0.18)]" />
                  <span>
                    Location set at <span className="tabular">{position[0].toFixed(4)}, {position[1].toFixed(4)}</span>. Tap the map to move it.
                  </span>
                </>
              ) : (
                "Or tap the map to drop a pin where you are."
              )}
            </p>
          </fieldset>

          <Button type="submit" size="lg" busy={searching} className="w-full">
            {!searching && <IconSearch size={18} />}
            Search for {label}
          </Button>
          <ErrorMessage>{error}</ErrorMessage>
        </form>
        )}

        <section aria-labelledby="results-title" aria-busy={searching} className="mt-6">
          <h2 id="results-title" ref={resultsRef} tabIndex={-1} className="sr-only">
            Search results
          </h2>
          {searching && <SkeletonList rows={3} label="Searching the road network…" />}
          {!searching && !result && (
            <EmptyState title="Results appear here, nearest first" icon={<IconDrop size={20} />}>
              {cityCount > 0
                ? `Covering ${cityCount} cities in Gujarat. Choose the patient's blood group and where you are, then search.`
                : "Choose the patient's blood group and where you are, then search."}
            </EmptyState>
          )}
          {!searching && result && (
            <Results
              key={searchKey}
              result={result}
              label={label}
              routeBankId={routeBankId}
              onShowRoute={showRoute}
              onWider={result.banks.length === 0 && radius < WIDE_RADIUS ? () => runSearch(WIDE_RADIUS) : undefined}
            />
          )}

          {!searching && result && (
            <div className="mt-6 border-t border-line pt-5">
              {animating ? (
                <div className="space-y-3 rounded-[var(--radius-panel)] bg-surface p-4">
                  <p className="text-sm font-medium" role="status">
                    Watching the search spread along the roads: {result.junctions_visited.toLocaleString("en-IN")} junctions explored.
                  </p>
                  <div>
                    <label htmlFor="speed" className="mb-1 flex justify-between text-[13px] font-medium text-ink-soft">
                      Speed <span className="tabular text-muted">{speed}×</span>
                    </label>
                    <input
                      id="speed"
                      type="range"
                      min={0.25}
                      max={4}
                      step={0.25}
                      value={speed}
                      onChange={(e) => setSpeed(Number(e.target.value))}
                      className="w-full accent-accent"
                    />
                  </div>
                  <Button variant="secondary" size="sm" onClick={() => setSkip(true)}>
                    Skip animation
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-4">
                  <Button variant="quiet" onClick={() => runSearch(radius, true)} className="shrink-0">
                    <IconPlay size={16} />
                    {animation ? "Replay how it works" : "Show how it works"}
                  </Button>
                  <p className="text-[13px] leading-snug text-muted">Watch the shortest-path search reach each bank, then draw the route.</p>
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      <div ref={mapRef} className="min-w-0 scroll-mt-20 lg:sticky lg:top-[5.5rem] lg:self-start">
        <MapView
          label="Map of blood banks, donors and the route"
          className="h-[22rem] shadow-[var(--shadow-float)] lg:h-[calc(100dvh-7.5rem)]"
          center={center}
          key={city?.id ?? "none"}
          user={position}
          radiusKm={result ? radius : undefined}
          banks={animating ? [] : mapBanks}
          donors={animating || !result ? [] : result.donors.map((d) => ({ id: d.donor_id, name: d.name, lat: d.lat, lng: d.lng }))}
          route={shownRoute}
          fit={fit}
          onPick={pick}
          animation={animation}
          speed={speed}
          skip={skip}
          onAnimationDone={() => setAnimating(false)}
        />
        {allBanks.error && <p className="mt-2 text-sm text-muted">Blood bank pins could not be loaded: {allBanks.error}</p>}
      </div>
    </div>
  );
}

function GroupChips({ groups }: { groups: string[] }) {
  return (
    <span className="inline-flex flex-wrap gap-1 align-middle">
      {groups.map((g) => (
        <span key={g} className="rounded-md bg-surface px-1.5 py-px text-xs font-semibold text-ink-soft ring-1 ring-inset ring-line">
          {g}
        </span>
      ))}
    </span>
  );
}

function Results({
  result,
  label,
  routeBankId,
  onShowRoute,
  onWider,
}: {
  result: SearchResult;
  label: string;
  routeBankId?: string;
  onShowRoute: (bankId: string) => void;
  onWider?: () => void;
}) {
  if (result.banks.length > 0) {
    const n = result.banks.length;
    return (
      <>
        <p className="mb-4 text-[15px] leading-relaxed" role="status">
          <span className="font-semibold">
            {n} blood bank{n === 1 ? "" : "s"}
          </span>{" "}
          within {result.radius_km} km {n === 1 ? "has" : "have"} {label} or a compatible group <GroupChips groups={result.compatible_groups} />
        </p>
        <ShowMoreList
          items={result.banks}
          noun="blood banks"
          className="space-y-2"
          renderItem={(bank, index) => (
            <BankCard
              key={bank.bank_id}
              bank={bank}
              nearest={index === 0}
              routeShown={bank.bank_id === routeBankId}
              onShowRoute={() => onShowRoute(bank.bank_id)}
            />
          )}
        />
      </>
    );
  }
  return (
    <>
      <div role="status" className="mb-4 rounded-[var(--radius-panel)] border border-accent/25 bg-accent-soft p-4">
        <p className="font-semibold text-accent-dark">No blood bank within {result.radius_km} km has {label}.</p>
        <p className="mt-1 text-sm leading-relaxed text-accent-dark/85">
          {result.donors.length > 0
            ? "These donors nearby match and have agreed to be contacted. Call the nearest first."
            : "No matching donors who agreed to be contacted are nearby either."}
        </p>
        {onWider && (
          <Button variant="secondary" size="sm" className="mt-3" onClick={onWider}>
            Search wider ({WIDE_RADIUS} km)
          </Button>
        )}
      </div>
      {result.donors.length > 0 ? (
        <ShowMoreList
          items={result.donors}
          noun="donors"
          className="space-y-2"
          renderItem={(donor) => <DonorCard key={donor.donor_id} donor={donor} />}
        />
      ) : (
        <EmptyState title="Try a wider search">Stock changes through the day, so calling the nearest blood bank can also help.</EmptyState>
      )}
    </>
  );
}
