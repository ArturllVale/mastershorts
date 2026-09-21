export function fmt(seconds) {
  if (!seconds) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function totalOf(items, key) {
  if (!items || !items.length) return 0;
  return items.reduce((acc, item) => acc + (item[key] || 0), 0);
}
