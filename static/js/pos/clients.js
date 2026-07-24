import { api } from '../core/api.js';

export async function chercherClients(q) {
    return api('/pos/api/clients/?q=' + encodeURIComponent(q));
}

export async function creerClient(data) {
    return api('/pos/api/clients/creer/', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}
