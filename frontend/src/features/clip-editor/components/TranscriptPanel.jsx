import React, { useMemo, useCallback, useEffect, useRef, useState, useDeferredValue } from 'react';
import TranscriptChunk from '../TranscriptChunk';
import { fmt } from '../../../lib/clipUtils';

const CHUNK_WORDS = 50;

export default function TranscriptPanel({
    words,
    segments,
    selected,
    sourceTime,
    seekSource,
    setSegment
}) {
    const transcriptRef = useRef(null);
    const [selectedWord, setSelectedWord] = useState(null);

    const selectedSeg = segments[selected] || null;
    const highlightSeg = useDeferredValue(selectedSeg);
    const anchorIndex = useMemo(() => (
        selectedSeg ? words.findIndex((w) => w.e > selectedSeg.start) : -1
    ), [words, selectedSeg]);

    const activeWordIndex = useMemo(() => {
        let lo = 0;
        let hi = words.length - 1;
        let best = -1;
        while (lo <= hi) {
            const mid = (lo + hi) >> 1;
            if (words[mid].s <= sourceTime) { best = mid; lo = mid + 1; } else hi = mid - 1;
        }
        return best;
    }, [words, sourceTime]);

    const selectedWordIndex = useMemo(() => (
        selectedWord ? words.findIndex((w) => w.s === selectedWord.s && w.e === selectedWord.e) : -1
    ), [words, selectedWord]);

    const chunks = useMemo(() => {
        const out = [];
        for (let i = 0; i < words.length; i += CHUNK_WORDS) {
            out.push({ offset: i, items: words.slice(i, i + CHUNK_WORDS) });
        }
        return out;
    }, [words]);

    const scrollTranscriptTo = useCallback((selector) => {
        const box = transcriptRef.current;
        if (!box) return;
        const el = box.querySelector(selector);
        if (!el) return;
        box.scrollTop = Math.max(0, el.offsetTop - box.clientHeight / 2);
    }, []);

    useEffect(() => {
        scrollTranscriptTo('[data-anchor="1"]');
    }, [selected, words.length, scrollTranscriptTo]);

    useEffect(() => {
        scrollTranscriptTo('[data-active="1"]');
    }, [activeWordIndex, scrollTranscriptTo]);

    const pickWord = useCallback((w) => {
        setSelectedWord((prev) => (prev && prev.s === w.s && prev.e === w.e ? null : w));
        seekSource(w.s);
    }, [seekSource]);

    return (
        <div className="shrink-0 h-[30%] min-h-[9rem] flex flex-col">
            <div className="flex items-center justify-between mb-1.5 gap-2 shrink-0">
                <p className="eyebrow">Transcrição · vídeo original</p>
                {selectedWord ? (
                    <div className="flex items-center gap-1.5 shrink-0">
                        <button
                            onClick={() => setSegment(selected, { start: selectedWord.s }, { snap: false })}
                            title={`segmento #${selected + 1} inicia em "${selectedWord.w}" (${fmt(selectedWord.s)})`}
                            className="btn-quiet text-[11px] py-1 px-2"
                        >
                            #{selected + 1} inicia aqui
                        </button>
                        <button
                            onClick={() => setSegment(selected, { end: selectedWord.e }, { snap: false })}
                            title={`segmento #${selected + 1} termina em "${selectedWord.w}" (${fmt(selectedWord.e)})`}
                            className="btn-quiet text-[11px] py-1 px-2"
                        >
                            #{selected + 1} termina aqui
                        </button>
                    </div>
                ) : words.length > 0 ? (
                    <span className="readout shrink-0">CLIQUE EM UMA PALAVRA PARA DEFINIR O CORTE</span>
                ) : null}
            </div>
            {words.length === 0 ? (
                <p className="text-xs text-muted lowercase">este corte não possui transcrição</p>
            ) : (
                <div
                    ref={transcriptRef}
                    className="relative flex-1 min-h-0 flex flex-wrap content-start gap-x-1 gap-y-1.5 overflow-y-auto custom-scrollbar pr-1"
                >
                    {chunks.map((c) => {
                        const first = c.items[0].s;
                        const last = c.items[c.items.length - 1].e;
                        let lit = 'none';
                        if (highlightSeg && !(last <= highlightSeg.start || first >= highlightSeg.end)) {
                            lit = (first >= highlightSeg.start && last <= highlightSeg.end)
                                ? 'all' : highlightSeg;
                        }
                        const local = (idx) => (
                            idx >= c.offset && idx < c.offset + c.items.length ? idx - c.offset : -1
                        );
                        return (
                            <TranscriptChunk
                                key={c.offset}
                                items={c.items}
                                offset={c.offset}
                                lit={lit}
                                active={local(activeWordIndex)}
                                anchorAt={local(anchorIndex)}
                                selectedAt={local(selectedWordIndex)}
                                onPick={pickWord}
                            />
                        );
                    })}
                </div>
            )}
        </div>
    );
}
