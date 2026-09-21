export function getFontStack(fontFamily) {
  const name = (fontFamily || '').trim();
  if (!name) return '"Anton", "Montserrat", sans-serif';
  if (/noto\s*serif/i.test(name)) {
    return '"Noto Serif", Georgia, serif';
  }
  if (/anton/i.test(name)) {
    return '"Anton", Impact, sans-serif';
  }
  if (/montserrat/i.test(name)) {
    return '"Montserrat", sans-serif';
  }
  if (/inter/i.test(name)) {
    return '"Inter", "Inter Black", sans-serif';
  }
  return `"${name}", sans-serif`;
}

export const notoSerifFontFace = "";
export const NOTO_SERIF_FONT_FAMILY = '"Noto Serif", Georgia, serif';
