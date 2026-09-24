import React, { useState, useEffect } from 'react';
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Info, 
  RefreshCw, 
  Loader2, 
  Server, 
  HardDrive, 
  Database, 
  Sparkles, 
  Cpu, 
  Cookie, 
  FileVideo, 
  FolderCheck,
  ExternalLink
} from 'lucide-react';
import Modal from './ui/Modal';
import { getApiUrl } from '../config';

const ITEM_ICONS = {
  ffmpeg: FileVideo,
  render_service: Server,
  prisma: Database,
  llm: Sparkles,
  output_dir: FolderCheck,
  gpu_encoder: Cpu,
  ytdlp: HardDrive,
  cookies: Cookie,
};

export default function PreflightModal({ isOpen, onClose }) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const fetchPreflight = async () => {
    setLoading(true);
    setError(null);
    try {
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

      const res = await fetch(getApiUrl('/api/preflight'), { headers });
      if (!res.ok) {
        throw new Error(`Erro na API (${res.status})`);
      }
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err.message || 'Falha ao conectar à API de pré-voo.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchPreflight();
    }
  }, [isOpen]);

  const renderStatusBadge = (status) => {
    switch (status) {
      case 'ok':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-ok/10 text-ok border border-ok/20">
            <CheckCircle2 size={11} /> OK
          </span>
        );
      case 'warn':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-brass/10 text-brass border border-brass/20">
            <AlertTriangle size={11} /> AVISO
          </span>
        );
      case 'error':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-danger/10 text-danger border border-danger/20">
            <XCircle size={11} /> ERRO
          </span>
        );
      case 'info':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-paper3 text-muted border border-rule">
            <Info size={11} /> INFO
          </span>
        );
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Diagnóstico de Ambiente & Preflight"
      eyebrow="VERIFICAÇÃO DE SISTEMA"
      size="lg"
      footer={
        <div className="flex items-center justify-between w-full">
          <button
            type="button"
            onClick={fetchPreflight}
            disabled={loading}
            className="btn-secondary px-3.5 py-1.5 text-xs flex items-center gap-1.5"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>{loading ? 'Verificando...' : 'Verificar Novamente'}</span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="btn-primary px-4 py-1.5 text-xs"
          >
            Concluído
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        {/* Banner de Status Geral */}
        {data && (
          <div
            className={`p-3.5 rounded-card border flex items-center justify-between gap-3 ${
              data.status === 'ok'
                ? 'bg-ok/5 border-ok/30 text-ink'
                : data.status === 'warn'
                ? 'bg-brass/5 border-brass/30 text-ink'
                : 'bg-danger/5 border-danger/30 text-ink'
            }`}
          >
            <div className="flex items-center gap-2.5 min-w-0">
              {data.status === 'ok' ? (
                <CheckCircle2 size={20} className="text-ok shrink-0" />
              ) : data.status === 'warn' ? (
                <AlertTriangle size={20} className="text-brass shrink-0" />
              ) : (
                <XCircle size={20} className="text-danger shrink-0" />
              )}
              <div className="min-w-0 text-left">
                <p className="text-xs font-semibold">
                  {data.status === 'ok'
                    ? 'Todos os serviços essenciais estão operacionais'
                    : data.status === 'warn'
                    ? 'Atenção recomendada para itens secundários'
                    : 'Atenção: Existem pendências críticas de configuração'}
                </p>
                <p className="text-[11px] text-muted truncate">
                  {data.status === 'ok'
                    ? 'Pipeline pronta para ingestão, corte, transcrição e renderização.'
                    : 'Revise os detalhes abaixo para garantir máxima performance e estabilidade.'}
                </p>
              </div>
            </div>
            <span className="text-[11px] font-mono text-muted shrink-0 hidden sm:inline">
              8 checagens ativas
            </span>
          </div>
        )}

        {/* Loading / Error States */}
        {loading && !data && (
          <div className="py-12 flex flex-col items-center justify-center text-muted space-y-2">
            <Loader2 size={24} className="animate-spin text-violet" />
            <p className="text-xs">Executando diagnósticos do sistema...</p>
          </div>
        )}

        {error && (
          <div className="p-3 bg-danger/10 border border-danger/30 rounded-input text-xs text-danger flex items-center gap-2">
            <XCircle size={15} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Checklist */}
        {data?.checks && (
          <div className="divide-y divide-rule border border-rule rounded-card bg-paper overflow-hidden">
            {data.checks.map((item) => {
              const IconComp = ITEM_ICONS[item.id] || Info;
              return (
                <div
                  key={item.id}
                  className="p-3 sm:px-4 flex flex-col gap-1.5 hover:bg-paper2/50 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="p-1.5 rounded-input bg-paper2 text-ink2 border border-rule shrink-0">
                        <IconComp size={15} />
                      </div>
                      <div className="min-w-0 text-left">
                        <span className="text-xs font-semibold text-ink block leading-snug">
                          {item.name}
                        </span>
                        <span className="text-[11px] text-ink2 block leading-snug truncate">
                          {item.message}
                        </span>
                      </div>
                    </div>
                    <div className="shrink-0">
                      {renderStatusBadge(item.status)}
                    </div>
                  </div>

                  {item.detail && (
                    <div className="text-[10px] text-left font-mono text-muted/70 truncate pl-8">
                      {item.detail}
                    </div>
                  )}

                  {item.troubleshooting && item.status !== 'ok' && (
                    <div className="mt-1 ml-8 p-2 rounded-input bg-paper3 border border-rule text-[11px] text-muted leading-relaxed">
                      <strong className="text-ink font-medium">Como resolver: </strong>
                      {item.troubleshooting}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Modal>
  );
}
