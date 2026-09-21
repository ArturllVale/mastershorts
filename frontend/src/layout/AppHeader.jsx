import React from 'react';
import { Menu, Plus, AlertTriangle } from 'lucide-react';
import UsageMeter from '../components/UsageMeter';
import ProfileMenu from '../components/ProfileMenu';

export default function AppHeader({
  setNavOpen,
  activeNav,
  status,
  handleReset,
  billingEnabled,
  isManaged,
  plan,
  setTopUpInfo,
  setShowTopUp,
  setShowPlanChoice,
  setShowLogin,
  isSignedIn,
  keysMissing,
  goToTab
}) {
  return (
    <header className="h-14 border-b border-rule bg-paper flex items-center justify-between gap-2 px-3 sm:px-6 shrink-0 z-10">
      <div className="flex items-center gap-2 sm:gap-4 min-w-0">
        <button
          onClick={() => setNavOpen(true)}
          aria-label="Open navigation"
          className="md:hidden -ml-1 p-2 rounded-input text-muted active:bg-paper3 transition-colors shrink-0"
        >
          <Menu size={20} />
        </button>
        <span data-tutorial="nav-clips" className="md:hidden font-semibold text-sm text-ink truncate">
          {activeNav?.label || 'MasterShorts'}
        </span>
        {status !== 'idle' && (
          <button
            onClick={handleReset}
            className="btn-secondary px-3 py-1.5 text-xs shrink-0 gap-1.5"
            aria-label="Novo Projeto"
          >
            <Plus size={14} />
            <span className="hidden sm:inline">Novo Projeto</span>
          </button>
        )}
      </div>

      <div className="flex items-center gap-2 sm:gap-4 shrink-0">
        {billingEnabled && isManaged && (
          <UsageMeter onClick={() => {
            if (plan === 'free') { setTopUpInfo({ context: 'upsell' }); setShowTopUp(true); }
            else { window.location.hash = '#/account'; }
          }} />
        )}
        {billingEnabled && isSignedIn && !isManaged && (
          <button onClick={() => setShowPlanChoice(true)}
            className="btn-primary px-3.5 py-1.5 text-xs">
            Escolher um plano
          </button>
        )}
        {billingEnabled && !isSignedIn && (
          <button onClick={() => setShowLogin(true)}
            className="btn-ghost px-3.5 py-1.5 text-xs">
            Entrar
          </button>
        )}
        {billingEnabled && isSignedIn && <ProfileMenu />}

        {keysMissing && (
          <button
            onClick={() => (billingEnabled && !isSignedIn ? setShowLogin(true) : goToTab('settings'))}
            className="badge-warn hover:brightness-110 transition-all hidden sm:inline-flex cursor-pointer"
            title="Configurar chaves de API ou escolher um plano"
          >
            <AlertTriangle size={12} />
            <span className="hidden md:inline">
              {'Chave API do Gemini Ausente'}
            </span>
            <span className="md:hidden">Chaves Ausentes</span>
          </button>
        )}
      </div>
    </header>
  );
}
