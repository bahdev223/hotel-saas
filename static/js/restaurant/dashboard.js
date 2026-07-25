import { api } from '../core/api.js';
import { formatMoney } from '../core/money.js';

export function dashboardApp() {
    return {
        d: null,
        lastUpdate: null,
        error: false,
        refreshInterval: null,

        async init() {
            await this.load();
            this.refreshInterval = setInterval(() => this.load(), 30000);
        },

        destroy() {
            if (this.refreshInterval) clearInterval(this.refreshInterval);
        },

        async load() {
            try {
                const data = await api('/restaurant/api/dashboard/');
                this.d = data;
                this.lastUpdate = new Date();
                this.error = false;
            } catch {
                this.error = true;
            }
        },

        maxBarH(total) {
            const max = Math.max(...(this.d?.ca_7jours || []).map(j => j.total), 1);
            return Math.max((total / max) * 110, 4);
        },

        formatMoney(v) {
            return formatMoney(v);
        },

        get lastUpdateStr() {
            if (!this.lastUpdate) return '';
            return this.lastUpdate.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        },

        barClass(i) {
            const len = this.d?.ca_7jours?.length || 0;
            return i === len - 1 ? 'bg-secondary' : 'bg-secondary/40';
        },
    };
}
