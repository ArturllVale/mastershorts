import React, { useState } from 'react';
import { ArrowDown, ArrowRight, Check, ChevronDown, Github, MoveRight, Cpu, KeyRound, Send, Server, HardDrive } from 'lucide-react';
import PricingSection from './PricingSection';

// The honest hosted-vs-self-hosted trade-off. The software is identical and open
// source either way, so the plans have to earn their price on hardware, keys and
// setup rather than on features. Timings are measured on our own pipeline: an
// 8-minute input takes ~50s on the server GPU and 5-8 min on CPU.
// The landing page carries its own shorter version of this (Landing.jsx "Two ways
// to use OpenShorts"); this detailed table is only for the standalone #/pricing.
const HOSTED_VS_SELF = [
  {
    icon: Cpu,
    label: 'Velocidade',
    hosted: 'Um vídeo de 8 minutos é cortado em cerca de 50 segundos em nossa GPU NVIDIA.',
    self: '5 a 8 minutos para o mesmo vídeo em uma CPU comum, a menos que você tenha uma GPU CUDA.',
  },
  {
    icon: KeyRound,
    label: 'Chaves de API',
    hosted: 'A chave Gemini está inclusa. Nada para criar, colar ou recarregar.',
    self: 'Você cria e utiliza sua própria chave Gemini, além de ElevenLabs e fal.ai para dublagem.',
  },
  {
    icon: Server,
    label: 'Instalação',
    hosted: 'Faça login e cole um link. Nada para instalar.',
    self: '8GB+ de RAM, Node.js, Python e download de modelos pesados na primeira execução.',
  },
  {
    icon: HardDrive,
    label: 'Armazenamento',
    hosted: 'Os cortes ficam salvos na nuvem e abrem em qualquer navegador.',
    self: 'No seu próprio computador e com seus próprios backups.',
  },
];

// Billing / value questions reused verbatim from Landing.jsx faqs
const FAQS = [
  {
    question: "O MasterShorts é realmente gratuito? Qual é a pegadinha?",
    answer: "Não há pegadinha. A versão local/auto-hospedada é 100% gratuita e de código aberto: você roda na sua máquina, traz suas próprias chaves de API e não há marcas d'água nem limites de uso. O plano em nuvem oferece a conveniência de rodar em nossos servidores com GPU rápida (~50 segundos por vídeo), sem precisar instalar nada, com 20 minutos grátis todo mês e planos acessíveis para criadores que precisam de mais minutos."
  },
  {
    question: "Como o MasterShorts se compara ao Opus Clip?",
    answer: "O MasterShorts oferece detecção inteligente de momentos virais com IA, reenquadramento facial vertical automático 9:16, legendas animadas em português, geração de títulos e miniaturas, além de dublagem por voz em múltiplos idiomas. Ele roda na nuvem ou localmente no seu computador com privacidade total dos seus dados."
  },
  {
    question: "O MasterShorts pode gerar miniaturas e títulos para o YouTube de graça?",
    answer: "Sim. O MasterShorts inclui estúdio completo com sugestão de títulos virais, chat interativo de refinamento com IA, gerador de miniaturas personalizadas e descrições automáticas com capítulos para publicação direta."
  },
  {
    question: "O acesso à API e ao servidor MCP custa extra?",
    answer: "Não. Todos os planos podem utilizar a API REST e o servidor MCP para integrar automações com Claude, ChatGPT ou n8n consumindo os mesmos minutos mensais da sua conta."
  },
  {
    question: "Quais são os requisitos de sistema para rodar localmente?",
    answer: "Recomenda-se 8GB+ de RAM, Python 3.11+, Node.js 18+, FFmpeg instalado e um processador moderno multi-core. Placas de vídeo NVIDIA com suporte a CUDA aceleram ainda mais o processamento."
  }
];

const TRUST_CARDS = [
  {
    eyebrow: 'sem marcas d’água nos planos pagos',
    body: (
      <>
        Seus cortes exportam limpos e em alta resolução. Os planos contabilizam minutos de vídeo processado por mês, nunca créditos artificiais por corte.
      </>
    ),
  },
  {
    eyebrow: 'cancele quando quiser',
    body: (
      <>
        Comece no plano gratuito — 20 minutos por mês, sem necessidade de cartão de crédito. Cancele sua assinatura a qualquer momento com um clique.
      </>
    ),
  },
];

const FAQItem = ({ question, answer, isOpen, onClick }) => (
  <div>
    <button
      onClick={onClick}
      className="w-full flex items-center justify-between px-1 py-5 text-left"
    >
      <span className="text-ink font-medium pr-4">{question}</span>
      <ChevronDown
        size={18}
        className={`text-muted flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`}
      />
    </button>
    {isOpen && (
      <div className="px-1 pb-6">
        <p className="text-muted text-sm leading-relaxed">{answer}</p>
      </div>
    )}
  </div>
);

const DemoFigure = ({ src, label, className = '', children }) => (
  <figure className={`border border-rule rounded-card overflow-hidden bg-paper2 ${className}`}>
    <div className="relative">
      <video
        src={src}
        autoPlay
        muted
        loop
        playsInline
        preload="metadata"
        className="block w-full h-auto"
      />
      {children}
    </div>
    <figcaption className="readout px-3 py-2 border-t border-rule">{label}</figcaption>
  </figure>
);

// Conversion-focused paywall / pricing page (#/pricing). Wraps <PricingSection/>.
export default function PricingPage({ onRequireLogin }) {
  const [openFaq, setOpenFaq] = useState(null);

  const scrollToPlans = () => {
    document.getElementById('pricing-plans')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-paper text-ink2 animate-fade">
      {/* Header */}
      <header className="px-6 pt-20 pb-12">
        <div className="max-w-6xl mx-auto text-center">
          <p className="eyebrow mb-5">PLANOS E PREÇOS</p>
          <h1 className="font-display text-ink tracking-tight text-4xl md:text-6xl leading-[1.02] mb-5">
            Comece a criar cortes em minutos.
          </h1>
          <p className="font-mono text-xs text-text-tertiary">Plano gratuito · 20 min/mês · Sem cartão de crédito</p>
        </div>
      </header>

      {/* Demo proof strip */}
      <section className="px-6 pb-16">
        <div className="max-w-4xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-5 md:gap-6">
            <DemoFigure src="/demo/clip-source.mp4" label="entrada · 16:9" />

            <MoveRight size={20} className="text-accent hidden md:block" aria-hidden="true" />
            <ArrowDown size={20} className="text-accent md:hidden justify-self-center" aria-hidden="true" />

            <DemoFigure
              src="/demo/clip-vertical.mp4"
              label="saída · 9:16 · rastreado"
              className="w-44 sm:w-48 justify-self-center md:justify-self-auto"
            />
          </div>
          <p className="text-center text-xs text-text-tertiary mt-4">
            Resultado real do gerador de cortes — mesmo vídeo, reenquadrado por rastreamento facial com IA.
          </p>
        </div>
      </section>

      {/* Pricing grid */}
      <section id="pricing-plans" className="px-6 py-16 border-t border-border scroll-mt-8">
        <div className="max-w-6xl mx-auto">
          <PricingSection onRequireLogin={onRequireLogin} />
        </div>
      </section>

      {/* Hosted vs self-hosted */}
      <section className="px-6 py-16 border-t border-border">
        <div className="max-w-5xl mx-auto">
          <div className="mb-8">
            <p className="eyebrow mb-3">EM NUVEM OU AUTO-HOSPEDADO</p>
            <h2 className="font-display text-3xl md:text-4xl text-text-primary tracking-tight">
              O que você está realmente pagando
            </h2>
            <p className="text-text-secondary text-sm mt-3 max-w-2xl leading-relaxed">
              O software é o mesmo e de código aberto. O que um plano em nuvem oferece é o hardware acelerado,
              as chaves de API inclusas e a conveniência de não configurar servidores.
            </p>
          </div>

          <div className="hidden md:grid grid-cols-[9rem_1fr_1fr] gap-x-6 pb-2 mb-2 border-b border-border">
            <span />
            <span className="eyebrow">Hospedado na nuvem</span>
            <span className="eyebrow">Auto-hospedado (Local)</span>
          </div>

          <div className="divide-y divide-border border-b border-border">
            {HOSTED_VS_SELF.map(({ icon: Icon, label, hosted, self }) => (
              <div key={label} className="py-4 grid gap-2 md:grid-cols-[9rem_1fr_1fr] md:gap-x-6 md:items-start">
                <div className="flex items-center gap-2 text-text-primary">
                  <Icon size={15} className="text-text-tertiary shrink-0" />
                  <span className="text-sm font-medium">{label}</span>
                </div>
                <div>
                  <span className="eyebrow block mb-1 md:hidden">Hospedado na nuvem</span>
                  <p className="text-sm text-text-primary leading-relaxed">
                    <Check size={14} className="text-success inline-block mr-1.5 -mt-0.5" />
                    {hosted}
                  </p>
                </div>
                <div>
                  <span className="eyebrow block mb-1 mt-2 md:hidden">Auto-hospedado (Local)</span>
                  <p className="text-sm text-text-secondary leading-relaxed">{self}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
            <p className="text-xs text-text-tertiary leading-relaxed max-w-xl">
              Executar no seu próprio computador é 100% gratuito e sempre será. Requer hardware adequado,
              suas próprias chaves de API e tempo de processamento.
            </p>
          </div>
        </div>
      </section>

      {/* Trust strip */}
      <section className="px-6 py-16 border-t border-border">
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-4">
          {TRUST_CARDS.map((card) => (
            <div key={card.eyebrow} className="card p-6">
              <div className="flex items-center gap-2 mb-3">
                <Check size={16} className="text-success shrink-0" />
                <span className="eyebrow">{card.eyebrow}</span>
              </div>
              <p className="text-sm text-text-secondary leading-relaxed">{card.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Mini FAQ */}
      <section className="px-6 py-16 border-t border-border">
        <div className="max-w-3xl mx-auto">
          <div className="mb-10">
            <p className="eyebrow mb-3">DÚVIDAS · PERGUNTAS FREQUENTES</p>
            <h2 className="font-display text-3xl md:text-4xl text-text-primary tracking-tight">
              Perguntas Comuns
            </h2>
          </div>
          <div className="divide-y divide-border border-y border-border">
            {FAQS.map((faq, i) => (
              <FAQItem
                key={i}
                question={faq.question}
                answer={faq.answer}
                isOpen={openFaq === i}
                onClick={() => setOpenFaq(openFaq === i ? null : i)}
              />
            ))}
          </div>
        </div>
      </section>

      {/* Closing statement */}
      <section className="px-6 py-24 border-t border-border">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="font-display text-3xl md:text-5xl text-text-primary tracking-tight mb-8">
            Vinte minutos gratuitos. Todo mês. Sem cartão até você decidir.
          </h2>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <button onClick={scrollToPlans} className="btn-primary whitespace-nowrap">
              Começar Grátis
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
