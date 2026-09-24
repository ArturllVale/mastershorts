import React from 'react';
import { Sparkles } from 'lucide-react';
import { cn } from '../lib/utils';

export default function NavFooterLinks({ collapsed = false, billingEnabled }) {
  if (!billingEnabled) return null;

  return (
    <a
      href="#/pricing"
      title="Planos e Preços"
      className={cn(
        'flex items-center h-9 rounded-lg text-xs text-muted hover:text-ink hover:bg-paper3/60 transition-colors font-medium overflow-hidden',
        collapsed ? 'justify-center px-0' : 'gap-2.5 px-2.5'
      )}
    >
      <Sparkles size={15} className="shrink-0 text-brass" />
      <span
        className={cn(
          'whitespace-nowrap overflow-hidden transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] truncate',
          collapsed ? 'max-w-0 opacity-0 -translate-x-2 pointer-events-none' : 'max-w-[120px] opacity-100 translate-x-0'
        )}
      >
        Planos e Preços
      </span>
    </a>
  );
}
