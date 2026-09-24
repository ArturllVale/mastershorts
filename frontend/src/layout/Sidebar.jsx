import React, { useState } from 'react';
import { Lock, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '../lib/utils';
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
    <aside
      className={cn(
        'hidden md:flex flex-col h-full shrink-0 bg-paper2 border-r border-rule overflow-hidden select-none',
        'transition-[width] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]',
        isCollapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Brand Header */}
      <div className="relative h-14 border-b border-rule flex items-center px-3.5 shrink-0 overflow-hidden">
        <a
          href="#landing"
          className="flex items-center gap-3 min-w-0 overflow-hidden"
          title="MasterShorts Studio"
        >
          <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 overflow-hidden shadow-sm bg-paper3/60 border border-rule/50">
            <img src="/logo-mastershorts.svg" alt="MasterShorts" className="w-full h-full object-contain" />
          </div>
          <div
            className={cn(
              'flex flex-col min-w-0 overflow-hidden whitespace-nowrap transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]',
              isCollapsed ? 'max-w-0 opacity-0 -translate-x-3 pointer-events-none' : 'max-w-[140px] opacity-100 translate-x-0'
            )}
          >
            <span className="font-semibold text-sm text-ink tracking-tight leading-none truncate">MasterShorts</span>
            <span className="text-[9px] font-mono uppercase tracking-widest text-violet mt-1 font-semibold">STUDIO IA</span>
          </div>
        </a>

        {/* Quick Collapse Button in Header */}
        <button
          type="button"
          onClick={toggleCollapse}
          aria-label={isCollapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'}
          title={isCollapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'}
          className={cn(
            'absolute right-2.5 p-1.5 rounded-lg text-muted hover:text-ink hover:bg-paper3 transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]',
            isCollapsed ? 'opacity-0 pointer-events-none scale-75' : 'opacity-100 scale-100'
          )}
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-2.5 py-3 space-y-1 overflow-y-auto custom-scrollbar overflow-x-hidden">
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
              className={cn(
                'group relative w-full flex items-center h-10 rounded-xl transition-all duration-200 select-none overflow-hidden',
                isCollapsed ? 'justify-center px-0' : 'gap-3 px-3',
                isActive
                  ? 'bg-paper3 text-ink font-semibold shadow-sm border border-rule2'
                  : 'text-muted hover:text-ink hover:bg-paper3/60 border border-transparent',
                tabLocked(item.id) ? 'opacity-40 cursor-not-allowed hover:bg-transparent hover:text-muted' : ''
              )}
            >
              {isActive && (
                <span className="absolute left-0 top-2 bottom-2 w-0.5 bg-brass rounded-full" aria-hidden="true" />
              )}
              <NavIcon
                size={18}
                className={cn(
                  'shrink-0 transition-transform duration-200 group-hover:scale-105',
                  isActive ? 'text-brass' : ''
                )}
              />
              <div
                className={cn(
                  'flex items-center gap-2 flex-1 min-w-0 overflow-hidden whitespace-nowrap transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]',
                  isCollapsed ? 'max-w-0 opacity-0 -translate-x-3 pointer-events-none' : 'max-w-[180px] opacity-100 translate-x-0'
                )}
              >
                <span className="text-sm flex-1 text-left truncate">{item.label}</span>
                {tabLocked(item.id) ? (
                  <Lock size={12} className="shrink-0 text-muted" />
                ) : item.byok ? (
                  <span className="readout text-[10px]">BYOK</span>
                ) : null}
              </div>
            </button>
          );
        })}
      </nav>

      {/* Footer & Toggle Collapse Bar */}
      <div className="p-2.5 border-t border-rule space-y-1 shrink-0 overflow-hidden">
        <NavFooterLinks collapsed={isCollapsed} billingEnabled={billingEnabled} />

        <button
          type="button"
          onClick={toggleCollapse}
          aria-label={isCollapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'}
          title={isCollapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'}
          className={cn(
            'w-full flex items-center h-9 px-2.5 rounded-lg text-muted hover:text-ink hover:bg-paper3 transition-all duration-200 text-xs font-medium overflow-hidden',
            isCollapsed ? 'justify-center' : 'justify-between'
          )}
        >
          <div className="flex items-center gap-2.5 overflow-hidden">
            <ChevronRight
              size={15}
              className={cn(
                'shrink-0 transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]',
                !isCollapsed && 'rotate-180'
              )}
            />
            <span
              className={cn(
                'whitespace-nowrap overflow-hidden transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]',
                isCollapsed ? 'max-w-0 opacity-0 -translate-x-2 pointer-events-none' : 'max-w-[120px] opacity-100 translate-x-0'
              )}
            >
              Recolher menu
            </span>
          </div>
        </button>
      </div>
    </aside>
  );
}
