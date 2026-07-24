import { api } from '../core/api.js';

export async function chargerCatalogue(entrepotId) {
    return api('/pos/api/catalogue/?entrepot_id=' + (entrepotId || ''));
}

export async function chargerCategories() {
    return api('/pos/api/categories/');
}

export async function chercherArticles(q) {
    return api('/pos/api/catalogue/?q=' + encodeURIComponent(q));
}
