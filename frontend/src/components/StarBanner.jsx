import React, { useState, useEffect } from 'react';
import { Sparkles } from 'lucide-react';

const TIPS = [
  "Clipes com ganchos visuais e legendas dinâmicas aumentam a retenção em até 400% no TikTok e Shorts.",
  "A Regra dos 3 Segundos: se o vídeo não capturar a atenção logo no início, o usuário vai rolar a tela.",
  "Cortes rápidos mantêm o ritmo alto! Remover silêncios e suspiros prende o espectador.",
  "Sabia que mais de 70% das pessoas assistem vídeos sem som? Legendas são obrigatórias.",
  "Comece já no meio da ação ou da frase. Isso cria curiosidade instantânea (o famoso 'Cold Open').",
  "O título no início (Hook) deve entregar um benefício claro: o que a pessoa ganha assistindo?",
  "Termine o vídeo de forma abrupta ou com um loop perfeito para incentivar uma segunda visualização.",
  "Histórias superam dicas genéricas. Contar um breve relato prende mais a atenção.",
  "Palavras fortes no gancho como 'Segredo', 'Nunca', 'Proibido' disparam a curiosidade humana.",
  "Coloque as informações cruciais no meio da tela, a interface do TikTok/Reels esconde as bordas."
];

export default function StarBanner({ message = 'Dica:' }) {
  const [tipIndex, setTipIndex] = useState(() => Math.floor(Math.random() * TIPS.length));
  const [fade, setFade] = useState(true);

  useEffect(() => {
    // Muda a dica a cada 15 segundos
    const interval = setInterval(() => {
      setFade(false); // inicia fade out
      setTimeout(() => {
        setTipIndex((prev) => (prev + 1) % TIPS.length);
        setFade(true); // inicia fade in
      }, 500); // meio segundo para a transição
    }, 20000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-input bg-paper2/90 border border-rule text-xs text-muted shadow-sm overflow-hidden">
      <Sparkles size={15} className="shrink-0 text-violet animate-pulse" />
      <span className={`leading-snug transition-opacity duration-500 ease-in-out ${fade ? 'opacity-100' : 'opacity-0'}`}>
        <strong className="text-ink font-medium">{message}</strong> {TIPS[tipIndex]}
      </span>
    </div>
  );
}
