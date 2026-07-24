import { api } from '../core/api.js';

export async function chargerSession() {
    return api('/pos/api/session/');
}

export async function ouvrirSession(data) {
    return api('/pos/api/session/ouvrir/', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function fermerSession(data) {
    return api('/pos/api/session/fermer/', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function relevéSession() {
    return api('/pos/api/session/releve/');
}
