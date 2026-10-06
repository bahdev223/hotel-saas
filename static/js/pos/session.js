import { api } from '../core/api.js';

export function posSessionDialog() {
    return {
        step: 'cloture',
        session: null,
        nouveauPlanning: null,
        loading: false,
        erreur: '',
        rafDepotRequis: false,
        sessionOuverte: false,
        pointVenteId: null,
        caisseId: null,
        employeId: null,
        requiresCashSession: false,
        comptage: {
            especes_comptees: '',
            montant_carte: '',
            montant_mobile: '',
            montant_cheque: '',
            notes: '',
        },

        init() {
            const config = window.PAGE_CONFIG || {};
            this.rafDepotRequis = config.raf_depot_requis || false;
            this.sessionOuverte = config.caisse_ouverte || false;
            this.pointVenteId = config.point_vente_id;
            this.caisseId = config.caisse_id;
            this.employeId = config.employe_id;
            this.requiresCashSession = !!config.requires_cash_session;
            this.session = config.session_a_fermer || this.session;
            if (this.session) {
                this.comptage.especes_comptees = String(
                    this.session.especes_attendues ?? this.session.solde_initial ?? ''
                );
                this.comptage.montant_carte = String(this.session.total_carte ?? '');
                this.comptage.montant_mobile = String(this.session.total_mobile_money ?? '');
                this.comptage.montant_cheque = String(this.session.total_cheque ?? '');
            }
            this.nouveauPlanning = config.nouveau_planning || this.nouveauPlanning;

            if (this.session) {
                this.step = 'cloture';
            } else if (this.nouveauPlanning) {
                this.step = 'ouverture';
            } else if (!this.sessionOuverte && this.requiresCashSession) {
                this.step = 'aucun_planning';
            } else {
                this.step = 'none';
            }
            window.addEventListener('pos:session-cloture-requise', (e) => {
                this.session = e.detail.session;
                this.nouveauPlanning = e.detail.nouveauPlanning;
                this.step = 'cloture';
            });
        },

        async cloturer() {
            if (this.loading || !this.session) return;
            this.loading = true;
            this.erreur = '';
            try {
                const data = await api('/pos/api/sessions/fermer/', {
                    method: 'POST',
                    body: JSON.stringify({
                        session_id: this.session.id,
                        especes_comptees: this.comptage.especes_comptees,
                        montant_carte: this.comptage.montant_carte || null,
                        montant_mobile: this.comptage.montant_mobile || null,
                        montant_cheque: this.comptage.montant_cheque || null,
                        notes: this.comptage.notes || '',
                    })
                });
                if (!data.success) {
                    this.erreur = data.error || 'Erreur lors de la fermeture';
                    this.loading = false;
                    return;
                }
                if (this.nouveauPlanning) {
                    this.step = 'ouverture';
                    this.session = null;
                    this.loading = false;
                } else {
                    window.location.reload();
                }
            } catch(e) {
                this.erreur = e?.message || 'Erreur réseau';
                this.loading = false;
            }
        },

        async ouvrirSession() {
            if (this.loading) return;
            this.loading = true;
            this.erreur = '';
            try {
                const data = await api('/pos/api/sessions/ouvrir/', {
                    method: 'POST',
                    body: JSON.stringify({
                        caisse_id: this.caisseId,
                        point_vente_id: this.pointVenteId,
                        caissier_id: this.employeId,
                        debut_prevu: this.nouveauPlanning?.debut || null,
                        fin_prevu: this.nouveauPlanning?.fin || null,
                    })
                });
                if (data.success) {
                    window.location.reload();
                } else {
                    this.erreur = data.error || 'Erreur ouverture session';
                    this.loading = false;
                }
            } catch(e) {
                this.erreur = 'Erreur réseau';
                this.loading = false;
            }
        },

        formatMoney(v) { return new Intl.NumberFormat('fr-FR').format(v || 0); },
    };
}
