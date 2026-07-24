import { api } from '../core/api.js';
import { getCsrfToken } from '../core/csrf.js';
import { notifyError, notifyWarning } from '../core/notifications.js';

export function getCookieGlobal(name = 'csrftoken') {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : '';
}

export function checkSessionRequise(data) {
    if (data && data.error_code === 'SESSION_REQUISE') {
        notifyError(data.error || 'Session de caisse requise', 5000);
        setTimeout(() => window.location.reload(), 1500);
        return true;
    }
    return false;
}

export function openClientSelector() {
    const d = document.getElementById('client-selector-overlay');
    if (d) d.style.display = 'flex';
    const nom = document.getElementById('new-client-nom');
    if (nom) nom.value = '';
    const tel = document.getElementById('new-client-tel');
    if (tel) tel.value = '';
    const err = document.getElementById('new-client-error');
    if (err) err.classList.add('hidden');
    window.dispatchEvent(new CustomEvent('pos:open-client-selector'));
}

export function closeClientSelector() {
    const d = document.getElementById('client-selector-overlay');
    if (d) d.style.display = 'none';
    window.dispatchEvent(new CustomEvent('pos:close-client-selector'));
}

export function selectionnerDepuisListeNative(clientId) {
    if (!clientId) return;
    window.dispatchEvent(new CustomEvent('pos:select-client-by-id', { detail: clientId }));
    afficherCommandeInterface();
    closeClientSelector();
}

export function selectionnerPassagerNative() {
    window.dispatchEvent(new CustomEvent('pos:set-client-passager'));
    afficherCommandeInterface();
    closeClientSelector();
}

export function afficherCommandeInterface() {
    const lanceur = document.getElementById('lancer-commande-section');
    const cmd = document.getElementById('commande-interface-section');
    if (lanceur) lanceur.style.display = 'none';
    if (cmd) cmd.style.display = 'flex';
}

export function afficherLanceur() {
    const lanceur = document.getElementById('lancer-commande-section');
    const cmd = document.getElementById('commande-interface-section');
    if (lanceur) lanceur.style.display = 'flex';
    if (cmd) cmd.style.display = 'none';
}

export async function creerClientDepuisSelector() {
    const nom = document.getElementById('new-client-nom').value.trim();
    const tel = document.getElementById('new-client-tel').value.trim();
    const errorEl = document.getElementById('new-client-error');
    if (!nom) { errorEl.textContent = 'Le nom est obligatoire'; errorEl.classList.remove('hidden'); return; }
    if (!tel) { errorEl.textContent = 'Le téléphone est obligatoire'; errorEl.classList.remove('hidden'); return; }
    errorEl.classList.add('hidden');
    try {
        const d = await api('/pos/api/clients/creer/', {
            method: 'POST',
            body: JSON.stringify({ telephone: tel, nom: nom })
        });
        if (d.success) {
            window.dispatchEvent(new CustomEvent('pos:select-client', { detail: d.client }));
            afficherCommandeInterface();
            closeClientSelector();
        } else {
            errorEl.textContent = d.error || 'Erreur création';
            errorEl.classList.remove('hidden');
        }
    } catch(e) {
        errorEl.textContent = 'Erreur réseau';
        errorEl.classList.remove('hidden');
    }
}

export function payerCommande(id) {
    const config = window.PAGE_CONFIG || {};
    window.dispatchEvent(new CustomEvent('open-paiement-dialog', {
        detail: { commande_id: id, caisse_id: config.caisse_id }
    }));
}

export function modifierCommande(id) {
    window.dispatchEvent(new CustomEvent('modifier-commande', { detail: { id } }));
}

export function supprimerCommande(id) {
    window.dispatchEvent(new CustomEvent('supprimer-commande', { detail: { id } }));
}

export async function changerStatutCommande(id, statut) {
    try {
        const result = await api(`/pos/api/commandes/${id}/changer-statut/`, {
            method: 'POST',
            body: JSON.stringify({ statut: statut })
        });
        window.dispatchEvent(new CustomEvent('pos:charger-commandes'));
        if (statut === 'SERVIE' || statut === 'LIVREE') {
            window.dispatchEvent(new CustomEvent('pos:rafraichir-stock'));
        }
    } catch(e) {
        checkSessionRequise(e);
        notifyError('Erreur: ' + e.message);
    }
}

export async function imprimerRecuVente(venteId) {
    try {
        const d = await api(`/pos/api/ventes/${venteId}/recu/`);
        if (!d.success) {
            notifyError('Reçu introuvable');
            return;
        }
        const recu = d.recu;
        const now = new Date(recu.date);
        const dateStr = now.toLocaleDateString('fr-FR') + ' ' + now.toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'});
        let lignesHtml = '';
        if (recu.lignes && recu.lignes.length) {
            lignesHtml = '<div class="row row-items items-header"><span class="item-desc">Article</span><span class="item-qty">Qté</span><span class="item-price">PU</span><span class="item-total">Total</span></div>';
            recu.lignes.forEach(l => {
                lignesHtml += '<div class="row row-items"><span class="item-desc">' + l.description + '</span><span class="item-qty">' + l.quantite + '</span><span class="item-price">' + new Intl.NumberFormat('fr-FR').format(l.prix_unitaire) + '</span><span class="item-total">' + new Intl.NumberFormat('fr-FR').format(l.total_ttc) + '</span></div>';
            });
        }
        const styles = '@page{size:80mm auto;margin:0}*{margin:0;padding:0;box-sizing:border-box}body{font-family:"Courier New",monospace;font-size:12px;line-height:1.3;color:#000;width:80mm;padding:2mm 3mm;background:#fff}.header{text-align:center;border-bottom:1px dashed #333;padding-bottom:4px;margin-bottom:6px}.header h1{font-size:16px;font-weight:bold;letter-spacing:1px;text-transform:uppercase}.receipt-title{text-align:center;font-size:14px;font-weight:bold;margin:4px 0}.divider{border-top:1px dashed #333;margin:4px 0}.row{display:flex;justify-content:space-between;font-size:11px}.row-items{display:flex;justify-content:space-between;font-size:11px;padding:1px 0}.items-header{border-bottom:1px dashed #333;padding-bottom:2px;margin-bottom:2px;font-weight:bold}.item-desc{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.item-qty{width:30px;text-align:center}.item-price{width:50px;text-align:right}.item-total{width:60px;text-align:right}.total{font-weight:bold;font-size:13px;border-top:1px solid #333;border-bottom:1px solid #333;padding:4px 0;margin:4px 0}.payment-info{font-size:11px;margin:4px 0}.payment-info div{margin:1px 0}.footer{text-align:center;font-size:10px;margin-top:6px;padding-top:4px;border-top:1px dashed #333}.footer .merci{font-size:14px;font-weight:bold;margin:2px 0}.no-print{text-align:center;margin:10px 0}.no-print button{background:#000;color:#fff;border:none;padding:8px 24px;font-size:14px;border-radius:4px;cursor:pointer;margin:0 4px}.no-print button:hover{opacity:0.8}@media print{.no-print{display:none}@page{margin:0}body{margin:0;padding:2mm 3mm}}';
        const nom = (window.PAGE_CONFIG && window.PAGE_CONFIG.entreprise_nom) || 'ERP Hôtelier';
        const html = '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><title>Reçu ' + recu.reference + '</title><style>' + styles + '</style></head><body>'
            + '<div class="no-print"><button onclick="window.print()">🖨️ Imprimer</button><button onclick="window.close()" style="background:#666;">Fermer</button></div>'
            + '<div class="header"><h1>' + nom + '</h1></div>'
            + '<div class="receipt-title">REÇU DE CAISSE</div>'
            + '<div class="divider"></div>'
            + '<div class="row"><span>Réf: <strong>' + recu.reference + '</strong></span><span>' + dateStr + '</span></div>'
            + (recu.point_vente ? '<div class="row"><span>PV:</span><span>' + recu.point_vente + '</span></div>' : '')
            + (recu.client_nom ? '<div class="row"><span>Client:</span><span>' + recu.client_nom + '</span></div>' : '')
            + '<div class="divider"></div>'
            + (lignesHtml ? lignesHtml + '<div class="divider"></div>' : '')
            + '<div class="row total"><span>MONTANT TOTAL</span><span>' + new Intl.NumberFormat('fr-FR').format(recu.montant) + ' F</span></div>'
            + '<div class="divider"></div>'
            + '<div class="payment-info">'
            + '<div class="row"><span>Mode</span><span><strong>' + recu.mode_label + '</strong></span></div>'
            + (recu.servi_par ? '<div class="row"><span>Servi par:</span><span>' + recu.servi_par + '</span></div>' : '')
            + (recu.caisse ? '<div class="row"><span>Caisse:</span><span>' + recu.caisse + '</span></div>' : '')
            + '</div>'
            + '<div class="footer"><div class="merci">MERCI DE VOTRE VISITE</div><div style="font-size:9px;">' + recu.reference + '</div></div>'
            + '</body></html>';
        const w = window.open('', '_blank', 'width=400,height=600');
        if (w) { w.document.write(html); w.document.close(); }
    } catch(e) { notifyError('Erreur: ' + e.message); }
}
