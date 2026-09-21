export function encrypt(text) {
  if (!text) return text;
  return btoa(text);
}

export function decrypt(text) {
  if (!text) return text;
  try { return atob(text); } catch { return text; }
}
