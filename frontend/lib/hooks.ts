"use client";

import { useCallback, useEffect, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import type { City } from "@/lib/types";

interface Loaded<T> {
  data: T | null;
  error: string;
  loading: boolean;
  reload: () => void;
  setData: (data: T) => void;
}

/** GET a resource when the component mounts (and when `path` changes); stale responses are ignored. */
export function useApi<T>(path: string | null, pollMs = 0): Loaded<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(path !== null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();
    api<T>(path, { signal: controller.signal })
      .then((result) => {
        setData(result);
        setError("");
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorMessage(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    const timer = pollMs ? window.setTimeout(() => setVersion((v) => v + 1), pollMs) : 0;
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [path, version, pollMs]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, error, loading, reload, setData };
}

/** The demo login for the loaded dataset: ids of real cities carry the city as a prefix. */
export function demoEmail(cities: City[] | null, id: string, kind: "bank" | "hospital"): string {
  const city = cities?.[0]?.id;
  const prefix = !city || city === "synthetic" ? "" : `${city}.`;
  return `${prefix}${id}@${kind}.raktsetu.test`;
}
