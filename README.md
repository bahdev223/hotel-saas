# HôtelERP

Solution de gestion hôtelière complète et modulaire.

## Modules

- **Dashboard** — Tableau de bord personnalisable
- **Hôtel** — Chambres, réservations, clients
- **Restauration** — Restaurant, bar, commandes
- **Point de Vente (POS)** — Ventes, sessions de caisse, encaissement, commandes, livraisons, planning caissiers
- **Stock** — Produits, mouvements, inventaire, achats, fournisseurs, lots
- **RH** — Employés, contrats, congés, pointage
- **Paie** — Gestion des salaires, bulletins, rubriques
- **Trésorerie** — Caisse, banque, rapprochement, transferts
- **Facturation** — Factures, devis, avoirs
- **Comptabilité** — Plan comptable SYSCOHADA, écritures, journaux, bilan, compte résultat
- **Catalogue** — Produits et services

## Installation

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Déploiement

Compatible Coolify / Heroku. Voir `Procfile` et `runtime.txt`.

## Licence

Propriétaire — Tous droits réservés.
