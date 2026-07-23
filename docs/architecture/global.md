# Architecture Globale du Système Hôtelier

## Vue d'ensemble

ERP hôtelier modulaire développé avec Django.

Le système couvre :

- Gestion hôtelière
- Gestion restaurant/bar
- Point de Vente (POS)
- Gestion des stocks
- Paiements & trésorerie
- Comptabilité
- Ressources humaines
- Gestion de paie
- Dashboard décisionnel

---

# Stack Technique

| Technologie | Utilisation |
|---|---|
| Python 3.12 | Backend |
| Django 4.x | Framework principal |
| PostgreSQL | Base de données |
| Redis | Cache / tâches async |
| Bootstrap 5 | Interface utilisateur |
| Gunicorn | Serveur WSGI |
| Nginx | Reverse proxy |
| Mermaid | Diagrammes architecture |

---

# Architecture Modulaire

```text
hotel_project/
│
├── apps/
│   ├── authentication/
│   ├── hotel/
│   ├── restaurant/
│   ├── pos/
│   ├── stock/
│   ├── paiements/
│   ├── tresorerie/
│   ├── comptabilite/
│   ├── rh/
│   ├── paie/
│   ├── dashboard/
│   ├── depenses/
│   ├── achats/
│   └── clients/
│
├── docs/
├── static/
├── media/
└── templates/
