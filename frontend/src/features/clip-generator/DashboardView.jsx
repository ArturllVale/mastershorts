import React from 'react';
import { Youtube, Instagram, Activity, Loader2, Terminal, ChevronDown, Download, RotateCcw } from 'lucide-react';
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
  elevenLabsKey,
  handleClipPlay,
  handleClipPause,
  handleBulkSubtitles,
  bulkSub
}) {
  if (activeTab !== 'dashboard') return null;

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
                  Conecte Claude, ChatGPT ou n8n via MCP →
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
        <div className="h-full flex flex-col md:flex-row gap-3 md:gap-4 p-3 md:p-4 overflow-y-auto md:overflow-y-hidden custom-scrollbar animate-fade">
          
          {status !== 'complete' && (
            <div className="w-full md:w-[55%] lg:w-[60%] md:h-full flex flex-col shrink-0 md:shrink card p-3.5 sm:p-6 md:overflow-y-auto custom-scrollbar transition-all duration-500 ease-out">
              <div className="mb-4 sm:mb-6 flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-ink flex items-center gap-2">
                  <Activity className={`text-violet ${status === 'processing' ? 'animate-pulse' : ''}`} size={16} />
                  Análise de Vídeo em Tempo Real
                </h2>
                <div className="flex items-center gap-2">
                  <span className={status === 'processing' ? 'badge-brass' : 'badge-danger'}>
                    {status === 'processing' ? 'PROCESSANDO' : status === 'error' ? 'ERRO' : status.toUpperCase()}
                  </span>
                  {handleReset && (
                    <button
                      type="button"
                      onClick={handleReset}
                      className="px-2.5 py-1 text-xs font-medium text-ink2 hover:text-ink bg-paper2 hover:bg-paper3 border border-rule rounded-input transition-colors flex items-center gap-1.5"
                      title="Cancelar ou iniciar um novo vídeo"
                    >
                      <RotateCcw size={12} />
                      <span>Cancelar / Novo</span>
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
                <div className="mb-3 flex items-center gap-2.5 text-xs text-ink2 min-w-0 bg-paper2/80 px-3 py-2 rounded-input border border-rule">
                  <Loader2 size={15} className="animate-spin text-brass shrink-0" />
                  <div className="min-w-0 flex-1 flex items-center gap-2">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-brass font-semibold shrink-0">Status:</span>
                    <span className="min-w-0 truncate font-mono text-ink text-xs">
                      {logs.length ? logs[logs.length - 1] : 'Iniciando pipeline…'}
                    </span>
                  </div>
                </div>
              )}

              {status === 'processing' && (
                <div className="my-3">
                  <StarBanner message="Got a minute while this renders?" />
                </div>
              )}

              <div className={`bg-paper rounded-card border border-rule overflow-hidden flex flex-col transition-all duration-300 flex-1 ${logsVisible ? 'min-h-[160px] sm:min-h-[200px]' : 'min-h-0 flex-none'}`}>
                <button
                  type="button"
                  onClick={() => setLogsVisible(!logsVisible)}
                  aria-expanded={logsVisible}
                  className="w-full px-3.5 sm:px-4 py-2.5 border-b border-rule flex items-center justify-between gap-2 bg-paper2 shrink-0 text-left select-none"
                >
                  <span className="readout flex items-center gap-2">
                    <Terminal size={12} /> System Logs
                    <span className="text-[10px] text-muted normal-case font-normal">(mais recentes no topo)</span>
                  </span>
                  <span className="flex items-center gap-2 text-muted">
                    {!logsVisible && logs.length > 0 && (
                      <span className="readout normal-case">{logs.length}</span>
                    )}
                    <ChevronDown size={16} className={logsVisible ? '' : 'rotate-180'} />
                  </span>
                </button>
                {logsVisible && (
                  <div className="flex-1 p-3.5 sm:p-4 overflow-y-auto font-mono text-[11px] sm:text-xs space-y-1.5 custom-scrollbar text-muted break-words">
                    {status === 'processing' && (
                      <div className="flex items-center gap-2 text-brass text-[11px] pb-1 border-b border-dotted border-white/20 mb-1">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-brass animate-ping" />
                        <span className="font-sans font-medium text-[10px] uppercase tracking-wider">Última atualização em tempo real:</span>
                      </div>
                    )}
                    {[...logs].reverse().map((log, i) => {
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
                        <div key={i} className={`flex gap-3 py-1 border-b border-dotted border-white/20 last:border-0 hover:bg-white/[0.03] transition-colors px-1 ${textColor}`}>
                          <span className="text-muted/40 shrink-0 font-mono text-[10px] hidden sm:inline pt-0.5 select-none">
                            {new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}
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

          <div className={`${status === 'complete' ? 'w-full' : 'w-full md:w-[45%] lg:w-[40%]'} md:h-full flex flex-col shrink-0 md:shrink card p-3 sm:p-5 xl:p-6 transition-all duration-500 ease-out`}>
            <div className="mb-4 sm:mb-5 shrink-0 flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-rule/50">
              <h2 className="text-base sm:text-lg font-semibold text-ink flex flex-wrap items-center gap-2">
                <span>Shorts Gerados</span>
                {results?.clips?.length > 0 && (
                  <span className="readout bg-paper3 border border-rule px-2.5 py-0.5 rounded-full text-xs">
                    {results.clips.length} Clipes
                  </span>
                )}
                {results?.cost_analysis && !isManaged && (
                  <span className="readout bg-paper3 border border-rule px-2.5 py-0.5 rounded-full text-xs" title={`Input: ${results.cost_analysis.input_tokens} | Output: ${results.cost_analysis.output_tokens}`}>
                    GEMINI · ${results.cost_analysis.total_cost.toFixed(5)}
                  </span>
                )}
              </h2>
              {status === 'complete' && (
                <div className="flex items-center gap-2 shrink-0">
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
                      elevenLabsKey={elevenLabsKey}
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
                  <div className="h-full min-h-[120px] flex flex-col items-center justify-center text-danger space-y-2">
                    <p>Falha na geração dos clipes.</p>
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
