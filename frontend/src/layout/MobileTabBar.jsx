import React from 'react';
import { Menu } from 'lucide-react';

export default function MobileTabBar({ navItems, activeTab, goToTab, tabLocked, navOpen, setNavOpen }) {
  const tabs = navItems.filter((n) => n.primary);
  const moreActive = !tabs.some((t) => t.id === activeTab);
  
  return (
    <nav className="md:hidden shrink-0 border-t border-rule bg-paper2/95 backdrop-blur-md safe-bottom">
      <div className="flex items-stretch">
        {tabs.map((item) => {
          const NavIcon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              data-tutorial={item.id === 'dashboard' ? 'nav-clips' : undefined}
              onClick={() => goToTab(item.id)}
              disabled={tabLocked(item.id)}
              aria-current={isActive ? 'page' : undefined}
              title={tabLocked(item.id) ? 'Finish your first clips to unlock' : undefined}
              className={`flex-1 min-w-0 flex flex-col items-center justify-center gap-1 py-2 min-h-[56px] transition-colors select-none ${isActive ? 'text-ink font-medium' : 'text-muted active:text-ink2'} ${tabLocked(item.id) ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              <NavIcon size={19} className={isActive ? 'text-brass' : ''} />
              <span className="text-[11px] leading-none truncate max-w-full px-0.5">{item.short}</span>
            </button>
          );
        })}
        <button
          onClick={() => setNavOpen(true)}
          aria-label="More sections"
          aria-expanded={navOpen}
          className={`flex-1 min-w-0 flex flex-col items-center justify-center gap-1 py-2 min-h-[56px] transition-colors select-none ${moreActive ? 'text-ink font-medium' : 'text-muted active:text-ink2'}`}
        >
          <Menu size={19} className={moreActive ? 'text-brass' : ''} />
          <span className="text-[11px] leading-none">More</span>
        </button>
      </div>
    </nav>
  );
}
