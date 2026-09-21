import React, { useState, useEffect, useCallback } from 'react';
import { Loader2, CreditCard, LogOut, Plus } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { apiJson } from '../lib/api';
import { track } from '../lib/analytics';
import ApiKeysCard from './ApiKeysCard';
import DeleteAccountCard from './DeleteAccountCard';
import InvoicesCard from './InvoicesCard';

const fmt1 = (n) => Math.round((n || 0) * 10) / 10;

// Mirrors cloud/config.BILLING_ATTENTION_STATES: states where the customer has
// to do something (fix a card, finish a payment) before minutes come back.
const PAYMENT_ISSUE_STATES = ['past_due', 'unpaid', 'incomplete', 'paused'];

// Account/billing page: plan, usage meter, top-ups, manage billing, logout.
export default function AccountPage() {
  const { me, refreshMe, logout, plan, minutes } = useAuth();
  const [busy, setBusy] = useState(false);
  const [topups, setTopups] = useState([]);
  const [activating, setActivating] = useState(false);

  // After returning from Checkout the webhook may lag — poll /api/me briefly.
  useEffect(() => {
    const hash = window.location.hash || '';
    if (!hash.includes('checkout=success')) return;
    setActivating(true);
    let tries = 0;
    const t = setInterval(async () => {
      tries += 1;
      const data = await refreshMe();
      // 'free' is the default plan for any signed-in account, so it does NOT
      // mean the checkout landed — keep polling until the webhook writes the
      // paid subscription.
      const paidPlan = data?.plan && data.plan !== 'free';
      if (paidPlan || tries > 15) {
        clearInterval(t);
        setActivating(false);
        // Fire the Subscribed conversion goal. A pending-checkout stash (set in
        // PricingSection) carries the plan price, so we can attach real revenue;
        // top-ups don't set it, so they never count as a subscription.
        if (paidPlan) {
          let pending = null;
          try { pending = JSON.parse(localStorage.getItem('os_pending_checkout') || 'null'); } catch (_) { /* ignore */ }
          if (pending) {
            // This Plausible is Community Edition, which has no revenue goals —
            // so the price rides along as plain props (value_usd / plan) that CE
            // can break the goal down by. The exact MRR still lives in Stripe.
            track('Subscribed', {
              props: {
                plan: pending.plan,
                interval: pending.interval,
                value_usd: Math.round((pending.amount || 0) / 100),
              },
            });
            try { localStorage.removeItem('os_pending_checkout'); } catch (_) { /* ignore */ }
          }
        }
                window.location.hash = '#/account';
      }
    }, 2000);
    return () => clearInterval(t);
  }, [refreshMe]);

  useEffect(() => {
    apiJson('/api/billing/plans').then((d) => setTopups(d.topups || [])).catch(() => {});
  }, []);

  const openPortal = useCallback(async () => {
    setBusy(true);
    try {
      const { url } = await apiJson('/api/billing/portal', { method: 'POST' });
      window.location.href = url;
    } catch (e) { setBusy(false); alert('Não foi possível abrir o portal de cobrança.'); }
  }, []);

  const buyTopup = useCallback(async (price_id) => {
    setBusy(true);
    try {
      const { url } = await apiJson('/api/billing/checkout', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ price_id }),
      });
      window.location.href = url;
    } catch (e) { setBusy(false); alert(e?.detail || 'Não foi possível iniciar o checkout.'); }
  }, []);

  if (!me) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-brass" /></div>;

  const m = minutes || {};
  const total = (m.plan_allowance || 0) + (m.topup_remaining || 0) + (m.plan_used || 0);
  const usedPct = total > 0 ? Math.min(100, ((m.plan_used || 0) / (m.plan_allowance || 1)) * 100) : 0;
  const low = total > 0 && (m.remaining || 0) <= total * 0.2;

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="eyebrow mb-1.5">MINHA CONTA</p>
          <h2 className="font-display text-2xl text-text-primary leading-tight tracking-tight">Sua Conta</h2>
          <p className="text-text-tertiary text-sm mt-1">{me.user?.email}</p>
        </div>
        <button onClick={logout} className="btn-quiet shrink-0">
          <LogOut size={16} /> Sair
        </button>
      </div>

      {activating && (
        <div className="card px-4 py-3 text-sm text-text-secondary flex items-center gap-2">
          <Loader2 size={16} className="animate-spin text-accent" /> Ativando seu plano…
        </div>
      )}

      <div className="card p-6">
        <div className="flex items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-text-primary font-medium capitalize">{plan ? `Plano ${plan}` : 'Nenhum plano ativo'}</span>
            {me.status && me.status !== 'active'
              && !PAYMENT_ISSUE_STATES.includes(me.status) && (
              <span className="badge-warn">{me.status}</span>
            )}
            {me.cancel_at_period_end && (
              <span className="badge-warn">Cancela no fim do período</span>
            )}
          </div>
          {me.has_billing_account ? (
            <button onClick={openPortal} disabled={busy} className="btn-ghost px-4 py-2 shrink-0">
              <CreditCard size={16} /> Gerenciar cobrança
            </button>
          ) : (
            <button onClick={() => { window.location.hash = '#/pricing'; }} className="btn-primary px-4 py-2 shrink-0 text-xs">
              Fazer Upgrade
            </button>
          )}
        </div>

        {PAYMENT_ISSUE_STATES.includes(me.status) && (
          <div className="mb-4 rounded-lg border border-warn/40 bg-warn/5 p-3 text-sm text-text-secondary">
            <b className="text-text-primary">Não conseguimos cobrar seu cartão.</b>{' '}
            {me.status === 'incomplete'
              ? 'Seu pagamento não foi concluído, logo o plano não foi iniciado.'
              : 'Seu plano está pausado e você está em minutos gratuitos até que seja processado.'}{' '}
            <button onClick={openPortal} disabled={busy}
                    className="underline underline-offset-2 hover:text-text-primary">
              Atualize seu cartão
            </button>{' '}
            para reativar imediatamente.
          </div>
        )}

        <div className="space-y-2.5">
          <div className="flex justify-between text-sm">
            <span className="text-text-tertiary">Minutos do plano</span>
            <span className="text-text-secondary font-mono text-xs">{fmt1(m.plan_used)} / {fmt1(m.plan_allowance)} usados</span>
          </div>
          <div className="h-2 bg-surface-2 rounded-full overflow-hidden border border-border/40">
            <div className={`h-full transition-all rounded-full ${low ? 'bg-warn' : 'bg-accent'}`} style={{ width: `${usedPct}%` }} />
          </div>
          <div className="flex justify-between text-sm pt-1">
            <span className="text-text-tertiary">Minutos avulsos</span>
            <span className="text-text-secondary font-mono text-xs">{fmt1(m.topup_remaining)} restantes</span>
          </div>
          <div className="flex justify-between text-sm pt-2.5 border-t border-border">
            <span className="text-text-primary font-medium">Total restante</span>
            <span className="text-accent font-semibold font-mono">{fmt1(m.remaining)} min</span>
          </div>
        </div>
      </div>

      {/* Only accounts that ever had a Stripe relationship can have invoices. */}
      {me.has_billing_account && <InvoicesCard />}

      {topups.length > 0 && (
        <div className="card p-6">
          <h3 className="font-display text-lg text-text-primary mb-1 flex items-center gap-2"><Plus size={16} className="text-accent" /> Comprar Mais Minutos</h3>
          <p className="text-text-tertiary text-sm mb-4">Minutos avulsos nunca expiram enquanto seu plano estiver ativo.</p>
          <div className="grid grid-cols-2 gap-3">
            {topups.map((t) => (
              <button key={t.price_id} onClick={() => buyTopup(t.price_id)} disabled={busy}
                className="border border-border hover:border-accent rounded-lg p-4 text-left transition-all bg-surface-2/40 hover:bg-surface-2 disabled:opacity-50">
                <div className="text-text-primary font-medium">+{t.minutes} min</div>
                <div className="font-mono text-xs text-text-tertiary mt-1">
                  {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: (t.currency || 'BRL').toUpperCase(), maximumFractionDigits: 0 }).format((t.amount || 0) / 100)}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      <ApiKeysCard />

      <DeleteAccountCard />
    </div>
  );
}
