import React from 'react';
import { ChevronsRight, ChevronsLeft, X } from 'lucide-react';
import { fmt } from '../../../lib/clipUtils';

export default function ThreePointControls({
    markIn,
    markOut,
    markRange,
    minSeg,
    markHere,
    clearMarks,
    sendToClip,
    selected,
    segmentsLength,
    maxSegments
}) {
    return (
        <div className="shrink-0 rounded-input border border-rule bg-paper2 p-2 flex items-stretch gap-3">
            <div className="flex items-center gap-1.5 flex-1 min-w-0">
                <span className="readout shrink-0 text-muted">1 · MARCAR</span>
                <button onClick={() => markHere('in')} className="btn-quiet text-[11px] py-1 px-2 flex items-center gap-1 shrink-0">
                    <ChevronsRight size={12} /> início <span className="text-muted">i</span>
                </button>
                <button onClick={() => markHere('out')} className="btn-quiet text-[11px] py-1 px-2 flex items-center gap-1 shrink-0">
                    <ChevronsLeft size={12} /> fim <span className="text-muted">o</span>
                </button>
                <p className={`readout px-1 truncate ${markRange ? 'text-ink' : ''}`}>
                    {markIn === null ? '—:——' : fmt(markIn)}
                    {' → '}{markOut === null ? '—:——' : fmt(markOut)}
                    {markRange && ` · ${fmt(markRange.end - markRange.start)}`}
                    {markIn !== null && markOut !== null && !markRange
                        && ` · MENOR QUE ${minSeg}S`}
                </p>
                <button
                    onClick={clearMarks}
                    disabled={markIn === null && markOut === null}
                    className="p-1 rounded-input text-muted hover:text-ink hover:bg-paper3 disabled:opacity-40 shrink-0"
                    aria-label="limpar pontos de início e fim"
                >
                    <X size={13} />
                </button>
            </div>

            <div className="w-px bg-[color:var(--color-rule-2)] shrink-0" />

            <div className="flex items-center gap-1.5 shrink-0">
                <span className="readout text-muted">2 · ENVIAR</span>
                <button
                    onClick={() => sendToClip('replace')}
                    disabled={!markRange}
                    title="o segmento selecionado será substituído por este intervalo (.)"
                    className="btn-primary text-[11px] py-1.5 px-2 disabled:opacity-40"
                >
                    substituir #{selected + 1}
                </button>
                <button
                    onClick={() => sendToClip('insert')}
                    disabled={!markRange || segmentsLength >= maxSegments}
                    title="adiciona este intervalo como um novo segmento após o selecionado (,)"
                    className="btn-quiet text-[11px] py-1.5 px-2 disabled:opacity-40"
                >
                    inserir após #{selected + 1}
                </button>
            </div>
        </div>
    );
}
