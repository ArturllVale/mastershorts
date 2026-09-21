import React, { useState, useEffect } from 'react';
import { Loader2, Check, Zap, Clock } from 'lucide-react';
import { apiJson } from '../lib/api';
import { track } from '../lib/analytics';
import Modal from './ui/Modal';

// Opens when a job hits a 402 (quota exceeded). This is the highest-intent
// moment in the product — the user WANTS to clip a video and can't — so it
// sells the subscription first (recurring value: minutes, no watermark,
// permanent clips) and keeps one-time top-ups as a secondary escape hatch.
//
// Conversion techniques used (all honest — no fake scarcity or countdowns):
// - Goal-gradient: copy centers on finishing THIS video, not abstract quota.
// - Compromise effect: all three tiers shown, creator highlighted in the
//   middle — starter floors the price, pro anchors it, creator reads as the
//   sensible pick (and matches the pricing page's "most popular").
// - Outcome framing: every line says what the user GETS (clips ready to post,
//   a library that stays), with the free-plan fact stated second. The earlier
//   copy led with what free costs them, which reads as "pay to undo the
//   restrictions we added" — the losing side of an argument against our own
//   MIT repo, whose headline is literally "no watermarks, no limits".
// - Risk reversal: "cancel anytime" on the CTA.
//
// Deliberately NOT sold here: GPU rendering and the included Gemini key. Both
// are real and both are why the cloud beats self-hosting, but the free plan
// already gets them (the pricing page says "Same GPU rendering" on the free
// tier) — so they belong on the landing/pricing surface facing repo visitors,
// not in a modal shown to someone who is already using them.
const PLAN_BLURBS = {
  starter: 'Para quem está começando',
  creator: 'Para postagens diárias',
  pro: 'Para criadores profissionais',
};

// context: 'wall' (default) = user hit the 402 quota wall mid-task.
//          'upsell' = user opened it voluntarily (results banner, header meter)
//          — different framing: they still HAVE minutes, sell the watermark
//          removal + permanence instead of "you ran out".
// partialMinutes / onPartial: the server's offer to clip only the first N
// minutes of the blocked video on the minutes the user has (see
// app.partial_offer). Most walls open on an account that has not spent a
// single free minute and pasted a 21-90 min video (93 of 99 sampled,
// 16-sep-2026): they are being asked to pay before seeing one clip. The offer
// turns that wall into a first run; the plans stay the way to the whole video.
export default function TopUpModal({ onClose, required, remaining, partialMinutes = 0, onPartial = null,
                                     context = 'wall' }) {
  const [plans, setPlans] = useState([]);
  const [topups, setTopups] = useState([]);
  const [showTopups, setShowTopups] = useState(false);
  const [busyPrice, setBusyPrice] = useState(null);
  const isUpsell = context === 'upsell';

  useEffect(() => {
    track(isUpsell ? 'UpsellModalSeen' : 'QuotaWallSeen',
          { props: { required: required ?? null, remaining: remaining ?? null } });
    apiJson('/api/billing/plans')
      .then((d) => {
        const monthly = (d.plans || []).filter((p) => p.interval === 'month');
        setPlans(['starter', 'creator', 'pro']
          .map((name) => monthly.find((p) => p.plan === name))
          .filter(Boolean));
        setTopups(d.topups || []);
      })
      .catch(() => {});
    // Plans are fetched once per open; the props only shape the copy.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Instrumented in three steps on purpose. Between 25-jul and 1-ago the modals
  // logged 35 checkout clicks and Stripe recorded ONE new subscription, and
  // nothing in between was measured — this modal fired only its own
  // *ModalCheckout event, so "clicked but never reached Stripe" and "reached
  // Stripe and abandoned" were indistinguishable. CheckoutStarted (click, same
  // meaning as PricingSection's) → CheckoutRedirected (we hold a Stripe URL) →
  // CheckoutFailed (we don't) separates them.
  const source = isUpsell ? 'upsell' : 'wall';

  const buy = async (entry, kind) => {
    setBusyPrice(entry.price_id);
    const props = { kind, plan: entry.plan || null, minutes: entry.minutes, source };
    track(isUpsell ? 'UpsellModalCheckout' : 'QuotaWallCheckout', { props });
    track('CheckoutStarted', { props });
    // Same stash PricingSection sets, so a plan bought from the modal also
    // carries its price into the Subscribed goal (AccountPage reads it back).
    // Top-ups deliberately don't set it — they never count as a subscription.
    if (kind === 'subscription') {
      try {
        localStorage.setItem('os_pending_checkout', JSON.stringify({
          plan: entry.plan, interval: entry.interval, amount: entry.amount,
          currency: entry.currency,
        }));
      } catch (_) { /* ignore storage errors */ }
    }
    try {
      const { url } = await apiJson('/api/billing/checkout', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ price_id: entry.price_id }),
      });
      track('CheckoutRedirected', { props });
      window.location.href = url;
    } catch (e) {
      track('CheckoutFailed', { props: { ...props, reason: String(e?.detail || e?.message || 'unknown').slice(0, 120) } });
      setBusyPrice(null);
      alert(e?.detail || 'Não foi possível iniciar o checkout.');
    }
  };

  const fmt = (a, c) => new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: (c || 'BRL').toUpperCase(), maximumFractionDigits: 0,
  }).format((a || 0) / 100);

  const blockedByLength = typeof required === 'number' && typeof remaining === 'number';
  const partialOffer = !isUpsell && partialMinutes > 0 && typeof onPartial === 'function';
  const remainingShown = Math.max(0, Math.round((remaining || 0) * 10) / 10);

  return (
    <Modal isOpen onClose={onClose} eyebrow="UPGRADE"
           title={isUpsell ? 'Mantenha seus cortes para sempre' : 'Seu vídeo está pronto para corte'} size="xl">
      {/* Goal-gradient framing: they're one step from the thing they came for. */}
      <p className="text-muted text-sm mb-5">
        {isUpsell
          ? <>Cada corte sai <b className="text-ink font-medium">pronto para postar</b> e fica salvo na sua biblioteca para sempre. No plano gratuito, os cortes possuem marca d'água e são apagados após 7 dias.</>
          : blockedByLength
            ? <>Este vídeo tem <b className="text-ink font-medium">{required} min</b> de duração e você tem{' '}
                <b className="text-ink font-medium">{remainingShown} min</b> este mês. Escolha um plano para renderizar o vídeo completo imediatamente.</>
            : <>Você utilizou seus minutos gratuitos deste mês. Escolha um plano e continue cortando agora mesmo.</>}
      </p>

      {partialOffer && (
        <div className="mb-5 card p-4 flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex-1 text-sm text-ink2">
            <b className="text-ink font-medium">Ou veja o resultado primeiro:</b> corte os primeiros{' '}
            <b className="text-ink font-medium">{partialMinutes} min</b> agora com os minutos disponíveis,
            e decida com os cortes em mãos.
          </div>
          <button onClick={onPartial} disabled={busyPrice !== null}
                  className="btn-ghost whitespace-nowrap">
            Cortar os primeiros {partialMinutes} min
          </button>
        </div>
      )}

      <div className="grid sm:grid-cols-3 gap-3">
        {plans.map((entry) => {
          const highlight = entry.plan === 'creator';
          return (
            <div key={entry.price_id}
                 className={`relative card p-5 flex flex-col ${highlight ? 'border-brass' : ''}`}>
              {highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 badge-float">
                  Mais popular
                </span>
              )}
              <h3 className="font-display text-lg text-ink capitalize">{entry.plan}</h3>
              <p className="text-muted text-xs mb-3">{PLAN_BLURBS[entry.plan] || ''}</p>
              <div className="mb-3 flex items-baseline gap-1.5">
                <span className="font-display text-3xl text-ink tabular-nums">{fmt(entry.amount, entry.currency)}</span>
                <span className="readout">/mês</span>
              </div>
              <ul className="space-y-1.5 text-sm text-ink2 mb-4 flex-1">
                <li className="flex items-start gap-2">
                  <Check size={15} className="text-ok shrink-0 mt-0.5" />
                  <span><b>{entry.minutes} min</b> todo mês ({Math.round(entry.minutes / 20)}× sua cota gratuita)</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check size={15} className="text-ok shrink-0 mt-0.5" />
                  <span>Cortes <b>prontos para postar</b>, sem marca d'água</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check size={15} className="text-ok shrink-0 mt-0.5" />
                  <span>Sua biblioteca <b>permanente</b> (cortes gratuitos expiram em 7 dias)</span>
                </li>
                <li className="flex items-start gap-2">
                  <Zap size={15} className="text-brass shrink-0 mt-0.5" />
                  <span>Sem fila de espera</span>
                </li>
              </ul>
              <button onClick={() => buy(entry, 'subscription')} disabled={busyPrice !== null}
                      className={`w-full ${highlight ? 'btn-primary' : 'btn-ghost'}`}>
                {busyPrice === entry.price_id
                  ? <Loader2 size={18} className="animate-spin" />
                  : `Assinar ${entry.plan.charAt(0).toUpperCase() + entry.plan.slice(1)}`}
              </button>
              <p className="text-center text-xs text-muted mt-2">Cancele quando quiser.</p>
            </div>
          );
        })}
        {plans.length === 0 && (
          <div className="sm:col-span-3 flex justify-center py-8">
            <Loader2 className="animate-spin text-brass" />
          </div>
        )}
      </div>

      {/* Secondary escape hatch: one-time packs, deliberately de-emphasized. */}
      <div className="mt-4 text-center">
        {!showTopups ? (
          <button onClick={() => setShowTopups(true)}
                  className="text-xs text-muted underline underline-offset-2 hover:text-ink2 transition-colors">
            Precisa apenas de alguns minutos extras? Pacotes avulsos
          </button>
        ) : (
          <div className="grid grid-cols-2 gap-3 mt-2">
            {topups.map((t) => (
              <button key={t.price_id} onClick={() => buy(t, 'topup')} disabled={busyPrice !== null}
                      className="border border-rule hover:border-brass rounded-card p-3 text-left transition-colors disabled:opacity-50">
                <div className="text-ink text-sm font-medium flex items-center gap-1.5">
                  <Clock size={14} className="text-muted" />+{t.minutes} min
                </div>
                <div className="readout mt-0.5">{fmt(t.amount, t.currency)} · pagamento único</div>
              </button>
            ))}
            {topups.length === 0 && (
              <div className="col-span-2 flex justify-center py-3">
                <Loader2 className="animate-spin text-brass" size={18} />
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
