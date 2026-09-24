import React, { useState, useEffect } from 'react';
import { Menu, Plus, AlertTriangle, Activity } from 'lucide-react';
import UsageMeter from '../components/UsageMeter';
import ProfileMenu from '../components/ProfileMenu';
import PreflightModal from '../components/PreflightModal';
import { getApiUrl } from '../config';

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
  const [showPreflight, setShowPreflight] = useState(false);
  const [preflightStatus, setPreflightStatus] = useState(null);

  useEffect(() => {
    let isMounted = true;
    const headers = {};
    const llmProvider = localStorage.getItem('llm_provider');
    const gemini = localStorage.getItem('gemini_key');
    const llmKey = localStorage.getItem('llm_api_key');
    const mistral = localStorage.getItem('mistral_api_key');
    const openrouter = localStorage.getItem('openrouter_api_key');
    const llmBaseUrl = localStorage.getItem('llm_base_url');
    
    if (llmProvider) headers['x-llm-provider'] = llmProvider;
    if (gemini) headers['x-llm-api-key'] = gemini;
    if (llmKey && llmProvider === 'openai') headers['x-llm-api-key'] = llmKey;
    if (mistral) headers['x-mistral-key'] = mistral;
    if (openrouter) headers['x-openrouter-key'] = openrouter;
    if (llmBaseUrl) headers['x-llm-base-url'] = llmBaseUrl;

    fetch(getApiUrl('/api/preflight'), { headers })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (isMounted && d) setPreflightStatus(d.status);
      })
      .catch(() => {
        if (isMounted) setPreflightStatus('error');
      });
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <header className="h-14 border-b border-rule bg-paper/90 backdrop-blur-md flex items-center justify-between gap-2 px-3 sm:px-6 shrink-0 z-10">
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

        <button
          type="button"
          onClick={() => setShowPreflight(true)}
          className={`px-2.5 py-1 rounded-full text-xs font-mono font-medium flex items-center gap-1.5 transition-colors border select-none cursor-pointer ${
            preflightStatus === 'ok'
              ? 'bg-ok/10 border-ok/30 text-ok hover:bg-ok/20'
              : preflightStatus === 'warn'
              ? 'bg-brass/10 border-brass/30 text-brass hover:bg-brass/20'
              : preflightStatus === 'error'
              ? 'bg-danger/10 border-danger/30 text-danger hover:bg-danger/20'
              : 'bg-paper3 border-rule text-muted hover:text-ink'
          }`}
          title="Abrir diagnóstico do ambiente e pré-voo (FFmpeg, Remotion, GPU, etc.)"
        >
          <Activity size={12} className={preflightStatus && preflightStatus !== 'ok' ? 'animate-pulse' : ''} />
          <span className="hidden sm:inline">Preflight</span>
          <span className="text-[10px] uppercase font-semibold">
            {preflightStatus === 'ok' ? 'OK' : preflightStatus === 'warn' ? 'Aviso' : preflightStatus === 'error' ? 'Erro' : '...'}
          </span>
        </button>

        <PreflightModal isOpen={showPreflight} onClose={() => setShowPreflight(false)} />
      </div>
    </header>
  );
}
