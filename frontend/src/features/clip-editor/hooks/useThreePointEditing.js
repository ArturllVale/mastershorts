import { useState, useMemo } from 'react';

const round3 = (t) => Math.round(t * 1000) / 1000;

export function useThreePointEditing({
    sourceRef,
    minSeg,
    selected,
    segments,
    limits,
    dispatch
}) {
    const [markIn, setMarkIn] = useState(null);
    const [markOut, setMarkOut] = useState(null);

    const markHere = (which) => {
        const v = sourceRef.current;
        if (!v || !Number.isFinite(v.currentTime)) return;
        (which === 'in' ? setMarkIn : setMarkOut)(round3(v.currentTime));
    };

    const clearMarks = () => {
        setMarkIn(null);
        setMarkOut(null);
    };

    const markRange = useMemo(() => {
        if (markIn === null || markOut === null) return null;
        const lo = Math.min(markIn, markOut);
        const hi = Math.max(markIn, markOut);
        return hi - lo >= minSeg ? { start: round3(lo), end: round3(hi) } : null;
    }, [markIn, markOut, minSeg]);

    const sendToClip = (mode) => {
        if (!markRange) return;
        if (mode === 'replace') {
            dispatch({
                type: 'commit',
                segments: segments.map((s, i) => (i === selected ? { ...markRange } : s)),
                select: selected,
            });
            return;
        }
        if (segments.length >= limits.max_segments) return;
        const next = segments.slice();
        next.splice(selected + 1, 0, { ...markRange });
        dispatch({ type: 'commit', segments: next, select: selected + 1 });
    };

    return {
        markIn,
        setMarkIn,
        markOut,
        setMarkOut,
        markHere,
        clearMarks,
        markRange,
        sendToClip
    };
}
