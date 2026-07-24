import { api } from '../core/api.js';
import { getCsrfToken } from '../core/csrf.js';
import { notifyError, notifyWarning, notifySuccess } from '../core/notifications.js';
import { formatMoney } from '../core/money.js';

export function createPosStore() {
    return {
        categories: {},
        sous_categories: {},
        activeCategorie: null,
        activeSousCategorie: null,
        panier: [],
        typeCommande: 'SUR_PLACE',
        selectedClient: null,
        showClientSelector: false,
        clientId: '',
        clientNom: '',
        selectedClientId: '',
        clientsList: [],
        clientTelephone: '',
        adresseLivraison: '',
        pointVenteSlug: '',
        commandes: [],
        showCommandes: false,
        fraisLivraison: 0,
        entrepotDisponibles: [],
        entrepotActif: null,
        stocksParEntrepot: {},
        planningBloque: false,
        blocageMessage: 'Planning terminé',
        blocageLoading: false,
        blocageErreur: '',
        planningFinHeure: null,
        searchTerm: '',
        pointVenteId: null,

        async init() {
            const c = window.PAGE_CONFIG || {};
            this.categories = c.categories || {};
            this.sous_categories = c.sous_categories || {};
            this.activeCategorie = c.active_categorie || Object.keys(c.categories || {})[0] || '';
            this.entrepotDisponibles = c.entrepots_disponibles || [];
            this.entrepotActif = c.entrepot_par_defaut || null;
            this.stocksParEntrepot = c.stocks_par_entrepot || {};
            this.pointVenteSlug = c.point_vente_slug || '';
            this.planningFinHeure = c.planning_fin_heure || null;
            this.pointVenteId = c.point_vente_id;

            this.selectedClient = null;
            await this.chargerClients();
            await this.chargerProduits();
            await this.chargerCommandes();
            setInterval(() => { this.chargerCommandes(); }, 15000);
            setInterval(() => this.rafraichirStock(), 30000);
            setInterval(() => this.verifierSession(), 35000);
            this.$watch('activeCategorie', () => this.searchTerm = '');
            window.addEventListener('paiement-effectue', () => {
                this.chargerCommandes();
                this.rafraichirStock();
            });
            window.addEventListener('reservation-confirmed', (e) => {
                this.panier.push(e.detail);
            });
            window.addEventListener('modifier-commande', (e) => this._modifierCommande(e.detail.id));
            window.addEventListener('supprimer-commande', (e) => this._supprimerCommande(e.detail.id));
            
            // Écouteurs pour interactions depuis JS natif (globals.js)
            window.addEventListener('pos:open-client-selector', () => this.showClientSelector = true);
            window.addEventListener('pos:close-client-selector', () => this.showClientSelector = false);
            window.addEventListener('pos:select-client-by-id', (e) => {
                const c = this.clientsList.find(x => String(x.id) === String(e.detail));
                if (c) {
                    this.selectedClient = c;
                    this.clientId = c.id;
                    this.clientNom = c.nom;
                }
            });
            window.addEventListener('pos:set-client-passager', () => {
                this.selectedClient = { id: '', nom: 'Client Passager', telephone: '' };
                this.clientId = '';
                this.clientNom = '';
            });
            window.addEventListener('pos:select-client', (e) => {
                this.selectedClient = e.detail;
                this.clientId = e.detail.id;
                this.clientNom = e.detail.nom;
                this.showClientSelector = false;
                this.chargerClients();
            });
            window.addEventListener('pos:charger-commandes', () => this.chargerCommandes());
            window.addEventListener('pos:rafraichir-stock', () => this.rafraichirStock());
        },

        clickItem(item) {
            if (item.type === 'LOCATION') {
                if (item.statut_unite === 'OCCUPEE') {
                    notifyWarning('Cette chambre est déjà occupée');
                    return;
                }
                window.dispatchEvent(new CustomEvent('open-reservation', { detail: item }));
            } else {
                this.ajouterAuPanier(item);
            }
        },

        get commandesParStatut() {
            const grouped = {};
            const labels = ['EN_ATTENTE', 'EN_PREPARATION', 'PRETE', 'SERVIE', 'LIVREE', 'ANNULEE'];
            for (const st of labels) {
                const items = this.commandes.filter(c => c.statut_code === st);
                if (items.length) grouped[this.statutLabel(st)] = items;
            }
            return grouped;
        },

        get commandesFiltrees() {
            if (!this.filtreStatut) return this.commandes;
            return this.commandes.filter(c => this.statutLabel(c.statut_code) === this.filtreStatut);
        },

        get itemsFiltres() {
            const items = this.categories[this.activeCategorie] || [];
            let filtered = this.activeSousCategorie
                ? items.filter(it => it.sous_categorie === this.activeSousCategorie)
                : items;
            if (this.searchTerm) {
                const q = this.searchTerm.toLowerCase();
                filtered = filtered.filter(it => it.nom.toLowerCase().includes(q));
            }
            return filtered;
        },

        _buildProduitsUrl() {
            let url = '/pos/api/produits/';
            const params = new URLSearchParams();
            if (this.pointVenteSlug) params.set('point_vente_slug', this.pointVenteSlug);
            if (this.entrepotActif) params.set('entrepot_id', this.entrepotActif);
            const qs = params.toString();
            if (qs) url += '?' + qs;
            return url;
        },

        async chargerProduits() {
            try {
                const data = await api(this._buildProduitsUrl());
                if (data.success && data.categories) {
                    this.categories = data.categories;
                    this.sous_categories = data.sous_categories || {};
                    if (!this.activeCategorie) {
                        this.activeCategorie = Object.keys(data.categories)[0] || '';
                    }
                    let total = 0, avecImage = 0, premiers = [];
                    for (const cat in data.categories) {
                        for (const item of data.categories[cat]) {
                            total++;
                            if (item.image) {
                                avecImage++;
                                if (premiers.length < 3) premiers.push(item.image);
                            }
                        }
                    }
                    console.debug(`[POS] ${total} produits chargés, ${avecImage} avec image`);
                    if (premiers.length > 0) {
                        const testImg = new Image();
                        testImg.onload = () => console.debug('[POS] TEST IMAGE OK:', premiers[0]);
                        testImg.onerror = () => console.debug('[POS] TEST IMAGE ERROR:', premiers[0]);
                        testImg.src = premiers[0];
                    }
                }
            } catch(e) { console.error(e); }
        },

        async rafraichirStock() {
            try {
                const data = await api(this._buildProduitsUrl());
                if (!data.success || !data.categories) return;
                const stockById = {};
                for (const cat in data.categories) {
                    for (const it of data.categories[cat]) {
                        if (it.article_type === 'PRODUIT') stockById[it.id] = it.stock;
                    }
                }
                for (const cat in this.categories) {
                    for (const it of this.categories[cat]) {
                        if (it.article_type === 'PRODUIT' && it.id in stockById) {
                            it.stock = stockById[it.id];
                        }
                    }
                }
            } catch(e) { /* silencieux */ }
        },

        changerEntrepot() {
            this.chargerProduits();
        },

        async verifierSession() {
            if (this.planningBloque) return;
            try {
                const d = await api(`/pos/api/sessions/verifier-etat/${this.pointVenteId}/`);
                if (!d.success) return;
                if (d.planning_expire && d.session_a_fermer) {
                    window.dispatchEvent(new CustomEvent('pos:session-cloture-requise', {
                        detail: { session: d.session_a_fermer, nouveauPlanning: d.nouveau_planning }
                    }));
                } else if (!d.session_active && !d.nouveau_planning) {
                    this.planningBloque = true;
                    this.blocageMessage = 'Session fermée';
                }
            } catch (e) {}
        },

        async cloturerSessionBloquee() {
            window.location.reload();
        },

        async _modifierCommande(id) {
            try {
                const d = await api(`/pos/api/commandes/${id}/`);
                if (!d.success || !d.commande) {
                    notifyError('Commande introuvable');
                    return;
                }
                const cmd = d.commande;
                const lignes = (cmd.lignes || []).map(l => {
                    const base = { id: l.article_id, nom: l.article, prix: l.prix_unitaire, total: l.total };
                    if (l.type === 'LOCATION') {
                        return Object.assign(base, { heures: l.quantite || 1, type: 'LOCATION', article_type: 'UNITE' });
                    }
                    if (l.type === 'MENU') {
                        return Object.assign(base, { quantite: l.quantite || 1, type: 'RESTAURANT', article_type: 'MENU' });
                    }
                    return Object.assign(base, { quantite: l.quantite || 1, type: 'BRASSERIE', article_type: 'PRODUIT' });
                });
                this.panier = lignes;
                if (cmd.client_id) { this.clientId = String(cmd.client_id); this.clientNom = cmd.client_nom || ''; }
                this.showCommandes = false;
                await api(`/pos/api/commandes/${id}/changer-statut/`, {
                    method: 'POST',
                    body: JSON.stringify({ statut: 'ANNULEE' })
                });
                this.chargerCommandes();
            } catch(e) { notifyError('Erreur modification: ' + e.message); }
        },

        async _supprimerCommande(id) {
            if (!confirm('Supprimer cette commande ?')) return;
            try {
                await api(`/pos/api/commandes/${id}/changer-statut/`, {
                    method: 'POST',
                    body: JSON.stringify({ statut: 'ANNULEE' })
                });
                this.chargerCommandes();
            } catch(e) { notifyError('Erreur suppression: ' + e.message); }
        },

        get tempsRestant() {
            if (!this.planningFinHeure) return null;
            const [h, m] = this.planningFinHeure.split(':').map(Number);
            const fin = new Date();
            fin.setHours(h, m, 0, 0);
            const diff = (fin - new Date()) / 1000;
            return Math.max(0, Math.floor(diff));
        },

        afficheTempsRestant() {
            if (this.tempsRestant === null) return '--';
            const h = Math.floor(this.tempsRestant / 3600);
            const m = Math.floor((this.tempsRestant % 3600) / 60);
            return `${h}h${String(m).padStart(2, '0')}min`;
        },

        async chargerClients() {
            try {
                const d = await api('/pos/api/clients/recherche/?search=');
                if (d.success) this.clientsList = d.clients;
            } catch(e) { console.error(e); }
        },

        ouvrirSelectorClient() {
            const { openClientSelector } = window;
            if (openClientSelector) openClientSelector();
        },

        closeClientSelector() {
            this.showClientSelector = false;
        },

        selectionnerDepuisListe() {
            if (!this.selectedClientId) return;
            const c = this.clientsList.find(x => x.id === this.selectedClientId);
            if (c) {
                this.selectedClient = c;
                this.clientId = c.id;
                this.clientNom = c.nom;
                this.showClientSelector = false;
            }
        },

        selectionnerPassager() {
            this.selectedClient = { id: '', nom: 'Client Passager', telephone: '' };
            this.clientId = '';
            this.clientNom = '';
            this.showClientSelector = false;
        },

        changerClient() {
            this.selectedClient = null;
            this.clientId = '';
            this.clientNom = '';
            this.selectedClientId = '';
            const { afficherLanceur } = window;
            if (afficherLanceur) afficherLanceur();
        },

        statutLabel(code) {
            const map = {
                'EN_ATTENTE': 'En attente',
                'EN_PREPARATION': 'Préparation',
                'PRETE': 'Prête',
                'EN_COURS_DE_LIVRAISON': 'Livraison',
                'SERVIE': 'Servie',
                'LIVREE': 'Livrée',
                'ANNULEE': 'Annulée',
            };
            return map[code] || code;
        },

        statutClass(code) {
            const map = {
                'EN_ATTENTE': 'bg-yellow-900/30 text-yellow-300',
                'EN_PREPARATION': 'bg-blue-900/30 text-blue-300',
                'PRETE': 'bg-green-900/30 text-green-300',
                'EN_COURS_DE_LIVRAISON': 'bg-purple-900/30 text-purple-300',
                'SERVIE': 'bg-gray-700 text-on-surface',
                'LIVREE': 'bg-gray-700 text-on-surface',
                'ANNULEE': 'bg-red-900/30 text-red-300',
            };
            return map[code] || 'bg-surface-container-highest';
        },

        async chargerCommandes() {
            try {
                const d = await api(`/pos/api/commandes/liste/?point_vente=${this.pointVenteId}`);
                if (d.success) {
                    this.commandes = d.commandes;
                }
            } catch(e) { console.error(e); }
        },

        boutonsStatut(c) {
            let btns = '';
            if (c.statut_code === 'EN_ATTENTE') {
                btns += `<button onclick="modifierCommande(${c.id})" title="Modifier" class="text-xs bg-blue-600 text-white w-7 h-7 rounded-full hover:bg-blue-700"><i class="fas fa-edit"></i></button>`;
                btns += `<button onclick="supprimerCommande(${c.id})" title="Supprimer" class="text-xs bg-red-600 text-white w-7 h-7 rounded-full hover:bg-red-700"><i class="fas fa-trash"></i></button>`;
                btns += `<button onclick="payerCommande(${c.id})" class="text-xs bg-secondary text-black px-3 py-1.5 rounded hover:bg-secondary/80 font-bold">Payer</button>`;
            }
            return btns;
        },

        get total() {
            return this.panier.reduce((sum, item) => sum + item.total, 0);
        },

        ajouterAuPanier(item) {
            if (item.type === 'LOCATION') {
                if (item.statut_unite === 'OCCUPEE') { notifyWarning('Cette unité est déjà occupée'); return; }
                this.panier.push({
                    id: item.id,
                    nom: item.nom,
                    prix: item.prix,
                    type: item.type,
                    article_type: item.article_type,
                    heures: 1,
                    total: item.prix,
                    type_unite: item.type_unite,
                    capacite: item.capacite,
                });
                return;
            }
            const stockDispo = item.stock !== undefined ? item.stock : 999;
            if (stockDispo <= 0) {
                notifyWarning('Stock insuffisant pour ' + item.nom);
                return;
            }
            const existing = this.panier.find(i => i.id === item.id && i.article_type === item.article_type);
            const qteActuelle = existing ? existing.quantite : 0;
            if (qteActuelle >= stockDispo) {
                notifyWarning('Stock insuffisant pour ' + item.nom + ' (' + stockDispo + ' disponible(s))');
                return;
            }
            if (existing) {
                existing.quantite++;
                existing.total = existing.quantite * existing.prix;
            } else {
                this.panier.push({
                    id: item.id,
                    nom: item.nom,
                    prix: item.prix,
                    type: item.type,
                    article_type: item.article_type,
                    quantite: 1,
                    total: item.prix
                });
            }
        },

        modifierQuantite(index, delta) {
            const item = this.panier[index];
            if (item.type === 'LOCATION') {
                item.heures = Math.max(1, (item.heures || 1) + delta);
                item.total = item.heures * item.prix;
                return;
            }
            const newQte = (item.quantite || 1) + delta;
            if (newQte <= 0) {
                this.panier.splice(index, 1);
            } else {
                item.quantite = newQte;
                item.total = item.quantite * item.prix;
            }
        },

        supprimerDuPanier(index) {
            this.panier.splice(index, 1);
        },

        annulerCommande() {
            if (confirm('Annuler la commande ?')) {
                this.panier = [];
                this.clientNom = '';
                this.clientTelephone = '';
                this.adresseLivraison = '';
                this.fraisLivraison = 0;
            }
        },

        async validerCommande() {
            if (this.panier.length === 0) {
                notifyWarning('Panier vide');
                return;
            }

            const lignes = this.panier.map(item => {
                if (item.type === 'LOCATION') {
                    return {
                        type_article: 'LOCATION',
                        unite_id: item.id,
                        heures: item.heures,
                        prix: item.prix,
                        total: item.total,
                    };
                }
                return {
                    type_article: item.article_type,
                    [item.article_type === 'MENU' ? 'menu_id' : 'produit_id']: item.id,
                    quantite: item.quantite,
                };
            });

            try {
                const data = await api('/pos/api/commandes/creer/', {
                    method: 'POST',
                    body: JSON.stringify({
                        point_vente_slug: this.pointVenteSlug,
                        type_commande: this.typeCommande,
                        client_id: this.clientId || null,
                        client_nom: this.clientNom || '',
                        client_telephone: this.clientTelephone || '',
                        adresse_livraison: this.adresseLivraison || '',
                        frais_livraison: this.typeCommande === 'LIVRAISON' ? (Number(this.fraisLivraison) || 0) : 0,
                        entrepot_id: this.entrepotActif,
                        notes: '',
                        lignes: lignes
                    })
                });
                if (data.success) {
                    this.panier = [];
                    this.clientNom = '';
                    this.clientTelephone = '';
                    this.adresseLivraison = '';
                    this.fraisLivraison = 0;
                    this.chargerCommandes();
                } else {
                    const { checkSessionRequise } = window;
                    if (checkSessionRequise && checkSessionRequise(data)) return;
                    notifyError(data.error);
                }
            } catch(e) {
                notifyError('Erreur réseau');
            }
        },

        formatMoney(value) {
            return formatMoney(value);
        },

        getCookie(name) {
            return getCsrfToken();
        },
    };
}
