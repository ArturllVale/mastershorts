import { useEffect } from 'react';

/**
 * A job is marked complete BEFORE the server finishes uploading all clips to R2.
 * This hook chases the backend until all clips have a durable copy, so that
 * ResultCard components don't fall back to streaming from the ephemeral /api/videos route.
 */
export function useDurableClips({ isManaged, jobId, status, resultsCount, fetchCurrentDurableMap, setDurableClips }) {
  // Chase durable map on mount / job completion
  useEffect(() => {
    if (!isManaged || !jobId || status !== 'complete' || !resultsCount) return;
    let cancelled = false;
    (async () => {
      for (const delay of [0, 3000, 8000, 20000, 40000]) {
        if (delay) await new Promise((r) => setTimeout(r, delay));
        if (cancelled) return;
        let map;
        try { map = await fetchCurrentDurableMap(); } catch { return; }
        if (cancelled) return;
        setDurableClips(map);
        if (Object.keys(map).length >= resultsCount) return;
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isManaged, jobId, status, resultsCount]);
}
