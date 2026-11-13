"use client";

import dynamic from "next/dynamic";
import { useLayoutEffect, useState, type ComponentProps } from "react";

function MapPlaceholder({ className = "h-72" }: { className?: string }) {
  return (
    <div role="status" className={`grid place-items-center rounded-xl border border-line bg-surface text-sm text-muted ${className}`}>
      Loading map…
    </div>
  );
}

/** Leaflet needs `window`, so the map is loaded in the browser only. */
const LeafletMap = dynamic(() => import("@/components/Map"), { ssr: false, loading: () => <MapPlaceholder /> });

/**
 * The map, mounted only while its page is visible.
 *
 * With cacheComponents on, Next.js does not unmount a page on navigation: it
 * hides it with React's <Activity>, running effect cleanups, and re-runs the
 * effects when the user comes back. react-leaflet destroys its Leaflet map in
 * that cleanup and never creates a new one, so returning to the page crashed
 * ("Map container is being reused by another instance"). Taking the map out of
 * the tree while hidden gives a fresh map on every return. This is the
 * useLayoutEffect-cleanup reset from the Next.js "Preserving UI state" guide.
 */
export default function MapView(props: ComponentProps<typeof LeafletMap>) {
  const [visible, setVisible] = useState(false);
  useLayoutEffect(() => {
    // Mount after the first client render, and again each time the page is shown.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setVisible(true);
    return () => setVisible(false);
  }, []);
  return visible ? <LeafletMap {...props} /> : <MapPlaceholder className={props.className} />;
}
