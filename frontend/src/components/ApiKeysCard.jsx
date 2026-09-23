import React, { useState, useEffect, useCallback } from 'react';
import { KeyRound, Plus, Trash2, Copy, Check, Loader2 } from 'lucide-react';
import { apiJson } from '../lib/api';

// API keys for programmatic access (scripts, automations, n8n). The raw key is
// returned exactly once by POST /api/keys, so it is surfaced in a one-time
// banner the user must copy before it disappears.
export default function ApiKeysCard() {
  const [keys, setKeys] = useState(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [freshKey, setFreshKey] = useState(null); // { key, name } shown once
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    apiJson('/api/keys').then((d) => setKeys(d.keys || [])).catch(() => setKeys([]));
  }, []);
  useEffect(() => { load(); }, [load]);

  const createKey = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiJson('/api/keys', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() || undefined }),
      });
      setFreshKey(d);
      setCopied(false);
      setName('');
      load();
    } catch (e) { alert(e?.detail || 'Não foi possível criar a chave.'); }
    setBusy(false);
  }, [name, load]);

  const revoke = useCallback(async (k) => {
    if (!window.confirm(`Revogar "${k.name}"? Qualquer aplicativo usando esta chave parará de funcionar imediatamente.`)) return;
    try {
      await apiJson(`/api/keys/${k.id}`, { method: 'DELETE' });
      load();
    } catch (e) { alert(e?.detail || 'Não foi possível revogar a chave.'); }
  }, [load]);

  const copyKey = useCallback(() => {
    navigator.clipboard?.writeText(freshKey.key).then(() => setCopied(true)).catch(() => {});
  }, [freshKey]);

  const active = (keys || []).filter((k) => !k.revoked);

  return (
    <div className="card p-6">
      <h3 className="font-display text-lg text-text-primary mb-1 flex items-center gap-2">
        <KeyRound size={16} className="text-accent" /> Chaves de API
      </h3>
      <p className="text-text-secondary text-sm mb-4 leading-relaxed">
        Chaves para clientes CLI, scripts e API REST. Aplicativos conectados através de Claude ou ChatGPT
        também aparecem aqui. Revogar uma chave desconecta o app imediatamente.
      </p>

      {freshKey && (
        <div className="mb-4 rounded-lg border border-accent/40 bg-accent/5 p-3.5 text-sm">
          <p className="text-text-primary mb-2">
            <b>Copie sua nova chave agora.</b> Por motivos de segurança ela não será exibida novamente.
          </p>
          <div className="flex items-center gap-2">
            <code className="font-mono text-xs text-accent bg-surface-1 px-2.5 py-1.5 rounded border border-border flex-1 break-all select-all">{freshKey.key}</code>
            <button onClick={copyKey} className="btn-ghost px-3 py-1.5 shrink-0 text-xs">
              {copied ? <Check size={14} className="text-success" /> : <Copy size={14} />} {copied ? 'Copiado' : 'Copiar'}
            </button>
          </div>
        </div>
      )}

      {keys === null ? (
        <div className="flex justify-center py-4"><Loader2 className="animate-spin text-accent" size={18} /></div>
      ) : (
        <>
          {active.length > 0 && (
            <div className="space-y-2 mb-4">
              {active.map((k) => (
                <div key={k.id} className="flex items-center justify-between gap-3 border border-border bg-surface-2/30 rounded-lg px-3 py-2 text-sm">
                  <div className="min-w-0">
                    <span className="text-text-primary font-medium">{k.name || 'Chave Sem Nome'}</span>{' '}
                    <code className="font-mono text-xs text-text-tertiary ml-2">{k.prefix}…</code>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="font-mono text-xs text-text-tertiary">
                      {k.last_used_at ? `Usada em ${new Date(k.last_used_at).toLocaleDateString()}` : 'Nunca usada'}
                    </span>
                    <button onClick={() => revoke(k)} title="Revogar chave"
                            className="text-text-tertiary hover:text-danger transition-colors p-1">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') createKey(); }}
              placeholder="Nome da chave (ex: n8n, claude)"
              className="input-field flex-1 text-sm"
              maxLength={60}
            />
            <button onClick={createKey} disabled={busy} className="btn-ghost px-4 py-2 shrink-0 text-xs">
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />} Criar Chave
            </button>
          </div>
        </>
      )}
    </div>
  );
}
