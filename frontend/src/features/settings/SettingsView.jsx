import React from 'react';
import { Shield, Sparkles, Cpu, Server } from 'lucide-react';
import KeyInput from '../../components/KeyInput';
import OpenAiEndpointInput from '../../components/OpenAiEndpointInput';

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
}) {
  return (
    <div className="h-full overflow-y-auto p-4 sm:p-8 max-w-2xl mx-auto animate-fade">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-8">
        <div>
          <p className="eyebrow mb-1.5">04 · SETTINGS</p>
          <h1 className="font-display lowercase text-2xl text-ink">Settings</h1>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted mt-1">
          <Shield size={12} className="text-ok shrink-0" /> Privacy: keys and endpoints only live in your browser
        </div>
      </div>

      {isManaged ? (
        <div className="card p-6 mb-2">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-input bg-paper3 flex items-center justify-center shrink-0">
                <Shield size={16} className="text-brass" />
              </div>
              <h2 className="text-base font-medium text-ink lowercase">Included in your plan</h2>
            </div>
            <span className="badge-ok">Managed</span>
          </div>
          <p className="text-xs text-muted mb-0 leading-relaxed">
            Your plan includes the <strong>Clip Generator</strong> and <strong>YouTube Studio</strong>,
            fully managed — no API keys required.
          </p>
        </div>
      ) : billingEnabled ? (
        <div className="card p-6 mb-2">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-input bg-paper3 flex items-center justify-center shrink-0">
                <Sparkles size={16} className="text-brass" />
              </div>
              <h2 className="text-base font-medium text-ink lowercase">Choose your plan</h2>
            </div>
            <span className="badge-ok">Free plan available</span>
          </div>
          <p className="text-xs text-muted mb-5 leading-relaxed">
            Generate shorts with zero setup — no API keys needed. Start free with 20 min/month, or go paid from $12/mo. Cancel anytime.
          </p>
          <button onClick={() => setShowPlanChoice(true)} className="btn-primary py-2 px-4 text-sm">
            <Sparkles size={16} /> Choose a plan
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Provider Selector Switch */}
          <div className="card p-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted mb-0.5">AI Engine</p>
                <p className="text-xs text-ink2">
                  Choose which provider analyzes video content to discover viral moments.
                </p>
              </div>

              {/* Pill Switch */}
              <div className="flex bg-paper3 p-1 rounded-btn border border-rule shrink-0 self-start sm:self-auto">
                <button
                  type="button"
                  onClick={() => setLlmProvider && setLlmProvider('gemini')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-input transition-all ${
                    llmProvider === 'gemini'
                      ? 'bg-paper text-ink shadow-sm border border-rule2 font-semibold'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  <Sparkles size={13} className={llmProvider === 'gemini' ? 'text-brass' : 'text-muted'} />
                  Google Gemini
                </button>
                <button
                  type="button"
                  onClick={() => setLlmProvider && setLlmProvider('openai')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-input transition-all ${
                    llmProvider === 'openai'
                      ? 'bg-paper text-ink shadow-sm border border-rule2 font-semibold'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  <Server size={13} className={llmProvider === 'openai' ? 'text-brass' : 'text-muted'} />
                  OpenAI Endpoint
                </button>
              </div>
            </div>
          </div>

          {/* Active Provider Configuration */}
          {llmProvider === 'gemini' ? (
            <KeyInput onKeySet={setApiKey} savedKey={apiKey} />
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
