import { api } from '../core/api.js';

export async function listeRecettes(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return api('/restaurant/api/recettes/liste/?' + qs);
}

export async function detailRecette(id) {
    return api(`/restaurant/api/recettes/${id}/`);
}

export async function creerRecette(data) {
    return api('/restaurant/api/recettes/creer/', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function sauverIngredients(recetteId, ingredients) {
    return api(`/restaurant/api/recette/${recetteId}/ingredients/save/`, {
        method: 'POST',
        body: JSON.stringify({ ingredients }),
    });
}

export async function sauverEtapes(recetteId, etapes) {
    return api(`/restaurant/api/recette/${recetteId}/etapes/save/`, {
        method: 'POST',
        body: JSON.stringify({ etapes }),
    });
}
