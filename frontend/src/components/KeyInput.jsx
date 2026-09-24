import React, { useState, useEffect } from 'react';
import { Key, Eye, EyeOff, Check, ExternalLink, Loader2, AlertCircle, Sparkles } from 'lucide-react';

export default function KeyInput({ onKeySet, savedKey }) {
    const [key, setKey] = useState(savedKey || '');
    const [isVisible, setIsVisible] = useState(false);
    const [isSaved, setIsSaved] = useState(!!savedKey);
    const [testStatus, setTestStatus] = useState(null); // null | 'testing' | 'ok' | 'error'
    const [testMessage, setTestMessage] = useState('');

    useEffect(() => {
        if (savedKey) setKey(savedKey);
    }, [savedKey]);

    const handleSave = () => {
        if (key.trim().length > 0) {
            onKeySet(key.trim());
            setIsSaved(true);
            setTimeout(() => setIsSaved(false), 2500);
        }
    };

    const handleTest = async () => {
        if (!key.trim()) return;
        setTestStatus('testing');
        setTestMessage('');
        try {
            const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${key.trim()}`);
            if (res.ok) {
                setTestStatus('ok');
                setTestMessage('Chave válida e autenticada com sucesso no Google AI Studio!');
            } else {
                setTestStatus('error');
                setTestMessage(`HTTP ${res.status}: Chave inválida ou limites de cota excedidos.`);
            }
        } catch {
            setTestStatus('error');
            setTestMessage('Erro de conexão ou rede ao consultar os servidores da Google.');
        }
    };

    return (
        <div className="card p-5 sm:p-6 border border-rule/80 bg-paper2/90 shadow-card rounded-panel backdrop-blur-sm animate-fade space-y-5">
            {/* Standardized Card Header */}
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="flex items-start gap-3 min-w-0">
                    <div className="p-2.5 bg-paper3 rounded-xl text-brass shrink-0 mt-0.5 border border-rule">
                        <Key size={18} />
                    </div>
                    <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                            <h2 className="text-base sm:text-lg font-semibold text-ink">Google Gemini API</h2>
                            <span className="badge-ok text-[10px] uppercase font-semibold">Recomendado</span>
                        </div>
                        <p className="text-xs text-muted mt-1 leading-relaxed">
                            Provedor nativo para análise semântica, corte automático e transcrição com alta velocidade e gratuidade.
                        </p>
                    </div>
                </div>
                <a
                    href="https://aistudio.google.com/app/apikey"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-brass hover:underline flex items-center gap-1 shrink-0 self-start sm:self-auto font-medium"
                >
                    <span>Criar chave gratuita</span>
                    <ExternalLink size={12} />
                </a>
            </div>

            {/* Field */}
            <div className="space-y-1.5">
                <label className="block text-xs font-medium text-ink">
                    Chave de API Gemini <span className="text-brass">*</span>
                </label>
                <div className="relative">
                    <input
                        type={isVisible ? 'text' : 'password'}
                        value={key}
                        onChange={(e) => {
                            setKey(e.target.value);
                            setIsSaved(false);
                            setTestStatus(null);
                        }}
                        placeholder="AIzaSy..."
                        className="input-field font-mono text-xs w-full pr-10 h-10"
                    />
                    <button
                        type="button"
                        onClick={() => setIsVisible(!isVisible)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink transition-colors p-1"
                    >
                        {isVisible ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                </div>
                <p className="text-[11px] text-muted">
                    Sua chave é armazenada de forma segura exclusivamente no armazenamento local do seu navegador.
                </p>
            </div>

            {/* Test Status Feedback */}
            {testStatus && (
                <div
                    className={`px-3.5 py-2.5 rounded-lg text-xs flex items-center gap-2 animate-fade ${
                        testStatus === 'ok'
                            ? 'bg-ok/10 text-ok border border-ok/30'
                            : 'bg-danger/10 text-danger border border-danger/30'
                    }`}
                >
                    {testStatus === 'ok' ? <Check size={14} className="shrink-0" /> : <AlertCircle size={14} className="shrink-0" />}
                    <span>{testMessage}</span>
                </div>
            )}

            {/* Standardized Bottom Action Bar */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-3 border-t border-rule">
                <button
                    type="button"
                    onClick={handleTest}
                    disabled={!key.trim() || testStatus === 'testing'}
                    className="btn-secondary py-2 px-3.5 text-xs flex items-center justify-center gap-1.5 w-full sm:w-auto"
                >
                    {testStatus === 'testing' ? (
                        <><Loader2 size={13} className="animate-spin text-brass" /> Testando Chave…</>
                    ) : (
                        'Testar Chave'
                    )}
                </button>

                <button
                    type="button"
                    onClick={handleSave}
                    disabled={!key.trim()}
                    className={isSaved ? 'badge-ok px-4 py-2 text-xs flex items-center justify-center gap-1.5 cursor-default w-full sm:w-auto' : 'btn-primary py-2 px-4 text-xs flex items-center justify-center w-full sm:w-auto'}
                >
                    {isSaved ? <><Check size={14} /> Chave Salva</> : 'Salvar Configuração'}
                </button>
            </div>
        </div>
    );
}
