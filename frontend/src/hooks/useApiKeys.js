import { useState } from 'react';
import { decrypt, encrypt } from '../lib/crypto';

/**
 * Hook to manage API keys and LLM configuration stored in localStorage.
 * Handles encrypted and unencrypted keys.
 */
export function useApiKeys() {
  // Unencrypted Gemini Key
  const [apiKey, setApiKey] = useState(localStorage.getItem('gemini_key') || '');

  // LLM Provider: 'gemini' | 'openai'
  const [llmProvider, setLlmProvider] = useState(() => localStorage.getItem('llm_provider') || 'gemini');
  const [llmBaseUrl, setLlmBaseUrl] = useState(() => localStorage.getItem('llm_base_url') || '');
  const [llmModel, setLlmModel] = useState(() => localStorage.getItem('llm_model') || 'llama3.1:8b');
  const [llmApiKey, setLlmApiKey] = useState(() => {
    const stored = localStorage.getItem('llm_api_key');
    if (stored) {
      try { return decrypt(stored); } catch { return stored; }
    }
    return '';
  });
  const [llmFallbackModels, setLlmFallbackModels] = useState(() => localStorage.getItem('llm_fallback_models') || 'openrouter/openrouter/free, nvidia/nemotron-3-super-120b-a12b, grok-cli/grok-4.6, agnes/agnes-2.5-flash');

  // Upload-Post API Key - Load encrypted
  const [uploadPostKey, setUploadPostKey] = useState(() => {
    const stored = localStorage.getItem('uploadPostKey_v3');
    if (stored) return decrypt(stored);
    return '';
  });

  // ElevenLabs API State - Load encrypted
  const [elevenLabsKey, setElevenLabsKey] = useState(() => {
    const stored = localStorage.getItem('elevenLabsKey_v1');
    if (stored) return decrypt(stored);
    return '';
  });

  // fal.ai API State - Load encrypted
  const [falKey, setFalKey] = useState(() => {
    const stored = localStorage.getItem('falKey_v1');
    if (stored) return decrypt(stored);
    return '';
  });

  // Saving methods that persist to localStorage (encrypting as needed)
  const saveApiKey = (key) => {
    setApiKey(key);
    localStorage.setItem('gemini_key', key);
  };

  const saveLlmProvider = (provider) => {
    setLlmProvider(provider);
    localStorage.setItem('llm_provider', provider);
  };

  const saveLlmBaseUrl = (url) => {
    setLlmBaseUrl(url);
    localStorage.setItem('llm_base_url', url);
  };

  const saveLlmModel = (model) => {
    setLlmModel(model);
    localStorage.setItem('llm_model', model);
  };

  const saveLlmApiKey = (key) => {
    setLlmApiKey(key);
    if (!key) {
      localStorage.removeItem('llm_api_key');
    } else if (!key.startsWith('ENC:')) {
      localStorage.setItem('llm_api_key', encrypt(key));
    }
  };

  const saveUploadPostKey = (key) => {
    setUploadPostKey(key);
    if (!key.startsWith('ENC:')) {
      localStorage.setItem('uploadPostKey_v3', encrypt(key));
    }
  };

  const saveElevenLabsKey = (key) => {
    setElevenLabsKey(key);
    if (!key.startsWith('ENC:')) {
      localStorage.setItem('elevenLabsKey_v1', encrypt(key));
    }
  };

  const saveFalKey = (key) => {
    setFalKey(key);
    if (!key.startsWith('ENC:')) {
      localStorage.setItem('falKey_v1', encrypt(key));
    }
  };

  const saveLlmFallbackModels = (models) => {
    setLlmFallbackModels(models);
    localStorage.setItem('llm_fallback_models', models);
  };

  return {
    apiKey,
    setApiKey: saveApiKey,
    llmProvider,
    setLlmProvider: saveLlmProvider,
    saveLlmProvider,
    llmBaseUrl,
    setLlmBaseUrl: saveLlmBaseUrl,
    saveLlmBaseUrl,
    llmModel,
    setLlmModel: saveLlmModel,
    saveLlmModel,
    llmApiKey,
    setLlmApiKey: saveLlmApiKey,
    saveLlmApiKey,
    llmFallbackModels,
    setLlmFallbackModels: saveLlmFallbackModels,
    saveLlmFallbackModels,
    uploadPostKey,
    setUploadPostKey,
    saveUploadPostKey,
    elevenLabsKey,
    setElevenLabsKey,
    saveElevenLabsKey,
    falKey,
    setFalKey,
    saveFalKey,
  };
}
