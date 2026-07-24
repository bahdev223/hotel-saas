import { api } from '../core/api.js';

export async function commandesCuisine() {
    return api('/restaurant/api/cuisine/commandes/');
}

export async function commandeIngredients(commandeId) {
    return api(`/restaurant/api/cuisine/commande/${commandeId}/ingredients/`);
}

export async function lancerCuisson(commandeId, mode = 'auto', ingredients = []) {
    return api(`/restaurant/api/cuisine/commande/${commandeId}/lancer/`, {
        method: 'POST',
        body: JSON.stringify({ mode, ingredients }),
    });
}

export async function changerStatutCuisine(commandeId, statut) {
    return api(`/restaurant/api/cuisine/commande/${commandeId}/statut/`, {
        method: 'POST',
        body: JSON.stringify({ statut }),
    });
}
