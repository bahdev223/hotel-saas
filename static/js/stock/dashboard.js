import { api } from '../core/api.js';

export async function dashboardStats() {
    return api('/stock/api/dashboard/');
}

export async function notifications() {
    return api('/stock/api/notifications/');
}

export async function produitsAlerte() {
    return api('/stock/api/alertes/');
}
