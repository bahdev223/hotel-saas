import { api } from '../core/api.js';

export async function transferer(produitId, quantite, sourceId, destId) {
    return api('/stock/api/transfert/', {
        method: 'POST',
        body: JSON.stringify({
            produit_id: produitId,
            quantite,
            entrepot_source_id: sourceId,
            entrepot_dest_id: destId,
        }),
    });
}

export async function listeEntrepots() {
    return api('/stock/api/entrepots/liste/');
}
