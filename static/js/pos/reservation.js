import { formatMoney } from '../core/money.js';

export function posReservation() {
    return {
        ouvert: false,
        item: { nom: '', prix: 0, prix_jour: 0, id: null, type_unite: '', capacite: 0 },
        typeTarif: 'DEMI_JOUR',
        heureDebut: '08:00',
        heureFin: '20:00',

        ouvrir(data) {
            this.item = data;
            this.typeTarif = 'DEMI_JOUR';
            this.heureDebut = '08:00';
            this.heureFin = '20:00';
            this.ouvert = true;
        },
        fermer() { this.ouvert = false; },

        setForfait(mode) { this.typeTarif = mode; },

        get dureeHeures() {
            if (this.typeTarif === 'DEMI_JOUR') return 12;
            if (this.typeTarif === 'JOUR') return 24;
            const [h1, m1] = (this.heureDebut || '08:00').split(':').map(Number);
            const [h2, m2] = (this.heureFin || '08:00').split(':').map(Number);
            let diff = (h2 + m2/60) - (h1 + m1/60);
            if (diff <= 0) diff += 24;
            return Math.max(0.5, diff);
        },

        get totalEstime() {
            if (!this.item || !this.item.prix) return 0;
            const tauxJ = this.item.prix_jour || this.item.prix * 24;
            if (this.typeTarif === 'DEMI_JOUR') return Math.round(tauxJ / 2);
            if (this.typeTarif === 'JOUR') return tauxJ;
            return Math.round(this.item.prix * this.dureeHeures);
        },

        descriptionResa() {
            if (this.typeTarif === 'DEMI_JOUR') return 'Demi-journée (12h)';
            if (this.typeTarif === 'JOUR') return 'Journée entière (24h)';
            return this.heureDebut + ' → ' + this.heureFin + ' (' + this.dureeHeures.toFixed(1) + 'h)';
        },

        confirmer() {
            const tauxJ = this.item.prix_jour || (this.item.prix * 24);
            const taux = this.typeTarif === 'DEMI_JOUR' ? Math.round(tauxJ / 2 / 12) :
                         this.typeTarif === 'JOUR' ? tauxJ :
                         this.item.prix;
            const heures = this.dureeHeures;
            const total = this.totalEstime;
            window.dispatchEvent(new CustomEvent('reservation-confirmed', {
                detail: {
                    id: this.item.id, nom: this.item.nom, prix: taux,
                    prix_heure: this.item.prix, prix_jour: this.item.prix_jour || 0,
                    type: 'LOCATION', article_type: 'UNITE',
                    type_tarif: this.typeTarif,
                    heures: heures, total: total,
                    heure_debut: this.typeTarif === 'PERSO' ? this.heureDebut : null,
                    heure_fin: this.typeTarif === 'PERSO' ? this.heureFin : null,
                    type_unite: this.item.type_unite, capacite: this.item.capacite,
                }
            }));
            this.fermer();
        },

        formatMoney(v) { return formatMoney(v); },
    };
}
