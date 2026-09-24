import React from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';

export default function EditorFooter({
    renderError,
    overCaps,
    total,
    limits,
    canRender,
    dirty,
    doRender,
    rendering,
    renderSeconds,
    needsSourcePath,
    onClose,
    setConfirmClose
}) {
    return (
        <div className="shrink-0 pt-4 mt-4 border-t border-rule">
            {renderError && (
                <div className="mb-3 px-3 py-2 rounded-input text-xs text-danger bg-[color-mix(in_oklab,var(--color-danger)_10%,transparent)] flex items-center gap-2">
                    <AlertCircle size={14} className="shrink-0" /> {renderError}
                </div>
            )}
            {overCaps && (
                <p className="mb-3 text-[11px] text-warn lowercase">
                    {total > limits.max_total_seconds ? `o corte ultrapassa ${Math.round(limits.max_total_seconds)}s` : `mais de ${limits.max_segments} segmentos`}
                </p>
            )}
            <div className="flex gap-2">
                <button
                    className="btn-ghost"
                    onClick={() => (rendering ? onClose() : dirty ? setConfirmClose(true) : onClose())}
                >
                    {rendering ? 'fechar' : dirty ? 'cancelar' : 'fechar'}
                </button>
                <button className="btn-primary flex-1 flex items-center justify-center gap-2" disabled={!canRender || !dirty} onClick={doRender}>
                    {rendering
                        ? (<><Loader2 size={16} className="animate-spin text-brassink" /> renderizando novamente… {renderSeconds}s</>)
                        : (needsSourcePath ? 'renderizar a partir do original' : 'renderizar corte')}
                </button>
            </div>
            {rendering && (
                <p className="text-[11px] text-muted mt-2 lowercase">
                    você pode fechar este editor; a renderização continuará em segundo plano e o corte será atualizado quando terminar
                </p>
            )}
        </div>
    );
}
