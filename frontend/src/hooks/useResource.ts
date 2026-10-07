import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { api, errorMessage } from "../api/client";

export function useResource<T>(path: string | null, poll = false) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((n) => n + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;
    let delay = 3000;
    setLoading(true);
    setData(undefined);
    setError("");
    if (!path) {
      setLoading(false);
      return;
    }
    async function refresh() {
      try {
        const response = await api.get<T>(path!, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setData(response.data);
        setError("");
        setLoading(false);
        const state = (response.data as { status?: string }).status;
        if (poll && state && ["PENDING", "QUEUED", "RUNNING"].includes(state)) {
          delay = Math.min(15000, delay * 1.3);
          timer = window.setTimeout(refresh, delay);
        }
      } catch (e) {
        if (axios.isCancel(e) || controller.signal.aborted) return;
        setError(errorMessage(e));
        setLoading(false);
        if (poll) {
          delay = Math.min(30000, delay * 2);
          timer = window.setTimeout(refresh, delay);
        }
      }
    }
    void refresh();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [path, poll, revision]);
  return { data, error, loading, reload };
}
