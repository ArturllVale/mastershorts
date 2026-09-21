import React from 'react';
import { TrendingUp } from 'lucide-react';

export default function ViralHUD({ score, explanation }) {
    if (!Number.isFinite(score)) return null;

    return (
        <div className="mb-3 bg-paper/80 rounded-input border border-rule p-2.5 sm:p-3 flex gap-2.5 sm:gap-3 items-center shadow-sm min-w-0">
            <div className="flex flex-col items-center justify-center bg-paper2 border border-rule2 rounded-input w-12 h-12 shrink-0 py-1 px-1">
                <span className={
                    score >= 80 ? 'text-xl sm:text-2xl font-bold text-ok leading-none tracking-tight'
                        : score >= 65 ? 'text-xl sm:text-2xl font-bold text-violet leading-none tracking-tight'
                            : 'text-xl sm:text-2xl font-bold text-ink2 leading-none tracking-tight'
                }>
                    {score}
                </span>
                <span className="text-[8px] sm:text-[9px] font-mono uppercase tracking-wider text-muted mt-0.5 font-semibold">VIRAL</span>
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5 min-w-0">
                    <TrendingUp size={12} className="text-violet shrink-0" />
                    <span className="eyebrow text-[10px] text-violet font-mono truncate tracking-wider font-semibold">
                        ANÁLISE DE MOMENTO VIRAL
                    </span>
                </div>
                <p className="text-xs text-ink2 leading-relaxed line-clamp-2 break-words">
                    {explanation || "Gancho de alto impacto com retenção imediata e forte potencial de engajamento."}
                </p>
            </div>
        </div>
    );
}
