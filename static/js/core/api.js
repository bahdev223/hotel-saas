import { getCsrfToken } from './csrf.js';

export async function api(url, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set('Accept', 'application/json');

    const body = options.body;
    if (body && !(body instanceof FormData)) {
        headers.set('Content-Type', 'application/json');
    }

    const method = (options.method || 'GET').toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
        headers.set('X-CSRFToken', getCsrfToken());
    }

    const response = await fetch(url, { ...options, headers, credentials: 'same-origin' });

    let data = null;
    try { data = await response.json(); } catch { data = null; }

    if (!response.ok) {
        const msg = data?.error || data?.message || `Erreur ${response.status}`;
        throw new Error(msg);
    }

    return data;
}
