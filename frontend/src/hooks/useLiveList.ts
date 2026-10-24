import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";

/**
 * Loads a public listing and keeps it fresh: refetches every `intervalMs`, when the tab regains focus,
 * and on demand. A failed load surfaces an error instead of spinning forever.
 */
export function useLiveList<T>(path: string, intervalMs = 20000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);

  const reload = useCallback(async () => {
    try {
      const res = await api<T>(path);
      if (!alive.current) return;
      setData(res);
      setError(null);
    } catch (e) {
      if (alive.current) setError(e instanceof ApiError ? e.message : "Can't reach the server. Retrying…");
    }
  }, [path]);

  useEffect(() => {
    alive.current = true;
    reload();
    const t = setInterval(reload, intervalMs);
    const onFocus = () => document.visibilityState === "visible" && reload();
    document.addEventListener("visibilitychange", onFocus);
    return () => {
      alive.current = false;
      clearInterval(t);
      document.removeEventListener("visibilitychange", onFocus);
    };
  }, [reload, intervalMs]);

  return { data, error, reload };
}
