import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

/** Загрузка данных с повторным запросом и опциональным опросом (для живого статуса заявки). */
export function useResource<T>(load: () => Promise<T>, deps: unknown[], pollMs?: (data: T | undefined) => number | null) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const active = useRef(false);
  const generation = useRef(0);
  const requestSequence = useRef(0);
  const loadRef = useRef(load);
  loadRef.current = load;
  const pollRef = useRef(pollMs);
  pollRef.current = pollMs;

  const reload = useCallback(async () => {
    const resourceGeneration = generation.current;
    const sequence = ++requestSequence.current;
    const isCurrent = () => active.current && resourceGeneration === generation.current && sequence === requestSequence.current;
    try {
      const d = await loadRef.current();
      if (isCurrent()) {
        setData(d);
        setError(null);
      }
      return d;
    } catch (e) {
      if (isCurrent()) setError(e instanceof ApiError ? e : new ApiError(0, "UNKNOWN", String(e)));
      return undefined;
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, []);

  const updateData = useCallback<typeof setData>((value) => {
    if (!active.current) return;
    ++requestSequence.current;
    setData(value);
    setError(null);
    setLoading(false);
  }, []);

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    active.current = true;
    ++generation.current;
    setData(undefined);
    setError(null);
    setLoading(true);
    const tick = async () => {
      const d = await reload();
      if (!alive) return;
      const ms = pollRef.current?.(d);
      if (ms) timer = window.setTimeout(tick, ms);
    };
    tick();
    return () => {
      alive = false;
      active.current = false;
      ++generation.current;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, setData: updateData, error, loading, reload };
}

/** Выполнение действия с блокировкой кнопки и текстом ошибки. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Что-то пошло не так. Повторите действие.");
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, setError, run };
}
