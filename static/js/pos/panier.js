import { api } from '../core/api.js';
import { formatMoney } from '../core/money.js';

export function ajouterAuPanier(panier, article, quantite = 1) {
    const existant = panier.find(l => l.id === article.id);
    if (existant) {
        existant.quantite += quantite;
    } else {
        panier.push({
            id: article.id,
            nom: article.nom,
            prix: article.prix_vente,
            quantite,
            total: () => this.quantite * this.prix,
        });
    }
}

export function retirerDuPanier(panier, index) {
    panier.splice(index, 1);
}

export function totalPanier(panier) {
    return panier.reduce((s, l) => s + l.quantite * l.prix, 0);
}

export async function validerPanier(panier, data = {}) {
    return api('/pos/api/commandes/creer/', {
        method: 'POST',
        body: JSON.stringify({
            lignes: panier.map(l => ({ article_id: l.id, quantite: l.quantite })),
            ...data,
        }),
    });
}
