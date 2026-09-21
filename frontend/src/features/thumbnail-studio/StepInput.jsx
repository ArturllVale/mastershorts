import React from 'react';
import { Video, Loader2, Check, Sparkles, Type } from 'lucide-react';
import DragDropZone from './DragDropZone';

export default function StepInput({
    needsKey,
    videoFile,
    setVideoFile,
    setMode,
    handlePreUpload,
    setPreprocessSessionId,
    isPreprocessing,
    preprocessSessionId,
    handleAnalyze,
    isAnalyzing,
    manualTitle,
    setManualTitle,
    handleManualNext
}) {
    return (
        <div className={`grid md:grid-cols-2 gap-6 ${needsKey ? 'opacity-50 pointer-events-none select-none' : ''}`}>
            {/* Mode A: Video Analysis */}
            <div className="card card-hover p-6 space-y-4">
                <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 rounded-lg bg-surface-2 border border-border flex items-center justify-center">
                        <Video size={16} className="text-accent" />
                    </div>
                    <div>
                        <p className="eyebrow">A · ANALYZE VIDEO</p>
                        <p className="text-xs text-text-tertiary mt-0.5">AI suggests viral titles from your content</p>
                    </div>
                </div>

                <DragDropZone
                    label="Upload video file"
                    accept="video/*"
                    onFile={(f) => { setVideoFile(f); setMode('video'); handlePreUpload(f); }}
                    file={videoFile}
                    onClear={() => { setVideoFile(null); setPreprocessSessionId(null); }}
                    icon={Video}
                />

                {isPreprocessing && (
                    <div className="flex items-center gap-2 text-xs text-text-secondary bg-surface-2 border border-border rounded-lg px-3 py-2">
                        <Loader2 size={12} className="animate-spin text-accent" />
                        Pre-processing video (Whisper transcription starting)...
                    </div>
                )}
                {preprocessSessionId && !isPreprocessing && (
                    <div className="flex items-center gap-2 text-xs text-success bg-success/10 border border-success/30 rounded-lg px-3 py-2">
                        <Check size={12} />
                        Video uploaded — transcription running in background
                    </div>
                )}

                <button
                    onClick={handleAnalyze}
                    disabled={isAnalyzing || !videoFile}
                    className="w-full btn-primary"
                >
                    {isAnalyzing ? (
                        <>
                            <Loader2 size={16} className="animate-spin" />
                            Analyzing video...
                        </>
                    ) : (
                        <>
                            <Sparkles size={16} className="hidden sm:block" />
                            <span className="whitespace-nowrap">Analyze & Get Titles</span>
                        </>
                    )}
                </button>
            </div>

            {/* Mode B: Manual Title */}
            <div className="card card-hover p-6 space-y-4 flex flex-col">
                <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 rounded-lg bg-surface-2 border border-border flex items-center justify-center">
                        <Type size={16} className="text-accent" />
                    </div>
                    <div>
                        <p className="eyebrow">B · WRITE YOUR OWN</p>
                        <p className="text-xs text-text-tertiary mt-0.5">Skip analysis, enter your title directly</p>
                    </div>
                </div>

                <div className="flex-1 flex flex-col justify-center">
                    <input
                        type="text"
                        value={manualTitle}
                        onChange={(e) => setManualTitle(e.target.value)}
                        placeholder="Enter your YouTube title..."
                        className="input-field text-sm mb-4"
                        maxLength={70}
                    />
                    <p className="font-mono text-xs text-text-tertiary mb-4">{manualTitle.length} / 70</p>
                    <button
                        onClick={handleManualNext}
                        disabled={!manualTitle.trim()}
                        className="w-full btn-secondary"
                    >
                        Skip Analysis →
                    </button>
                </div>
            </div>
        </div>
    );
}
