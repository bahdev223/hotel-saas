import { api } from '../core/api.js';

export async function chargerCommandes() {
    return api('/pos/api/commandes/');
}

export async function chargerCommande(id) {
    return api(`/pos/api/commandes/${id}/`);
}

export async function changerStatut(id, statut) {
    return api(`/pos/api/commandes/${id}/statut/`, {
        method: 'POST',
        body: JSON.stringify({ statut }),
    });
}

export async function annulerCommande(id) {
    return api(`/pos/api/commandes/${id}/annuler/`, { method: 'POST' });
}
