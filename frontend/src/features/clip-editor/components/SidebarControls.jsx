import React from 'react';
import { Undo2, Redo2, Plus } from 'lucide-react';
import SegmentRow from '../SegmentRow';

export default function SidebarControls({
    segments,
    selected,
    statePastLength,
    stateFutureLength,
    limits,
    dispatch,
    setSegment,
    sourceOpen,
    seekSource,
    moveSegment,
    splitSegment,
    deleteSegment,
    minSeg,
    addSegment,
    sourceAvailable,
    framing,
    setFraming,
    renderedFraming,
    snapToWords,
    setSnapToWords,
    reapplyCaptions,
    setReapplyCaptions,
    outOfRange,
    footerNode // To inject EditorFooter without importing it here to keep dependency clean
}) {
    return (
        <div className="w-full xl:w-[21rem] shrink-0 flex flex-col min-h-0">
            <div className="flex-1 xl:overflow-y-auto custom-scrollbar pr-1 space-y-5">
                {/* segments */}
                <div>
                    <div className="flex items-center justify-between mb-2">
                        <p className="eyebrow">Segmentos · {segments.length}/{limits.max_segments}</p>
                        <div className="flex items-center gap-1">
                            <button className="p-1.5 rounded-input text-muted hover:text-ink hover:bg-paper3 disabled:opacity-45" disabled={!statePastLength} onClick={() => dispatch({ type: 'undo' })} aria-label="desfazer"><Undo2 size={14} /></button>
                            <button className="p-1.5 rounded-input text-muted hover:text-ink hover:bg-paper3 disabled:opacity-45" disabled={!stateFutureLength} onClick={() => dispatch({ type: 'redo' })} aria-label="refazer"><Redo2 size={14} /></button>
                        </div>
                    </div>
                    <div className="space-y-2">
                        {segments.map((seg, i) => (
                            <SegmentRow
                                key={i}
                                seg={seg}
                                i={i}
                                selected={selected}
                                outOfRange={outOfRange}
                                dispatch={dispatch}
                                setSegment={setSegment}
                                sourceOpen={sourceOpen}
                                seekSource={seekSource}
                                moveSegment={moveSegment}
                                splitSegment={splitSegment}
                                deleteSegment={deleteSegment}
                                minSeg={minSeg}
                                limits={limits}
                                segments={segments}
                            />
                        ))}
                    </div>
                    <button
                        onClick={addSegment}
                        disabled={segments.length >= limits.max_segments}
                        className="mt-2 w-full flex items-center justify-center gap-1.5 py-2 rounded-input border border-dashed border-rule2 text-xs lowercase text-ink2 hover:bg-paper3 transition-colors disabled:opacity-45"
                    >
                        <Plus size={14} /> adicionar segmento
                    </button>
                    {!sourceAvailable && (
                        <p className="text-[11px] text-muted mt-2 leading-relaxed">
                            o vídeo original não está mais disponível no servidor, portanto os cortes estão
                            limitados ao intervalo deste corte
                        </p>
                    )}
                </div>

                {/* framing override */}
                <div>
                    <p className="eyebrow mb-2">Enquadramento</p>
                    <div className="grid grid-cols-3 gap-1.5">
                        {[
                            { value: 'auto', label: 'automático', hint: 'A IA define por cena' },
                            { value: 'full', label: 'quadro inteiro', hint: 'plano completo, sem corte lateral' },
                            { value: 'track', label: 'seguir pessoa', hint: 'câmera segue a pessoa falante' },
                        ].map((f) => (
                            <button
                                key={f.value}
                                type="button"
                                title={f.hint}
                                disabled={f.value !== 'auto' && !sourceAvailable}
                                onClick={() => setFraming(f.value)}
                                className={`py-1.5 px-2 rounded-input border text-xs lowercase transition-colors
                                    ${framing === f.value
                                        ? 'border-[color:var(--color-accent)] text-ink'
                                        : 'border-rule2 text-muted hover:border-[color:var(--color-accent)]'}
                                    disabled:opacity-40 disabled:cursor-not-allowed`}
                            >
                                {f.label}
                            </button>
                        ))}
                    </div>
                    {!sourceAvailable && (
                        <p className="text-[11px] text-muted mt-1.5 leading-relaxed">
                            mudanças de enquadramento requerem o vídeo original, que não está mais no servidor
                        </p>
                    )}
                    {framing !== renderedFraming && (
                        <p className="text-[11px] text-muted mt-1.5 leading-relaxed">
                            alterar o enquadramento reprocessa todo o vídeo (mais lento que um recorte rápido)
                        </p>
                    )}
                </div>

                {/* toggles */}
                <div className="space-y-2.5">
                    <label className="flex items-center justify-between cursor-pointer">
                        <span className="text-xs lowercase text-ink2">alinhar cortes às palavras faladas</span>
                        <span className="relative inline-flex items-center">
                            <input type="checkbox" checked={snapToWords} onChange={(e) => setSnapToWords(e.target.checked)} className="sr-only peer" />
                            <span className="w-8 h-4 rounded-full bg-paper3 peer-checked:bg-brass transition-colors after:content-[''] after:absolute after:left-0.5 after:top-0.5 after:w-3 after:h-3 after:rounded-full after:bg-ink after:transition-transform peer-checked:after:translate-x-4" />
                        </span>
                    </label>
                    <label className="flex items-center justify-between cursor-pointer">
                        <span className="text-xs lowercase text-ink2">reaplicar legendas após o recorte</span>
                        <span className="relative inline-flex items-center">
                            <input type="checkbox" checked={reapplyCaptions} onChange={(e) => setReapplyCaptions(e.target.checked)} className="sr-only peer" />
                            <span className="w-8 h-4 rounded-full bg-paper3 peer-checked:bg-brass transition-colors after:content-[''] after:absolute after:left-0.5 after:top-0.5 after:w-3 after:h-3 after:rounded-full after:bg-ink after:transition-transform peer-checked:after:translate-x-4" />
                        </span>
                    </label>
                </div>

                {/* keyboard legend */}
                <div>
                    <p className="eyebrow mb-2">Atalhos</p>
                    <p className="readout leading-relaxed">
                        ESPAÇO REPRODUZIR · S DIVIDIR · ⌫ EXCLUIR · ⌘Z DESFAZER
                        {sourceOpen && ' · I INÍCIO · O FIM · , INSERIR · . SUBSTITUIR'}
                    </p>
                </div>
            </div>

            {footerNode}
        </div>
    );
}
