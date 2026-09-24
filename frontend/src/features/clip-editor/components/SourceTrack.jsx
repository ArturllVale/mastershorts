import React from 'react';
import { fmt } from '../../../lib/clipUtils';
import { SEGMENT_COLORS } from '../constants';

export default function SourceTrack({
    sourceDuration,
    edl,
    sourceAvailable,
    sourceTrackRef,
    startGhostDrag,
    canonical,
    segments,
    selected,
    startTrimDrag,
    markRange,
    ghost,
    markIn,
    markOut,
    sourceOpen,
    sourceTime
}) {
    return (
        <div className="shrink-0 select-none">
            <div className="flex items-center justify-between mb-1.5 gap-3">
                <p className="readout">
                    SOURCE · {fmt(sourceDuration)}{edl?.source?.duration_estimated ? ' (EST.)' : ''}
                    {!sourceAvailable && ' · EXPIRED — TRIMS LIMITED TO THE ORIGINAL RANGE'}
                </p>
                {sourceAvailable && (
                    <p className="readout hidden xl:block truncate">
                        DRAG EMPTY SPACE TO MARK IN/OUT · BLOCK TO MOVE · EDGES TO TRIM
                    </p>
                )}
            </div>
            <div
                ref={sourceTrackRef}
                onPointerDown={startGhostDrag}
                className={`relative h-8 rounded-input border overflow-hidden touch-none ${sourceAvailable ? 'bg-paper border-rule cursor-crosshair' : 'bg-paper border-rule opacity-60'}`}
            >
                {/* canonical range marker */}
                {sourceDuration > 0 && (
                    <div
                        className="absolute top-0 bottom-0 border-x border-rule2 bg-paper3/60 pointer-events-none"
                        style={{
                            left: `${(canonical.start / sourceDuration) * 100}%`,
                            width: `${((canonical.end - canonical.start) / sourceDuration) * 100}%`,
                        }}
                    />
                )}
                {sourceDuration > 0 && segments.map((seg, i) => (
                    <div
                        key={i}
                        // Body drag slides the segment along the source without
                        // changing its duration; the edges trim it.
                        onPointerDown={(e) => startTrimDrag(e, i, 'move', sourceTrackRef.current, sourceDuration)}
                        className={`absolute top-1 bottom-1 rounded-[4px] touch-none cursor-grab active:cursor-grabbing ${i === selected ? 'ring-1 ring-[color:var(--color-accent)]' : ''}`}
                        style={{
                            left: `${(seg.start / sourceDuration) * 100}%`,
                            width: `${Math.max(((seg.end - seg.start) / sourceDuration) * 100, 0.4)}%`,
                            // A short segment on a 14-minute source is a sliver;
                            // without a floor there is nothing left to grab.
                            minWidth: '14px',
                            background: SEGMENT_COLORS[i % SEGMENT_COLORS.length],
                        }}
                        title={`#${i + 1} · ${fmt(seg.start)} → ${fmt(seg.end)} — drag to move, edges to trim`}
                    >
                        {/* Capped at a third each so the middle stays grabbable
                            however narrow the block gets. */}
                        <div
                            onPointerDown={(e) => startTrimDrag(e, i, 'start', sourceTrackRef.current, sourceDuration)}
                            className="absolute left-0 top-0 bottom-0 w-1.5 max-w-[33%] touch-none cursor-ew-resize rounded-l-[4px] bg-ink/35"
                        />
                        <div
                            onPointerDown={(e) => startTrimDrag(e, i, 'end', sourceTrackRef.current, sourceDuration)}
                            className="absolute right-0 top-0 bottom-0 w-1.5 max-w-[33%] touch-none cursor-ew-resize rounded-r-[4px] bg-ink/35"
                        />
                    </div>
                ))}
                {markRange && sourceDuration > 0 && !ghost && (
                    <div
                        className="absolute inset-y-0 border-x-2 border-brass bg-brass/15 pointer-events-none"
                        style={{
                            left: `${(markRange.start / sourceDuration) * 100}%`,
                            width: `${((markRange.end - markRange.start) / sourceDuration) * 100}%`,
                        }}
                    />
                )}
                {/* A lone mark still has to be visible, or setting IN and
                    then hunting for OUT gives no feedback at all. */}
                {sourceDuration > 0 && !ghost && !markRange && [markIn, markOut].map((t, i) => (
                    t === null ? null : (
                        <div
                            key={i}
                            className="absolute inset-y-0 w-0.5 bg-brass pointer-events-none"
                            style={{ left: `${(t / sourceDuration) * 100}%` }}
                        />
                    )
                ))}
                {/* the source monitor's own playhead */}
                {sourceOpen && sourceDuration > 0 && (
                    <div
                        className="absolute top-0 bottom-0 w-px bg-ink pointer-events-none"
                        style={{ left: `${(Math.min(sourceTime, sourceDuration) / sourceDuration) * 100}%` }}
                    />
                )}
                {ghost && sourceDuration > 0 && (
                    <div
                        className="absolute top-1 bottom-1 rounded-[4px] bg-ink/40 border border-dashed border-ink pointer-events-none"
                        style={{
                            left: `${(ghost.start / sourceDuration) * 100}%`,
                            width: `${((ghost.end - ghost.start) / sourceDuration) * 100}%`,
                        }}
                    />
                )}
            </div>
            <div className="flex justify-between mt-1">
                <span className="readout">0:00</span>
                <span className="readout">{fmt(sourceDuration / 2)}</span>
                <span className="readout">{fmt(sourceDuration)}</span>
            </div>
        </div>
    );
}
