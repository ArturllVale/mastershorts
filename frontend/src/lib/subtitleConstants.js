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
    id: 'auto',
    label: 'Auto (Anton)',
    style: 'karaoke',
    effect: 'pop',
    highlightColor: '#FFE500',
    fontColor: '#FFFFFF',
    baseOpacity: 1.0,
    uppercase: true,
    fontName: 'Anton',
    borderWidth: 4,
    fontSize: 44,
    marginV: 43
  },
  {
    id: 'montserrat',
    label: 'Montserrat',
    style: 'karaoke',
    effect: 'pop',
    highlightColor: '#00FF66',
    fontColor: '#FFFFFF',
    baseOpacity: 1.0,
    uppercase: true,
    fontName: 'Montserrat',
    borderWidth: 4,
    fontSize: 42,
    marginV: 43
  },
  {
    id: 'inter',
    label: 'Inter Black',
    style: 'karaoke',
    effect: 'pop',
    highlightColor: '#00E5FF',
    fontColor: '#FFFFFF',
    baseOpacity: 1.0,
    uppercase: true,
    fontName: 'Inter Black',
    borderWidth: 4,
    fontSize: 42,
    marginV: 43
  },
  {
    id: 'neon',
    label: 'Neon Glow',
    style: 'karaoke',
    effect: 'glow',
    highlightColor: '#FF3366',
    fontColor: '#FFFFFF',
    baseOpacity: 0.75,
    uppercase: true,
    fontName: 'Anton',
    borderWidth: 3,
    fontSize: 44,
    marginV: 43
  },
  {
    id: 'elegante',
    label: 'Elegante',
    style: 'karaoke',
    effect: 'pop',
    highlightColor: '#FFD700',
    fontColor: '#FFFFFF',
    baseOpacity: 1.0,
    uppercase: false,
    fontName: 'Noto Serif',
    borderWidth: 3,
    fontSize: 40,
    marginV: 43
  },
  {
    id: 'classico',
    label: 'Clássico',
    style: 'classic',
    effect: 'none',
    highlightColor: '#FFFFFF',
    fontColor: '#FFFFFF',
    baseOpacity: 1.0,
    uppercase: false,
    fontName: 'Montserrat',
    borderWidth: 3,
    fontSize: 36,
    marginV: 43
  }
];
