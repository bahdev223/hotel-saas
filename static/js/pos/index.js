import { createPosStore } from './pos-store.js';
import { posReservation } from './reservation.js';
import { posSessionDialog } from './session.js';

import {
    getCookieGlobal, checkSessionRequise,
    openClientSelector, closeClientSelector,
    selectionnerDepuisListeNative, selectionnerPassagerNative,
    afficherCommandeInterface, afficherLanceur,
    creerClientDepuisSelector, payerCommande,
    modifierCommande, supprimerCommande,
    changerStatutCommande, imprimerRecuVente
} from './globals.js';

import { notify, notifySuccess, notifyError, notifyWarning } from '../core/notifications.js';
import { api } from '../core/api.js';

window.notify = notify;
window.notifySuccess = notifySuccess;
window.notifyError = notifyError;
window.notifyWarning = notifyWarning;
window.api = api;

window.getCookieGlobal = getCookieGlobal;
window.checkSessionRequise = checkSessionRequise;
window.openClientSelector = openClientSelector;
window.closeClientSelector = closeClientSelector;
window.selectionnerDepuisListeNative = selectionnerDepuisListeNative;
window.selectionnerPassagerNative = selectionnerPassagerNative;
window.afficherCommandeInterface = afficherCommandeInterface;
window.afficherLanceur = afficherLanceur;
window.creerClientDepuisSelector = creerClientDepuisSelector;
window.payerCommande = payerCommande;
window.modifierCommande = modifierCommande;
window.supprimerCommande = supprimerCommande;
window.changerStatutCommande = changerStatutCommande;
window.imprimerRecuVente = imprimerRecuVente;

document.addEventListener('alpine:init', () => {
    Alpine.data('posApp', createPosStore);
    Alpine.data('posReservation', posReservation);
    Alpine.data('posSessionDialog', posSessionDialog);
});
