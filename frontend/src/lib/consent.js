export function applyConsent() {
  const consent = localStorage.getItem('cookie_consent');
  if (consent === 'accepted') {}
}
export function getConsent() { return {}; }
export function hasDecided() { return true; }
export function acceptAll() {}
export function rejectAll() {}
export function setConsent() {}
export function onConsentOpenRequest() {}
