import { api } from '../core/api.js';

export async function lancerProduction(recetteId, quantite, entrepotSourceId, entrepotDestId) {
    return api('/restaurant/api/produire/', {
        method: 'POST',
        body: JSON.stringify({
            recette_id: recetteId,
            quantite,
            entrepot_source_id: entrepotSourceId,
            entrepot_dest_id: entrepotDestId || entrepotSourceId,
        }),
    });
}

export async function verifierStock(recetteId, entrepotId) {
    return api(`/restaurant/api/verifier-stock/${recetteId}/?entrepot_id=${entrepotId}`);
}

export async function historiqueProduction(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return api('/restaurant/api/production/historique/?' + qs);
}
