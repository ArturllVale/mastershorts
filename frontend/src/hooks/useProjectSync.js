import { useRef, useCallback } from 'react';
import { saveProjectState } from '../services/projectService';

/**
 * Hook to manage project state synchronization (saving edits back to server)
 * and chasing durable file URLs after edits.
 */
export function useProjectSync({
  jobId,
  isManaged,
  fetchCurrentDurableMap,
  setDurableClips,
  setResults,
  setProjectState
}) {
  const jobIdRef = useRef(jobId);
  jobIdRef.current = jobId;

  const clipStateSync = useRef({ timer: null, pending: {}, files: {}, jobId: null });

  const flushClipState = useCallback(() => {
    const s = clipStateSync.current;
    if (s.timer) { clearTimeout(s.timer); s.timer = null; }
    const entries = Object.entries(s.pending);
    if (!s.jobId || entries.length === 0) return;
    const clips = entries.map(([i, v]) => ({
      index: Number(i),
      active_layers: v.activeLayers,
      server_file: v.serverVideoFile,
    }));
    s.pending = {};
    saveProjectState(s.jobId, clips).catch(() => {});
  }, []);

  const chaseDurableFile = useCallback(async (index, expectedFile) => {
    const forJob = jobIdRef.current;
    for (const delay of [2500, 6000, 15000, 30000]) {
      await new Promise((r) => setTimeout(r, delay));
      if (jobIdRef.current !== forJob) return;
      let map;
      try { map = await fetchCurrentDurableMap(); } catch { return; }
      if (jobIdRef.current !== forJob) return;
      setDurableClips(map);
      if (map[index]?.filename === expectedFile) return;
    }
  }, [fetchCurrentDurableMap, setDurableClips]);

  const handleClipStateChange = useCallback((index, state) => {
    if (!isManaged || !jobIdRef.current) return;
    const s = clipStateSync.current;
    const currentJobId = jobIdRef.current;
    
    if (s.jobId !== currentJobId) { s.pending = {}; s.files = {}; s.jobId = currentJobId; }
    s.pending[index] = state;
    
    const files = s.files || (s.files = {});
    const file = state?.serverVideoFile;
    if (file && files[index] !== file) {
      const isMount = files[index] === undefined;
      files[index] = file;
      if (!isMount) chaseDurableFile(index, file);
    }
    if (s.timer) clearTimeout(s.timer);
    s.timer = setTimeout(flushClipState, 2000);
  }, [isManaged, chaseDurableFile, flushClipState]);

  const handleClipRerendered = useCallback((index, data) => {
    const newFile = (data.new_video_url || '').split('/').pop();
    setResults((prev) => {
      if (!prev?.clips?.[index]) return prev;
      const clips = prev.clips.slice();
      clips[index] = {
        ...clips[index],
        video_url: data.new_video_url,
        start: data.start,
        end: data.end,
        recipe: data.recipe,
      };
      return { ...prev, clips };
    });
    setProjectState((prev) => {
      if (!prev?.clips) return prev;
      return {
        ...prev,
        clips: prev.clips.map((c) => (c.index === index
          ? { ...c, server_file: newFile, active_layers: null }
          : c)),
      };
    });
    setDurableClips((prev) => {
      if (!(index in prev)) return prev;
      const next = { ...prev };
      delete next[index];
      return next;
    });
    handleClipStateChange(index, { activeLayers: null, serverVideoFile: newFile });
  }, [setResults, setProjectState, setDurableClips, handleClipStateChange]);

  return {
    flushClipState,
    chaseDurableFile,
    handleClipStateChange,
    handleClipRerendered,
  };
}
