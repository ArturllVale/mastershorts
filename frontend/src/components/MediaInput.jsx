import React, { useState, useEffect, useRef } from 'react';
import { Link2, Upload, FileVideo, X, Info, ChevronDown, Sparkles, ClipboardPaste, Loader2 } from 'lucide-react';
import { getApiUrl } from '../config';
import { cn } from '../lib/utils';

const SUPPORTED_PLATFORMS = [
    'YouTube', 'Vimeo', 'TikTok', 'X / Twitter', 'Twitch',
    'Facebook', 'Instagram', 'Dailymotion', 'Reddit', 'Streamable',
];

export default function MediaInput({ onProcess, isProcessing }) {
    const [youtubeUrlEnabled, setYoutubeUrlEnabled] = useState(true);
    // 1st priority: 'url', 2nd priority: 'file'
    const [mode, setMode] = useState('url');
    const [url, setUrl] = useState('');
    const [file, setFile] = useState(null);
    const [acknowledged, setAcknowledged] = useState(false);
    const [outputFormat, setOutputFormat] = useState('vertical'); // vertical | horizontal | square
    const [showInfo, setShowInfo] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [targetClips, setTargetClips] = useState('');
    const [clipMinSeconds, setClipMinSeconds] = useState('');
    const [clipMaxSeconds, setClipMaxSeconds] = useState('');
    const [autoHook, setAutoHook] = useState(() => {
        try { return localStorage.getItem('os_auto_hook') !== '0'; } catch { return true; }
    });
    const [autoHookStyle, setAutoHookStyle] = useState(() => {
        try { return localStorage.getItem('os_auto_hook_style') || 'classic'; } catch { return 'classic'; }
    });
    const [layout, setLayout] = useState(() => {
        try { return localStorage.getItem('os_layout') || 'auto'; } catch { return 'auto'; }
    });
    const [forceRerun, setForceRerun] = useState(false);
    const infoRef = useRef(null);

    useEffect(() => {
        if (!showInfo) return;
        const onClick = (e) => {
            if (infoRef.current && !infoRef.current.contains(e.target)) setShowInfo(false);
        };
        document.addEventListener('mousedown', onClick);
        return () => document.removeEventListener('mousedown', onClick);
    }, [showInfo]);

    useEffect(() => {
        fetch(getApiUrl('/api/config'))
            .then((r) => (r.ok ? r.json() : null))
            .then((cfg) => {
                if (cfg && cfg.youtubeUrlEnabled === false) {
                    setYoutubeUrlEnabled(false);
                    setMode('file');
                }
            })
            .catch(() => {});
    }, []);

    useEffect(() => {
        let pending = null;
        try {
            pending = localStorage.getItem('os_pending_url');
            if (pending) localStorage.removeItem('os_pending_url');
        } catch { /* ignore */ }
        if (pending) {
            setMode('url');
            setUrl(pending);
        }
    }, []);

    const handlePaste = async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text && text.trim()) {
                setUrl(text.trim());
            }
        } catch {
            // Clipboard permission denied or unsupported
        }
    };

    const hasMedia = mode === 'url' ? Boolean(url?.trim()) : Boolean(file);
    const canSubmit = !isProcessing && acknowledged && hasMedia;

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!canSubmit) return;
        const advanced = {
            targetClips: targetClips || null,
            clipMinSeconds: clipMinSeconds || null,
            clipMaxSeconds: clipMaxSeconds || null,
            autoHook,
            autoHookStyle,
            layout,
        };
        try {
            localStorage.setItem('os_auto_hook', autoHook ? '1' : '0');
            localStorage.setItem('os_auto_hook_style', autoHookStyle);
            localStorage.setItem('os_layout', layout);
        } catch { /* ignore */ }
        if (mode === 'url' && url) {
            onProcess({ type: 'url', payload: url, acknowledged: true, outputFormat, forceRerun, ...advanced });
        } else if (mode === 'file' && file) {
            onProcess({ type: 'file', payload: file, acknowledged: true, outputFormat, forceRerun, ...advanced });
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setFile(e.dataTransfer.files[0]);
            setMode('file');
        }
    };

    return (
        <div className="card p-5 sm:p-7 animate-fade border border-white/[0.08] bg-paper2/90 shadow-elevated rounded-panel backdrop-blur-md">
            {/* Source Mode Toggle Tabs (1st: Colar Link, 2nd: Enviar Arquivo) */}
            <div className="flex p-1 bg-paper/80 rounded-xl border border-rule mb-6 shadow-inner gap-1" data-tutorial="source-tabs">
                {youtubeUrlEnabled && (
                    <button
                        type="button"
                        onClick={() => setMode('url')}
                        className={cn(
                            'flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-xs font-semibold transition-all duration-200 select-none cursor-pointer',
                            mode === 'url'
                                ? 'bg-paper3 text-ink shadow-sm border border-rule2'
                                : 'text-muted hover:text-ink hover:bg-paper2/50 border border-transparent'
                        )}
                    >
                        <Link2 size={15} className={mode === 'url' ? 'text-violet' : ''} />
                        <span>Colar Link do Vídeo</span>
                    </button>
                )}
                <button
                    type="button"
                    onClick={() => setMode('file')}
                    className={cn(
                        'flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-xs font-semibold transition-all duration-200 select-none cursor-pointer',
                        mode === 'file'
                            ? 'bg-paper3 text-ink shadow-sm border border-rule2'
                            : 'text-muted hover:text-ink hover:bg-paper2/50 border border-transparent'
                    )}
                >
                    <Upload size={15} className={mode === 'file' ? 'text-violet' : ''} />
                    <span>Enviar Arquivo de Vídeo</span>
                </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
                {mode === 'url' ? (
                    <div className="space-y-3" data-tutorial="drop-zone">
                        <div className="relative flex items-center">
                            <div className="absolute left-3.5 text-muted pointer-events-none">
                                <Link2 size={16} />
                            </div>
                            <input
                                type="url"
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                placeholder="Cole o link do vídeo (YouTube, TikTok, Vimeo, Twitch...)"
                                className="input-field pl-10 pr-24 h-12 text-sm font-sans placeholder:text-muted/60 focus:border-violet focus:ring-1 focus:ring-violet/40 transition-all"
                                required
                            />
                            <div className="absolute right-2 flex items-center gap-1" ref={infoRef}>
                                {url ? (
                                    <button
                                        type="button"
                                        onClick={() => setUrl('')}
                                        aria-label="Limpar link"
                                        className="p-1.5 text-muted hover:text-ink rounded-md transition-colors"
                                        title="Limpar"
                                    >
                                        <X size={15} />
                                    </button>
                                ) : (
                                    <button
                                        type="button"
                                        onClick={handlePaste}
                                        className="px-2 py-1 text-[11px] font-mono text-violet hover:text-violet/90 bg-violet/10 hover:bg-violet/20 border border-violet/20 rounded transition-colors flex items-center gap-1"
                                        title="Colar da área de transferência"
                                    >
                                        <ClipboardPaste size={12} />
                                        <span>Colar</span>
                                    </button>
                                )}
                                <button
                                    type="button"
                                    onClick={() => setShowInfo((v) => !v)}
                                    aria-label="Plataformas suportadas"
                                    className="p-1.5 text-muted hover:text-violet transition-colors"
                                    title="Ver plataformas suportadas"
                                >
                                    <Info size={16} />
                                </button>
                                {showInfo && (
                                    <div className="absolute right-0 top-full mt-2 w-72 z-30 card p-4 text-left animate-fade shadow-elevated border-rule2">
                                        <p className="eyebrow mb-2">Plataformas Suportadas</p>
                                        <div className="flex flex-wrap gap-1.5 mb-2.5">
                                            {SUPPORTED_PLATFORMS.map((p) => (
                                                <span key={p} className="text-[11px] px-2 py-0.5 rounded-full bg-paper3 border border-rule text-ink2">
                                                    {p}
                                                </span>
                                            ))}
                                        </div>
                                        <p className="text-xs text-muted leading-relaxed">
                                            E mais de 1.000 fontes públicas de vídeo suportadas automaticamente.
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>
                        {url && (
                            <label className="flex items-center gap-2 cursor-pointer text-xs text-muted hover:text-ink transition-colors select-none pt-1">
                                <input
                                    type="checkbox"
                                    checked={forceRerun}
                                    onChange={(e) => setForceRerun(e.target.checked)}
                                    className="w-3.5 h-3.5 rounded border-rule bg-paper2 text-violet focus:ring-violet/30 cursor-pointer"
                                />
                                <span>Refazer do zero (ignorar projeto e cortes anteriores deste link)</span>
                            </label>
                        )}
                    </div>
                ) : (
                    <div
                        data-tutorial="drop-zone"
                        className={cn(
                            'border-2 border-dashed rounded-card p-6 sm:p-8 text-center transition-all duration-200 cursor-pointer bg-paper/40',
                            file ? 'border-violet/70 bg-violet/5' : 'border-rule2 hover:border-rule-strong hover:bg-paper3/40'
                        )}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={handleDrop}
                    >
                        {file ? (
                            <div className="flex items-center justify-between gap-3 p-3 bg-paper2 rounded-input border border-rule min-w-0 max-w-md mx-auto">
                                <div className="flex items-center gap-3 min-w-0">
                                    <div className="w-10 h-10 rounded-input bg-violet/10 border border-violet/30 flex items-center justify-center shrink-0">
                                        <FileVideo size={20} className="text-violet" />
                                    </div>
                                    <div className="min-w-0 text-left">
                                        <p className="font-medium text-sm text-ink truncate">{file.name}</p>
                                        <p className="readout text-[11px] text-muted">
                                            {(file.size / (1024 * 1024)).toFixed(1)} MB · Pronto
                                        </p>
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => setFile(null)}
                                    aria-label="Remover vídeo"
                                    className="p-1.5 text-muted hover:text-ink hover:bg-paper3 rounded-full transition-colors shrink-0"
                                >
                                    <X size={16} />
                                </button>
                            </div>
                        ) : (
                            <label className="cursor-pointer block space-y-2.5">
                                <input
                                    type="file"
                                    accept="video/*"
                                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                                    className="hidden"
                                />
                                <div className="w-12 h-12 rounded-full bg-paper3 border border-rule flex items-center justify-center mx-auto text-muted group-hover:text-violet transition-colors">
                                    <Upload size={20} />
                                </div>
                                <div>
                                    <p className="text-sm font-semibold text-ink">Clique para enviar ou arraste o vídeo aqui</p>
                                    <p className="text-xs text-muted mt-1">MP4, MOV, WEBM ou MKV (até 2GB)</p>
                                </div>
                            </label>
                        )}
                    </div>
                )}

                {/* Output Format Picker */}
                <div data-tutorial="output-format" className="space-y-2">
                    <div className="flex items-center justify-between">
                        <label className="block text-xs font-semibold text-muted uppercase tracking-wider font-mono">
                            Formato de Saída
                        </label>
                        <span className="text-[11px] font-mono text-muted">9:16 Otimizado</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 sm:gap-3">
                        {[
                            { value: 'vertical', label: '9:16 Vertical', hint: 'Shorts · TikTok · Reels', w: 15, h: 26, badge: 'Popular' },
                            { value: 'square', label: '1:1 Quadrado', hint: 'Feed & Redes', w: 20, h: 20 },
                            { value: 'horizontal', label: '16:9 Paisagem', hint: 'YouTube & Desktop', w: 26, h: 15 },
                        ].map((f) => {
                            const active = outputFormat === f.value;
                            return (
                                <button
                                    key={f.value}
                                    type="button"
                                    onClick={() => setOutputFormat(f.value)}
                                    className={cn(
                                        'relative py-3 px-2 sm:px-3 rounded-xl border flex flex-col items-center justify-between gap-1.5 transition-all duration-200 select-none cursor-pointer',
                                        active
                                            ? 'border-violet bg-violet/[0.08] text-ink shadow-sm ring-1 ring-violet/30'
                                            : 'border-rule bg-paper/60 text-muted hover:border-rule2 hover:text-ink2 hover:bg-paper2/50'
                                    )}
                                >
                                    {f.badge && (
                                        <span className="absolute -top-2 right-2 text-[9px] font-mono font-bold uppercase tracking-wider bg-violet text-white px-1.5 py-0.2 rounded-full shadow-sm">
                                            {f.badge}
                                        </span>
                                    )}
                                    <span
                                        className={cn(
                                            "rounded-[3px] border-2 transition-all flex items-center justify-center my-0.5",
                                            active ? "border-violet bg-violet/20" : "border-rule2 bg-transparent"
                                        )}
                                        style={{ width: `${f.w}px`, height: `${f.h}px` }}
                                    />
                                    <div className="text-center min-w-0 w-full">
                                        <span className="block font-semibold text-xs leading-none truncate">{f.label}</span>
                                        <span className="block text-[10px] text-muted truncate mt-0.5">{f.hint}</span>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Collapsible Advanced Options */}
                <div className="rounded-xl border border-rule bg-paper/50 overflow-hidden">
                    <button
                        type="button"
                        onClick={() => setShowAdvanced((v) => !v)}
                        className="w-full flex items-center justify-between px-4 py-2.5 text-xs text-muted hover:text-ink transition-colors select-none"
                    >
                        <span className="flex items-center gap-2 font-medium">
                            <ChevronDown size={14} className={cn('transition-transform duration-200', showAdvanced && 'rotate-180')} />
                            <span>Controles Avançados de Geração</span>
                            {(targetClips || clipMinSeconds || clipMaxSeconds || !autoHook) && (
                                <span className="w-1.5 h-1.5 rounded-full bg-violet shrink-0" />
                            )}
                        </span>
                        <span className="text-[11px] text-muted-dim font-mono">
                            {showAdvanced ? 'Ocultar' : 'Configurar'}
                        </span>
                    </button>
                    {showAdvanced && (
                        <div className="p-4 pt-2 border-t border-rule space-y-4 animate-fade text-left">
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                <div>
                                    <label className="block text-[11px] font-mono uppercase text-muted mb-1">Quantidade Alvo</label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="15"
                                        step="1"
                                        value={targetClips}
                                        onChange={(e) => setTargetClips(e.target.value)}
                                        placeholder="Automático"
                                        className="input-field text-xs py-1.5"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[11px] font-mono uppercase text-muted mb-1">Duração Mínima (s)</label>
                                    <input
                                        type="number"
                                        min="5"
                                        max="175"
                                        step="1"
                                        value={clipMinSeconds}
                                        onChange={(e) => setClipMinSeconds(e.target.value)}
                                        placeholder="15"
                                        className="input-field text-xs py-1.5"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[11px] font-mono uppercase text-muted mb-1">Duração Máxima (s)</label>
                                    <input
                                        type="number"
                                        min="10"
                                        max="180"
                                        step="1"
                                        value={clipMaxSeconds}
                                        onChange={(e) => setClipMaxSeconds(e.target.value)}
                                        placeholder="60"
                                        className="input-field text-xs py-1.5"
                                    />
                                </div>
                            </div>

                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-rule">
                                <div>
                                    <p className="text-xs font-medium text-ink">Enquadramento Vertical</p>
                                    <p className="text-[11px] text-muted">Estratégia de corte para vídeos widescreen</p>
                                </div>
                                <select
                                    value={layout}
                                    onChange={(e) => setLayout(e.target.value)}
                                    className="input-field !w-auto text-xs py-1.5 cursor-pointer"
                                    aria-label="Estratégia de enquadramento vertical"
                                >
                                    <option value="auto">Automático (IA escolhe por cena)</option>
                                    <option value="split">Dois oradores empilhados (Split)</option>
                                    <option value="screencast">Tela sobre apresentador</option>
                                    <option value="none">Corte simples único</option>
                                </select>
                            </div>

                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-rule">
                                <label className="flex items-center gap-2.5 text-xs text-ink cursor-pointer select-none">
                                    <input
                                        type="checkbox"
                                        checked={autoHook}
                                        onChange={(e) => setAutoHook(e.target.checked)}
                                        className="w-4 h-4 rounded accent-violet cursor-pointer"
                                    />
                                    <span>Inserir título gancho viral nos clipes gerados</span>
                                </label>
                                {autoHook && (
                                    <select
                                        value={autoHookStyle}
                                        onChange={(e) => setAutoHookStyle(e.target.value)}
                                        className="input-field !w-auto text-xs py-1.5 cursor-pointer"
                                        aria-label="Estilo do gancho"
                                    >
                                        <option value="classic">Estilo Clássico</option>
                                        <option value="dark">Estilo Escuro</option>
                                        <option value="yellow">Destaque Amarelo</option>
                                        <option value="red">Alerta Vermelho</option>
                                        <option value="outline">Contorno</option>
                                        <option value="outline_yellow">Contorno Dourado</option>
                                    </select>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {/* Rights attestation */}
                <label className={cn(
                    "flex items-start gap-2.5 text-left text-xs transition-all cursor-pointer select-none p-2 rounded-lg",
                    hasMedia && !acknowledged
                        ? "bg-violet/10 border border-violet/30 text-ink shadow-sm"
                        : "text-muted hover:text-ink2"
                )}>
                    <input
                        type="checkbox"
                        checked={acknowledged}
                        onChange={(e) => setAcknowledged(e.target.checked)}
                        className="mt-0.5 w-4 h-4 rounded accent-violet cursor-pointer"
                    />
                    <span className="leading-relaxed">
                        Confirmo que possuo os direitos para processar este conteúdo. Veja nossos{' '}
                        <a href="/terms" target="_blank" rel="noopener noreferrer" className="text-ink underline hover:text-violet" onClick={(e) => e.stopPropagation()}>Termos</a> e{' '}
                        <a href="/privacy" target="_blank" rel="noopener noreferrer" className="text-ink underline hover:text-violet" onClick={(e) => e.stopPropagation()}>Política de Privacidade</a>.
                    </span>
                </label>

                {/* Primary Submit Action */}
                <button
                    type="submit"
                    data-tutorial="generate"
                    disabled={!canSubmit}
                    className={cn(
                        'w-full flex items-center justify-center gap-2.5 py-3.5 px-6 rounded-xl text-sm sm:text-base font-bold transition-all duration-300 select-none',
                        canSubmit
                            ? 'bg-gradient-to-r from-violet-600 via-purple-600 to-indigo-600 hover:from-violet-500 hover:via-purple-500 hover:to-indigo-500 text-white shadow-[0_4px_24px_rgba(139,92,246,0.45)] hover:shadow-[0_6px_32px_rgba(139,92,246,0.65)] border border-violet-400/40 hover:border-violet-300/70 active:scale-[0.99] cursor-pointer'
                            : 'bg-paper3/90 text-muted/70 border border-rule cursor-not-allowed shadow-none'
                    )}
                >
                    {isProcessing ? (
                        <>
                            <Loader2 size={18} className="animate-spin text-white" />
                            <span>Analisando e Processando Vídeo…</span>
                        </>
                    ) : (
                        <>
                            <Sparkles size={17} className={canSubmit ? 'text-amber-300 animate-pulse' : 'text-muted/40'} />
                            <span>Gerar Shorts Virais</span>
                        </>
                    )}
                </button>
            </form>
        </div>
    );
}
