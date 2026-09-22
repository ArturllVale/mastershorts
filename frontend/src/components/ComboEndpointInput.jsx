import React, { useState, useEffect } from 'react';
import { Key, Eye, EyeOff, Check, Sparkles, Layers, Shield, ExternalLink, Loader2, AlertCircle, RefreshCw } from 'lucide-react';

export default function ComboEndpointInput({
  savedGeminiKey = '',
  savedOpenrouterKey = '',
  savedMistralKey = '',
  onSave,
}) {
  const [geminiKey, setGeminiKey] = useState(savedGeminiKey);
  const [openrouterKey, setOpenrouterKey] = useState(savedOpenrouterKey);
  const [mistralKey, setMistralKey] = useState(savedMistralKey);

  const [visibleGemini, setVisibleGemini] = useState(false);
  const [visibleOpenrouter, setVisibleOpenrouter] = useState(false);
  const [visibleMistral, setVisibleMistral] = useState(false);

  const [isSaved, setIsSaved] = useState(Boolean(savedGeminiKey || savedOpenrouterKey || savedMistralKey));
  const [testStatus, setTestStatus] = useState(null); // null | 'testing' | 'ok' | 'error'
  const [testResults, setTestResults] = useState([]);

  useEffect(() => {
    if (savedGeminiKey) setGeminiKey(savedGeminiKey);
    if (savedOpenrouterKey) setOpenrouterKey(savedOpenrouterKey);
    if (savedMistralKey) setMistralKey(savedMistralKey);
  }, [savedGeminiKey, savedOpenrouterKey, savedMistralKey]);

  const handleSave = () => {
    if (onSave) {
      onSave({
        geminiKey: geminiKey.trim(),
        openrouterKey: openrouterKey.trim(),
        mistralKey: mistralKey.trim(),
      });
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 2500);
    }
  };

  const testConnection = async () => {
    setTestStatus('testing');
    setTestResults([]);
    const results = [];

    // Test Gemini
    if (geminiKey.trim()) {
      try {
        const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${geminiKey.trim()}`);
        if (res.ok) {
          results.push({ provider: 'Gemini', ok: true, msg: 'Autenticado (gemini-2.5-flash / flash-lite)' });
        } else {
          results.push({ provider: 'Gemini', ok: false, msg: `HTTP ${res.status}: Chave inválida ou cota esgotada` });
        }
      } catch (e) {
        results.push({ provider: 'Gemini', ok: false, msg: 'Erro de rede ou bloqueio de CORS' });
      }
    } else {
      results.push({ provider: 'Gemini', ok: null, msg: 'Chave não preenchida (opcional)' });
    }

    // Test OpenRouter
    if (openrouterKey.trim()) {
      try {
        const res = await fetch('https://openrouter.ai/api/v1/models', {
          headers: {
            Authorization: `Bearer ${openrouterKey.trim()}`,
          },
        });
        if (res.ok) {
          results.push({ provider: 'OpenRouter', ok: true, msg: 'Autenticado (modelo openrouter/free)' });
        } else {
          results.push({ provider: 'OpenRouter', ok: false, msg: `HTTP ${res.status}: Chave inválida` });
        }
      } catch (e) {
        results.push({ provider: 'OpenRouter', ok: false, msg: 'Erro de conexão com OpenRouter' });
      }
    } else {
      results.push({ provider: 'OpenRouter', ok: null, msg: 'Chave não preenchida (opcional)' });
    }

    // Test Mistral
    if (mistralKey.trim()) {
      try {
        const res = await fetch('https://api.mistral.ai/v1/models', {
          headers: {
            Authorization: `Bearer ${mistralKey.trim()}`,
          },
        });
        if (res.ok) {
          results.push({ provider: 'Mistral', ok: true, msg: 'Autenticado (mistral-small-latest / nemo)' });
        } else {
          results.push({ provider: 'Mistral', ok: false, msg: `HTTP ${res.status}: Chave inválida` });
        }
      } catch (e) {
        results.push({ provider: 'Mistral', ok: false, msg: 'Erro de conexão com Mistral' });
      }
    } else {
      results.push({ provider: 'Mistral', ok: null, msg: 'Chave não preenchida (opcional)' });
    }

    setTestResults(results);
    const hasAnyOk = results.some((r) => r.ok === true);
    setTestStatus(hasAnyOk ? 'ok' : 'error');
  };

  const hasAtLeastOneKey = Boolean(geminiKey.trim() || openrouterKey.trim() || mistralKey.trim());

  return (
    <div className="card p-4 sm:p-6 mb-8 animate-fade space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="p-2.5 bg-paper3 rounded-input text-brass shrink-0 mt-0.5">
            <Layers size={20} />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-display text-base sm:text-lg text-ink">Combo Gratuito: Gemini + OpenRouter + Mistral</h2>
              <span className="badge-ok text-[10px] uppercase font-semibold">3-em-1 Free</span>
            </div>
            <p className="text-xs text-muted mt-1 leading-relaxed">
              Alta disponibilidade com rotação inteligente e fallback automático entre os três provedores usando apenas modelos gratuitos.
            </p>
          </div>
        </div>
      </div>

      {/* Explanatory Banner */}
      <div className="p-3 bg-paper3/70 rounded-input border border-rule text-xs text-ink2 space-y-1.5 leading-relaxed">
        <div className="flex items-center gap-1.5 text-ink font-semibold">
          <RefreshCw size={13} className="text-brass shrink-0" />
          <span>Como funciona a contingência (fallback):</span>
        </div>
        <ul className="list-disc list-inside space-y-1 text-muted text-[11px] pl-1">
          <li>
            <strong className="text-ink">Google Gemini:</strong> Utiliza os modelos gratuitos <code className="font-mono text-ink">gemini-2.5-flash</code> ou <code className="font-mono text-ink">gemini-3.1-flash-lite</code>.
          </li>
          <li>
            <strong className="text-ink">OpenRouter:</strong> Utiliza o <code className="font-mono text-ink">openrouter/free</code>, que roteia automaticamente entre os modelos gratuitos disponíveis na plataforma sem selecionar um fixo.
          </li>
          <li>
            <strong className="text-ink">Mistral AI:</strong> Utiliza os modelos do tier gratuito da La Plateforme (<code className="font-mono text-ink">mistral-small-latest</code> e <code className="font-mono text-ink">open-mistral-nemo</code>).
          </li>
          <li>
            Se qualquer modelo sofrer limite de taxa (HTTP 429), indisponibilidade temporária ou timeout, o sistema avança imediatamente para o próximo da lista sem falhar o corte do vídeo.
          </li>
        </ul>
      </div>

      {/* Form Fields */}
      <div className="space-y-4">
        {/* Gemini API Key */}
        <div>
          <div className="flex flex-wrap items-center justify-between gap-1 mb-1.5">
            <label className="text-xs font-medium text-ink flex items-center gap-1.5">
              <Sparkles size={13} className="text-brass" />
              1. Chave da API do Google Gemini
            </label>
            <a
              href="https://aistudio.google.com/app/apikey"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-brass hover:underline flex items-center gap-1"
            >
              Criar chave gratuita <ExternalLink size={10} />
            </a>
          </div>
          <div className="relative">
            <input
              type={visibleGemini ? 'text' : 'password'}
              value={geminiKey}
              onChange={(e) => {
                setGeminiKey(e.target.value);
                setIsSaved(false);
              }}
              placeholder="AIzaSy..."
              className="input-field font-mono text-xs w-full pr-10"
            />
            <button
              type="button"
              onClick={() => setVisibleGemini(!visibleGemini)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink transition-colors"
            >
              {visibleGemini ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <p className="text-[11px] text-muted mt-1">
            Modelo free utilizado: <code className="font-mono text-ink">gemini-2.5-flash</code> (Google AI Studio).
          </p>
        </div>

        {/* OpenRouter API Key */}
        <div>
          <div className="flex flex-wrap items-center justify-between gap-1 mb-1.5">
            <label className="text-xs font-medium text-ink flex items-center gap-1.5">
              <Layers size={13} className="text-brass" />
              2. Chave da API do OpenRouter
            </label>
            <a
              href="https://openrouter.ai/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-brass hover:underline flex items-center gap-1"
            >
              Obter chave no OpenRouter <ExternalLink size={10} />
            </a>
          </div>
          <div className="relative">
            <input
              type={visibleOpenrouter ? 'text' : 'password'}
              value={openrouterKey}
              onChange={(e) => {
                setOpenrouterKey(e.target.value);
                setIsSaved(false);
              }}
              placeholder="sk-or-v1-..."
              className="input-field font-mono text-xs w-full pr-10"
            />
            <button
              type="button"
              onClick={() => setVisibleOpenrouter(!visibleOpenrouter)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink transition-colors"
            >
              {visibleOpenrouter ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <p className="text-[11px] text-muted mt-1">
            Modelo configurado: <code className="font-mono text-ink font-semibold">openrouter/free</code> (Free Models Router que balanceia entre todos os modelos gratuitos).
          </p>
        </div>

        {/* Mistral API Key */}
        <div>
          <div className="flex flex-wrap items-center justify-between gap-1 mb-1.5">
            <label className="text-xs font-medium text-ink flex items-center gap-1.5">
              <Key size={13} className="text-brass" />
              3. Chave da API do Mistral AI
            </label>
            <a
              href="https://console.mistral.ai/api-keys"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-brass hover:underline flex items-center gap-1"
            >
              Obter chave na Mistral <ExternalLink size={10} />
            </a>
          </div>
          <div className="relative">
            <input
              type={visibleMistral ? 'text' : 'password'}
              value={mistralKey}
              onChange={(e) => {
                setMistralKey(e.target.value);
                setIsSaved(false);
              }}
              placeholder="vj8..."
              className="input-field font-mono text-xs w-full pr-10"
            />
            <button
              type="button"
              onClick={() => setVisibleMistral(!visibleMistral)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink transition-colors"
            >
              {visibleMistral ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <p className="text-[11px] text-muted mt-1">
            Modelo free utilizado: <code className="font-mono text-ink">mistral-small-latest</code> (Mistral La Plateforme).
          </p>
        </div>
      </div>

      {/* Test Results Output */}
      {testResults.length > 0 && (
        <div className="p-3 bg-paper2 rounded-input border border-rule space-y-1.5 animate-fade">
          <p className="text-[11px] font-semibold text-ink uppercase tracking-wider">Resultado da Validação:</p>
          {testResults.map((r) => (
            <div key={r.provider} className="flex flex-col sm:flex-row sm:items-center justify-between text-xs py-1 gap-1 border-b border-rule/50 last:border-b-0">
              <span className="font-medium text-ink flex items-center gap-1.5">
                {r.ok === true && <Check size={13} className="text-ok shrink-0" />}
                {r.ok === false && <AlertCircle size={13} className="text-danger shrink-0" />}
                {r.ok === null && <span className="w-3 h-3 rounded-full bg-muted/40 shrink-0 inline-block" />}
                {r.provider}
              </span>
              <span className={`text-[11px] ${r.ok === true ? 'text-ok' : r.ok === false ? 'text-danger' : 'text-muted'}`}>
                {r.msg}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-3 border-t border-rule">
        <button
          type="button"
          onClick={testConnection}
          disabled={!hasAtLeastOneKey || testStatus === 'testing'}
          className="btn-secondary py-2 px-3.5 text-xs flex items-center justify-center gap-1.5 w-full sm:w-auto"
        >
          {testStatus === 'testing' ? (
            <><Loader2 size={13} className="animate-spin text-brass" /> Testando Provedores…</>
          ) : (
            'Testar Conexões'
          )}
        </button>

        <button
          type="button"
          onClick={handleSave}
          disabled={!hasAtLeastOneKey}
          className={isSaved ? 'badge-ok px-4 py-2 text-xs flex items-center justify-center gap-1.5 cursor-default w-full sm:w-auto' : 'btn-primary py-2 px-4 text-xs flex items-center justify-center w-full sm:w-auto'}
        >
          {isSaved ? <><Check size={14} /> Chaves Salvas</> : 'Salvar Configuração'}
        </button>
      </div>
    </div>
  );
}
