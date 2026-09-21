// The consent banner. Small on purpose — it is a legal control, not a feature.
//
// Two rules it exists to satisfy, both of which the previous "no banner at all"
// version failed once OpenPanel was identifying users by profile:
//   1. Nothing non-essential runs before the visitor agrees (see lib/consent.js —
//      the tracker is only loaded from there).
//   2. Refusing must cost exactly as much as accepting. "Reject all" and
//      "Accept all" are the same component with the same size, weight, colour
//      and position; there is no pre-ticked box and no dark pattern.
//
// It renders nothing once a decision exists — the footer link
// (openConsentManager) is how anyone changes their mind.
import { useEffect, useState } from 'react';
import {
  getConsent, hasDecided, acceptAll, rejectAll, setConsent,
  onConsentOpenRequest,
} from '../lib/consent';

const CATEGORY_COPY = [
  {
    key: 'necessary',
    label: 'Estritamente necessários',
    body: 'Sua sessão de login, o token de segurança para carregar seus próprios cortes e preferências de interface. Armazenados apenas neste navegador. Essenciais para o funcionamento.',
    locked: true,
  },
  {
    key: 'analytics',
    label: 'Métricas e aprimoramento',
    body: 'Métricas anônimas de uso para aprimoramento contínuo da aplicação. Sem redes de publicidade, sem venda de dados e sem rastreamento entre sites.',
    locked: true,
  },
  {
    key: 'marketing',
    label: 'Marketing',
    body: 'Rastreadores de anúncios e remarketing. Não utilizamos nenhum atualmente; mantido desligado por padrão.',
  },
];

export default function CookieBanner() {
  const [open, setOpen] = useState(() => !hasDecided());
  const [details, setDetails] = useState(false);
  const [draft, setDraft] = useState(() => getConsent());

  useEffect(() => onConsentOpenRequest(() => {
    setDraft(getConsent());
    setDetails(true);
    setOpen(true);
  }), []);

  if (!open) return null;

  const close = () => { setOpen(false); setDetails(false); };

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label="Preferências de cookies e privacidade"
      className="fixed inset-x-0 bottom-0 z-50 p-3 sm:p-4 pb-[max(0.75rem,env(safe-area-inset-bottom))]"
    >
      <div className="card mx-auto max-w-3xl p-4 sm:p-5 space-y-4 shadow-2xl">
        <div className="space-y-2">
          <h2 className="font-display text-lg text-ink">Privacidade e preferências</h2>
          <p className="text-sm text-ink2">
            Armazenamos apenas o necessário para a plataforma funcionar corretamente.
            Você pode personalizar suas preferências ou consultar nossa{' '}
            <a href="#legal" className="underline hover:text-ink">Política de Privacidade</a>.
          </p>
        </div>

        {details && (
          <ul className="space-y-3 border-t border-rule pt-3">
            {CATEGORY_COPY.map((cat) => (
              <li key={cat.key} className="flex gap-3">
                <input
                  type="checkbox"
                  id={`consent-${cat.key}`}
                  className="mt-1 h-4 w-4 shrink-0 accent-current"
                  checked={cat.locked ? true : !!draft[cat.key]}
                  disabled={cat.locked}
                  onChange={(e) => setDraft({ ...draft, [cat.key]: e.target.checked })}
                />
                <label htmlFor={`consent-${cat.key}`} className="text-sm">
                  <span className="text-ink">{cat.label}</span>
                  {cat.locked && <span className="text-muted"> · sempre ativo</span>}
                  <span className="block text-muted">{cat.body}</span>
                </label>
              </li>
            ))}
          </ul>
        )}

        <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
          {/* Reject and Accept are deliberately the same button. */}
          <button
            type="button"
            className="btn-ghost flex-1"
            onClick={() => { rejectAll(); close(); }}
          >
            Rejeitar todos
          </button>
          <button
            type="button"
            className="btn-ghost flex-1"
            onClick={() => { acceptAll(); close(); }}
          >
            Aceitar todos
          </button>
          {details ? (
            <button
              type="button"
              className="btn-quiet sm:w-auto"
              onClick={() => { setConsent(draft); close(); }}
            >
              Salvar preferências
            </button>
          ) : (
            <button
              type="button"
              className="btn-quiet sm:w-auto"
              onClick={() => setDetails(true)}
            >
              Personalizar
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
