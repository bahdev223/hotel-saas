# hotel_project/unfold_config.py
"""
Configuration Unfold pour l'ERP Hôtelier
"""

UNFOLD = {
    # ========== SITE ==========
    "SITE_TITLE": "ERP Hôtelier",
    "SITE_HEADER": "ERP Hôtelier - Gestion Hôtelière",
    "SITE_URL": "/",
    "SITE_ICON": "hotel",
    
    # ========== COULEURS ==========
    "COLORS": {
        "primary": {
            "50": "240 249 255",
            "100": "224 242 254", 
            "200": "186 230 253",
            "300": "125 211 252",
            "400": "56 189 248",
            "500": "0 112 150",
            "600": "2 132 199",
            "700": "3 105 161",
            "800": "7 89 133",
            "900": "12 74 110",
        },
        "secondary": {
            "500": "212 163 91",
        },
    },
    
    # ========== SIDEBAR ==========
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "TABLEAU DE BORD",
                "separator": True,
                "items": [
                    {
                        "title": "Vue d'ensemble",
                        "icon": "dashboard",
                        "link": "/admin/",
                    },
                    {
                        "title": "Dashboard personnalisé",
                        "icon": "analytics",
                        "link": "/admin/dashboard/",
                    },
                ],
            },
            {
                "title": "HOTEL",
                "separator": True,
                "items": [
                    {
                        "title": "Chambres",
                        "icon": "bed",
                        "link": "/admin/chambres/chambremodel/",
                    },
                    {
                        "title": "Réservations",
                        "icon": "calendar_today",
                        "link": "/admin/reservations/reservationmodel/",
                    },
                    {
                        "title": "Clients",
                        "icon": "people",
                        "link": "/admin/clients/clientmodel/",
                    },
                ],
            },
            {
                "title": "RESTAURATION",
                "separator": True,
                "items": [
                    {
                        "title": "Recettes",
                        "icon": "restaurant",
                        "link": "/admin/recettes/recettemodel/",
                    },
                    {
                        "title": "Commandes Restaurant",
                        "icon": "room_service",
                        "link": "/admin/restaurant/commandemodel/",
                    },
                    {
                        "title": "Commandes Bar",
                        "icon": "local_bar",
                        "link": "/admin/bar/commandebar/",
                    },
                    {
                        "title": "Tables",
                        "icon": "table_restaurant",
                        "link": "/admin/restaurant/table/",
                    },
                ],
            },
            {
                "title": "STOCK",
                "separator": True,
                "items": [
                    {
                        "title": "Produits",
                        "icon": "inventory_2",
                        "link": "/admin/stock/produit/",
                    },
                    {
                        "title": "Mouvements",
                        "icon": "swap_horiz",
                        "link": "/admin/stock/mouvementstock/",
                    },
                    {
                        "title": "Alerte stock",
                        "icon": "warning",
                        "link": "/admin/stock/produit/?statut=RUPTURE",
                    },
                ],
            },
            {
                "title": "RESSOURCES HUMAINES",
                "separator": True,
                "items": [
                    {
                        "title": "Employés",
                        "icon": "badge",
                        "link": "/admin/rh/employe/",
                    },
                    {
                        "title": "Contrats",
                        "icon": "description",
                        "link": "/admin/rh/contrat/",
                    },
                    {
                        "title": "Congés",
                        "icon": "beach_access",
                        "link": "/admin/rh/conge/",
                    },
                    {
                        "title": "Absences",
                        "icon": "sick",
                        "link": "/admin/rh/absence/",
                    },
                    {
                        "title": "Pointages",
                        "icon": "access_time",
                        "link": "/admin/rh/pointage/",
                    },
                    {
                        "title": "Départements",
                        "icon": "account_tree",
                        "link": "/admin/rh/departement/",
                    },
                    {
                        "title": "Postes",
                        "icon": "work",
                        "link": "/admin/rh/poste/",
                    },
                ],
            },
            {
                "title": "FINANCES",
                "separator": True,
                "items": [
                    {
                        "title": "Factures",
                        "icon": "receipt",
                        "link": "/admin/facturation/facture/",
                    },
                    {
                        "title": "Paiements",
                        "icon": "payments",
                        "link": "/admin/facturation/paiement/",
                    },
                    {
                        "title": "Comptabilité",
                        "icon": "account_balance",
                        "link": "/admin/comptabilite/comptemodel/",
                    },
                    {
                        "title": "Dépenses",
                        "icon": "shopping_cart",
                        "link": "/admin/depenses/depensemodel/",
                    },
                ],
            },
            {
                "title": "AUTHENTIFICATION",
                "separator": True,
                "items": [
                    {
                        "title": "Utilisateurs",
                        "icon": "admin_panel_settings",
                        "link": "/admin/auth/user/",
                    },
                    {
                        "title": "Groupes",
                        "icon": "group",
                        "link": "/admin/auth/group/",
                    },
                    {
                        "title": "Profils",
                        "icon": "badge",
                        "link": "/admin/authentication/profile/",
                    },
                    {
                        "title": "Tokens",
                        "icon": "key",
                        "link": "/admin/authentication/passwordresettoken/",
                    },
                ],
            },
            {
                "title": "ADMINISTRATION",
                "separator": True,
                "items": [
                    {
                        "title": "Permissions",
                        "icon": "lock",
                        "link": "/admin/auth/permission/",
                    },
                    {
                        "title": "Logs",
                        "icon": "history",
                        "link": "/admin/logs/",
                    },
                ],
            },
        ],
    },
    
    # ========== DASHBOARD ==========
    "DASHBOARD": {
        "show_recent_actions": True,
        "recent_actions_limit": 10,
        "cards": [
            {
                "title": "Employés actifs",
                "icon": "badge",
                "color": "primary",
                "link": "/admin/rh/employe/?actif__exact=1",
            },
            {
                "title": "Chambres occupées",
                "icon": "bed",
                "color": "secondary",
                "link": "/admin/chambres/chambremodel/?statut=OCCUPEE",
            },
            {
                "title": "Commandes aujourd'hui",
                "icon": "restaurant",
                "color": "success",
                "link": "/admin/restaurant/commandemodel/",
            },
            {
                "title": "Chiffre d'affaires mois",
                "icon": "payments",
                "color": "info",
                "link": "/admin/facturation/facture/",
            },
            {
                "title": "Utilisateurs actifs",
                "icon": "people",
                "color": "warning",
                "link": "/admin/auth/user/?is_active__exact=1",
            },
        ],
    },
    
    # ========== FILTRES ==========
    "TABS": [
        {
            "models": ["rh.Employe"],
            "items": [
                {
                    "title": "Tous les employés",
                    "link": "/admin/rh/employe/",
                },
                {
                    "title": "Employés actifs",
                    "link": "/admin/rh/employe/?actif__exact=1",
                },
                {
                    "title": "Sans compte utilisateur",
                    "link": "/admin/rh/employe/?user__isnull=True",
                },
            ],
        },
        {
            "models": ["rh.Conge"],
            "items": [
                {
                    "title": "En attente",
                    "link": "/admin/rh/conge/?statut=En+attente",
                },
                {
                    "title": "Validés",
                    "link": "/admin/rh/conge/?statut=Valide",
                },
            ],
        },
        {
            "models": ["chambres.ChambreModel"],
            "items": [
                {
                    "title": "Chambres libres",
                    "link": "/admin/chambres/chambremodel/?statut=LIBRE",
                },
                {
                    "title": "Chambres occupées",
                    "link": "/admin/chambres/chambremodel/?statut=OCCUPEE",
                },
                {
                    "title": "En nettoyage",
                    "link": "/admin/chambres/chambremodel/?statut=NETTOYAGE",
                },
            ],
        },
        {
            "models": ["comptabilite.CompteModel"],
            "items": [
                {
                    "title": "Tous les comptes",
                    "link": "/admin/comptabilite/comptemodel/",
                },
                {
                    "title": "Comptes de bilan",
                    "link": "/admin/comptabilite/comptemodel/?categorie=bilan",
                },
                {
                    "title": "Comptes de résultat",
                    "link": "/admin/comptabilite/comptemodel/?categorie=resultat",
                },
            ],
        },
        {
            "models": ["auth.User"],
            "items": [
                {
                    "title": "Tous les utilisateurs",
                    "link": "/admin/auth/user/",
                },
                {
                    "title": "Utilisateurs actifs",
                    "link": "/admin/auth/user/?is_active__exact=1",
                },
                {
                    "title": "Administrateurs",
                    "link": "/admin/auth/user/?is_staff__exact=1",
                },
            ],
        },
    ],
    
    # ========== EXTENSIONS ==========
    "EXTENSIONS": {
        "modeltranslation": {
            "flags": {
                "fr": "FR",
                "en": "EN",
            },
        },
        "import_export": True,
    },
}

