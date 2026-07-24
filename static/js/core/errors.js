import { notifyError } from './notifications.js';

export class ApiError extends Error {
    constructor(message, status = 0, data = null) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.data = data;
    }
}

export function handleApiError(err, fallback = 'Une erreur est survenue') {
    const msg = err?.message || fallback;
    notifyError(msg);
    console.error('[API Error]', err);
    return msg;
}

export function showFieldErrors(errors, formEl) {
    if (!formEl) return;
    for (const [field, messages] of Object.entries(errors)) {
        const input = formEl.querySelector(`[name="${field}"]`);
        if (input) {
            input.classList.add('border-red-500');
            const errEl = document.createElement('p');
            errEl.className = 'text-red-500 text-xs mt-1';
            errEl.textContent = Array.isArray(messages) ? messages[0] : messages;
            input.parentNode.appendChild(errEl);
        }
    }
}
