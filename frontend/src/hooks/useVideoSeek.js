import { useRef, useCallback, useEffect } from 'react';

export function useVideoSeek({
  coverage,
  dirty,
  segments,
  setPlayhead,
  videoRef,
  totalOf,
  renderedToClip,
  spanIndexAt
}) {
  const playSpanRef = useRef(0);
  const playRafRef = useRef(0);

  const COVERAGE_EPSILON = 0.05;

  const stepPlayback = useCallback((v) => {
    // Note: dragRef check happens upstream or we can pass a dragRef check function.
    if (!dirty) { setPlayhead(v.currentTime); return; }

    let i = playSpanRef.current;
    let sp = coverage[i];
    if (!sp) return;

    const spEnd = sp.rendered !== null ? sp.rendered + (sp.end - sp.start) : null;
    if (spEnd !== null && v.currentTime < spEnd - COVERAGE_EPSILON) {
      setPlayhead(sp.start + (v.currentTime - sp.rendered));
      return;
    }

    i += 1;
    const next = coverage[i];
    if (!next || next.rendered === null) {
      v.pause();
      if (spEnd !== null) { try { v.currentTime = spEnd; } catch { /* not seekable yet */ } }
      setPlayhead(next ? next.start : totalOf(segments));
      if (next) playSpanRef.current = i;
      return;
    }
    playSpanRef.current = i;
    setPlayhead(next.start);
    try { v.currentTime = next.rendered; } catch { /* not seekable yet */ }
  }, [coverage, dirty, segments, setPlayhead, totalOf]);

  const onClipTimeUpdate = useCallback((e) => stepPlayback(e.target), [stepPlayback]);

  const stopPlayLoop = useCallback(() => {
    if (playRafRef.current) cancelAnimationFrame(playRafRef.current);
    playRafRef.current = 0;
  }, []);

  const startPlayLoop = useCallback(() => {
    stopPlayLoop();
    const tick = () => {
      const v = videoRef.current;
      if (!v || v.paused || v.ended) { playRafRef.current = 0; return; }
      stepPlayback(v);
      playRafRef.current = requestAnimationFrame(tick);
    };
    playRafRef.current = requestAnimationFrame(tick);
  }, [stepPlayback, stopPlayLoop, videoRef]);

  useEffect(() => stopPlayLoop, [stopPlayLoop]);

  const onClipSeeked = useCallback((e, isScrubbing) => {
    if (!dirty || isScrubbing) return;
    const t = renderedToClip(e.target.currentTime);
    if (t === null) return;
    setPlayhead(t);
    playSpanRef.current = spanIndexAt(t);
  }, [dirty, renderedToClip, spanIndexAt, setPlayhead]);

  const onClipPlay = useCallback((e) => {
    if (dirty) {
      const sp = coverage[playSpanRef.current];
      if (sp && sp.rendered === null) { e.target.pause(); return; }
    }
    startPlayLoop();
  }, [coverage, dirty, startPlayLoop]);

  return {
    playSpanRef,
    stepPlayback,
    onClipTimeUpdate,
    stopPlayLoop,
    startPlayLoop,
    onClipSeeked,
    onClipPlay
  };
}
