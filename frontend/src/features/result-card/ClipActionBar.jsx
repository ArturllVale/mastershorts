import React from 'react';
import { LayoutPanelTop, Crosshair, Maximize2, Sparkles, Type, Loader2, Download } from 'lucide-react';
import { watermarkNoticeDismissed } from '../../components/WatermarkModal';

export default function ClipActionBar({
    onEditClip,
    index,
    onReframeClip,
    handleAutoEdit,
    isEditing,
    handleFixSplit,
    isFixingSplit,
    setShowSubtitleModal,
    isSubtitling,
    setShowHookModal,
    isHooking,
    plan,
    setShowWatermarkModal,
    downloadClip,
    downloadPct,
    _setShowModal
}) {
    return (
        <div className="mt-auto pt-3 border-t border-rule space-y-2.5">
            {/* Studio Tools Bar */}
            <div>
                <div className="grid grid-cols-3 sm:grid-cols-5 gap-1.5 sm:gap-2">
                    {onReframeClip && (
                        <button
                            onClick={() => onReframeClip(index)}
                            title="Ajustar Reenquadramento de Câmera e Oradores"
                            className="flex flex-col items-center justify-center py-1.5 sm:py-2 px-1 rounded-input border border-rule bg-paper hover:bg-paper3 hover:border-rule2 text-ink2 hover:text-ink transition-all duration-150 group min-w-0 shadow-sm"
                        >
                            <Crosshair size={14} className="text-muted group-hover:text-violet transition-colors mb-1 shrink-0" />
                            <span className="text-[10px] sm:text-[11px] font-medium leading-tight truncate w-full text-center">Enquadrar</span>
                        </button>
                    )}

                    <button
                        onClick={handleFixSplit}
                        disabled={isFixingSplit}
                        title="Corrigir Split Screen — re-renderiza com tela dividida entre os dois oradores"
                        className="flex flex-col items-center justify-center py-1.5 sm:py-2 px-1 rounded-input border border-rule bg-paper hover:bg-paper3 hover:border-rule2 text-ink2 hover:text-ink transition-all duration-150 group disabled:opacity-40 min-w-0 shadow-sm"
                    >
                        {isFixingSplit
                            ? <Loader2 size={14} className="animate-spin text-violet mb-1 shrink-0" />
                            : <LayoutPanelTop size={14} className="text-muted group-hover:text-violet transition-colors mb-1 shrink-0" />}
                        <span className="text-[10px] sm:text-[11px] font-medium leading-tight truncate w-full text-center">
                            {isFixingSplit ? 'Dividindo…' : 'Split'}
                        </span>
                    </button>

                    <button
                        onClick={handleAutoEdit}
                        disabled={isEditing}
                        title="Extender o clipe — adiciona mais contexto antes e depois"
                        className="flex flex-col items-center justify-center py-1.5 sm:py-2 px-1 rounded-input border border-rule bg-paper hover:bg-paper3 hover:border-rule2 text-ink2 hover:text-ink transition-all duration-150 group disabled:opacity-40 min-w-0 shadow-sm"
                    >
                        {isEditing
                            ? <Loader2 size={14} className="animate-spin text-violet mb-1 shrink-0" />
                            : <Maximize2 size={14} className="text-muted group-hover:text-violet transition-colors mb-1 shrink-0" />}
                        <span className="text-[10px] sm:text-[11px] font-medium leading-tight truncate w-full text-center">
                            {isEditing ? 'Extendendo…' : 'Extender'}
                        </span>
                    </button>

                    <button
                        onClick={() => setShowSubtitleModal(true)}
                        disabled={isSubtitling}
                        title="Legendas Animadas Personalizadas"
                        className="flex flex-col items-center justify-center py-1.5 sm:py-2 px-1 rounded-input border border-rule bg-paper hover:bg-paper3 hover:border-rule2 text-ink2 hover:text-ink transition-all duration-150 group disabled:opacity-40 min-w-0 shadow-sm"
                    >
                        {isSubtitling
                            ? <Loader2 size={14} className="animate-spin text-violet mb-1 shrink-0" />
                            : <Type size={14} className="text-muted group-hover:text-violet transition-colors mb-1 shrink-0" />}
                        <span className="text-[10px] sm:text-[11px] font-medium leading-tight truncate w-full text-center">
                            {isSubtitling ? 'Gerando…' : 'Legendas'}
                        </span>
                    </button>

                    <button
                        onClick={() => setShowHookModal(true)}
                        disabled={isHooking}
                        title="Título Gancho Viral nos primeiros segundos"
                        className="flex flex-col items-center justify-center py-1.5 sm:py-2 px-1 rounded-input border border-rule bg-paper hover:bg-paper3 hover:border-rule2 text-ink2 hover:text-ink transition-all duration-150 group disabled:opacity-40 min-w-0 shadow-sm"
                    >
                        {isHooking
                            ? <Loader2 size={14} className="animate-spin text-violet mb-1 shrink-0" />
                            : <Sparkles size={14} className="text-muted group-hover:text-violet transition-colors mb-1 shrink-0" />}
                        <span className="text-[10px] sm:text-[11px] font-medium leading-tight truncate w-full text-center">
                            {isHooking ? 'Inserindo…' : 'Gancho'}
                        </span>
                    </button>
                </div>
            </div>

            {/* Primary Output Actions */}
            <div className="flex items-center gap-2 pt-1">
                <button
                    onClick={(e) => {
                        e.preventDefault();
                        if (plan === 'free' && !watermarkNoticeDismissed()) {
                            setShowWatermarkModal(true);
                            return;
                        }
                        downloadClip();
                    }}
                    disabled={downloadPct !== null}
                    className="w-full btn-secondary text-xs py-2 px-2.5 sm:px-3 flex items-center justify-center gap-1.5 sm:gap-2 min-w-0"
                >
                    {downloadPct !== null ? (
                        <>
                            <Loader2 size={14} className="animate-spin text-violet shrink-0" />
                            <span className="truncate">Baixando {downloadPct}%</span>
                        </>
                    ) : (
                        <>
                            <Download size={14} className="shrink-0" />
                            <span className="truncate">Baixar MP4</span>
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}
