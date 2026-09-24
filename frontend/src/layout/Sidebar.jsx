import React from 'react';
import { Lock } from 'lucide-react';
import { cn } from '../lib/utils';
import NavFooterLinks from './NavFooterLinks';

export default function Sidebar({
  navItems,
  activeTab,
  goToTab,
  tabLocked,
  billingEnabled,
  isCollapsed = false
}) {
  return (
    <aside
      className={cn(
        'hidden md:flex flex-col h-full shrink-0 bg-paper2 border-r border-rule select-none overflow-hidden sidebar-transition',
        isCollapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Navigation Links with Stationary Anchored Icons */}
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
                'relative w-full flex items-center h-10 px-2 rounded-xl transition-colors duration-150 select-none overflow-hidden group',
                isActive
                  ? 'bg-paper3 text-ink font-semibold border border-rule2 shadow-sm'
                  : 'text-muted hover:text-ink hover:bg-paper3/60 border border-transparent',
                tabLocked(item.id) ? 'opacity-40 cursor-not-allowed hover:bg-transparent hover:text-muted' : ''
              )}
            >
              {isActive && (
                <span className="absolute left-0 top-2 bottom-2 w-0.5 bg-brass rounded-full" aria-hidden="true" />
              )}
              {/* Stationary icon anchor */}
              <div className="w-6 h-6 flex items-center justify-center shrink-0">
                <NavIcon
                  size={18}
                  className={cn(
                    'transition-transform duration-150 group-hover:scale-105',
                    isActive ? 'text-brass' : ''
                  )}
                />
              </div>

              {/* Text label with smooth slide and fade */}
              <div
                className={cn(
                  'ml-3 flex items-center gap-2 flex-1 min-w-0 overflow-hidden whitespace-nowrap sidebar-label-transition',
                  isCollapsed ? 'max-w-0 opacity-0 -translate-x-2 pointer-events-none' : 'max-w-[180px] opacity-100 translate-x-0'
                )}
              >
                <span className="text-sm text-left truncate">{item.label}</span>
                {tabLocked(item.id) ? (
                  <Lock size={12} className="shrink-0 text-muted ml-auto" />
                ) : item.byok ? (
                  <span className="readout text-[10px] ml-auto">BYOK</span>
                ) : null}
              </div>
            </button>
          );
        })}
      </nav>

      {/* Footer without toggle button */}
      <div className="p-2.5 border-t border-rule shrink-0 overflow-hidden">
        <NavFooterLinks collapsed={isCollapsed} billingEnabled={billingEnabled} />
      </div>
    </aside>
  );
}
