import React from 'react';
import { TrendingUp, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function ViralHUD({ score, explanation, reasons = [], risks = [] }) {
    if (!Number.isFinite(score)) return null;

    const hasDetails = reasons?.length > 0 || risks?.length > 0;

    return (
        <div className="mb-3 bg-paper/80 rounded-input border border-rule p-2.5 sm:p-3 flex gap-2.5 sm:gap-3 items-center shadow-sm min-w-0 relative group">
            <div className="flex flex-col items-center justify-center bg-paper2 border border-rule2 rounded-input w-12 h-12 shrink-0 py-1 px-1 relative">
                <span className={
                    score >= 80 ? 'text-xl sm:text-2xl font-bold text-ok leading-none tracking-tight'
                        : score >= 65 ? 'text-xl sm:text-2xl font-bold text-violet leading-none tracking-tight'
                            : 'text-xl sm:text-2xl font-bold text-ink2 leading-none tracking-tight'
                }>
                    {score}
                </span>
                <span className="text-[8px] sm:text-[9px] font-mono uppercase tracking-wider text-muted mt-0.5 font-semibold">VIRAL</span>
                
                {/* Visual cue that there's more info on hover */}
                {hasDetails && (
                    <div className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-ok rounded-full border border-paper shadow-sm"></div>
                )}
            </div>
            <div className="flex-1 min-w-0 cursor-default">
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

            {hasDetails && (
                <div className="absolute left-0 sm:left-14 top-full mt-2 w-72 bg-paper2 border border-rule2 shadow-xl shadow-black/20 rounded-xl p-4 z-[100] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 pointer-events-none group-hover:translate-y-0 -translate-y-1">
                    {reasons?.length > 0 && (
                        <div className="mb-3 last:mb-0">
                            <h4 className="text-[10px] font-bold text-ok uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                <CheckCircle2 size={12} />
                                Motivos
                            </h4>
                            <ul className="space-y-1.5 pl-0.5">
                                {reasons.map((reason, i) => (
                                    <li key={i} className="text-xs text-ink/90 flex items-start gap-2 leading-relaxed">
                                        <span className="text-ok mt-[3px] text-[10px]">•</span>
                                        <span>{reason}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                    
                    {reasons?.length > 0 && risks?.length > 0 && (
                        <div className="h-px w-full bg-rule my-3" />
                    )}

                    {risks?.length > 0 && (
                        <div className="mb-3 last:mb-0">
                            <h4 className="text-[10px] font-bold text-amber-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                <AlertTriangle size={12} />
                                Riscos
                            </h4>
                            <ul className="space-y-1.5 pl-0.5">
                                {risks.map((risk, i) => (
                                    <li key={i} className="text-xs text-ink/90 flex items-start gap-2 leading-relaxed">
                                        <span className="text-amber-500 mt-[3px] text-[10px]">•</span>
                                        <span>{risk}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
