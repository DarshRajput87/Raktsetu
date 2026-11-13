"use client";

import { useMemo, useRef, useState } from "react";

import { BankCard } from "@/components/BankCard";
import { DonorCard } from "@/components/DonorCard";
import MapView from "@/components/MapView";
import type { MapAnimation, MapBank } from "@/components/Map";
import { BloodGroupSelect, Button, ComponentSelect, EmptyState, ErrorMessage, Field, LoadingSpinner } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { COMPONENT_LABELS, type Bank, type BloodGroup, type City, type Component, type LatLng, type SearchResult } from "@/lib/types";

const DEFAULT_RADIUS = 25;
const WIDE_RADIUS = 50;
const FALLBACK_CENTER: LatLng = [23.0225, 72.5714];

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
  const [route, setRoute] = useState<{ bankId: string; points: LatLng[] } | null>(null);

  const [animation, setAnimation] = useState<MapAnimation | null>(null);
  const [animating, setAnimating] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [skip, setSkip] = useState(false);
  const resultsRef = useRef<HTMLHeadingElement>(null);
  const runId = useRef(0);

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
      setError("Choose your location first: use your location or tap the map.");
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
      if (trace && found.trace) {
        runId.current += 1;
        setSkip(false);
        setAnimating(true);
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
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  const routeBankId = route?.bankId ?? result?.route_bank_id;
  const mapBanks = useMemo<MapBank[]>(() => {
    const hits = new Map(result?.banks.map((b) => [b.bank_id, b]) ?? []);
    return (allBanks.data ?? []).map((bank) => {
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
  }, [allBanks.data, result, routeBankId]);

  const shownRoute = animating ? [] : (route?.points ?? result?.route ?? []);
  const fit = useMemo<LatLng[]>(() => {
    if (!position) return [];
    if (!result) return [position];
    if (animation) {
      const dLat = result.radius_km / 111;
      const dLng = result.radius_km / (111 * Math.cos((position[0] * Math.PI) / 180));
      return [[position[0] - dLat, position[1] - dLng], [position[0] + dLat, position[1] + dLng]];
    }
    const points = route?.points ?? result.route;
    if (points.length) return points;
    return [position, ...result.donors.slice(0, 10).map((d): LatLng => [d.lat, d.lng])];
  }, [position, result, route, animation]);

  const radius = result?.radius_km ?? DEFAULT_RADIUS;
  const label = `${group} ${COMPONENT_LABELS[component].toLowerCase()}`;

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
      <div className="min-w-0 space-y-5">
        <header>
          <h1 className="text-2xl font-bold tracking-tight">Find blood near you</h1>
          <p className="mt-1 text-sm text-muted">
            The nearest blood banks with compatible stock, by road distance. If no bank has stock, matching donors.
          </p>
        </header>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            runSearch(DEFAULT_RADIUS);
          }}
          className="space-y-3"
        >
          <div className="grid grid-cols-2 gap-3">
            <BloodGroupSelect value={group} onChange={(e) => setGroup(e.target.value as BloodGroup)} />
            <ComponentSelect value={component} onChange={(e) => setComponent(e.target.value as Component)} />
          </div>
          {cities.data && cities.data.length > 1 && (
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

          <fieldset>
            <legend className="mb-1 text-sm font-medium">Your location</legend>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" busy={locating} onClick={useMyLocation}>
                Use my location
              </Button>
              <Button variant="secondary" onClick={() => pick(center[0], center[1])}>
                Use city centre
              </Button>
            </div>
            <p className="mt-1 text-xs text-muted" aria-live="polite">
              {position
                ? `Location set: ${position[0].toFixed(4)}, ${position[1].toFixed(4)}. Tap the map to change it.`
                : "Or tap the map to drop a pin where you are."}
            </p>
          </fieldset>

          <Button type="submit" busy={searching} className="w-full">
            Search for {label}
          </Button>
          <ErrorMessage>{error}</ErrorMessage>
        </form>

        <section aria-labelledby="results-title" aria-busy={searching}>
          <h2 id="results-title" ref={resultsRef} tabIndex={-1} className="sr-only">
            Search results
          </h2>
          {searching && <LoadingSpinner label="Searching the road network…" />}
          {!searching && result && <Results result={result} label={label} routeBankId={routeBankId} onShowRoute={showRoute} />}

          {!searching && result && (
            <div className="mt-4 space-y-3 border-t border-line pt-4">
              {result.banks.length === 0 && radius < WIDE_RADIUS && (
                <Button variant="secondary" className="w-full" onClick={() => runSearch(WIDE_RADIUS)}>
                  Search wider ({WIDE_RADIUS} km)
                </Button>
              )}
              {animating ? (
                <div className="space-y-2 rounded-lg bg-surface p-3">
                  <p className="text-sm font-medium" role="status">
                    Showing how the search explored {result.junctions_visited.toLocaleString()} road junctions…
                  </p>
                  <Field label={`Speed: ${speed}×`}>
                    {(field) => (
                      <input
                        id={field.id}
                        type="range"
                        min={0.25}
                        max={4}
                        step={0.25}
                        value={speed}
                        onChange={(e) => setSpeed(Number(e.target.value))}
                        className="w-full accent-accent"
                      />
                    )}
                  </Field>
                  <Button variant="secondary" onClick={() => setSkip(true)}>
                    Skip animation
                  </Button>
                </div>
              ) : (
                <Button variant="ghost" onClick={() => runSearch(radius, true)}>
                  Show how it works (shortest-path animation)
                </Button>
              )}
            </div>
          )}
        </section>
      </div>

      <div className="min-w-0 lg:sticky lg:top-4 lg:self-start">
        <MapView
          label="Map of blood banks, donors and the route"
          className="h-80 lg:h-[calc(100vh-8rem)]"
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

function Results({
  result,
  label,
  routeBankId,
  onShowRoute,
}: {
  result: SearchResult;
  label: string;
  routeBankId?: string;
  onShowRoute: (bankId: string) => void;
}) {
  if (result.banks.length > 0) {
    return (
      <>
        <p className="mb-3 text-sm" role="status">
          <span className="font-semibold">
            {result.banks.length} blood bank{result.banks.length === 1 ? "" : "s"}
          </span>{" "}
          within {result.radius_km} km {result.banks.length === 1 ? "has" : "have"} {label} or a compatible group (
          {result.compatible_groups.join(", ")}). Nearest first.
        </p>
        <ul className="space-y-3">
          {result.banks.map((bank, index) => (
            <BankCard
              key={bank.bank_id}
              bank={bank}
              nearest={index === 0}
              onShowRoute={bank.bank_id === routeBankId ? undefined : () => onShowRoute(bank.bank_id)}
            />
          ))}
        </ul>
      </>
    );
  }
  return (
    <>
      <div role="status" className="mb-3 rounded-lg border border-accent bg-accent-soft px-3 py-2 text-sm text-accent-dark">
        <p className="font-semibold">No blood bank within {result.radius_km} km has stock.</p>
        {result.donors.length > 0 && <p>These donors nearby match and have agreed to be contacted. Nearest first.</p>}
      </div>
      {result.donors.length > 0 ? (
        <ul className="space-y-3">
          {result.donors.map((donor) => (
            <DonorCard key={donor.donor_id} donor={donor} />
          ))}
        </ul>
      ) : (
        <EmptyState title="No matching donors nearby either">Try a wider search, or a different component.</EmptyState>
      )}
    </>
  );
}
