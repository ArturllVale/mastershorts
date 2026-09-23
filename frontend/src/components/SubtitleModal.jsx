import React, { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import RemotionPreview from './RemotionPreview';
import Modal from './ui/Modal';
import SegmentedControl from './ui/SegmentedControl';
import {
    FONT_OPTIONS,
    COLOR_PRESETS,
    HIGHLIGHT_PRESETS,
    ANIMATION_OPTIONS,
    POSITION_OPTIONS,
    CAPTION_PRESETS,
} from '../lib/subtitleConstants';
import { fetchClipTranscript } from '../services/clipService';


const swatchClass = (selected) =>
    `w-6 h-6 rounded-full transition-all ${selected
        ? 'ring-2 ring-[color:var(--color-accent)] ring-offset-2 ring-offset-[color:var(--color-paper-2)]'
        : 'ring-1 ring-[color:var(--color-rule-2)] hover:ring-[color:var(--color-accent)]'}`;

export default function SubtitleModal({
    isOpen,
    onClose,
    onGenerate,
    onApplyAll,
    onRemove,
    isProcessing,
    videoUrl,
    jobId,
    clipIndex,
    existingHook,
    existingSubtitles,
    bulkCount = 0,
    bulkProgress
}) {
    const initStyle = existingSubtitles?.style || {};
    const [position, setPosition] = useState(existingSubtitles?.position || 'bottom');
    const [marginV, setMarginV] = useState(initStyle.marginV ?? 43);
    const [fontSize, setFontSize] = useState(
        initStyle.fontSize
            ? (initStyle.fontSize > 64 ? Math.round(initStyle.fontSize / 1.8) : initStyle.fontSize)
            : 44
    );
    const [fontName, setFontName] = useState(initStyle.fontFamily || 'Anton');
    const [fontColor, setFontColor] = useState(initStyle.fontColor || '#FFFFFF');
    const [activeTextColor, setActiveTextColor] = useState(initStyle.activeTextColor || '#FFFFFF');
    const [highlightColor, setHighlightColor] = useState(initStyle.highlightColor || '#FFE500');
    const [borderColor, setBorderColor] = useState(initStyle.borderColor || '#000000');
    const [borderWidth, setBorderWidth] = useState(
        initStyle.borderWidth != null
            ? (initStyle.borderWidth > 6 ? Math.round(initStyle.borderWidth / 1.5) : initStyle.borderWidth)
            : 4
    );
    const [bgColor, setBgColor] = useState(initStyle.bgColor || '#000000');
    const [bgOpacity, setBgOpacity] = useState(initStyle.bgOpacity ?? 0.0);
    const [animation, setAnimation] = useState(initStyle.animation || 'pop');
    const [showTextEditor, setShowTextEditor] = useState(false);

    // Karaoke (server-side ASS burn) state
    const [style, setStyle] = useState('karaoke'); // classic | karaoke
    const [effect, setEffect] = useState('pop'); // none | glow | pop | box
    const [baseOpacity, setBaseOpacity] = useState(initStyle.baseOpacity ?? 1.0);
    const [uppercase, setUppercase] = useState(initStyle.uppercase ?? true);
    const [activePreset, setActivePreset] = useState('auto');

    const applyPreset = (p) => {
        setActivePreset(p.id);
        if (p.style) setStyle(p.style);
        if (p.effect) setEffect(p.effect);
        if (p.highlightColor) setHighlightColor(p.highlightColor);
        if (p.baseOpacity != null) setBaseOpacity(p.baseOpacity);
        if (p.uppercase != null) setUppercase(p.uppercase);
        if (p.fontName) setFontName(p.fontName);
        if (p.borderWidth != null) setBorderWidth(p.borderWidth);
        if (p.fontSize) setFontSize(p.fontSize);
        if (p.marginV != null) setMarginV(p.marginV);
        setFontColor(p.fontColor || '#FFFFFF');
        if (p.activeTextColor) setActiveTextColor(p.activeTextColor);
        if (p.bgColor) setBgColor(p.bgColor);
        setBgOpacity(p.bgOpacity || 0);
        setAnimation(p.style === 'karaoke' ? (p.effect === 'pop' ? 'pop' : p.effect === 'glow' ? 'word-highlight' : 'karaoke') : 'none');
    };

    // Remotion preview state
    const [captions, setCaptions] = useState([]);
    const [originalCaptions, setOriginalCaptions] = useState([]);
    const [editableText, setEditableText] = useState('');
    const [durationSec, setDurationSec] = useState(30);
    const [captionsLoading, setCaptionsLoading] = useState(false);
    const [useRemotionPreview, setUseRemotionPreview] = useState(false);

    // Fetch word-level captions when modal opens
    useEffect(() => {
        if (!isOpen || !jobId || clipIndex === undefined) return;

        setCaptionsLoading(true);
        fetchClipTranscript(jobId, clipIndex)
            .then((data) => {
                if (data && data.captions && data.captions.length > 0) {
                    setCaptions(data.captions);
                    setOriginalCaptions(data.captions);
                    setEditableText(data.captions.map(c => c.text).join(' '));
                    setDurationSec(data.durationSec || 30);
                    setUseRemotionPreview(true);
                } else {
                    setUseRemotionPreview(false);
                }
            })
            .catch(() => setUseRemotionPreview(false))
            .finally(() => setCaptionsLoading(false));
    }, [isOpen, jobId, clipIndex]);

    // When user edits text, redistribute words across original timestamps
    const handleTextEdit = (newText) => {
        setEditableText(newText);
        const newWords = newText.split(/\s+/).filter(w => w.length > 0);
        if (newWords.length === 0 || originalCaptions.length === 0) {
            setCaptions([]);
            return;
        }

        const newCaptions = [];
        const numNew = newWords.length;
        const numOld = originalCaptions.length;
        
        if (numNew === numOld) {
            // 1:1 mapping: keep exact original timestamps
            for (let i = 0; i < numNew; i++) {
                newCaptions.push({
                    text: newWords[i],
                    startMs: originalCaptions[i].startMs,
                    endMs: originalCaptions[i].endMs,
                });
            }
        } else if (numNew > numOld) {
            // More words than original: distribute new words inside original intervals
            const ratio = numNew / numOld;
            let newIndex = 0;
            for (let i = 0; i < numOld; i++) {
                const oldCap = originalCaptions[i];
                const targetEndIndex = Math.min(Math.round((i + 1) * ratio), numNew);
                const count = targetEndIndex - newIndex;
                
                if (count > 0) {
                    const duration = oldCap.endMs - oldCap.startMs;
                    const chunkDur = duration / count;
                    for (let j = 0; j < count; j++) {
                        newCaptions.push({
                            text: newWords[newIndex],
                            startMs: Math.round(oldCap.startMs + j * chunkDur),
                            endMs: Math.round(oldCap.startMs + (j + 1) * chunkDur),
                        });
                        newIndex++;
                    }
                }
            }
            while (newIndex < numNew) {
                 const oldCap = originalCaptions[numOld - 1];
                 newCaptions.push({
                     text: newWords[newIndex],
                     startMs: oldCap.startMs,
                     endMs: oldCap.endMs,
                 });
                 newIndex++;
            }
        } else {
            // Fewer words than original: combine old intervals
            const ratio = numOld / numNew;
            let oldIndex = 0;
            for (let i = 0; i < numNew; i++) {
                const targetEndIndex = Math.min(Math.round((i + 1) * ratio), numOld);
                if (targetEndIndex > oldIndex) {
                     newCaptions.push({
                         text: newWords[i],
                         startMs: originalCaptions[oldIndex].startMs,
                         endMs: originalCaptions[targetEndIndex - 1].endMs,
                     });
                     oldIndex = targetEndIndex;
                } else {
                     newCaptions.push({
                         text: newWords[i],
                         startMs: originalCaptions[oldIndex].startMs,
                         endMs: originalCaptions[oldIndex].endMs,
                     });
                }
            }
        }
        setCaptions(newCaptions);
    };

    if (!isOpen) return null;

    // Build subtitle config for Remotion
    const subtitleConfig = {
        captions,
        position,
        style: {
            fontFamily: fontName,
            fontSize: fontSize * 1.8, // Scale up for 1080p canvas (Remotion renders in 1920px height)
            fontColor,
            activeTextColor,
            highlightColor,
            borderColor,
            // ×1.5 is a calibration factor: CSS textShadow of (borderWidth×1.5)px on the 1920px
            // canvas produces the same visual weight as the libass ASS Outline rendered at
            // max(1, round(borderWidth×1.5×288/1920)) units in PlayResY=288 space.
            borderWidth: borderWidth * 1.5,
            bgColor,
            bgOpacity,
            animation,
            marginV,
            // Karaoke look reflected live in the playable preview.
            baseOpacity: style === 'karaoke' ? baseOpacity : 1,
            uppercase: style === 'karaoke' ? uppercase : false,
        },
    };

    // Fallback: static CSS preview (scaled to the ~600px preview container, 600/1920 = 0.3125)
    // ×1.5 calibration factor mirrors the subtitleConfig above so both previews look the same.
    const bw = Math.max(Math.round(borderWidth * 1.5 * 0.3125), 0);
    const bc = borderColor;
    const outlineShadow = bw > 0 ? [
        `-${bw}px -${bw}px 0 ${bc}`, `${bw}px -${bw}px 0 ${bc}`,
        `-${bw}px ${bw}px 0 ${bc}`, `${bw}px ${bw}px 0 ${bc}`,
        `0 -${bw}px 0 ${bc}`, `0 ${bw}px 0 ${bc}`,
        `-${bw}px 0 0 ${bc}`, `${bw}px 0 0 ${bc}`,
    ].join(', ') : 'none';

    const fallbackPreviewStyle = {
        fontFamily: fontName,
        color: fontColor,
        fontSize: `${Math.round(fontSize * 1.8 * 0.3125)}px`,
        fontWeight: /anton/i.test(fontName) ? 400 : 800,
        maxWidth: '85%',
        padding: '6px 12px',
        borderRadius: '4px',
        textAlign: 'center',
        lineHeight: '1.3',
        textTransform: uppercase ? 'uppercase' : 'none',
        ...(bgOpacity > 0
            ? {
                backgroundColor: `${bgColor}${Math.round(bgOpacity * 255).toString(16).padStart(2, '0')}`,
                textShadow: 'none',
            }
            : { textShadow: outlineShadow }
        ),
    };

    const marginPercent = ((marginV ?? 43) / 288) * 100;
    const fallbackPositionStyle =
        position === 'top'
            ? { top: `${marginPercent}%`, bottom: 'auto' }
            : position === 'middle' || position === 'center'
                ? { top: '50%', transform: 'translateY(-50%)' }
                : { bottom: `${marginPercent}%`, top: 'auto' };

    return (
        <Modal isOpen={isOpen} onClose={onClose} size="xl" eyebrow="EDITOR · LEGENDAS" title="Legendas">
            <div className="flex flex-col md:flex-row gap-6">
                {/* Left: Preview */}
                <div className="flex-1 flex flex-col items-center justify-center bg-black rounded-card border border-rule overflow-hidden relative aspect-[9/16] max-h-[600px]">
                    {captionsLoading ? (
                        <div className="flex items-center gap-2 text-muted">
                            <Loader2 size={16} className="animate-spin" />
                            <span className="text-sm lowercase">Carregando prévia...</span>
                        </div>
                    ) : useRemotionPreview ? (
                        <RemotionPreview
                            videoUrl={videoUrl}
                            durationInSeconds={durationSec}
                            subtitles={subtitleConfig}
                            hook={existingHook || null}
                        />
                    ) : (
                        <>
                            <video src={videoUrl} className="w-full h-full object-contain opacity-50" muted playsInline />
                            <div
                                className="absolute w-full px-8 text-center transition-all duration-200 pointer-events-none flex flex-col items-center justify-center"
                                style={fallbackPositionStyle}
                            >
                                <span style={fallbackPreviewStyle}>
                                    É assim que suas legendas<br />aparecerão no vídeo
                                </span>
                            </div>
                        </>
                    )}
                </div>

                {/* Right: Controls */}
                <div className="w-full md:w-80 flex flex-col">
                    <div className="space-y-5 flex-1 overflow-y-auto custom-scrollbar pr-1">
                        {/* Caption presets (server-side karaoke burn) */}
                        <div>
                            <p className="eyebrow mb-2">Predefinições</p>
                            <div className="grid grid-cols-3 gap-1.5">
                                {CAPTION_PRESETS.map((p) => (
                                    <button
                                        key={p.id}
                                        onClick={() => applyPreset(p)}
                                        className={`px-2 py-1.5 rounded-input border text-xs transition-colors flex items-center gap-1.5 justify-center
                                            ${activePreset === p.id
                                                ? 'border-[color:var(--color-accent)] text-ink'
                                                : 'border-rule2 text-muted hover:border-[color:var(--color-accent)]'}`}
                                        title={p.label}
                                    >
                                        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: p.highlightColor }} />
                                        <span className="truncate">{p.label}</span>
                                    </button>
                                ))}
                            </div>
                            {style === 'karaoke' && (
                                <div className="mt-3 space-y-3 animate-fade">
                                    <div className="flex items-center justify-between">
                                        <span className="readout">MAIÚSCULAS</span>
                                        <label className="relative inline-flex items-center cursor-pointer">
                                            <input type="checkbox" checked={uppercase} onChange={(e) => setUppercase(e.target.checked)} className="sr-only peer" />
                                            <div className="w-8 h-4 rounded-full bg-paper3 peer-checked:bg-brass transition-colors after:content-[''] after:absolute after:top-0 after:left-0 after:h-4 after:w-4 after:rounded-full after:bg-ink after:transition-all peer-checked:after:translate-x-full"></div>
                                        </label>
                                    </div>
                                    <div>
                                        <div className="flex justify-between mb-1">
                                            <span className="readout">Atenuar palavras inativas</span>
                                            <span className="readout">{Math.round(baseOpacity * 100)}%</span>
                                        </div>
                                        <input
                                            type="range"
                                            min="30"
                                            max="100"
                                            value={Math.round(baseOpacity * 100)}
                                            onChange={(e) => setBaseOpacity(parseInt(e.target.value) / 100)}
                                            className="w-full accent-[var(--color-accent)]"
                                        />
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Position Selector */}
                        <div>
                            <div className="flex justify-between items-center mb-2">
                                <p className="eyebrow">Posição</p>
                                <span className="readout">
                                    {position === 'bottom' ? 'Rodapé' : position === 'top' ? 'Topo' : 'Centro'}
                                </span>
                            </div>
                            <SegmentedControl
                                options={POSITION_OPTIONS}
                                value={position}
                                onChange={(val) => {
                                    setPosition(val);
                                    if (val === 'middle' || val === 'center') {
                                        setMarginV(144);
                                    } else if (marginV > 120 || marginV < 15) {
                                        setMarginV(43);
                                    }
                                }}
                                size="sm"
                            />
                        </div>

                        {/* Fine vertical position adjustment */}
                        <div>
                            <div className="flex justify-between items-center mb-1">
                                <p className="eyebrow">Ajuste de Altura (Vertical)</p>
                                <span className="readout">{Math.round((marginV / 288) * 100)}%</span>
                            </div>
                            <input
                                type="range"
                                min="15"
                                max="140"
                                step="1"
                                value={marginV}
                                onChange={(e) => setMarginV(parseInt(e.target.value, 10))}
                                className="w-full accent-[var(--color-accent)]"
                            />
                            <div className="flex justify-between items-center mt-0.5">
                                <span className="readout">Mais baixo</span>
                                <button
                                    type="button"
                                    onClick={() => setMarginV(43)}
                                    className="readout underline hover:text-ink cursor-pointer"
                                    title="Restaurar margem padrão automática (43px / ~15%)"
                                >
                                    Padrão (43)
                                </button>
                                <span className="readout">Mais alto</span>
                            </div>
                        </div>

                        {/* Animation Style */}
                        <div>
                            <p className="eyebrow mb-2">Animação</p>
                            <SegmentedControl
                                options={ANIMATION_OPTIONS}
                                value={animation}
                                onChange={(val) => {
                                    setAnimation(val);
                                    if (val === 'none') {
                                        setEffect('none');
                                    } else if (val === 'word-highlight') {
                                        setEffect('glow');
                                    } else if (val === 'karaoke') {
                                        setEffect('box');
                                    } else {
                                        setEffect('pop');
                                    }
                                }}
                                columns={2}
                                size="sm"
                            />
                        </div>

                        {/* Editable Transcript (collapsible) */}
                        {useRemotionPreview && (
                            <div>
                                <button
                                    type="button"
                                    onClick={() => setShowTextEditor(!showTextEditor)}
                                    className="w-full flex items-center justify-between mb-2"
                                >
                                    <span className="eyebrow">Editar texto ({captions.length} palavras)</span>
                                    <span className={`text-muted transition-transform ${showTextEditor ? 'rotate-180' : ''}`}>▾</span>
                                </button>
                                {showTextEditor && (
                                    <textarea
                                        value={editableText}
                                        onChange={(e) => handleTextEdit(e.target.value)}
                                        rows={5}
                                        className="input-field resize-none leading-relaxed animate-fade text-xs"
                                        placeholder="Editar texto das legendas..."
                                    />
                                )}
                            </div>
                        )}

                        {/* Font Family */}
                        <div>
                            <p className="eyebrow mb-2">Fonte</p>
                            <select
                                value={fontName}
                                onChange={(e) => setFontName(e.target.value)}
                                className="input-field"
                            >
                                {FONT_OPTIONS.map((f) => (
                                    <option key={f.value} value={f.value} style={{ fontFamily: f.value }}>{f.label}</option>
                                ))}
                            </select>
                        </div>

                        {/* Font Size */}
                        <div>
                            <div className="flex justify-between items-center mb-1">
                                <p className="eyebrow">Tamanho da fonte</p>
                                <span className="readout">{fontSize}px</span>
                            </div>
                            <input
                                type="range"
                                min="20"
                                max="64"
                                step="1"
                                value={fontSize}
                                onChange={(e) => setFontSize(parseInt(e.target.value, 10))}
                                className="w-full accent-[var(--color-accent)]"
                            />
                            <div className="flex justify-between">
                                <span className="readout">Pequeno</span>
                                <span className="readout">Padrão (44px)</span>
                                <span className="readout">Grande</span>
                            </div>
                        </div>

                        {/* Text Color */}
                        <div>
                            <p className="eyebrow mb-2">Cor do texto</p>
                            <div className="flex flex-wrap items-center gap-2.5" style={{ paddingLeft: '1em' }}>
                                {COLOR_PRESETS.map((c) => {
                                    const col = c.color || c.value;
                                    return (
                                        <button
                                            key={col}
                                            onClick={() => setFontColor(col)}
                                            className={swatchClass(fontColor === col)}
                                            style={{ backgroundColor: col }}
                                            title={c.label}
                                        />
                                    );
                                })}
                                <label className="w-6 h-6 rounded-full border border-dashed border-rule2 cursor-pointer flex items-center justify-center hover:border-brass transition-colors overflow-hidden relative" title="Cor personalizada">
                                    <span className="text-xs text-muted leading-none">+</span>
                                    <input type="color" value={fontColor} onChange={(e) => setFontColor(e.target.value)} className="absolute inset-0 opacity-0 cursor-pointer" />
                                </label>
                            </div>
                        </div>

                        {/* Highlight Color */}
                        <div>
                            <p className="eyebrow mb-2">Destaque da palavra</p>
                            <div className="flex flex-wrap items-center gap-2.5" style={{ paddingLeft: '1em' }}>
                                {HIGHLIGHT_PRESETS.map((c) => {
                                    const col = c.color || c.value;
                                    return (
                                        <button
                                            key={col}
                                            onClick={() => setHighlightColor(col)}
                                            className={swatchClass(highlightColor === col)}
                                            style={{ backgroundColor: col }}
                                            title={c.label}
                                        />
                                    );
                                })}
                                <label className="w-6 h-6 rounded-full border border-dashed border-rule2 cursor-pointer flex items-center justify-center hover:border-brass transition-colors overflow-hidden relative" title="Cor personalizada">
                                    <span className="text-xs text-muted leading-none">+</span>
                                    <input type="color" value={highlightColor} onChange={(e) => setHighlightColor(e.target.value)} className="absolute inset-0 opacity-0 cursor-pointer" />
                                </label>
                            </div>
                        </div>

                        {/* Active Text Color (Only for Karaoke/Fundo) */}
                        {animation === 'karaoke' && (
                            <div className="animate-fade mt-4">
                                <p className="eyebrow mb-2">Cor do texto destacado</p>
                                <div className="flex flex-wrap items-center gap-2.5" style={{ paddingLeft: '1em' }}>
                                    {COLOR_PRESETS.map((c) => {
                                        const col = c.color || c.value;
                                        return (
                                            <button
                                                key={`atc-${col}`}
                                                onClick={() => setActiveTextColor(col)}
                                                className={swatchClass(activeTextColor === col)}
                                                style={{ backgroundColor: col }}
                                                title={c.label}
                                            />
                                        );
                                    })}
                                    <label className="w-6 h-6 rounded-full border border-dashed border-rule2 cursor-pointer flex items-center justify-center hover:border-brass transition-colors overflow-hidden relative" title="Cor personalizada">
                                        <span className="text-xs text-muted leading-none">+</span>
                                        <input type="color" value={activeTextColor} onChange={(e) => setActiveTextColor(e.target.value)} className="absolute inset-0 opacity-0 cursor-pointer" />
                                    </label>
                                </div>
                            </div>
                        )}

                        {/* Border / Outline */}
                        <div>
                            <p className="eyebrow mb-2">Borda / Contorno</p>
                            <div className="flex items-center gap-3">
                                <label className="relative w-8 h-8 rounded-input border border-rule2 cursor-pointer overflow-hidden shrink-0" title="Cor da borda">
                                    <div className="w-full h-full" style={{ backgroundColor: borderColor }} />
                                    <input type="color" value={borderColor} onChange={(e) => setBorderColor(e.target.value)} className="absolute inset-0 opacity-0 cursor-pointer" />
                                </label>
                                <div className="flex-1">
                                    <input
                                        type="range"
                                        min="0"
                                        max="6"
                                        value={borderWidth}
                                        onChange={(e) => setBorderWidth(parseInt(e.target.value, 10))}
                                        className="w-full accent-[var(--color-accent)]"
                                    />
                                    <div className="flex justify-between">
                                        <span className="readout">Nenhuma</span>
                                        <span className="readout">Padrão (4)</span>
                                        <span className="readout">Espessa</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Background Box */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <p className="eyebrow">Fundo</p>
                                <label className="relative inline-flex items-center cursor-pointer">
                                    <input type="checkbox" checked={bgOpacity > 0} onChange={(e) => setBgOpacity(e.target.checked ? 0.5 : 0)} className="sr-only peer" />
                                    <div className="w-8 h-4 rounded-full bg-paper3 peer-checked:bg-brass transition-colors after:content-[''] after:absolute after:top-0 after:left-0 after:h-4 after:w-4 after:rounded-full after:bg-ink after:transition-all peer-checked:after:translate-x-full"></div>
                                </label>
                            </div>
                            {bgOpacity > 0 && (
                                <div className="space-y-3 animate-fade">
                                    <div className="flex items-center gap-3">
                                        <label className="relative w-8 h-8 rounded-input border border-rule2 cursor-pointer overflow-hidden shrink-0" title="Cor de fundo">
                                            <div className="w-full h-full" style={{ backgroundColor: bgColor }} />
                                            <input type="color" value={bgColor} onChange={(e) => setBgColor(e.target.value)} className="absolute inset-0 opacity-0 cursor-pointer" />
                                        </label>
                                        <div className="flex-1">
                                            <input
                                                type="range"
                                                min="10"
                                                max="100"
                                                value={Math.round(bgOpacity * 100)}
                                                onChange={(e) => setBgOpacity(parseInt(e.target.value) / 100)}
                                                className="w-full accent-[var(--color-accent)]"
                                            />
                                            <div className="flex justify-between">
                                                <span className="readout">Transparente</span>
                                                <span className="readout">{Math.round(bgOpacity * 100)}%</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="mt-5 shrink-0 space-y-2">
                        {(() => {
                            // Text edits must survive the server render path too
                            // (issue #69): send the edited words whenever the text
                            // differs from what the transcript produced.
                            const textEdited = originalCaptions.length > 0
                                && editableText.trim() !== originalCaptions.map((c) => c.text).join(' ').trim();
                            const styleOptions = {
                                position,
                                margin_v: marginV,
                                marginV,
                                fontSize,
                                fontName,
                                fontColor,
                                borderColor,
                                borderWidth,
                                bgColor,
                                bgOpacity,
                                // Karaoke burn (server-side ASS render)
                                style,
                                effect,
                                baseOpacity,
                                uppercase,
                                highlightColor,
                                activeTextColor,
                                max_chars: 16,
                                max_duration: 1.4,
                                // Remotion data
                                remotion: useRemotionPreview ? subtitleConfig : null,
                                captions: textEdited ? captions : null,
                            };
                            const bulkRunning = bulkProgress?.running;
                            return (
                                <>
                                    <div className="flex gap-2">
                                        <button onClick={onClose} className="btn-ghost">
                                            Cancelar
                                        </button>
                                        <button
                                            onClick={() => onGenerate(styleOptions)}
                                            disabled={isProcessing}
                                            className="btn-primary flex-1"
                                        >
                                            {(isProcessing && !bulkRunning) && <Loader2 size={16} className="animate-spin text-brassink" />}
                                            {(isProcessing && !bulkRunning) ? 'Gerando...' : 'Aplicar neste Corte'}
                                        </button>
                                    </div>
                                    {onApplyAll && bulkCount > 1 && (
                                        <button
                                            onClick={() => onApplyAll({ ...styleOptions, captions: null })}
                                            disabled={isProcessing}
                                            className="btn-ghost w-full flex items-center justify-center gap-2 text-xs"
                                        >
                                            {bulkRunning
                                                ? <><Loader2 size={14} className="animate-spin" /> Aplicando em todos… {bulkProgress.current}/{bulkProgress.total}</>
                                                : `Aplicar este estilo em todos os ${bulkCount} cortes`}
                                        </button>
                                    )}
                                    {onRemove && (
                                        <button
                                            onClick={onRemove}
                                            disabled={isProcessing}
                                            className="text-xs text-danger/80 hover:text-danger underline underline-offset-2 transition-colors disabled:opacity-50 text-center w-full block py-1"
                                        >
                                            Remover legendas deste corte
                                        </button>
                                    )}
                                </>
                            );
                        })()}
                    </div>
                </div>
            </div>
        </Modal>
    );
}
