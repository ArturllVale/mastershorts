import React from 'react';
import { Sparkles, ArrowRight } from 'lucide-react';

// Slim, non-blocking banner shown above a tool when a hosted user has no
// entitlement. Google-authed users get the free plan automatically, so this
// only fires for signed-out or magic-link-only accounts.
export default function TrialGate({ toolName = 'this' }) {
  return (
    <div className="card mx-3 sm:mx-6 mt-3 px-3.5 sm:px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4 shrink-0 animate-fade">
      <div className="flex items-start sm:items-center gap-2.5 sm:gap-3 text-sm min-w-0">
        <Sparkles size={16} className="shrink-0 text-brass mt-0.5 sm:mt-0" />
        <div className="text-ink2 leading-relaxed min-w-0">
          <span className="font-medium text-ink">Modo de prévia.</span>{' '}
          Entre com o <span className="font-medium text-ink">Google</span> para usar {toolName} grátis —
          20 min/mês, sem cartão de crédito.
        </div>
      </div>
      <button
        onClick={() => { window.location.hash = '#/pricing'; }}
        className="btn-primary shrink-0 text-xs px-4 py-2 w-full sm:w-auto"
      >
        Começar grátis <ArrowRight size={14} />
      </button>
    </div>
  );
}
