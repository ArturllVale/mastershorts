import React from 'react';
import { Lock, X } from 'lucide-react';
import NavFooterLinks from './NavFooterLinks';

export default function MobileNavDrawer({ navItems, activeTab, goToTab, tabLocked, navOpen, setNavOpen, billingEnabled }) {
  if (!navOpen) return null;
  
  return (
    <div
      className="md:hidden fixed inset-0 z-[90] flex"
      role="dialog"
      aria-modal="true"
      aria-label="Navigation"
    >
      <div
        className="absolute inset-0 bg-black/70 animate-fade"
        onClick={() => setNavOpen(false)}
        aria-hidden="true"
      />
      <div className="relative w-[17rem] max-w-[82vw] h-full bg-paper2 border-r border-rule flex flex-col animate-slide-in-left shadow-modal">
        <div className="flex items-center justify-between px-5 h-14 border-b border-rule shrink-0">
          <a href="#landing" className="flex items-center gap-2.5" onClick={() => setNavOpen(false)}>
            <div className="w-7 h-7 rounded-input overflow-hidden shrink-0">
              <img src="/logo-mastershorts.svg" alt="" className="w-full h-full object-contain" />
            </div>
            <span className="font-semibold text-base text-ink tracking-tight">MasterShorts</span>
          </a>
          <button
            onClick={() => setNavOpen(false)}
            aria-label="Fechar navegação"
            className="p-1.5 rounded-input text-muted hover:text-ink hover:bg-paper3 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto custom-scrollbar px-3 py-3 space-y-1">
          {navItems.map((item) => {
            const NavIcon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => goToTab(item.id)}
                disabled={tabLocked(item.id)}
                aria-current={isActive ? 'page' : undefined}
                title={tabLocked(item.id) ? 'Finish your first clips to unlock' : undefined}
                className={`relative w-full flex items-center gap-3 px-3.5 py-2.5 rounded-input transition-colors ${isActive ? 'bg-paper3 text-ink font-medium border border-rule2' : 'text-muted active:bg-paper3/60 border border-transparent'} ${tabLocked(item.id) ? 'opacity-40 cursor-not-allowed' : ''}`}
              >
                {isActive && (
                  <span className="absolute left-0 top-2 bottom-2 w-0.5 bg-brass rounded-full" aria-hidden="true" />
                )}
                <NavIcon size={18} className={`shrink-0 ${isActive ? 'text-brass' : ''}`} />
                <span className="text-sm flex-1 text-left truncate">{item.label}</span>
                {tabLocked(item.id)
                  ? <Lock size={12} className="shrink-0" />
                  : item.byok ? <span className="readout text-[10px] shrink-0">BYOK</span> : null}
              </button>
            );
          })}
        </nav>

        <div className="px-3 py-3 border-t border-rule space-y-0.5 safe-bottom shrink-0">
          <NavFooterLinks billingEnabled={billingEnabled} />
        </div>
      </div>
    </div>
  );
}
