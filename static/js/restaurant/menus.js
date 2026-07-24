import { api } from '../core/api.js';

export async function listeMenus() {
    return api('/restaurant/api/menus/');
}

export async function detailMenu(id) {
    return api(`/restaurant/api/menus/${id}/`);
}

export async function composerMenu(id, lignes) {
    return api(`/restaurant/api/menus/${id}/composer/`, {
        method: 'POST',
        body: JSON.stringify({ lignes }),
    });
}
