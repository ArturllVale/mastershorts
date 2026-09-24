import React from 'react';
import { Shield, Sparkles, Server, Layers, Check } from 'lucide-react';
import KeyInput from '../../components/KeyInput';
import OpenAiEndpointInput from '../../components/OpenAiEndpointInput';
import ComboEndpointInput from '../../components/ComboEndpointInput';

export default function SettingsView({
  isManaged,
  billingEnabled,
  setShowPlanChoice,
  setApiKey,
  apiKey,
  llmProvider = 'gemini',
  setLlmProvider,
  llmBaseUrl = '',
  setLlmBaseUrl,
  llmModel = '',
  setLlmModel,
  llmApiKey = '',
  setLlmApiKey,
  llmFallbackModels = '',
  setLlmFallbackModels,
  openrouterApiKey = '',
  setOpenrouterApiKey,
  mistralApiKey = '',
  setMistralApiKey,
}) {
  return (
    <div className="h-full overflow-y-auto custom-scrollbar p-4 sm:p-6 md:p-8 max-w-4xl mx-auto animate-fade">
      {/* Settings Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6 pb-4 border-b border-rule">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-ink">
            Configurações do Sistema
          </h1>
          <p className="text-xs text-muted mt-1">
            Gerencie modelos de inteligência artificial, provedores e endpoints locais.
          </p>
        </div>
        <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-paper2 border border-rule text-xs text-muted shrink-0 self-start sm:self-auto">
          <Shield size={13} className="text-ok shrink-0" />
          <span>Privacidade Total · Armazenamento Local</span>
        </div>
      </div>

      {isManaged ? (
        <div className="card p-5 sm:p-6 border border-rule/80 bg-paper2/90 shadow-card rounded-panel backdrop-blur-sm mb-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-paper3 rounded-xl text-brass border border-rule shrink-0">
                <Shield size={18} />
              </div>
              <div>
                <h2 className="text-base font-semibold text-ink">Incluso no seu plano</h2>
                <p className="text-xs text-muted">Acesso gerenciado sem necessidade de chaves</p>
              </div>
            </div>
            <span className="badge-ok">Gerenciado</span>
          </div>
          <p className="text-xs text-muted leading-relaxed">
            Seu plano inclui o <strong>Gerador de Clipes</strong> e o <strong>Estúdio YouTube</strong>,
            totalmente integrados na nuvem.
          </p>
        </div>
      ) : billingEnabled ? (
        <div className="card p-5 sm:p-6 border border-rule/80 bg-paper2/90 shadow-card rounded-panel backdrop-blur-sm mb-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-paper3 rounded-xl text-brass border border-rule shrink-0">
                <Sparkles size={18} />
              </div>
              <div>
                <h2 className="text-base font-semibold text-ink">Plano e Licença</h2>
                <p className="text-xs text-muted">Acesso instantâneo sem configurações manuais de API</p>
              </div>
            </div>
            <span className="badge-ok">Gratuito disponível</span>
          </div>
          <p className="text-xs text-muted leading-relaxed">
            Gere shorts sem precisar de chaves de API externas. Inicie gratuitamente com 20 min/mês ou assine planos a partir de R$ 12/mês.
          </p>
          <button
            onClick={() => setShowPlanChoice(true)}
            className="btn-primary py-2 px-4 text-xs font-semibold"
          >
            <Sparkles size={14} /> Escolher um Plano
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Provider Selector Switch */}
          <div className="card p-5 sm:p-6 border border-rule/80 bg-paper2/90 shadow-card rounded-panel backdrop-blur-sm space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-ink">Selecione o Provedor de IA</h3>
              <p className="text-xs text-muted mt-0.5">
                Escolha qual mecanismo processa o vídeo e detecta os momentos virais.
              </p>
            </div>

            {/* Responsive 3-Card Option Selector */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Option 1: Google Gemini */}
              <button
                type="button"
                onClick={() => setLlmProvider && setLlmProvider('gemini')}
                className={`p-3.5 rounded-xl border text-left transition-all duration-200 relative flex flex-col justify-between cursor-pointer min-h-[96px] ${
                  llmProvider === 'gemini'
                    ? 'border-violet bg-violet/[0.08] shadow-sm ring-1 ring-violet/30'
                    : 'border-rule bg-paper/60 hover:border-rule2 hover:bg-paper2/50'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Sparkles size={15} className={llmProvider === 'gemini' ? 'text-violet shrink-0' : 'text-muted shrink-0'} />
                    <span className="text-xs font-semibold text-ink truncate">Google Gemini</span>
                  </div>
                  {llmProvider === 'gemini' ? (
                    <div className="w-4 h-4 rounded-full bg-violet text-white flex items-center justify-center shrink-0">
                      <Check size={10} strokeWidth={3} />
                    </div>
                  ) : (
                    <span className="w-2 h-2 rounded-full bg-rule2 shrink-0" />
                  )}
                </div>
                <p className="text-[11px] text-muted leading-relaxed line-clamp-2">
                  Chave do Google AI Studio (Free Tier rápido).
                </p>
              </button>

              {/* Option 2: Endpoint OpenAI */}
              <button
                type="button"
                onClick={() => setLlmProvider && setLlmProvider('openai')}
                className={`p-3.5 rounded-xl border text-left transition-all duration-200 relative flex flex-col justify-between cursor-pointer min-h-[96px] ${
                  llmProvider === 'openai'
                    ? 'border-violet bg-violet/[0.08] shadow-sm ring-1 ring-violet/30'
                    : 'border-rule bg-paper/60 hover:border-rule2 hover:bg-paper2/50'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Server size={15} className={llmProvider === 'openai' ? 'text-violet shrink-0' : 'text-muted shrink-0'} />
                    <span className="text-xs font-semibold text-ink truncate">Endpoint OpenAI</span>
                  </div>
                  {llmProvider === 'openai' ? (
                    <div className="w-4 h-4 rounded-full bg-violet text-white flex items-center justify-center shrink-0">
                      <Check size={10} strokeWidth={3} />
                    </div>
                  ) : (
                    <span className="w-2 h-2 rounded-full bg-rule2 shrink-0" />
                  )}
                </div>
                <p className="text-[11px] text-muted leading-relaxed line-clamp-2">
                  Ollama, LM Studio, vLLM ou OmniRoute local.
                </p>
              </button>

              {/* Option 3: Combo Free */}
              <button
                type="button"
                onClick={() => setLlmProvider && setLlmProvider('combo')}
                className={`p-3.5 rounded-xl border text-left transition-all duration-200 relative flex flex-col justify-between cursor-pointer min-h-[96px] ${
                  llmProvider === 'combo'
                    ? 'border-violet bg-violet/[0.08] shadow-sm ring-1 ring-violet/30'
                    : 'border-rule bg-paper/60 hover:border-rule2 hover:bg-paper2/50'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Layers size={15} className={llmProvider === 'combo' ? 'text-violet shrink-0' : 'text-muted shrink-0'} />
                    <span className="text-xs font-semibold text-ink truncate">Combo 3-em-1</span>
                  </div>
                  {llmProvider === 'combo' ? (
                    <div className="w-4 h-4 rounded-full bg-violet text-white flex items-center justify-center shrink-0">
                      <Check size={10} strokeWidth={3} />
                    </div>
                  ) : (
                    <span className="w-2 h-2 rounded-full bg-rule2 shrink-0" />
                  )}
                </div>
                <p className="text-[11px] text-muted leading-relaxed line-clamp-2">
                  Gemini + OpenRouter + Mistral com fallback.
                </p>
              </button>
            </div>
          </div>

          {/* Active Provider Configuration */}
          {llmProvider === 'gemini' ? (
            <KeyInput onKeySet={setApiKey} savedKey={apiKey} />
          ) : llmProvider === 'combo' ? (
            <ComboEndpointInput
              savedGeminiKey={apiKey}
              savedOpenrouterKey={openrouterApiKey}
              savedMistralKey={mistralApiKey}
              onSave={({ geminiKey, openrouterKey, mistralKey }) => {
                if (setApiKey) setApiKey(geminiKey);
                if (setOpenrouterApiKey) setOpenrouterApiKey(openrouterKey);
                if (setMistralApiKey) setMistralApiKey(mistralKey);
              }}
            />
          ) : (
            <OpenAiEndpointInput
              savedBaseUrl={llmBaseUrl}
              savedModel={llmModel}
              savedApiKey={llmApiKey}
              savedFallbackModels={llmFallbackModels}
              onSave={({ baseUrl, model, apiKey: newKey, fallbackModels }) => {
                if (setLlmBaseUrl) setLlmBaseUrl(baseUrl);
                if (setLlmModel) setLlmModel(model);
                if (setLlmApiKey) setLlmApiKey(newKey);
                if (setLlmFallbackModels) setLlmFallbackModels(fallbackModels);
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}
