import React from 'react';
import { Film, ChevronUp, ChevronDown, Scissors, Trash2 } from 'lucide-react';

const SEGMENT_COLORS = [
    '#f59e0b', '#3b82f6', '#10b981', '#ec4899', '#8b5cf6',
    '#ef4444', '#06b6d4', '#84cc16', '#6366f1', '#f43f5e'
];

const fmt = (s) => {
    const min = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${min}:${sec.toString().padStart(2, '0')}`;
};

export default function SegmentRow({
    seg,
    i,
    selected,
    outOfRange,
    dispatch,
    setSegment,
    sourceOpen,
    seekSource,
    moveSegment,
    splitSegment,
    deleteSegment,
    minSeg,
    limits,
    segments
}) {
    return (
        <div
            onClick={() => dispatch({ type: 'select', index: i })}
            className={`rounded-input border p-2.5 cursor-pointer transition-colors ${i === selected ? 'border-[color:var(--color-accent)] bg-paper3' : 'border-rule hover:bg-paper3'} ${outOfRange(seg) ? 'border-[color:var(--color-danger)]' : ''}`}
        >
            <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded-full shrink-0" style={{ background: SEGMENT_COLORS[i % SEGMENT_COLORS.length] }} />
                <span className="readout">#{i + 1}</span>
                <input
                    type="number"
                    step="0.1"
                    value={seg.start}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => setSegment(i, { start: parseFloat(e.target.value) || 0 }, { snap: false })}
                    className="input-field w-20 py-1 px-1.5 text-xs text-center"
                    aria-label={`segment ${i + 1} start`}
                />
                <span className="text-muted text-xs">→</span>
                <input
                    type="number"
                    step="0.1"
                    value={seg.end}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => setSegment(i, { end: parseFloat(e.target.value) || 0 }, { snap: false })}
                    className="input-field w-20 py-1 px-1.5 text-xs text-center"
                    aria-label={`segment ${i + 1} end`}
                />
                <span className="readout ml-auto">{fmt(seg.end - seg.start)}</span>
            </div>
            <div className="flex items-center gap-1 mt-2">
                {sourceOpen && (
                    <button className="p-1 rounded-input text-muted hover:text-ink hover:bg-paper" onClick={(e) => { e.stopPropagation(); dispatch({ type: 'select', index: i }); seekSource(seg.start); }} aria-label="show this segment in the source monitor"><Film size={13} /></button>
                )}
                <button className="p-1 rounded-input text-muted hover:text-ink hover:bg-paper disabled:opacity-45" disabled={i === 0} onClick={(e) => { e.stopPropagation(); moveSegment(i, -1); }} aria-label="move up"><ChevronUp size={13} /></button>
                <button className="p-1 rounded-input text-muted hover:text-ink hover:bg-paper disabled:opacity-45" disabled={i === segments.length - 1} onClick={(e) => { e.stopPropagation(); moveSegment(i, 1); }} aria-label="move down"><ChevronDown size={13} /></button>
                <button className="p-1 rounded-input text-muted hover:text-ink hover:bg-paper disabled:opacity-45" disabled={seg.end - seg.start < minSeg * 2 || segments.length >= limits.max_segments} onClick={(e) => { e.stopPropagation(); splitSegment(i); }} aria-label="split segment"><Scissors size={13} /></button>
                <button className="p-1 rounded-input text-danger hover:bg-paper disabled:opacity-45 ml-auto" disabled={segments.length <= 1} onClick={(e) => { e.stopPropagation(); deleteSegment(i); }} aria-label="delete segment"><Trash2 size={13} /></button>
            </div>
            {outOfRange(seg) && (
                <p className="text-[11px] text-danger mt-1.5 lowercase">outside the original range — the source video is gone</p>
            )}
        </div>
    );
}
