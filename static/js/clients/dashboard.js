import { api } from '../core/api.js';

export async function dashboardClients() {
    return api('/clients/api/dashboard/');
}

export async function chercherClients(q) {
    return api('/clients/api/clients/?q=' + encodeURIComponent(q));
}

export async function creerClient(data) {
    return api('/clients/api/clients/creer/', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}
