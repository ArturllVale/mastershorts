import React, { useState, useEffect } from 'react';
import { Terminal, Eye, EyeOff, Check, Loader2, Sparkles, Server, AlertCircle, Layers, Plus, Zap } from 'lucide-react';

const PRESETS = [
  {
    name: 'OmniRoute (Local)',
    url: 'http://localhost:20128/v1',
    model: 'auto',
    fallbackModels: '',
  },
  { name: 'Ollama', url: 'http://localhost:11434/v1', model: 'llama3.1:8b', fallbackModels: '' },
  { name: 'LM Studio', url: 'http://localhost:1234/v1', model: 'local-model', fallbackModels: '' },
  { name: 'vLLM', url: 'http://localhost:8000/v1', model: 'meta-llama/Meta-Llama-3.1-8B-Instruct', fallbackModels: '' },
  { name: 'OpenAI', url: 'https://api.openai.com/v1', model: 'gpt-4o-mini', fallbackModels: '' },
  { name: 'OpenRouter', url: 'https://openrouter.ai/api/v1', model: 'meta-llama/llama-3.1-8b-instruct', fallbackModels: '' },
  { name: 'Groq', url: 'https://api.groq.com/openai/v1', model: 'llama-3.1-8b-instant', fallbackModels: '' },
];

const RECOMMENDED_FALLBACKS = [
  { label: 'OpenRouter Free', id: 'openrouter/openrouter/free' },
  { label: 'NVIDIA Nemotron 120B', id: 'nvidia/nemotron-3-super-120b-a12b' },
  { label: 'Grok 4.6', id: 'grok-cli/grok-4.6' },
  { label: 'Agnes 2.5 Flash', id: 'agnes/agnes-2.5-flash' },
];

export default function OpenAiEndpointInput({
  savedBaseUrl = '',
  savedModel = '',
  savedApiKey = '',
  savedFallbackModels = '',
  onSave
}) {
  const [baseUrl, setBaseUrl] = useState(savedBaseUrl);
  const [model, setModel] = useState(savedModel || 'llama3.1:8b');
  const [apiKey, setApiKey] = useState(savedApiKey);
  const [fallbackModels, setFallbackModels] = useState(
    savedFallbackModels || ''
  );
  const [isVisible, setIsVisible] = useState(false);
  const [isSaved, setIsSaved] = useState(!!savedBaseUrl);
  const [testStatus, setTestStatus] = useState(null); // null | 'testing' | 'ok' | 'error'
  const [testMessage, setTestMessage] = useState('');
  const [availableModels, setAvailableModels] = useState([]);

  useEffect(() => {
    if (savedBaseUrl) setBaseUrl(savedBaseUrl);
    if (savedModel) setModel(savedModel);
    if (savedApiKey) setApiKey(savedApiKey);
    if (savedFallbackModels) setFallbackModels(savedFallbackModels);
  }, [savedBaseUrl, savedModel, savedApiKey, savedFallbackModels]);

  const handleSave = () => {
    if (baseUrl.trim()) {
      onSave({
        baseUrl: baseUrl.trim(),
        model: model.trim() || 'llama3.1:8b',
        apiKey: apiKey.trim(),
        fallbackModels: fallbackModels.trim(),
      });
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 2500);
    }
  };

  const applyPreset = (preset) => {
    setBaseUrl(preset.url);
    setModel(preset.model);
    if (preset.fallbackModels !== undefined) {
      setFallbackModels(preset.fallbackModels);
    }
    setIsSaved(false);
    setTestStatus(null);
  };

  const addFallbackModel = (modelId) => {
    const current = fallbackModels
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (!current.includes(modelId)) {
      const updated = [...current, modelId].join(', ');
      setFallbackModels(updated);
      setIsSaved(false);
    }
  };

  const loadOmniRouteFallbacks = () => {
    const list = RECOMMENDED_FALLBACKS.map((r) => r.id).join(', ');
    setFallbackModels(list);
    setIsSaved(false);
  };

  const handleTestConnection = async () => {
    if (!baseUrl.trim()) return;
    setTestStatus('testing');
    setTestMessage('');

    try {
      const cleanUrl = baseUrl.trim().replace(/\/+$/, '');
      const headers = { 'Content-Type': 'application/json' };
      if (apiKey.trim()) {
        headers['Authorization'] = `Bearer ${apiKey.trim()}`;
      }

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 6000);

      const res = await fetch(`${cleanUrl}/models`, {
        method: 'GET',
        headers,
        signal: controller.signal,
      }).catch(async () => {
        // Some local servers only support POST /chat/completions or /v1/models
        return await fetch(cleanUrl, {
          method: 'GET',
          headers,
          signal: controller.signal,
        });
      });

      clearTimeout(timeoutId);

      if (res && res.ok) {
        let count = 0;
        try {
          const data = await res.json();
          if (data && Array.isArray(data.data)) {
            const ids = data.data.map((m) => m.id).filter(Boolean);
            setAvailableModels(ids);
            count = ids.length;
          }
        } catch (_) {}
        setTestStatus('ok');
        setTestMessage(count > 0 ? `Conexão bem-sucedida! (${count} modelos detectados)` : 'Endpoint acessível!');
      } else if (res) {
        setTestStatus('ok');
        setTestMessage(`Servidor respondeu (HTTP ${res.status})`);
      } else {
        throw new Error('Network error or CORS blocked');
      }
    } catch (e) {
      setTestStatus('error');
      setTestMessage(
        e.name === 'AbortError'
          ? 'Tempo de conexão esgotado (verifique se o servidor está rodando)'
          : 'Não foi possível conectar diretamente (se for local, verifique o CORS do gateway)'
      );
    }
  };

  return (
    <div className="card p-4 sm:p-6 mb-8 animate-fade space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-paper3 rounded-input text-brass">
            <Server size={18} />
          </div>
          <div>
            <h2 className="font-display text-lg text-ink">Endpoint Compatível com OpenAI</h2>
            <p className="text-xs text-muted">OmniRoute, Ollama, LM Studio, vLLM, OpenRouter ou NVIDIA NIM</p>
          </div>
        </div>
        <span className="readout">BYOK</span>
      </div>

      {/* Presets Chips */}
      <div>
        <label className="block text-[11px] font-mono uppercase tracking-wider text-muted mb-2">
          Predefinições Rápidas
        </label>
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p.name}
              type="button"
              onClick={() => applyPreset(p)}
              className="px-2.5 py-1 text-xs rounded-input bg-paper3 hover:bg-paper3/80 text-ink border border-rule hover:border-brass/40 transition-colors flex items-center gap-1.5"
            >
              <Sparkles size={11} className="text-brass" />
              <span>{p.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Form Fields */}
      <div className="space-y-4">
        {/* Base URL */}
        <div>
          <label className="block text-xs font-medium text-ink mb-1.5">
            URL Base do Endpoint <span className="text-brass">*</span>
          </label>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => {
              setBaseUrl(e.target.value);
              setIsSaved(false);
              setTestStatus(null);
            }}
            placeholder="http://localhost:11434/v1"
            className="input-field font-mono text-xs w-full"
          />
          <p className="text-[11px] text-muted mt-1">
            Formato: <code className="font-mono text-ink">http://localhost:20128/v1</code> ou <code className="font-mono text-ink">https://api.openai.com/v1</code>
          </p>
        </div>

        {/* Model Name */}
        <div>
          <label className="block text-xs font-medium text-ink mb-1.5">
            Modelo Principal <span className="text-brass">*</span>
          </label>
          <input
            type="text"
            list="available-models-list"
            value={model}
            onChange={(e) => {
              setModel(e.target.value);
              setIsSaved(false);
            }}
            placeholder="gemini/gemini-2.5-flash ou llama3.1:8b"
            className="input-field font-mono text-xs w-full"
          />
          {availableModels.length > 0 && (
            <datalist id="available-models-list">
              {availableModels.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          )}
          <p className="text-[11px] text-muted mt-1">
            Ex: <code className="font-mono text-ink">gemini/gemini-2.5-flash</code>. No OmniRoute, use <code className="font-mono text-ink">auto</code> para fallback nativo.
          </p>
        </div>

        {/* Fallback Models */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium text-ink flex items-center gap-1.5">
              <Layers size={13} className="text-brass" />
              Modelos de Contingência (Fallback) <span className="text-muted font-normal">(Separados por vírgula)</span>
            </label>
            <button
              type="button"
              onClick={loadOmniRouteFallbacks}
              className="text-[11px] text-brass hover:underline flex items-center gap-1 font-medium"
            >
              <Zap size={11} /> Preencher Recomendados
            </button>
          </div>
          <input
            type="text"
            value={fallbackModels}
            onChange={(e) => {
              setFallbackModels(e.target.value);
              setIsSaved(false);
            }}
            placeholder="openrouter/openrouter/free, nvidia/nvidia/nemotron-3-super-120b-a12b, grok-cli/grok-4.6"
            className="input-field font-mono text-xs w-full"
          />
          <div className="flex flex-wrap items-center gap-1.5 mt-2">
            <span className="text-[11px] text-muted mr-1">Candidatos verificados:</span>
            {RECOMMENDED_FALLBACKS.map((rf) => (
              <button
                key={rf.id}
                type="button"
                onClick={() => addFallbackModel(rf.id)}
                className="text-[10px] font-mono px-2 py-0.5 rounded bg-paper3 hover:bg-paper3/80 text-ink border border-rule hover:border-brass/40 transition-colors flex items-center gap-1"
                title={`Adicionar ${rf.id}`}
              >
                <Plus size={10} className="text-brass" />
                {rf.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-muted mt-1.5">
            Se o modelo principal falhar (429 rate limit, 400 ou 500), o sistema tenta automaticamente os fallbacks em sequência sem abortar o processamento do vídeo.
          </p>
        </div>

        {/* API Key */}
        <div>
          <label className="block text-xs font-medium text-ink mb-1.5">
            Chave de API / Token Bearer <span className="text-muted font-normal">(Opcional para servidores locais abertos)</span>
          </label>
          <div className="relative">
            <input
              type={isVisible ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value);
                setIsSaved(false);
              }}
              placeholder="sk-... or ollama"
              className="input-field font-mono text-xs w-full pr-10"
            />
            <button
              type="button"
              onClick={() => setIsVisible(!isVisible)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink transition-colors"
            >
              {isVisible ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>
      </div>

      {/* Status & Feedback */}
      {testStatus && (
        <div
          className={`px-3 py-2 rounded-input text-xs flex items-center gap-2 ${
            testStatus === 'ok'
              ? 'bg-ok/10 text-ok border border-ok/30'
              : 'bg-danger/10 text-danger border border-danger/30'
          }`}
        >
          {testStatus === 'ok' ? <Check size={14} /> : <AlertCircle size={14} />}
          <span>{testMessage}</span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-rule">
        <button
          type="button"
          onClick={handleTestConnection}
          disabled={!baseUrl.trim() || testStatus === 'testing'}
          className="btn-secondary py-2 px-3.5 text-xs flex items-center gap-1.5"
        >
          {testStatus === 'testing' ? (
            <><Loader2 size={13} className="animate-spin text-brass" /> Testando…</>
          ) : (
            'Testar Conexão'
          )}
        </button>

        <button
          type="button"
          onClick={handleSave}
          disabled={!baseUrl.trim()}
          className={isSaved ? 'badge-ok px-4 py-2 text-xs flex items-center gap-1.5 cursor-default' : 'btn-primary py-2 px-4 text-xs'}
        >
          {isSaved ? <><Check size={14} /> Salvo</> : 'Salvar Configuração'}
        </button>
      </div>
    </div>
  );
}
