import React from 'react';
import { Sparkles } from 'lucide-react';

export default function NavFooterLinks({ collapsed = false, billingEnabled }) {
  if (!billingEnabled) return null;

  return (
    <a
      href="#/pricing"
      title="Planos e Preços"
      className={`flex items-center ${
        collapsed ? 'justify-center p-2' : 'gap-2 px-3 py-2'
      } text-xs text-muted hover:text-ink hover:bg-paper3/60 rounded-input transition-colors font-medium`}
    >
      <Sparkles size={14} className="shrink-0 text-brass" />
      {!collapsed && <span className="truncate">Planos e Preços</span>}
    </a>
  );
}
