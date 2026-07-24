import { api } from '../core/api.js';

export async function listerStocks(entrepotId) {
    return api('/stock/api/produits/stock/?entrepot_id=' + entrepotId);
}

export async function entreeStock(produitId, quantite, raison, entrepotId) {
    return api(`/stock/api/produits/${produitId}/entree/`, {
        method: 'POST',
        body: JSON.stringify({ quantite, raison, entrepot_id: entrepotId }),
    });
}

export async function sortieStock(produitId, quantite, raison, entrepotId) {
    return api(`/stock/api/produits/${produitId}/sortie/`, {
        method: 'POST',
        body: JSON.stringify({ quantite, raison, entrepot_id: entrepotId }),
    });
}
