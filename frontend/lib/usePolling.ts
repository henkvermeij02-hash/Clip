"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

/**
 * Fetch a backend endpoint and refresh it every `intervalMs` while the page is
 * visible. Returns the latest data, an error message and a manual reload.
 */
export function usePolling<T>(path: string | null, intervalMs = 3000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const pathRef = useRef(path);
  pathRef.current = path;

  const load = useCallback(async () => {
    const current = pathRef.current;
    if (!current) return;
    try {
      const result = await api<T>(current);
      if (pathRef.current === current) {
        setData(result);
        setError(null);
      }
    } catch (e) {
      if (pathRef.current === current) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (pathRef.current === current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!path) return;
    setLoading(true);
    load();
    if (!intervalMs) return;
    const id = setInterval(() => {
      if (document.visibilityState === "visible") load();
    }, intervalMs);
    return () => clearInterval(id);
  }, [path, intervalMs, load]);

  return { data, error, loading, reload: load, setData };
}
