import { useMemo, useCallback } from 'react';
import { totalOf } from '../../../lib/clipUtils';

const COVERAGE_EPSILON = 0.02;

export function useEditorTimeline({
    segments,
    renderedSegments,
    framing,
    renderedFraming
}) {
    // The rendered file IS renderedSegments cut and concatenated in order, so any instant
    // of source still inside one of those ranges exists in the file and can be played.
    const coverage = useMemo(() => {
        if (!segments.length) return [];
        if (!renderedSegments || framing !== renderedFraming) {
            return [{ start: 0, end: totalOf(segments), rendered: null }];
        }
        const spans = [];
        let clipAcc = 0;
        for (const seg of segments) {
            const segLen = seg.end - seg.start;
            const pieces = [];
            let renAcc = 0;
            for (const r of renderedSegments) {
                const lo = Math.max(seg.start, r.start);
                const hi = Math.min(seg.end, r.end);
                if (hi - lo > COVERAGE_EPSILON) {
                    pieces.push({ lo, hi, rendered: renAcc + (lo - r.start) });
                }
                renAcc += r.end - r.start;
            }
            pieces.sort((a, b) => a.lo - b.lo);

            let cursor = seg.start;
            for (const piece of pieces) {
                const lo = Math.max(piece.lo, cursor);
                if (piece.hi - lo <= COVERAGE_EPSILON) continue;
                if (lo - cursor > COVERAGE_EPSILON) {
                    spans.push({
                        start: clipAcc + (cursor - seg.start),
                        end: clipAcc + (lo - seg.start),
                        rendered: null,
                    });
                }
                spans.push({
                    start: clipAcc + (lo - seg.start),
                    end: clipAcc + (piece.hi - seg.start),
                    rendered: piece.rendered + (lo - piece.lo),
                });
                cursor = piece.hi;
            }
            if (seg.end - cursor > COVERAGE_EPSILON) {
                spans.push({
                    start: clipAcc + (cursor - seg.start),
                    end: clipAcc + segLen,
                    rendered: null,
                });
            }
            clipAcc += segLen;
        }
        return spans;
    }, [segments, renderedSegments, framing, renderedFraming]);

    const missingSeconds = useMemo(() => coverage.reduce(
        (acc, sp) => (sp.rendered === null ? acc + (sp.end - sp.start) : acc), 0), [coverage]);

    const spanIndexAt = useCallback((t) => {
        const i = coverage.findIndex((sp) => t >= sp.start - COVERAGE_EPSILON && t < sp.end);
        return i >= 0 ? i : coverage.length - 1;
    }, [coverage]);

    const clipToRendered = useCallback((t) => {
        const sp = coverage[spanIndexAt(t)];
        if (!sp || sp.rendered === null) return null;
        const offset = Math.max(0, Math.min(t - sp.start, sp.end - sp.start));
        return sp.rendered + offset;
    }, [coverage, spanIndexAt]);

    const renderedToClip = useCallback((r) => {
        for (const sp of coverage) {
            if (sp.rendered === null) continue;
            const end = sp.rendered + (sp.end - sp.start);
            if (r >= sp.rendered - COVERAGE_EPSILON && r <= end + COVERAGE_EPSILON) {
                return sp.start + (r - sp.rendered);
            }
        }
        return null;
    }, [coverage]);

    const hasCovered = useMemo(
        () => coverage.some((sp) => sp.rendered !== null), [coverage]);

    const clampToCovered = useCallback((t, from, { path = false } = {}) => {
        if (!hasCovered) return t;
        const forward = t >= from;

        let wall = null;
        if (path) {
            wall = forward
                ? coverage.find((sp) => sp.rendered === null
                    && sp.end > from + COVERAGE_EPSILON && sp.start < t - COVERAGE_EPSILON)
                : [...coverage].reverse().find((sp) => sp.rendered === null
                    && sp.start < from - COVERAGE_EPSILON && sp.end > t + COVERAGE_EPSILON);
        }
        if (!wall) {
            const sp = coverage[spanIndexAt(t)];
            if (!sp || sp.rendered !== null) return t;
            wall = sp;
        }

        let lo = coverage.indexOf(wall);
        let hi = lo;
        while (lo > 0 && coverage[lo - 1].rendered === null) lo -= 1;
        while (hi < coverage.length - 1 && coverage[hi + 1].rendered === null) hi += 1;
        
        const near = Math.max(0, coverage[lo].start - 0.001);
        const far = coverage[hi].end;
        const hasBefore = lo > 0;
        const hasAfter = hi < coverage.length - 1;

        if (forward) return hasBefore ? near : (hasAfter ? far : t);
        return hasAfter ? far : (hasBefore ? near : t);
    }, [coverage, hasCovered, spanIndexAt]);

    const clipToSource = useCallback((t) => {
        let acc = 0;
        for (const seg of segments) {
            const len = seg.end - seg.start;
            if (t < acc + len) return seg.start + (t - acc);
            acc += len;
        }
        const last = segments[segments.length - 1];
        return last ? last.end : 0;
    }, [segments]);

    return {
        coverage,
        missingSeconds,
        spanIndexAt,
        clipToRendered,
        renderedToClip,
        hasCovered,
        clampToCovered,
        clipToSource
    };
}
