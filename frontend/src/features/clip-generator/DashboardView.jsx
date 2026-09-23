import React, { useMemo, useRef } from 'react';
import { Youtube, Instagram, Activity, Loader2, Terminal, ChevronDown, Download, RotateCcw, Play, RefreshCw, AlertCircle, Trash2 } from 'lucide-react';
import MediaInput from '../../components/MediaInput';
import ProcessingAnimation from '../../components/ProcessingAnimation';
import StarBanner from '../../components/StarBanner';
import ResultCard from '../../components/ResultCard';

const TikTokIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M19.589 6.686a4.793 4.793 0 0 1-3.77-4.245V2h-3.445v13.672a2.896 2.896 0 0 1-5.201 1.743l-.002-.001.002.001a2.895 2.895 0 0 1 3.183-4.51v-3.5a6.329 6.329 0 0 0-5.394 10.692 6.33 6.33 0 0 0 10.857-4.424V8.687a8.182 8.182 0 0 0 4.773 1.526V6.79a4.831 4.831 0 0 1-1.003-.104z" />
  </svg>
);

export default function DashboardView({
  activeTab,
  status,
  tutorialLock,
  billingEnabled,
  goToTab,
  handleProcess,
  handleReset,
  handleRetry,
  isRetrying = false,
  handleDeleteProject,
  isDeleting = false,
  processingMedia,
  syncedTime,
  isSyncedPlaying,
  syncTrigger,
  logs,
  logsVisible,
  setLogsVisible,
  results,
  isManaged,
  handleDownloadAll,
  downloadingAll,
  partialJob,
  plan,
  setTopUpInfo,
  setShowTopUp,
  rankedClips,
  jobId,
  setEditingClip,
  setReframingClip,
  projectState,
  handleClipStateChange,
  durableClips,
  apiKey,
  handleClipPlay,
  handleClipPause,
  handleBulkSubtitles,
  bulkSub
}) {
  if (activeTab !== 'dashboard') return null;

  const lastLog = logs && logs.length ? logs[logs.length - 1] : '';
  const isConnectionError = Boolean(logs && logs.some(l => 
    typeof l === 'string' && (
      l.includes('10061') || 
      l.toLowerCase().includes('recusou') || 
      l.toLowerCase().includes('connecterror') || 
      l.toLowerCase().includes('connection refused') ||
      l.toLowerCase().includes('omniroute')
    )
  ));

  // Maintain immutable timestamps (HH:mm) per log event instead of ticking live seconds
  const logTimestampsRef = useRef(new Map());

  const formattedLogs = useMemo(() => {
    if (!Array.isArray(logs) || logs.length === 0) {
      logTimestampsRef.current.clear();
      return [];
    }

    const storageKey = jobId ? `mastershorts_log_timestamps_${jobId}` : null;
    const cache = logTimestampsRef.current;

    if (storageKey && cache.size === 0) {
      try {
        const stored = sessionStorage.getItem(storageKey);
        if (stored) {
          const parsed = JSON.parse(stored);
          Object.entries(parsed).forEach(([k, v]) => cache.set(k, v));
        }
      } catch (e) {
        // ignore
      }
    }

    const now = new Date();
    const currentClock = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    let cacheUpdated = false;

    const result = logs.map((log, index) => {
      const logStr = typeof log === 'string' ? log : String(log || '');
      const key = `${index}:${logStr}`;
      let time = cache.get(key);

      if (!time) {
        // If log already starts with a timestamp like "10:05 ..." or "[10:05] ..."
        const match = logStr.match(/^\[?(\d{1,2}:\d{2})\]?\s*(.*)$/);
        if (match) {
          time = match[1].padStart(5, '0');
        } else {
          time = currentClock;
        }
        cache.set(key, time);
        cacheUpdated = true;
      }

      // If the log text had embedded timestamp, strip it so it doesn't double-display
      const cleanText = logStr.replace(/^\[?\d{1,2}:\d{2}\]?\s+/, '');

      return {
        id: key,
        raw: cleanText,
        timestamp: time,
      };
    });

    if (cacheUpdated && storageKey) {
      try {
        const serialized = {};
        cache.forEach((v, k) => { serialized[k] = v; });
        sessionStorage.setItem(storageKey, JSON.stringify(serialized));
      } catch (e) {
        // ignore
      }
    }

    return result;
  }, [logs, jobId]);

  return (
    <>
      {status === 'idle' && (
        <div className="h-full overflow-y-auto custom-scrollbar animate-fade">
          <div className="min-h-full flex flex-col items-center justify-center px-4 py-5 sm:p-6">
          <div className="max-w-xl w-full text-center space-y-5 sm:space-y-8">
            <div className="space-y-2.5 sm:space-y-4">
              <p className="eyebrow hidden sm:block font-mono text-violet font-semibold">01 · GERADOR DE CLIPES</p>
              <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-ink">
                Transforme vídeos longos em shorts virais.
              </h1>
              <p className="text-sm sm:text-base text-ink2">
                Cole um link do YouTube ou envie um arquivo. A IA extrai os melhores momentos, reformata para 9:16 e adiciona legendas automáticas.
              </p>
              {!tutorialLock && (
              <p className="text-xs text-muted">
                Automatize com agentes de IA:{' '}
                <a
                  href={billingEnabled ? '#/account' : '#app'}
                  onClick={(e) => { if (!billingEnabled) { e.preventDefault(); goToTab('settings'); } }}
                  className="text-ink underline underline-offset-2 hover:text-violet transition-colors font-medium"
                >
                  Conecte automações e integrações via API →
                </a>
              </p>
              )}
            </div>

            <MediaInput onProcess={handleProcess} isProcessing={status === 'processing'} />

            <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-8 text-muted text-xs sm:text-sm">
              <span className="flex items-center gap-2"><Youtube size={16} /> YouTube</span>
              <span className="flex items-center gap-2"><Instagram size={16} /> Instagram</span>
              <span className="flex items-center gap-2"><TikTokIcon size={16} /> TikTok</span>
            </div>
          </div>
          </div>
        </div>
      )}

      {(status === 'processing' || status === 'complete' || status === 'error') && (
        <div className="h-full flex flex-col md:flex-row gap-3 md:gap-4 p-2.5 sm:p-3 md:p-4 overflow-y-auto md:overflow-hidden custom-scrollbar animate-fade">
          
          {status !== 'complete' && (
            <div className="w-full md:w-[52%] lg:w-[55%] xl:w-[58%] md:h-full flex flex-col shrink-0 md:shrink card p-3 sm:p-4 lg:p-5 overflow-y-auto custom-scrollbar transition-all duration-500 ease-out">
              <div className="mb-2.5 sm:mb-3 flex items-center justify-between gap-2 shrink-0">
                <h2 className="text-xs sm:text-sm font-semibold text-ink flex items-center gap-1.5 sm:gap-2 min-w-0 truncate">
                  <Activity className={`text-violet shrink-0 ${status === 'processing' ? 'animate-pulse' : ''}`} size={15} />
                  <span className="truncate">Análise de Vídeo em Tempo Real</span>
                </h2>
                <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
                  <span className={`text-[10px] sm:text-xs px-2 py-0.5 sm:px-2.5 sm:py-1 ${status === 'processing' ? 'badge-brass' : 'badge-danger'}`}>
                    {status === 'processing' ? 'PROCESSANDO' : status === 'error' ? 'ERRO' : status.toUpperCase()}
                  </span>
                  {status === 'error' && handleRetry && (
                    <button
                      type="button"
                      onClick={handleRetry}
                      disabled={isRetrying}
                      className="px-2.5 py-1 text-xs font-semibold text-white bg-violet hover:bg-violet/90 rounded-input transition-colors flex items-center gap-1 shadow-sm disabled:opacity-50"
                      title="Continuar processamento mantendo o progresso atual"
                    >
                      {isRetrying ? (
                        <>
                          <Loader2 size={12} className="animate-spin" />
                          <span className="hidden sm:inline">Retomando…</span>
                        </>
                      ) : (
                        <>
                          <RefreshCw size={12} />
                          <span className="hidden sm:inline">Continuar</span>
                        </>
                      )}
                    </button>
                  )}
                  {handleReset && (
                    <button
                      type="button"
                      onClick={handleReset}
                      className="px-2 py-1 text-[11px] sm:text-xs font-medium text-ink2 hover:text-ink bg-paper2 hover:bg-paper3 border border-rule rounded-input transition-colors flex items-center gap-1"
                      title="Cancelar ou iniciar um novo vídeo"
                    >
                      <RotateCcw size={11} />
                      <span>Cancelar</span>
                    </button>
                  )}
                  {handleDeleteProject && jobId && (
                    <button
                      type="button"
                      onClick={() => handleDeleteProject(jobId)}
                      disabled={isDeleting}
                      className="px-2 py-1 text-[11px] sm:text-xs font-medium text-danger hover:text-white bg-danger/10 hover:bg-danger border border-danger/30 rounded-input transition-colors flex items-center gap-1"
                      title="Excluir este projeto e todos os seus arquivos do servidor"
                    >
                      {isDeleting ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
                      <span>Excluir</span>
                    </button>
                  )}
                </div>
              </div>

              {processingMedia && (
                <ProcessingAnimation
                  media={processingMedia}
                  isComplete={status === 'complete'}
                  syncedTime={syncedTime}
                  isSyncedPlaying={isSyncedPlaying}
                  syncTrigger={syncTrigger}
                />
              )}

              {status === 'processing' && (
                <div className="mb-2 sm:mb-2.5 flex items-center gap-2 text-xs text-ink2 min-w-0 bg-paper2/80 px-2.5 py-1.5 sm:px-3 sm:py-2 rounded-input border border-rule shrink-0">
                  <Loader2 size={14} className="animate-spin text-brass shrink-0" />
                  <div className="min-w-0 flex-1 flex items-center gap-1.5">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-brass font-semibold shrink-0">Status:</span>
                    <span className="min-w-0 truncate font-mono text-ink text-xs">
                      {lastLog || 'Iniciando processamento…'}
                    </span>
                  </div>
                </div>
              )}

              {status === 'error' && (
                <div className="mb-4 p-3.5 sm:p-4 rounded-card border border-danger/40 bg-danger/10 text-ink space-y-3 animate-fade">
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-danger/20 rounded-lg text-danger shrink-0 mt-0.5">
                      <AlertCircle size={18} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
                        Falha no Processamento
                      </h3>
                      <p className="text-xs text-ink2 mt-1 leading-relaxed break-words font-mono">
                        {lastLog || 'Ocorreu um erro durante a execução do processo.'}
                      </p>
                      {isConnectionError && (
                        <div className="mt-2.5 bg-paper2/95 p-3 rounded-lg border border-rule text-xs space-y-1.5">
                          <p className="font-semibold text-ink flex items-center gap-1.5">
                            💡 <span>Dica OmniRoute / IA Local:</span>
                          </p>
                          <p className="text-ink2 leading-relaxed">
                            O OmniRoute ou seu provedor local de IA parece estar desligado ou inacessível.
                            Inicie o <strong>OmniRoute</strong> e depois clique em <strong>Continuar</strong> para retomar imediatamente de onde parou, sem precisar baixar ou transcrever o vídeo de novo!
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-rule/50 justify-end">
                    {handleDeleteProject && jobId && (
                      <button
                        type="button"
                        onClick={() => handleDeleteProject(jobId)}
                        disabled={isDeleting}
                        className="px-3.5 py-2 text-xs font-medium text-danger hover:text-white bg-danger/10 hover:bg-danger border border-danger/30 rounded-input transition-colors flex items-center gap-1.5"
                        title="Excluir este projeto para começar do zero"
                      >
                        {isDeleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                        <span>Excluir e Começar do Zero</span>
                      </button>
                    )}
                    {handleRetry && (
                      <button
                        type="button"
                        onClick={handleRetry}
                        disabled={isRetrying}
                        className="px-4 py-2 text-xs font-semibold text-white bg-violet hover:bg-violet/90 rounded-input transition-all flex items-center gap-2 shadow disabled:opacity-50"
                      >
                        {isRetrying ? (
                          <>
                            <Loader2 size={14} className="animate-spin" />
                            <span>Retomando processamento...</span>
                          </>
                        ) : (
                          <>
                            <RefreshCw size={14} />
                            <span>Continuar / Tentar Novamente</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              )}

              {status === 'processing' && (
                <div className="my-2 sm:my-2.5 shrink-0">
                  <StarBanner message="Dica:" />
                </div>
              )}

              <div className={`bg-paper rounded-card border border-rule overflow-hidden flex flex-col transition-all duration-300 ${logsVisible ? 'flex-1 min-h-[130px] sm:min-h-[160px]' : 'min-h-0 shrink-0'}`}>
                <button
                  type="button"
                  onClick={() => setLogsVisible(!logsVisible)}
                  aria-expanded={logsVisible}
                  className="w-full px-3 py-2 sm:px-3.5 sm:py-2.5 border-b border-rule flex items-center justify-between gap-2 bg-paper2 shrink-0 text-left select-none"
                >
                  <span className="readout flex items-center gap-1.5 text-[11px]">
                    <Terminal size={12} /> Logs do Sistema
                    <span className="text-[10px] text-muted normal-case font-normal hidden sm:inline">(mais recentes no topo)</span>
                  </span>
                  <span className="flex items-center gap-2 text-muted">
                    {!logsVisible && logs.length > 0 && (
                      <span className="readout normal-case text-[10px]">{logs.length}</span>
                    )}
                    <ChevronDown size={14} className={logsVisible ? '' : 'rotate-180'} />
                  </span>
                </button>
                {logsVisible && (
                  <div className="flex-1 p-2.5 sm:p-3.5 overflow-y-auto font-mono text-[11px] sm:text-xs space-y-1 custom-scrollbar text-muted break-words">
                    {status === 'processing' && (
                      <div className="flex items-center gap-2 text-brass text-[11px] pb-1 border-b border-dotted border-white/20 mb-1">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-brass animate-ping" />
                        <span className="font-sans font-medium text-[10px] uppercase tracking-wider">Processamento em andamento:</span>
                      </div>
                    )}
                    {[...formattedLogs].reverse().map((item) => {
                      const log = item.raw;
                      const isError = log.toLowerCase().includes('error') || log.includes('failed');
                      const isWarning = log.includes('[LLM Fallback]') || log.toLowerCase().includes('warning');
                      const isSuccess = log.toLowerCase().includes('success') || log.toLowerCase().includes('done') || log.toLowerCase().includes('built');
                      const isInfo = log.includes('🤖') || log.includes('⚡') || log.includes('🎥') || log.includes('[');
                      
                      let textColor = 'text-muted';
                      if (isError) textColor = 'text-danger';
                      else if (isWarning) textColor = 'text-brass';
                      else if (isSuccess) textColor = 'text-ok';
                      else if (isInfo) textColor = 'text-ink';

                      return (
                        <div key={item.id} className={`flex items-baseline gap-3 py-1 border-b border-dotted border-white/20 last:border-0 hover:bg-white/[0.03] transition-colors px-1 ${textColor}`}>
                          <span className="text-muted/50 shrink-0 font-mono text-[11px] tabular-nums select-none tracking-tight">
                            {item.timestamp}
                          </span>
                          <span className="min-w-0 break-words leading-relaxed">{log}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          <div className={`${status === 'complete' ? 'w-full' : 'w-full md:w-[48%] lg:w-[45%] xl:w-[42%]'} md:h-full flex flex-col shrink-0 md:shrink card p-3 sm:p-4 lg:p-5 transition-all duration-500 ease-out`}>
            <div className="mb-3 sm:mb-4 shrink-0 flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-rule/50">
              <h2 className="text-sm sm:text-base font-semibold text-ink flex flex-wrap items-center gap-2">
                <span>Shorts Gerados</span>
                {results?.clips?.length > 0 && (
                  <span className="readout bg-paper3 border border-rule px-2 py-0.5 rounded-full text-xs">
                    {results.clips.length} Clipes
                  </span>
                )}
                {results?.cost_analysis && !isManaged && (
                  <span className="readout bg-paper3 border border-rule px-2 py-0.5 rounded-full text-xs" title={`Input: ${results.cost_analysis.input_tokens} | Output: ${results.cost_analysis.output_tokens}`}>
                    GEMINI · ${results.cost_analysis.total_cost.toFixed(5)}
                  </span>
                )}
              </h2>
              {status === 'complete' && (
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  {handleDeleteProject && jobId && (
                    <button
                      type="button"
                      onClick={() => handleDeleteProject(jobId)}
                      disabled={isDeleting}
                      className="px-3 py-1.5 text-xs font-medium text-danger hover:text-white bg-danger/10 hover:bg-danger border border-danger/30 rounded-input transition-all flex items-center justify-center gap-1.5 shadow-sm"
                      title="Excluir este projeto e todos os seus arquivos do servidor para refazer do zero"
                    >
                      {isDeleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                      <span>Excluir e Refazer do Zero</span>
                    </button>
                  )}
                  {handleReset && (
                    <button
                      type="button"
                      onClick={handleReset}
                      className="btn-secondary px-3.5 py-1.5 text-xs flex items-center justify-center gap-1.5"
                      title="Iniciar um novo vídeo"
                    >
                      <RotateCcw size={14} /> Novo Vídeo
                    </button>
                  )}
                  {results?.clips?.length > 0 && (
                    <button
                      onClick={handleDownloadAll}
                      disabled={downloadingAll}
                      className="btn-secondary px-3.5 py-1.5 text-xs flex items-center justify-center gap-1.5"
                      title="Baixar todos os clipes em arquivo ZIP"
                    >
                      {downloadingAll
                        ? <><Loader2 size={14} className="animate-spin text-violet" /> Compactando…</>
                        : <><Download size={14} /> Baixar Todos (ZIP)</>}
                    </button>
                  )}
                </div>
              )}
            </div>

            {status === 'complete' && results?.clips?.length > 0 && (
              <div className="mb-3 space-y-2">
                {partialJob && (
                  <button
                    onClick={() => { setTopUpInfo({ context: 'upsell' }); setShowTopUp(true); }}
                    className="w-full text-left px-3.5 py-2.5 rounded-input bg-paper3 border border-violet/40 hover:border-violet text-xs transition-colors flex items-center justify-between"
                  >
                    <span className="text-ink">Estes clipes são dos primeiros {partialJob.processed_minutes} de {partialJob.total_minutes} minutos.</span>
                    <span className="text-violet font-medium ml-2">Processar vídeo completo →</span>
                  </button>
                )}
                {plan === 'free' && !partialJob && (
                  <button
                    onClick={() => { setTopUpInfo({ context: 'upsell' }); setShowTopUp(true); }}
                    className="w-full text-left px-3.5 py-2.5 rounded-input bg-paper3 border border-violet/40 hover:border-violet text-xs transition-colors flex items-center justify-between"
                  >
                    <span className="text-ink">Clipes da versão gratuita expiram em 7 dias.</span>
                    <span className="text-violet font-medium ml-2">Remover limites →</span>
                  </button>
                )}
              </div>
            )}

            <div className="flex-1 overflow-y-auto custom-scrollbar p-1">
              {results && results.clips && results.clips.length > 0 ? (
                <div className={`grid gap-6 pb-10 ${status === 'complete' ? 'grid-cols-1 2xl:grid-cols-2 min-[2400px]:grid-cols-3' : 'grid-cols-1'}`}>
                  {rankedClips.map(({ clip, index: i }, rankIndex) => (
                    <ResultCard
                      key={`${jobId}-${i}-${clip.video_url || ''}`}
                      clip={clip}
                      index={i}
                      rankIndex={rankIndex}
                      jobId={jobId}
                      onEditClip={(index) => setEditingClip(index)}
                      onReframeClip={(index) => setReframingClip(index)}
                      initialState={projectState?.clips?.find((c) => c.index === i) || null}
                      onStateChange={handleClipStateChange}
                      durable={durableClips[i]}
                      geminiApiKey={apiKey}
                      isManaged={isManaged}
                      onPlay={(time) => handleClipPlay(time)}
                      onPause={handleClipPause}
                      onBulkSubtitle={handleBulkSubtitles}
                      clipCount={results.clips.length}
                      bulkProgress={bulkSub}
                    />
                  ))}
                </div>
              ) : (
                status === 'processing' ? (
                  <div className="h-full min-h-[140px] flex flex-col items-center justify-center text-muted space-y-3 text-center px-4">
                    <Loader2 size={28} className="animate-spin text-violet" />
                    <p className="text-sm">Aguardando clipes...</p>
                    <p className="text-xs text-muted/80 max-w-[28ch] leading-snug">
                      Eles aparecerão aqui um a um conforme forem renderizados.
                    </p>
                  </div>
                ) : status === 'error' ? (
                  <div className="h-full min-h-[140px] flex flex-col items-center justify-center text-center p-4 space-y-3">
                    <AlertCircle size={28} className="text-danger" />
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-ink">Processamento interrompido</p>
                      <p className="text-xs text-muted max-w-[28ch]">
                        Inicie o OmniRoute/servidor e clique em Continuar para prosseguir.
                      </p>
                    </div>
                    {handleRetry && (
                      <button
                        type="button"
                        onClick={handleRetry}
                        disabled={isRetrying}
                        className="px-3.5 py-1.5 text-xs font-semibold text-white bg-violet hover:bg-violet/90 rounded-input transition-colors flex items-center gap-1.5 shadow disabled:opacity-50"
                      >
                        {isRetrying ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                        <span>Continuar</span>
                      </button>
                    )}
                  </div>
                ) : null
              )}
            </div>
          </div>

        </div>
      )}
    </>
  );
}
