import { useCallback } from 'react';

/**
 * Hook to manage drag and drop segment trimming and ghost segment creation.
 */
export function useDragSegment({
  dragRef,
  segments,
  dispatch,
  bounds,
  minSeg,
  snapEdge,
  seekSource,
  setGhost,
  setMarkIn,
  setMarkOut,
  sourceAvailable,
  sourceDuration,
  sourceTrackRef
}) {

  const onDragMove = useCallback((e) => {
    const d = dragRef.current;
    if (!d || d.kind) return;
    const dt = (e.clientX - d.startX) / d.pxPerSec;
    const seg = { ...d.base[d.idx] };

    if (d.edge === 'move') {
      const len = seg.end - seg.start;
      seg.start = Math.max(d.lo, Math.min(d.hi - len, seg.start + dt));
      seg.end = seg.start + len;
      const t = seg.start;
      if (d.scrub && t !== d.last) { d.last = t; d.seek(t); }
    } else if (d.edge === 'start') {
      seg.start = Math.max(d.lo, Math.min(seg.end - d.minSeg, seg.start + dt));
      const t = seg.start;
      if (d.scrub && t !== d.last) { d.last = t; d.seek(t); }
    } else {
      seg.end = Math.min(d.hi, Math.max(seg.start + d.minSeg, seg.end + dt));
      const t = seg.end;
      if (d.scrub && t !== d.last) { d.last = t; d.seek(t); }
    }

    const next = d.base.slice();
    next[d.idx] = seg;
    d.last = { seg, next };
    dispatch({ type: 'preview', segments: next });
  }, [dragRef, dispatch]);

  const onDragUp = useCallback(() => {
    const d = dragRef.current;
    dragRef.current = null;
    window.removeEventListener('pointermove', onDragMove);
    window.removeEventListener('pointerup', onDragUp);
    window.removeEventListener('pointercancel', onDragUp);
    if (!d || d.kind || !d.last) return;

    const { seg, next } = d.last;
    const snapped = { ...seg };
    if (d.edge === 'move') {
      const len = seg.end - seg.start;
      snapped.start = Math.max(d.lo, Math.min(d.hi - len, d.snap(seg.start, 'start')));
      snapped.end = snapped.start + len;
    } else if (d.edge === 'start') {
      snapped.start = Math.max(d.lo, Math.min(seg.end - d.minSeg, d.snap(seg.start, 'start')));
    } else {
      snapped.end = Math.min(d.hi, Math.max(d.snap(seg.end, 'end'), seg.start + d.minSeg));
    }
    
    const clean = { start: Math.round(snapped.start * 1000) / 1000, end: Math.round(snapped.end * 1000) / 1000 };
    dispatch({ type: 'commit', segments: next.map((s, i) => (i === d.idx ? clean : s)), select: d.idx });
  }, [dragRef, dispatch, onDragMove]);

  const startTrimDrag = useCallback((e, idx, edge, trackEl, secondsOnTrack) => {
    if (e.button !== undefined && e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    const rect = trackEl?.getBoundingClientRect();
    if (!rect || !secondsOnTrack) return;
    try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* empty */ }
    
    const scrub = trackEl === sourceTrackRef.current;
    if (scrub) {
      const seg = segments[idx];
      if (seg) seekSource(edge === 'end' ? seg.end : seg.start);
    }
    
    dragRef.current = {
      idx, edge, startX: e.clientX, pxPerSec: rect.width / secondsOnTrack,
      base: segments.map((s) => ({ ...s })), last: null,
      lo: bounds.lo, hi: bounds.hi, minSeg, snap: snapEdge,
      scrub, seek: seekSource,
    };
    dispatch({ type: 'select', index: idx });
    window.addEventListener('pointermove', onDragMove);
    window.addEventListener('pointerup', onDragUp);
    window.addEventListener('pointercancel', onDragUp);
  }, [bounds.hi, bounds.lo, dispatch, dragRef, minSeg, onDragMove, onDragUp, seekSource, segments, snapEdge, sourceTrackRef]);

  const onGhostMove = useCallback((e) => {
    const d = dragRef.current;
    if (!d || d.kind !== 'ghost') return;
    const t = Math.max(0, Math.min(d.duration, d.t0 + (e.clientX - d.startX) / d.pxPerSec));
    d.seek(t);
    d.range = { start: Math.min(d.t0, t), end: Math.max(d.t0, t) };
    setGhost({ ...d.range });
  }, [dragRef, setGhost]);

  const onGhostUp = useCallback(() => {
    const d = dragRef.current;
    dragRef.current = null;
    window.removeEventListener('pointermove', onGhostMove);
    window.removeEventListener('pointerup', onGhostUp);
    window.removeEventListener('pointercancel', onGhostUp);
    setGhost(null);
    if (!d || !d.range) return;
    const seg = {
      start: Math.round(d.snap(d.range.start, 'start') * 1000) / 1000,
      end: Math.round(d.snap(d.range.end, 'end') * 1000) / 1000,
    };
    if (seg.end - seg.start < d.minSeg) return;
    d.mark(seg.start, seg.end);
  }, [dragRef, onGhostMove, setGhost]);

  const startGhostDrag = useCallback((e) => {
    if (e.button !== undefined && e.button !== 0) return;
    if (!sourceAvailable || !sourceDuration) return;
    const rect = sourceTrackRef.current?.getBoundingClientRect();
    if (!rect) return;
    e.preventDefault();
    const t0 = ((e.clientX - rect.left) / rect.width) * sourceDuration;
    seekSource(t0);
    try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* empty */ }
    dragRef.current = {
      kind: 'ghost', startX: e.clientX, pxPerSec: rect.width / sourceDuration,
      t0, duration: sourceDuration, range: null, snap: snapEdge, minSeg,
      seek: seekSource,
      mark: (a, b) => { setMarkIn(a); setMarkOut(b); },
    };
    window.addEventListener('pointermove', onGhostMove);
    window.addEventListener('pointerup', onGhostUp);
    window.addEventListener('pointercancel', onGhostUp);
  }, [dragRef, minSeg, onGhostMove, onGhostUp, seekSource, setMarkIn, setMarkOut, snapEdge, sourceAvailable, sourceDuration, sourceTrackRef]);

  return {
    startTrimDrag,
    startGhostDrag
  };
}
