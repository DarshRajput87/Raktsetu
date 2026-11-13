"use client";

import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useRef } from "react";
import { Circle, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";

import type { BankReached, LatLng, TraceStep } from "@/lib/types";

export interface MapBank {
  id: string;
  name: string;
  lat: number;
  lng: number;
  /** idle: no result for it; hit: has stock; best: the nearest one with stock */
  state?: "idle" | "hit" | "best";
  label?: string;
}

export interface MapDonor {
  id: string;
  name: string;
  lat: number;
  lng: number;
}

export interface MapAnimation {
  /** Change this to start a new run. */
  runId: number;
  trace: TraceStep[];
  banksReached: BankReached[];
  route: LatLng[];
  bestBankId?: string;
}

interface Props {
  center: LatLng;
  zoom?: number;
  user?: LatLng | null;
  radiusKm?: number;
  banks?: MapBank[];
  donors?: MapDonor[];
  route?: LatLng[];
  /** Points the view should include; refits when the list changes. */
  fit?: LatLng[];
  onPick?: (lat: number, lng: number) => void;
  animation?: MapAnimation | null;
  /** 1 = normal. Read live, so a slider can change it mid-run. */
  speed?: number;
  /** Set true to jump to the end of a running animation. */
  skip?: boolean;
  onAnimationDone?: () => void;
  label: string;
  className?: string;
}

function pin(kind: string, text = "", size = 22) {
  return L.divIcon({ className: "", html: `<div class="pin ${kind}">${text}</div>`, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
}

const ICONS = {
  idle: pin("pin-bank-idle", "", 16),
  hit: pin("pin-bank", "B", 22),
  best: pin("pin-bank-best", "B", 30),
  donor: pin("pin-donor", "D", 18),
  user: pin("pin-user", "", 18),
  reached: pin("pin-reached", "B", 24),
  reachedEmpty: pin("pin-reached-empty", "", 18),
};

function ClickToPick({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({ click: (event) => onPick(event.latlng.lat, event.latlng.lng) });
  return null;
}

function FitTo({ points }: { points: LatLng[] }) {
  const map = useMap();
  const key = points.map((p) => p.join(",")).join(";");
  useEffect(() => {
    if (points.length === 1) map.setView(points[0], Math.max(map.getZoom(), 13));
    else if (points.length > 1) map.fitBounds(L.latLngBounds(points), { padding: [30, 30], maxZoom: 15 });
    // `key` stands for the contents of `points`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key]);
  return null;
}

/**
 * Plays Dijkstra's search: junctions light up in the order they were visited
 * (spreading out like a wave), each bank flashes when it is reached, and then
 * the route to the nearest bank with stock is drawn piece by piece.
 * Drawn with Leaflet's canvas renderer, a batch of junctions per frame.
 */
function TraceAnimation({
  animation,
  speedRef,
  skipRef,
  onDone,
}: {
  animation: MapAnimation;
  speedRef: React.RefObject<number>;
  skipRef: React.RefObject<boolean>;
  onDone: () => void;
}) {
  const map = useMap();
  const doneRef = useRef(onDone);
  useEffect(() => {
    doneRef.current = onDone;
  });

  useEffect(() => {
    const { trace, banksReached, route, bestBankId } = animation;
    const renderer = L.canvas({ padding: 0.5 });
    const layer = L.layerGroup().addTo(map);
    const banksAt = new Map<string, BankReached[]>();
    for (const bank of banksReached) banksAt.set(bank.node, [...(banksAt.get(bank.node) ?? []), bank]);
    const line = L.polyline([], { color: "#b3202f", weight: 5, opacity: 0.9 }).addTo(layer);

    // About 4 seconds at normal speed, never fewer than 20 junctions per frame.
    const perFrame = Math.max(20, Math.ceil(trace.length / 240));
    const routePerFrame = Math.max(1, Math.ceil(route.length / 60));
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let i = 0;
    let r = 0;
    let frame = 0;

    function showBank(bank: BankReached) {
      const best = bank.bank_id === bestBankId;
      const marker = L.marker([bank.lat, bank.lng], {
        icon: bank.has_stock ? ICONS.reached : ICONS.reachedEmpty,
        zIndexOffset: bank.has_stock ? 600 : 300,
        keyboard: false,
      }).addTo(layer);
      if (bank.has_stock) {
        marker.bindTooltip(`${bank.dist_km.toFixed(1)} km${best ? ", nearest" : ""}`, {
          permanent: true,
          direction: "top",
          offset: [0, -12],
          className: "pin-label",
        });
      }
    }

    function step() {
      const instant = skipRef.current || reduced;
      const speed = instant ? Infinity : speedRef.current;
      if (i < trace.length) {
        const end = Math.min(trace.length, i + perFrame * speed);
        for (; i < end; i++) {
          const t = trace[i];
          L.circleMarker([t.lat, t.lng], { renderer, radius: 2, stroke: false, fillColor: "#b3202f", fillOpacity: 0.45, interactive: false }).addTo(layer);
          banksAt.get(t.node)?.forEach(showBank);
        }
      } else if (r < route.length) {
        const end = Math.min(route.length, r + routePerFrame * speed);
        for (; r < end; r++) line.addLatLng(route[r]);
      } else {
        doneRef.current();
        return;
      }
      frame = requestAnimationFrame(step);
    }

    frame = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(frame);
      layer.remove();
    };
  }, [map, animation, speedRef, skipRef]);

  return null;
}

export default function LeafletMap({
  center,
  zoom = 11,
  user,
  radiusKm,
  banks = [],
  donors = [],
  route = [],
  fit = [],
  onPick,
  animation,
  speed = 1,
  skip = false,
  onAnimationDone,
  label,
  className = "h-72",
}: Props) {
  const speedRef = useRef(speed);
  const skipRef = useRef(skip);
  useEffect(() => {
    speedRef.current = speed;
    skipRef.current = skip;
  }, [speed, skip]);
  const noop = useMemo(() => () => {}, []);

  return (
    <div role="region" aria-label={label} className={`relative z-0 overflow-hidden rounded-xl border border-line ${className}`}>
      <MapContainer center={center} zoom={zoom} scrollWheelZoom className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {onPick && <ClickToPick onPick={onPick} />}
        <FitTo points={fit} />

        {user && radiusKm && (
          <Circle center={user} radius={radiusKm * 1000} pathOptions={{ color: "#1a6fe8", weight: 1, fillOpacity: 0.04 }} interactive={false} />
        )}
        {route.length > 1 && <Polyline positions={route} pathOptions={{ color: "#b3202f", weight: 5, opacity: 0.9 }} />}

        {banks.map((bank) => (
          <Marker
            key={`${bank.id}-${bank.state ?? "idle"}`}
            position={[bank.lat, bank.lng]}
            icon={ICONS[bank.state ?? "idle"]}
            zIndexOffset={bank.state === "best" ? 800 : bank.state === "hit" ? 500 : 0}
            title={bank.name}
            alt={`Blood bank: ${bank.name}`}
          >
            <Tooltip direction="top" offset={[0, -10]}>
              {bank.name}
              {bank.label ? `, ${bank.label}` : ""}
            </Tooltip>
          </Marker>
        ))}
        {donors.map((donor) => (
          <Marker key={donor.id} position={[donor.lat, donor.lng]} icon={ICONS.donor} title={donor.name} alt={`Donor: ${donor.name}`} zIndexOffset={400}>
            <Tooltip direction="top" offset={[0, -10]}>
              Donor: {donor.name}
            </Tooltip>
          </Marker>
        ))}
        {user && <Marker position={user} icon={ICONS.user} title="Your location" alt="Your location" zIndexOffset={1000} />}

        {animation && (
          <TraceAnimation key={animation.runId} animation={animation} speedRef={speedRef} skipRef={skipRef} onDone={onAnimationDone ?? noop} />
        )}
      </MapContainer>
    </div>
  );
}
