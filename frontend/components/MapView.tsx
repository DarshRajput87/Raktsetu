"use client";

import dynamic from "next/dynamic";

/** Leaflet needs `window`, so the map is loaded in the browser only. */
const MapView = dynamic(() => import("@/components/Map"), {
  ssr: false,
  loading: () => (
    <div role="status" className="grid h-72 place-items-center rounded-xl border border-line bg-surface text-sm text-muted">
      Loading map…
    </div>
  ),
});

export default MapView;
