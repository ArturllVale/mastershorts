import { useCallback } from 'react';

export function useClipScrub({
    dragRef,
    clipTrackRef,
    clipTrackSeconds,
    total,
    playhead,
    clampToCovered,
    setPlayhead,
    clipToRendered,
    spanIndexAt,
    playSpanRef,
    videoRef,
    seekSource,
    clipToSource,
    sourceOpen
}) {
    const onScrubMove = useCallback((e) => {
        const d = dragRef.current;
        if (!d || d.kind !== 'scrub') return;
        d.apply(d.at(e.clientX), { path: true });
    }, [dragRef]);

    const onScrubUp = useCallback(() => {
        dragRef.current = null;
        window.removeEventListener('pointermove', onScrubMove);
        window.removeEventListener('pointerup', onScrubUp);
        window.removeEventListener('pointercancel', onScrubUp);
    }, [dragRef, onScrubMove]);

    const startClipScrub = useCallback((e) => {
        if (e.button !== undefined && e.button !== 0) return;
        const rect = clipTrackRef.current?.getBoundingClientRect();
        if (!rect || !clipTrackSeconds) return;
        e.preventDefault();
        try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* window listeners still fire */ }

        const at = (clientX) => Math.max(0, Math.min(
            total, ((clientX - rect.left) / rect.width) * clipTrackSeconds));
        
        let last = playhead;
        const apply = (raw, { path = false } = {}) => {
            const t = clampToCovered(raw, last, { path });
            last = t;
            setPlayhead(t);
            const r = clipToRendered(t);
            playSpanRef.current = spanIndexAt(t);
            if (r !== null && videoRef.current) {
                try { videoRef.current.currentTime = r; } catch { /* not seekable yet */ }
            }
            if (sourceOpen) seekSource(clipToSource(t));
        };

        apply(at(e.clientX));
        dragRef.current = { kind: 'scrub', at, apply };
        window.addEventListener('pointermove', onScrubMove);
        window.addEventListener('pointerup', onScrubUp);
        window.addEventListener('pointercancel', onScrubUp);
    }, [clipTrackRef, clipTrackSeconds, total, playhead, clampToCovered, setPlayhead, clipToRendered, spanIndexAt, playSpanRef, videoRef, clipToSource, seekSource, sourceOpen, dragRef, onScrubMove, onScrubUp]);

    return {
        startClipScrub
    };
}
