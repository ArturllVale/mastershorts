import React from 'react';

const fmt = (s) => {
    const min = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${min}:${sec.toString().padStart(2, '0')}`;
};

const TranscriptChunk = React.memo(function TranscriptChunk({
    items, offset, lit, active, anchorAt, selectedAt, onPick,
}) {
    return (
        <>
            {items.map((w, i) => {
                const inside = lit === 'all'
                    || (lit !== 'none' && w.e > lit.start && w.s < lit.end);
                const isActive = i === active;
                const isSel = i === selectedAt;
                return (
                    <button
                        key={`${w.s}-${offset + i}`}
                        data-anchor={i === anchorAt ? '1' : undefined}
                        data-active={isActive ? '1' : undefined}
                        onClick={() => onPick(w)}
                        title={`${fmt(w.s)} – ${fmt(w.e)}`}
                        className={`px-1 py-0.5 rounded text-xs transition-colors ${
                            isSel ? 'bg-brass text-brassink'
                                : isActive ? 'bg-brass/30 text-ink'
                                    : inside ? 'text-ink hover:bg-paper3'
                                        : 'text-muted hover:bg-paper3'}`}
                    >
                        {w.w}
                    </button>
                );
            })}
        </>
    );
});

export default TranscriptChunk;
