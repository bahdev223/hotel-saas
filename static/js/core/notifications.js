export function notify(message, type = 'success', duration = 4000) {
    if (window.notify) {
        window.notify(message, type, duration);
        return;
    }
    const container = document.getElementById('toast-container');
    if (!container) return;
    const icons = { success: 'fa-check-circle', error: 'fa-exclamation-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
    const colors = { success: 'bg-green-50 border-green-500 text-green-800', error: 'bg-red-50 border-red-500 text-red-800', warning: 'bg-orange-50 border-orange-500 text-orange-800', info: 'bg-blue-50 border-blue-500 text-blue-800' };
    const el = document.createElement('div');
    el.className = `flex items-center gap-3 rounded-lg p-4 border-l-4 text-sm shadow-lg ${colors[type] || colors.info}`;
    el.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i><span>${message}</span>`;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.3s'; setTimeout(() => el.remove(), 300); }, duration);
}

export function notifySuccess(msg, duration) { notify(msg, 'success', duration); }
export function notifyError(msg, duration) { notify(msg, 'error', duration); }
export function notifyWarning(msg, duration) { notify(msg, 'warning', duration); }
export function notifyInfo(msg, duration) { notify(msg, 'info', duration); }
