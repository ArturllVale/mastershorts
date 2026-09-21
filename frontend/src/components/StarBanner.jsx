import React from 'react';
import { Sparkles } from 'lucide-react';

export default function StarBanner({ message = 'Dica Pro:' }) {
  return (
    <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-input bg-paper2/90 border border-rule text-xs text-muted shadow-sm">
      <Sparkles size={15} className="shrink-0 text-violet animate-pulse" />
      <span className="leading-snug">
        <strong className="text-ink font-medium">{message}</strong> Clipes com ganchos visuais e legendas dinâmicas aumentam a retenção em até 400% no TikTok e Shorts.
      </span>
    </div>
  );
}
