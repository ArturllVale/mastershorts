import React from 'react';
import { Shield, Sparkles, Cpu, Server, Layers } from 'lucide-react';
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
    <div className="h-full overflow-y-auto p-4 sm:p-8 max-w-2xl mx-auto animate-fade">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-8">
        <div>
          <p className="eyebrow mb-1.5">04 · CONFIGURAÇÕES</p>
          <h1 className="font-display lowercase text-2xl text-ink">Configurações</h1>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted mt-1">
          <Shield size={12} className="text-ok shrink-0" /> Privacidade: chaves e endpoints ficam salvos apenas no seu navegador
        </div>
      </div>

      {isManaged ? (
        <div className="card p-6 mb-2">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-input bg-paper3 flex items-center justify-center shrink-0">
                <Shield size={16} className="text-brass" />
              </div>
              <h2 className="text-base font-medium text-ink lowercase">Incluso no seu plano</h2>
            </div>
            <span className="badge-ok">Gerenciado</span>
          </div>
          <p className="text-xs text-muted mb-0 leading-relaxed">
            Seu plano inclui o <strong>Gerador de Cortes</strong> e o <strong>Estúdio YouTube</strong>,
            totalmente gerenciados — sem necessidade de chaves de API.
          </p>
        </div>
      ) : billingEnabled ? (
        <div className="card p-6 mb-2">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-input bg-paper3 flex items-center justify-center shrink-0">
                <Sparkles size={16} className="text-brass" />
              </div>
              <h2 className="text-base font-medium text-ink lowercase">Escolha seu plano</h2>
            </div>
            <span className="badge-ok">Plano gratuito disponível</span>
          </div>
          <p className="text-xs text-muted mb-5 leading-relaxed">
            Gere shorts sem configurações complicadas — sem necessidade de chaves de API. Comece gratuitamente com 20 min/mês ou assine a partir de R$ 12/mês. Cancele quando quiser.
          </p>
          <button onClick={() => setShowPlanChoice(true)} className="btn-primary py-2 px-4 text-sm">
            <Sparkles size={16} /> Escolher um plano
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Provider Selector Switch */}
          <div className="card p-4 sm:p-5 space-y-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted mb-1">Modelo de IA</p>
              <p className="text-xs text-ink2">
                Escolha qual provedor analisa o conteúdo do vídeo para encontrar momentos virais.
              </p>
            </div>

            {/* Responsive 3-Card Option Selector */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {/* Option 1: Google Gemini */}
              <button
                type="button"
                onClick={() => setLlmProvider && setLlmProvider('gemini')}
                className={`p-3 rounded-card border text-left transition-all relative flex flex-col justify-between cursor-pointer ${
                  llmProvider === 'gemini'
                    ? 'border-brass bg-paper3/90 shadow-sm'
                    : 'border-rule bg-paper2/50 hover:border-rule2 hover:bg-paper3/40'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <Sparkles size={14} className={llmProvider === 'gemini' ? 'text-brass shrink-0' : 'text-muted shrink-0'} />
                    <span className="text-xs font-semibold text-ink truncate">Google Gemini</span>
                  </div>
                  {llmProvider === 'gemini' && (
                    <span className="w-2 h-2 rounded-full bg-brass shrink-0" />
                  )}
                </div>
                <p className="text-[11px] text-muted leading-relaxed line-clamp-2">
                  Chave individual do Google AI Studio (Free Tier).
                </p>
              </button>

              {/* Option 2: Endpoint OpenAI */}
              <button
                type="button"
                onClick={() => setLlmProvider && setLlmProvider('openai')}
                className={`p-3 rounded-card border text-left transition-all relative flex flex-col justify-between cursor-pointer ${
                  llmProvider === 'openai'
                    ? 'border-brass bg-paper3/90 shadow-sm'
                    : 'border-rule bg-paper2/50 hover:border-rule2 hover:bg-paper3/40'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <Server size={14} className={llmProvider === 'openai' ? 'text-brass shrink-0' : 'text-muted shrink-0'} />
                    <span className="text-xs font-semibold text-ink truncate">Endpoint OpenAI</span>
                  </div>
                  {llmProvider === 'openai' && (
                    <span className="w-2 h-2 rounded-full bg-brass shrink-0" />
                  )}
                </div>
                <p className="text-[11px] text-muted leading-relaxed line-clamp-2">
                  Ollama, LM Studio, vLLM ou servidor compatível.
                </p>
              </button>

              {/* Option 3: Combo Free */}
              <button
                type="button"
                onClick={() => setLlmProvider && setLlmProvider('combo')}
                className={`p-3 rounded-card border text-left transition-all relative flex flex-col justify-between cursor-pointer ${
                  llmProvider === 'combo'
                    ? 'border-brass bg-paper3/90 shadow-sm'
                    : 'border-rule bg-paper2/50 hover:border-rule2 hover:bg-paper3/40'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <Layers size={14} className={llmProvider === 'combo' ? 'text-brass shrink-0' : 'text-muted shrink-0'} />
                    <span className="text-xs font-semibold text-ink truncate">Combo 3-em-1</span>
                  </div>
                  <span className="text-[9px] uppercase px-1.5 py-0.5 font-mono bg-paper3 border border-rule text-brass rounded font-semibold shrink-0">
                    Free
                  </span>
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
