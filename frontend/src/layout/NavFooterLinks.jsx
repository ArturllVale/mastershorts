import React from 'react';
import { Sparkles } from 'lucide-react';
import { cn } from '../lib/utils';

export default function NavFooterLinks({ collapsed = false, billingEnabled }) {
  if (!billingEnabled) return null;

  return (
    <a
      href="#/pricing"
      title="Planos e Preços"
      className="relative flex items-center h-9 px-2.5 rounded-lg text-xs text-muted hover:text-ink hover:bg-paper3/60 transition-colors font-medium overflow-hidden select-none"
    >
      <div className="w-6 h-6 flex items-center justify-center shrink-0">
        <Sparkles size={15} className="text-brass" />
      </div>
      <span
        className={cn(
          'ml-3 whitespace-nowrap overflow-hidden sidebar-label-transition truncate',
          collapsed ? 'max-w-0 opacity-0 pointer-events-none' : 'max-w-[180px] opacity-100'
        )}
      >
        Planos e Preços
      </span>
    </a>
  );
}
