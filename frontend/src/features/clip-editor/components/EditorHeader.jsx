import React from 'react';
import { X, PanelLeft, PanelLeftClose } from 'lucide-react';
import { fmt } from '../../../lib/clipUtils';

export default function EditorHeader({
    clipIndex,
    clipTitle,
    total,
    needsSourcePath,
    edl,
    sourceAvailable,
    showSource,
    setShowSource,
    confirmClose,
    setConfirmClose,
    rendering,
    dirty,
    onClose
}) {
    return (
        <div className="px-4 sm:px-6 pt-4 pb-3 border-b border-rule flex items-start justify-between gap-4 shrink-0">
            <div className="min-w-0">
                <p className="eyebrow mb-1">EDITOR · CORTE {clipIndex + 1}</p>
                <h2 className="font-display lowercase text-xl sm:text-2xl text-ink truncate">editar corte</h2>
                {clipTitle && <p className="text-xs text-muted truncate mt-0.5">{clipTitle}</p>}
                {/* Phone: the readouts move under the title — as a third
                    column they squeezed the title to two characters. */}
                <p className="readout sm:hidden mt-1 truncate">
                    {fmt(total)} · {needsSourcePath ? 'REENQUADRAMENTO COMPLETO' : 'RECORTE RÁPIDO'}
                </p>
            </div>
            <div className="flex items-center gap-2 sm:gap-3 shrink-0">
                <div className="text-right hidden sm:block">
                    <p className="readout">DURAÇÃO · {fmt(total)}</p>
                    <p className="readout mt-1">
                        {needsSourcePath ? 'PROCESSO · REENQUADRAMENTO' : 'PROCESSO · RECORTE RÁPIDO'}
                        {edl?.rerender_minutes > 0 && ` · ≈${Math.max(1, Math.ceil(total / 60))} MIN`}
                    </p>
                </div>
                {sourceAvailable && (
                    <button
                        onClick={() => setShowSource((v) => !v)}
                        title={showSource
                            ? 'ocultar o monitor original e editar apenas o corte'
                            : 'exibir o monitor original, transcrição e pontos de corte'}
                        aria-label={showSource ? 'ocultar original' : 'mostrar original'}
                        className="btn-quiet text-xs py-1.5 px-2.5 sm:px-3 flex items-center gap-1.5 lowercase"
                    >
                        {showSource ? <PanelLeftClose size={14} /> : <PanelLeft size={14} />}
                        <span className="hidden sm:inline">{showSource ? 'ocultar original' : 'mostrar original'}</span>
                    </button>
                )}
                {confirmClose ? (
                    <div className="flex flex-wrap items-center justify-end gap-2">
                        <span className="text-xs text-warn lowercase hidden sm:inline">descartar alterações?</span>
                        <button className="btn-danger text-xs py-1.5 px-3" onClick={onClose}>descartar</button>
                        <button className="btn-ghost text-xs py-1.5 px-3" onClick={() => setConfirmClose(false)}>continuar editando</button>
                    </div>
                ) : (
                    <button
                        onClick={() => (rendering ? onClose() : dirty ? setConfirmClose(true) : onClose())}
                        className="p-2 rounded-input text-muted hover:text-ink hover:bg-paper3 transition-colors"
                        aria-label="fechar editor"
                    >
                        <X size={18} />
                    </button>
                )}
            </div>
        </div>
    );
}
