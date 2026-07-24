import { api } from '../core/api.js';

export async function encaisser(commandeId, data) {
    return api(`/pos/api/commandes/${commandeId}/payer/`, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function modesPaiement() {
    return api('/pos/api/modes-paiement/');
}
