import React, { useState, useRef, useCallback } from 'react';
import { Trash2, AlertTriangle, Loader2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { apiJson } from '../lib/api';

// Mirrors cloud/account.DELETION_REASONS. A closed list rather than a text
// box, because the answer is stored in a record that outlives the account and
// free text is how personal data gets into one by accident.
const REASONS = [
  ['too_expensive', 'Muito caro'],
  ['not_using_it', 'Não estou usando'],
  ['clip_quality', 'A qualidade dos cortes não foi suficiente'],
  ['missing_feature', 'Falta um recurso que preciso'],
  ['found_alternative', 'Encontrei uma alternativa melhor'],
  ['privacy', 'Preocupações com privacidade'],
  ['other', 'Outro motivo'],
];

// GDPR Art. 17 erasure, self-service (backend: cloud/account.py). The privacy
// policy tells users they can delete their account from the dashboard, so this
// has to be findable — but it is also irreversible, hence: collapsed by
// default, an itemised list of what actually goes, and typing the account email
// as the confirmation step (there is no password to re-enter; sign-in is a
// magic link).
export default function DeleteAccountCard() {
  const { me, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // setBusy only disables the button on the next render, which a fast double
  // click beats. The server survives a duplicate call, but each one re-runs a
  // Stripe cancel and an R2 prefix delete for nothing.
  const sending = useRef(false);

  const email = me?.user?.email || '';
  // `!!email` matters: without it an account page rendered before /api/me
  // resolves would treat an empty box as a match and arm the delete button.
  const matches = !!email && confirm.trim().toLowerCase() === email.toLowerCase();

  const remove = useCallback(async () => {
    if (sending.current) return;
    sending.current = true;
    setBusy(true);
    setError('');
    try {
      await apiJson('/api/account', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm_email: confirm.trim(), reason: reason || undefined }),
      });
      // The session token now points at nothing. Drop it before navigating, or
      // the landing page spends a request discovering that for itself. The
      // funnel flags go too: they are the only reason a re-signup with the same
      // address would behave like a returning user rather than a fresh one.
      logout();
      try {
        localStorage.removeItem('os_socials_prompted');
        localStorage.removeItem('os_pending_checkout');
      } catch (_) { /* ignore */ }
      window.location.hash = '#/deleted';
      window.location.reload();
    } catch (e) {
      setError(e?.detail || 'Não foi possível excluir sua conta. Tente novamente ou entre em contato com o suporte.');
      sending.current = false;
      setBusy(false);
    }
  }, [confirm, reason, logout]);

  return (
    <div className="card p-6">
      <h3 className="font-display text-lg text-ink mb-1 flex items-center gap-2">
        <Trash2 size={16} className="text-danger" /> Excluir conta
      </h3>
      <p className="text-muted text-sm">
        Encerre sua conta do MasterShorts e apague todos os seus dados. Esta
        ação não pode ser desfeita.
      </p>

      {!open ? (
        <button onClick={() => setOpen(true)} className="btn-danger px-4 py-2 mt-4">
          <Trash2 size={16} /> Excluir minha conta
        </button>
      ) : (
        <div className="mt-4 space-y-4">
          <div className="rounded-card border border-danger/40 bg-danger/5 p-3 text-sm text-ink2">
            <p className="flex items-start gap-2 text-ink">
              <AlertTriangle size={16} className="text-danger shrink-0 mt-0.5" />
              <b>Isto é permanente. Não há recuperação.</b>
            </p>
            <p className="mt-2">Excluído imediatamente:</p>
            <ul className="list-disc pl-5 mt-1 space-y-0.5">
              <li>sua conta e dados de login</li>
              <li>todos os projetos, cortes e transcrições armazenados</li>
              <li>suas chaves de API, interrompendo automações ativas</li>
              <li>a conexão com qualquer rede social vinculada</li>
            </ul>
            <p className="mt-2">
              Qualquer assinatura ativa será cancelada como parte desta operação.
            </p>
          </div>

          <label className="block">
            <span className="text-sm text-muted">Por que você está saindo? (opcional)</span>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="input-field w-full text-sm mt-1"
            >
              <option value="">Prefiro não informar</option>
              {REASONS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm text-muted">
              Digite <b className="text-ink">{email}</b> para confirmar
            </span>
            <input
              value={confirm}
              onChange={(e) => { setConfirm(e.target.value); setError(''); }}
              autoComplete="off"
              spellCheck={false}
              className="input-field w-full text-sm mt-1"
            />
          </label>

          {error && <p className="text-sm text-danger">{error}</p>}

          <div className="flex items-center gap-2">
            <button onClick={remove} disabled={!matches || busy} className="btn-danger px-4 py-2">
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
              {busy ? 'Excluindo…' : 'Excluir definitivamente minha conta'}
            </button>
            <button onClick={() => { setOpen(false); setConfirm(''); setError(''); }}
                    disabled={busy} className="btn-quiet">
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
