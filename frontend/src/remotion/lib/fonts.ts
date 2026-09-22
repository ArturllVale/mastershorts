import { staticFile } from "remotion";

/**
 * CSS @font-face declaration for NotoSerif-Bold (bundled locally).
 * Use in components via: <style>{notoSerifFontFace}</style>
 */
export const NOTO_SERIF_FONT_FAMILY = "NotoSerif-Bold";

export const notoSerifFontFace = `
@font-face {
  font-family: '${NOTO_SERIF_FONT_FAMILY}';
  src: url('${staticFile("fonts/NotoSerif-Bold.ttf")}') format('truetype');
  font-weight: 700;
  font-style: normal;
}
`;

export const SUBTITLE_FONTS: Record<string, string> = {
  Anton: '"Anton", Impact, sans-serif',
  Montserrat: '"Montserrat", sans-serif',
  Inter: '"Inter Black", "Inter", sans-serif',
  "Inter Black": '"Inter Black", "Inter", sans-serif',
  "Noto Serif": '"Noto Serif", "Noto Serif Bold", Georgia, serif',
  "Noto Serif Bold": '"Noto Serif Bold", "Noto Serif", Georgia, serif',
};

export function getFontStack(fontFamily: string): string {
  const name = (fontFamily || '').trim();
  if (SUBTITLE_FONTS[name]) return SUBTITLE_FONTS[name];
  if (/noto\s*serif/i.test(name)) return '"Noto Serif", "Noto Serif Bold", Georgia, serif';
  if (/inter/i.test(name)) return '"Inter Black", "Inter", sans-serif';
  if (/montserrat/i.test(name)) return '"Montserrat", sans-serif';
  if (/anton/i.test(name)) return '"Anton", Impact, sans-serif';
  return `"${name}", sans-serif`;
}
