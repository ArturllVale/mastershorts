import React from 'react';
import { fmt } from '../../../lib/clipUtils';
import { COVERAGE_EPSILON, SEGMENT_COLORS } from '../constants';

export default function ClipTrack({
    total,
    dirty,
    missingSeconds,
    clipTrackRef,
    startClipScrub,
    blocks,
    dispatch,
    selected,
    outOfRange,
    startTrimDrag,
    clipTrackSeconds,
    coverage,
    playhead
}) {
    return (
        <div className="shrink-0 select-none">
            <div className="flex items-center justify-between mb-1.5 gap-3">
                <p className="readout">CORTE · {fmt(total)}</p>
                {dirty && (
                    <p className="readout truncate">
                        {missingSeconds > COVERAGE_EPSILON
                            ? `VERMELHO · ${fmt(missingSeconds)} AINDA NÃO RENDERIZADO`
                            : 'PRÉVIA DA EDIÇÃO'}
                    </p>
                )}
            </div>
            <div
                ref={clipTrackRef}
                onPointerDown={startClipScrub}
                className="relative h-12 rounded-input bg-paper border border-rule overflow-hidden touch-none cursor-pointer"
            >
                {blocks.map(({ seg, i, left, width }) => (
                    <div
                        key={i}
                        onPointerDown={() => dispatch({ type: 'select', index: i })}
                        className={`absolute top-1 bottom-1 rounded-[6px] border ${i === selected ? 'border-[color:var(--color-accent)]' : 'border-transparent'} ${outOfRange(seg) ? 'border-[color:var(--color-danger)]' : ''}`}
                        style={{ left: `${left}%`, width: `${width}%`, background: `color-mix(in oklab, ${SEGMENT_COLORS[i % SEGMENT_COLORS.length]} 28%, transparent)` }}
                    >
                        <span className="absolute inset-0 flex items-center justify-center readout pointer-events-none select-none">
                            #{i + 1} · {fmt(seg.end - seg.start)}
                        </span>
                        {/* trim handles */}
                        <div
                            onPointerDown={(e) => startTrimDrag(e, i, 'start', clipTrackRef.current, clipTrackSeconds)}
                            className="absolute left-0 top-0 bottom-0 w-2 touch-none cursor-ew-resize rounded-l-[6px]"
                            style={{ background: SEGMENT_COLORS[i % SEGMENT_COLORS.length] }}
                        />
                        <div
                            onPointerDown={(e) => startTrimDrag(e, i, 'end', clipTrackRef.current, clipTrackSeconds)}
                            className="absolute right-0 top-0 bottom-0 w-2 touch-none cursor-ew-resize rounded-r-[6px]"
                            style={{ background: SEGMENT_COLORS[i % SEGMENT_COLORS.length] }}
                        />
                    </div>
                ))}
                {/* Render status, as an NLE draws it */}
                {dirty && coverage.map((sp, i) => (
                    <div
                        key={i}
                        className={`absolute top-0 h-1 pointer-events-none ${
                            sp.rendered === null ? 'bg-danger' : 'bg-ok/50'}`}
                        style={{
                            left: `${(sp.start / clipTrackSeconds) * 100}%`,
                            width: `${((sp.end - sp.start) / clipTrackSeconds) * 100}%`,
                        }}
                    />
                ))}
                <div
                    title="arraste para navegar pelo corte"
                    className="absolute top-1 bottom-1 w-2.5 -ml-[5px] rounded-[4px] bg-ink border border-paper cursor-grab active:cursor-grabbing"
                    style={{ left: `${(Math.min(playhead, clipTrackSeconds) / clipTrackSeconds) * 100}%` }}
                />
            </div>
        </div>
    );
}
