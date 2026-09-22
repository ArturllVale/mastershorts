export const FONT_OPTIONS = [
  { value: 'Anton', label: 'Anton (Padrão Shorts)' },
  { value: 'Montserrat', label: 'Montserrat' },
  { value: 'Inter Black', label: 'Inter Black' },
  { value: 'Noto Serif', label: 'Noto Serif' }
];

export const COLOR_PRESETS = [
  { color: '#FFFFFF', value: '#FFFFFF', label: 'Branco' },
  { color: '#FFE500', value: '#FFE500', label: 'Amarelo' },
  { color: '#00E5FF', value: '#00E5FF', label: 'Ciano' },
  { color: '#00FF66', value: '#00FF66', label: 'Verde' },
  { color: '#000000', value: '#000000', label: 'Preto' }
];

export const HIGHLIGHT_PRESETS = [
  { color: '#FFE500', value: '#FFE500', label: 'Amarelo Pop' },
  { color: '#00FF66', value: '#00FF66', label: 'Verde Neon' },
  { color: '#00E5FF', value: '#00E5FF', label: 'Ciano' },
  { color: '#FF3366', value: '#FF3366', label: 'Rosa Neon' },
  { color: '#FFFFFF', value: '#FFFFFF', label: 'Branco' }
];

export const ANIMATION_OPTIONS = [
  { value: 'pop', label: 'Pop' },
  { value: 'word-highlight', label: 'Brilho' },
  { value: 'karaoke', label: 'Fundo' },
  { value: 'none', label: 'Nenhuma' }
];

export const POSITION_OPTIONS = [
  { value: 'bottom', label: 'Rodapé' },
  { value: 'middle', label: 'Centro' },
  { value: 'top', label: 'Topo' }
];

export const CAPTION_PRESETS = [
  {
    id: 'viral-beast',
    label: 'Viral Beast',
    style: 'karaoke',
    effect: 'pop',
    highlightColor: '#FFE500', // Yellow
    fontColor: '#FFFFFF',
    baseOpacity: 1.0,
    uppercase: true,
    fontName: 'Anton',
    borderWidth: 6,
    fontSize: 92,
    marginV: 43
  },
  {
    id: 'tiktok-box',
    label: 'TikTok Box',
    style: 'karaoke',
    effect: 'karaoke', // Fundo
    highlightColor: '#0066FF', // Blue bg for active like the user requested
    fontColor: '#FFFFFF', // White text for inactive
    activeTextColor: '#FFFFFF', // White text for active word
    bgColor: '#FFFFFF', 
    baseOpacity: 1.0,
    uppercase: false,
    fontName: 'Inter Black',
    borderWidth: 0,
    fontSize: 82,
    marginV: 50
  },
  {
    id: 'neon-glow',
    label: 'Neon Glow',
    style: 'karaoke',
    effect: 'glow',
    highlightColor: '#00FF66', // Neon Green
    fontColor: '#FFFFFF',
    baseOpacity: 0.65,
    uppercase: true,
    fontName: 'Montserrat',
    borderWidth: 2,
    fontSize: 86,
    marginV: 45
  },
  {
    id: 'impact-cyan',
    label: 'Impacto Ciano',
    style: 'karaoke',
    effect: 'pop',
    highlightColor: '#00E5FF',
    fontColor: '#FFFFFF',
    baseOpacity: 1.0,
    uppercase: true,
    fontName: 'Anton',
    borderWidth: 5,
    fontSize: 90,
    marginV: 43
  },
  {
    id: 'elegante',
    label: 'Elegante (Podcast)',
    style: 'karaoke',
    effect: 'none',
    highlightColor: '#FFD700',
    fontColor: '#FFFFFF',
    baseOpacity: 0.9,
    uppercase: false,
    fontName: 'Noto Serif',
    borderWidth: 2,
    fontSize: 78,
    marginV: 43
  }
];
