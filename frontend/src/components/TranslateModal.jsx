import React, { useState } from 'react';
import { Loader2, Languages, AlertCircle } from 'lucide-react';
import Modal from './ui/Modal';

const LANGUAGES = {
    "es": "Espanhol",
    "fr": "Francês",
    "de": "Alemão",
    "it": "Italiano",
    "pt": "Português",
    "pl": "Polonês",
    "hi": "Hindi",
    "ja": "Japonês",
    "ko": "Coreano",
    "zh": "Chinês",
    "ar": "Árabe",
    "ru": "Russo",
    "tr": "Turco",
    "nl": "Holandês",
    "sv": "Sueco",
    "id": "Indonésio",
    "fil": "Filipino",
    "ms": "Malaio",
    "vi": "Vietnamita",
    "th": "Tailandês",
    "uk": "Ucraniano",
    "el": "Grego",
    "cs": "Tcheco",
    "fi": "Finlandês",
    "ro": "Romeno",
    "da": "Dinamarquês",
    "bg": "Búlgaro",
    "hr": "Croata",
    "sk": "Eslovaco",
    "ta": "Tâmil",
    "en": "Inglês",
};

export default function TranslateModal({ isOpen, onClose, onTranslate, isProcessing, videoUrl, hasApiKey }) {
    const [targetLanguage, setTargetLanguage] = useState('es');

    if (!isOpen) return null;

    const handleSubmit = () => {
        console.log('[TranslateModal] handleSubmit called, targetLanguage:', targetLanguage);
        onTranslate({ targetLanguage });
    };

    return (
        <Modal
            isOpen={isOpen}
            onClose={isProcessing ? undefined : onClose}
            eyebrow="DUBLAGEM"
            title="Dublagem com IA"
            size="md"
            footer={
                <div className="flex gap-3">
                    <button
                        onClick={onClose}
                        disabled={isProcessing}
                        className="btn-ghost flex-1"
                    >
                        Cancelar
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={isProcessing || !hasApiKey}
                        className="btn-primary flex-1"
                    >
                        {isProcessing ? (
                            <>
                                <Loader2 size={16} className="animate-spin" />
                                Dublando...
                            </>
                        ) : (
                            <>
                                <Languages size={16} />
                                Dublar Voz
                            </>
                        )}
                    </button>
                </div>
            }
        >
            <div className="flex items-center gap-3 mb-5">
                <div className="w-10 h-10 rounded-input bg-surface-2 flex items-center justify-center shrink-0 border border-border">
                    <Languages size={18} className="text-accent" />
                </div>
                <p className="text-xs text-text-tertiary">Tradução e dublagem de voz por IA (ElevenLabs)</p>
            </div>

            {!hasApiKey && (
                <div className="mb-4 flex items-start gap-2">
                    <span className="badge-warn shrink-0"><AlertCircle size={12} /> Chave Ausente</span>
                    <p className="text-sm text-text-tertiary">Configure a chave de API da ElevenLabs nas Configurações primeiro.</p>
                </div>
            )}

            {/* Preview */}
            <div className="mb-5 rounded-lg overflow-hidden bg-black aspect-video border border-border">
                <video
                    src={videoUrl}
                    className="w-full h-full object-contain"
                    muted
                    playsInline
                />
            </div>

            {/* Language Selection */}
            <div className="mb-5">
                <label className="eyebrow block mb-2">
                    Idioma de Destino
                </label>
                <select
                    value={targetLanguage}
                    onChange={(e) => setTargetLanguage(e.target.value)}
                    className="input-field appearance-none cursor-pointer"
                    disabled={isProcessing}
                >
                    {Object.entries(LANGUAGES).sort((a, b) => a[1].localeCompare(b[1])).map(([code, name]) => (
                        <option key={code} value={code}>
                            {name}
                        </option>
                    ))}
                </select>
            </div>

            {/* Info */}
            <p className="text-xs text-text-tertiary leading-relaxed mb-2">
                O áudio será dublado com voz gerada por IA no idioma selecionado, mantendo as características do locutor original.
            </p>

            {/* AI Act art. 50 disclosure */}
            <p className="text-xs text-text-tertiary leading-relaxed mb-2">
                O arquivo dublado é sinalizado como conteúdo gerado por IA. Ao publicar, informe que a voz é sintética.
            </p>

            {/* Processing State */}
            {isProcessing && (
                <div className="mt-4 p-3 bg-surface-2 rounded-lg border border-border">
                    <div className="flex items-center gap-3">
                        <Loader2 size={18} className="text-accent animate-spin" />
                        <div>
                            <p className="text-sm text-text-primary font-medium">Dublando áudio...</p>
                            <p className="text-xs text-text-tertiary">Isso pode levar alguns minutos</p>
                        </div>
                    </div>
                </div>
            )}
        </Modal>
    );
}
