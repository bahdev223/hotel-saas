# HôtelERP

Solution de gestion hôtelière complète et modulaire.

## Modules

- **Dashboard** — Tableau de bord personnalisable
- **Hôtel** — Chambres, réservations, clients
- **Restauration** — Restaurant, bar, commandes
- **Stock** — Produits, mouvements, inventaire
- **RH** — Employés, contrats, congés, pointage
- **Paie** — Gestion des salaires
- **Trésorerie** — Caisse, banque, rapprochement
- **Facturation** — Factures, devis, avoirs
- **Comptabilité** — Plan comptable, écritures
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
