# HôtelERP

Solution de gestion hôtelière complète et modulaire.

## Modules

- **Dashboard** — Tableau de bord personnalisable
- **Hôtel** — Chambres, types de chambres, réservations, séjours, tarification dynamique
- **Restauration** — Restaurant, bar, commandes
- **Point de Vente (POS)** — Ventes, sessions de caisse, encaissement, commandes, livraisons, planning caissiers
- **Stock** — Produits, mouvements (entrées/sorties/transferts/ajustements), inventaires, valorisation PMP/FIFO, lots, numéros de série, nomenclature, conditionnements, journal de stock
- **RH** — Employés, contrats, congés, pointage
- **Paie** — Gestion des salaires, bulletins, rubriques
- **Trésorerie** — Caisse, banque, rapprochement, transferts
- **Facturation** — Factures, devis, avoirs
- **Comptabilité** — Plan comptable SYSCOHADA, écritures, journaux, bilan, compte résultat
- **Catalogue** — Produits et services
- **Entreprises** — Socle multi-établissement : entreprise, établissements, configuration, modules, séquences documentaires
- **Fournisseurs** — Gestion des fournisseurs et achats

## Architecture

### Socle Entreprises (Lot 1)
- Modèle `Entreprise` portant l'identité légale et commerciale
- Modèle `Etablissement` pour les établissements secondaires
- `ConfigurationEntreprise` : devise, symbole, couleurs
- `ConfigurationHotelière` : politique d'annulation, check-in/check-out
- `ModuleEntreprise` : activation modulaire par entreprise
- `SequenceDocument` : templates de numérotation (factures, réservations, etc.)
- Context processor injectant `entreprise_courante` dans tous les templates

### Tarification Hôtelière
- `TypeChambre` : catégories de chambres avec capacité et tarif de base
- `TypeTarif` : unités tarifaires (Standard, Petit-déjeuner inclus, Week-end, etc.)
- `PlanTarifaire` : regroupement de types tarifaires
- `TarifChambre` : prix spécifique (type chambre × plan × type tarif)
- `CreneauTarifaire` : variation saisonnière
- Service de calcul : `trouver_tarifs`, `trouver_tarif_optimal`, `calculer_montant`

### Cycle Réservation / Séjour (Lot 3)
- `Reservation` : intention (statuts : confirmée, en_attente, annulée)
- `ReservationChambre` : lignes de réservation avec tarif figé
- `Sejour` : occupation réelle (check-in → check-out)
- `Occupant` : occupants par séjour
- `ServiceSejour` : consommations extra (minibar, room service, etc.)
- `HistoriqueStatutChambre` : traçabilité des changements d'état
- Services : check-in (with or without reservation), check-out (calcul, paiement, libération), disponibilité, réservation

### Moteur Stock (django-stocks)
- Architecture générique : articles, dépôts, emplacements, lots, numéros de série
- Mouvements séparant **nature** (ENTREE/SORTIE/AJUSTEMENT) de **source** (ACHAT/VENTE/PRODUCTION/TRANSFERT/INVENTAIRE/CASSE/...)
- Valorisation : PMP (prix moyen pondéré), FIFO (couches), coût standard
- Inventaire : comparaison théorique/réel, validation avec ajustement automatique
- Journal de stock : état avant/après chaque mouvement
- Nomenclature : recettes / listes de composants avec taux de perte
- Conditionnement : facteurs de conversion multi-unités par article
- 19 sources système prédéfinies

### Nettoyage Templates (Lot 2)
- Toutes les références "HotelERP" remplacées par le nom dynamique de l'entreprise
- Logo avec fallback statique via le context processor
- Copyright dynamique

## Installation

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_data        # Données de démo ERP
python manage.py seed_stocks      # Données de démo Stock
python manage.py runserver
```

## Déploiement

Compatible Coolify / Heroku. Voir `Procfile` et `runtime.txt`.

## Licence

Propriétaire — Tous droits réservés.
