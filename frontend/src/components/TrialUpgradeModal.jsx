import React, { useState, useEffect } from 'react';
import { Loader2, Rocket, CheckCircle2 } from 'lucide-react';
import { apiJson } from '../lib/api';
import Modal from './ui/Modal';

// Shown when a TRIALING user hits the trial minute cap. Lets them end the trial
// and activate the paid plan right away (charges the card now, unlocks the full
// monthly minutes). The subscription webhook flips status→active server-side.
export default function TrialUpgradeModal({ plan, onActivated, onClose }) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const [planMinutes, setPlanMinutes] = useState(null);

  // Look up the full monthly minutes for the current plan (to show what unlocks).
  useEffect(() => {
    apiJson('/api/billing/plans')
      .then((d) => {
        const match = (d.plans || []).find((p) => p.plan === plan && p.interval === 'month');
        if (match) setPlanMinutes(match.minutes);
      })
      .catch(() => {});
  }, [plan]);

  const activate = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await apiJson('/api/billing/end-trial', { method: 'POST' });
      // Poll /api/me until the webhook flips the subscription to active.
      let ok = res?.status === 'active';
      for (let i = 0; i < 10 && !ok; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const me = await onActivated();
        ok = me?.status === 'active';
      }
      if (ok) {
        setDone(true);
        setTimeout(onClose, 1800);
      } else {
        // Charge is processing (or card needs attention) — let them proceed anyway.
        await onActivated();
        setError('Quase lá — seu plano está sendo ativado. Se não liberar em um instante, verifique seus dados de cobrança.');
      }
    } catch (e) {
      setError('Não foi possível ativar seu plano. Tente novamente ou gerencie a cobrança na sua conta.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal isOpen onClose={onClose} eyebrow="TESTE GRATUITO" size="md">
      {done ? (
        <div className="text-center py-4">
          <div className="inline-flex p-3 bg-paper3 rounded-full text-ok mb-4"><CheckCircle2 size={24} /></div>
          <h2 className="font-display text-xl text-ink mb-1">Tudo pronto!</h2>
          <p className="text-muted text-sm">Seu plano está ativo{planMinutes ? ` com ${planMinutes} minutos` : ''}. Prossiga para gerar seus cortes.</p>
        </div>
      ) : (
        <>
          <div className="inline-flex p-3 bg-paper3 rounded-full text-brass mb-4"><Rocket size={24} /></div>
          <h2 className="font-display text-xl text-ink mb-1">Você utilizou seus minutos de teste</h2>
          <p className="text-muted text-sm mb-6">
            Ative seu plano{plan ? <> <span className="capitalize font-medium text-ink">{plan}</span></> : ''} agora para desbloquear{' '}
            {planMinutes ? <><b className="text-ink font-medium">{planMinutes} minutos</b> todo mês</> : 'seus minutos mensais completos'} e continuar criando.
          </p>

          {error && <p className="text-warn text-xs mb-4">{error}</p>}

          <button
            onClick={activate}
            disabled={busy}
            className="btn-primary w-full"
          >
            {busy ? <><Loader2 size={18} className="animate-spin" /> Ativando…</> : <>Ativar meu plano agora</>}
          </button>
          <button
            onClick={onClose}
            disabled={busy}
            className="w-full mt-2 text-muted hover:text-ink text-sm py-2 disabled:opacity-60 transition-colors"
          >
            Talvez mais tarde
          </button>
        </>
      )}
    </Modal>
  );
}
