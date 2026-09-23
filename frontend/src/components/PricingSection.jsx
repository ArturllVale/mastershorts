import React, { useState, useEffect } from 'react';
import { Check, Loader2, Zap, Cpu, KeyRound, Send, HardDrive, Bot } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { apiJson } from '../lib/api';
import { track } from '../lib/analytics';
import SegmentedControl from './ui/SegmentedControl';

const PLAN_ORDER = ['starter', 'creator', 'pro'];
const PLAN_BLURB = {
  starter: 'Para quem está começando',
  creator: 'Para criadores frequentes',
  pro: 'Para usuários avançados e equipes',
};
const HIGHLIGHT = 'creator';
const FREE_MINUTES = 20;


const fmt = (amount, currency) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: (currency || 'BRL').toUpperCase(), maximumFractionDigits: 0 }).format((amount || 0) / 100);

// Free tier + 3 paid tiers with monthly/annual toggle. Checkout requires sign-in.
export default function PricingSection({ onRequireLogin }) {
  const { isSignedIn } = useAuth();
  const [plans, setPlans] = useState([]);
  const [interval, setInterval] = useState('month');
  const [loading, setLoading] = useState(true);
  const [busyPrice, setBusyPrice] = useState(null);

  useEffect(() => {
    apiJson('/api/billing/plans')
      .then((d) => setPlans(d.plans || []))
      .catch(() => setPlans([]))
      .finally(() => setLoading(false));
  }, []);

  const checkout = async (entry) => {
    if (!isSignedIn) { onRequireLogin?.(entry.price_id); return; }
    setBusyPrice(entry.price_id);
    // `source` segments this surface from the two modals (see TopUpModal), which
    // now emit the same three events.
    const props = { plan: entry.plan, interval: entry.interval, source: 'pricing' };
    track('CheckoutStarted', { props });
    // Stash the price so we can attach real revenue to the Subscribed goal when
    // the user returns from Stripe (see AccountPage's checkout=success handler).
    try {
      localStorage.setItem('os_pending_checkout', JSON.stringify({
        plan: entry.plan, interval: entry.interval, amount: entry.amount, currency: entry.currency,
      }));
    } catch (_) { /* ignore storage errors */ }
    try {
      const { url } = await apiJson('/api/billing/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ price_id: entry.price_id }),
      });
      track('CheckoutRedirected', { props });
      window.location.href = url;
    } catch (e) {
      track('CheckoutFailed', { props: { ...props, reason: String(e?.detail || e?.message || 'unknown').slice(0, 120) } });
      setBusyPrice(null);
      alert(e?.detail || 'Não foi possível iniciar o checkout. Tente novamente.');
    }
  };

  if (loading) {
    return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-brass" /></div>;
  }

  const byPlan = (plan) => plans.find((p) => p.plan === plan && p.interval === interval);

  return (
    <div className="max-w-5xl mx-auto">
      <div className="max-w-xs mx-auto mb-10">
        <SegmentedControl
          size="sm"
          value={interval}
          onChange={setInterval}
          options={[
            { value: 'month', label: 'Mensal' },
            { value: 'year', label: 'Anual', hint: '2 meses grátis' },
          ]}
        />
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Free tier — no card, Google sign-in only */}
        <div className="relative card p-6 flex flex-col">
          <h3 className="font-display text-xl text-text-primary capitalize">Gratuito</h3>
          <p className="text-text-secondary text-sm mb-4">Experimente em seus próprios vídeos</p>
          <div className="mb-4 flex items-baseline gap-1.5">
            <span className="font-display text-4xl text-text-primary tabular-nums">R$ 0</span>
            <span className="font-mono text-xs text-text-tertiary">/mês</span>
          </div>
          <ul className="space-y-2.5 text-sm text-text-secondary mb-6 flex-1">
            <li className="flex items-start gap-2"><Check size={16} className="text-success shrink-0 mt-0.5" /> <span><b>{FREE_MINUTES} min</b> de vídeo / mês</span></li>
            <li className="flex items-start gap-2"><Check size={16} className="text-success shrink-0 mt-0.5" /> <span>URL do YouTube ou envio de arquivo</span></li>
            <li className="flex items-start gap-2"><Cpu size={16} className="text-success shrink-0 mt-0.5" /> <span>Processamento em <b>GPU acelerada</b> (~50s por vídeo de 8 min)</span></li>
            <li className="flex items-start gap-2"><KeyRound size={16} className="text-success shrink-0 mt-0.5" /> <span>Chave Gemini inclusa, sem configuração</span></li>
            <li className="flex items-start gap-2"><Check size={16} className="text-success shrink-0 mt-0.5" /> <span>Sem cartão de crédito — login Google</span></li>
            <li className="flex items-start gap-2"><Check size={16} className="text-text-tertiary shrink-0 mt-0.5" /> <span className="text-text-tertiary">Marca d'água · cortes mantidos por 7 dias</span></li>
          </ul>
          <button
            onClick={() => { if (!isSignedIn) { onRequireLogin?.(null); } else { window.location.hash = ''; } }}
            className="w-full btn-ghost"
          >
            Começar Grátis
          </button>
          <p className="text-center text-xs text-text-tertiary mt-2">Minutos gratuitos renovam a cada mês.</p>
        </div>

        {PLAN_ORDER.map((plan) => {
          const entry = byPlan(plan);
          if (!entry) return null;
          const highlight = plan === HIGHLIGHT;
          return (
            <div
              key={plan}
              className={`relative card p-6 flex flex-col ${highlight ? 'border-accent shadow-card-hover' : ''}`}
            >
              {highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 badge-float">
                  Mais Popular
                </span>
              )}
              <h3 className="font-display text-xl text-text-primary capitalize">{plan}</h3>
              <p className="text-text-secondary text-sm mb-4">{PLAN_BLURB[plan]}</p>
              <div className="mb-4 flex items-baseline gap-1.5">
                <span className="font-display text-4xl text-text-primary tabular-nums">{fmt(entry.amount, entry.currency)}</span>
                <span className="font-mono text-xs text-text-tertiary">/{interval === 'month' ? 'mês' : 'ano'}</span>
              </div>
              <ul className="space-y-2.5 text-sm text-text-secondary mb-6 flex-1">
                <li className="flex items-start gap-2"><Check size={16} className="text-success shrink-0 mt-0.5" /> <span><b>{entry.minutes} min</b> de vídeo / mês</span></li>
                <li className="flex items-start gap-2"><Check size={16} className="text-success shrink-0 mt-0.5" /> <span><b>Sem marca d'água</b>, sem expiração de cortes</span></li>
                <li className="flex items-start gap-2"><Cpu size={16} className="text-success shrink-0 mt-0.5" /> <span><b>Renderização em GPU</b> (~50s por vídeo de 8 min)</span></li>
                <li className="flex items-start gap-2"><KeyRound size={16} className="text-success shrink-0 mt-0.5" /> <span>Chave Gemini + postagem automática inclusas</span></li>
                <li className="flex items-start gap-2"><Bot size={16} className="text-success shrink-0 mt-0.5" /> <span>Acesso à <b>API</b> para automações</span></li>
                {plan === 'pro' && <li className="flex items-start gap-2"><Zap size={16} className="text-accent shrink-0 mt-0.5" /> <span>Fila de processamento prioritária</span></li>}
              </ul>
              <button
                onClick={() => checkout(entry)}
                disabled={busyPrice === entry.price_id}
                className={`w-full ${highlight ? 'btn-primary' : 'btn-ghost'}`}
              >
                {busyPrice === entry.price_id ? <Loader2 size={18} className="animate-spin" /> : `Assinar ${plan.charAt(0).toUpperCase() + plan.slice(1)}`}
              </button>
              <p className="text-center text-xs text-text-tertiary mt-2">Cobrado {interval === 'month' ? 'mensalmente' : 'anualmente'}. Cancele quando quiser.</p>
            </div>
          );
        })}
      </div>

      {/* What every plan includes vs what's bring-your-own-key */}
      <div className="mt-10 grid md:grid-cols-2 gap-4">
        <div className="card p-6">
          <div className="mb-4">
            <span className="badge-ok"><Check size={12} /> Incluso em todos os planos</span>
          </div>
          <ul className="space-y-2 text-sm text-ink2">
            <li className="flex items-start gap-2"><Cpu size={15} className="text-ok shrink-0 mt-0.5" /> <span><b>Nossa GPU NVIDIA faz a renderização.</b> Um vídeo de 8 minutos é cortado em cerca de 50 segundos, em vez dos 5 a 8 minutos que levaria em uma CPU comum.</span></li>
            <li className="flex items-start gap-2"><KeyRound size={15} className="text-ok shrink-0 mt-0.5" /> <span><b>A chave da API Gemini está inclusa.</b> Nada para cadastrar, nada para colar, sem limites pessoais de requisição para monitorar.</span></li>
            <li className="flex items-start gap-2"><Send size={15} className="text-ok shrink-0 mt-0.5" /> <span><b>Postagem automática integrada</b> para TikTok, Instagram Reels e YouTube Shorts.</span></li>
            <li className="flex items-start gap-2"><HardDrive size={15} className="text-ok shrink-0 mt-0.5" /> <span><b>Cortes armazenados em nuvem</b>, prontos para reabrir e reeditar de qualquer navegador.</span></li>
            <li className="flex items-start gap-2"><Check size={15} className="text-ok shrink-0 mt-0.5" /> <span><b>YouTube Studio</b> completo: títulos, miniaturas e descrições.</span></li>
            <li className="flex items-start gap-2"><Bot size={15} className="text-ok shrink-0 mt-0.5" /> <span><b>API para integrações.</b> Conecte seus scripts ou ferramentas a um endpoint ativo e automatize o fluxo de ponta a ponta. Chamadas usam os mesmos minutos, sem custos extras.</span></li>
          </ul>
          <p className="text-xs text-muted mt-3 pt-3 border-t border-rule">
            Seus minutos mensais cobrem o processamento de vídeo. Títulos e descrições são gratuitos;
            geração de <b>miniaturas por IA</b> consome ~3 min de cota por lote.
          </p>
        </div>
        <div className="card p-6">
          <div className="mb-4">
            <span className="badge-warn"><Zap size={12} /> Traga sua própria chave</span>
          </div>
          <p className="text-sm text-muted mb-3 leading-relaxed">
            Recursos avançados como <b className="text-ink2">dublagem de voz</b> utilizam modelos externos de IA.
            Conecte suas próprias chaves para esses recursos — você é faturado diretamente por esses provedores. Seu plano cobre o corte de vídeo e orquestração.
          </p>
          <p className="text-xs text-muted">Créditos integrados estarão disponíveis em breve — sem necessidade de chaves.</p>
        </div>
      </div>

      <p className="text-center text-muted text-xs mt-8 lowercase">
        comece grátis agora mesmo, faça upgrade para mais minutos e sem marca d'água, ou execute em seu próprio hardware.
      </p>
    </div>
  );
}
