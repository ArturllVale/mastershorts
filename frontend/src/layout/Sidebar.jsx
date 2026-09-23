import React, { useState } from 'react';
import { Lock, ChevronLeft, ChevronRight } from 'lucide-react';
import NavFooterLinks from './NavFooterLinks';

const STORAGE_KEY = 'mastershorts_sidebar_collapsed';

export default function Sidebar({ navItems, activeTab, goToTab, tabLocked, billingEnabled }) {
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });

  const toggleCollapse = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // Ignore localStorage errors (e.g. private browsing)
      }
      return next;
    });
  };

  return (
    <div
      className={`hidden md:flex ${isCollapsed ? 'w-16' : 'w-64'} bg-paper2 border-r border-rule flex-col h-full shrink-0 transition-all duration-300`}
    >
      {/* Brand Header & Collapse Toggle */}
      <div
        className={`p-3.5 border-b border-rule flex items-center transition-all ${
          isCollapsed ? 'flex-col gap-2 justify-center px-2' : 'justify-between'
        }`}
      >
        <a
          href="#landing"
          className={`flex items-center gap-3 min-w-0 ${isCollapsed ? 'justify-center' : ''}`}
          title="MasterShorts Studio"
        >
          <div className="w-8 h-8 rounded-input flex items-center justify-center shrink-0 overflow-hidden shadow-sm">
            <img src="/logo-mastershorts.svg" alt="MasterShorts" className="w-full h-full object-contain" />
          </div>
          {!isCollapsed && (
            <div className="flex flex-col min-w-0">
              <span className="font-semibold text-base text-ink tracking-tight leading-none truncate">MasterShorts</span>
              <span className="text-[10px] font-mono uppercase tracking-widest text-violet mt-1 font-semibold">STUDIO IA</span>
            </div>
          )}
        </a>

        <button
          type="button"
          onClick={toggleCollapse}
          aria-label={isCollapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'}
          title={isCollapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'}
          className="p-1.5 rounded-input text-muted hover:text-ink hover:bg-paper3 transition-colors shrink-0"
        >
          {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Navigation Links */}
      <nav className={`flex-1 ${isCollapsed ? 'px-2' : 'px-3'} py-3 space-y-1 overflow-y-auto custom-scrollbar`}>
        {navItems.map((item) => {
          const NavIcon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              data-tutorial={item.id === 'dashboard' ? 'nav-clips' : undefined}
              onClick={() => goToTab(item.id)}
              title={tabLocked(item.id) ? 'Conclua seus primeiros cortes para desbloquear' : item.label}
              disabled={tabLocked(item.id)}
              className={`relative w-full flex items-center ${
                isCollapsed ? 'justify-center px-0 py-2.5' : 'gap-3 px-3.5 py-2.5'
              } rounded-input transition-all duration-150 select-none ${
                isActive
                  ? 'bg-paper3 text-ink font-medium shadow-sm border border-rule2'
                  : 'text-muted hover:text-ink hover:bg-paper3/60 border border-transparent'
              } ${tabLocked(item.id) ? 'opacity-40 cursor-not-allowed hover:bg-transparent hover:text-muted' : ''}`}
            >
              {isActive && (
                <span className="absolute left-0 top-2 bottom-2 w-0.5 bg-brass rounded-full" aria-hidden="true" />
              )}
              <NavIcon size={18} className={`shrink-0 ${isActive ? 'text-brass' : ''}`} />
              {!isCollapsed && (
                <>
                  <span className="text-sm flex-1 text-left truncate">{item.label}</span>
                  {tabLocked(item.id) ? (
                    <Lock size={12} className="shrink-0 text-muted" />
                  ) : item.byok ? (
                    <span className="readout text-[10px]">BYOK</span>
                  ) : null}
                  <span className="readout text-[10px] font-mono text-muted">{item.ord}</span>
                </>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer Links */}
      <div className={`p-3 border-t border-rule space-y-1 ${isCollapsed ? 'flex justify-center px-2' : ''}`}>
        <NavFooterLinks collapsed={isCollapsed} billingEnabled={billingEnabled} />
      </div>
    </div>
  );
}
