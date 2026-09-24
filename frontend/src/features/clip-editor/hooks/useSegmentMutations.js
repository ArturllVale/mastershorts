import { useCallback } from 'react';
import { SNAP_WINDOW_SECONDS } from '../constants';

export function useSegmentMutations({
    segments,
    dispatch,
    bounds,
    minSeg,
    limits,
    words,
    snapToWords,
    playhead
}) {
    const snapEdge = useCallback((t, kind) => {
        if (!snapToWords || !words.length) return t;
        let best = null;
        for (const w of words) {
            const c = kind === 'start' ? w.s : w.e;
            if (Math.abs(c - t) <= SNAP_WINDOW_SECONDS && (best === null || Math.abs(c - t) < Math.abs(best - t))) best = c;
        }
        return best ?? t;
    }, [snapToWords, words]);

    const clampSeg = useCallback((seg) => ({
        start: Math.max(bounds.lo, Math.min(seg.start, seg.end - minSeg)),
        end: Math.min(bounds.hi, Math.max(seg.end, seg.start + minSeg)),
    }), [bounds.lo, bounds.hi, minSeg]);

    const setSegment = useCallback((index, next, { snap = true } = {}) => {
        const updated = segments.map((s, i) => {
            if (i !== index) return s;
            const seg = { ...s, ...next };
            if (snap) {
                if (next.start !== undefined) seg.start = snapEdge(seg.start, 'start');
                if (next.end !== undefined) seg.end = snapEdge(seg.end, 'end');
            }
            return clampSeg(seg);
        });
        dispatch({ type: 'commit', segments: updated, select: index });
    }, [segments, snapEdge, clampSeg, dispatch]);

    const addSegment = useCallback(() => {
        if (segments.length >= limits.max_segments) return;
        const last = segments[segments.length - 1];
        let start = last ? last.end : bounds.lo;
        let end = start + 10;
        if (end > bounds.hi) { end = bounds.hi; start = Math.max(bounds.lo, end - 10); }
        if (end - start < minSeg) return;
        dispatch({ type: 'commit', segments: [...segments, { start: Math.round(start * 1000) / 1000, end: Math.round(end * 1000) / 1000 }], select: segments.length });
    }, [segments, limits.max_segments, bounds.lo, bounds.hi, minSeg, dispatch]);

    const deleteSegment = useCallback((index) => {
        if (segments.length <= 1) return;
        dispatch({ type: 'commit', segments: segments.filter((_, i) => i !== index), select: Math.max(0, index - 1) });
    }, [segments, dispatch]);

    const moveSegment = useCallback((index, dir) => {
        const j = index + dir;
        if (j < 0 || j >= segments.length) return;
        const next = segments.slice();
        [next[index], next[j]] = [next[j], next[index]];
        dispatch({ type: 'commit', segments: next, select: j });
    }, [segments, dispatch]);

    const splitSegment = useCallback((index) => {
        if (segments.length >= limits.max_segments) return;
        const seg = segments[index];
        if (seg.end - seg.start < minSeg * 2) return;
        let at = seg.start + (seg.end - seg.start) / 2;
        // Cut where the playhead is, when it sits inside this segment. It lives
        // on the current assembly now, so this no longer needs the rendered
        // recipe to still match.
        let offset = 0;
        for (let i = 0; i < segments.length; i += 1) {
            const len = segments[i].end - segments[i].start;
            if (i === index && playhead > offset + minSeg && playhead < offset + len - minSeg) {
                at = segments[i].start + (playhead - offset);
            }
            offset += len;
        }
        at = snapEdge(at, 'end');
        if (at - seg.start < minSeg || seg.end - at < minSeg) at = seg.start + (seg.end - seg.start) / 2;
        const next = segments.flatMap((s, i) => (i === index
            ? [{ start: s.start, end: Math.round(at * 1000) / 1000 }, { start: Math.round(at * 1000) / 1000, end: s.end }]
            : [s]));
        dispatch({ type: 'commit', segments: next, select: index });
    }, [segments, limits.max_segments, minSeg, playhead, snapEdge, dispatch]);

    return {
        snapEdge,
        clampSeg,
        setSegment,
        addSegment,
        deleteSegment,
        moveSegment,
        splitSegment
    };
}
