export class QuotaError extends Error {
  constructor(message) {
    super(message);
    this.name = 'QuotaError';
  }
}

export function getToken() {
  return localStorage.getItem('token');
}

export function setToken(token) {
  localStorage.setItem('token', token);
}

export function clearToken() {
  localStorage.removeItem('token');
}

export async function apiFetch(url, options = {}) {
  const token = getToken();
  const headers = new Headers(options.headers || {});
  
  // If the header isn't explicitly set to null/empty by the caller,
  // and we have a token, add the Authorization header.
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  
  const res = await fetch(url, { ...options, headers });
  
  if (res.status === 402 || res.status === 429) {
    throw new QuotaError(await res.text());
  }
  
  return res;
}

export async function apiJson(url, options = {}) {
  const res = await apiFetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text);
  }
  return res.json();
}
