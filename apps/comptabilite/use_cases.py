"""
═══════════════════════════════════════════════════════════════
USE CASE COMPTABLE — Spécification des écritures métier
═══════════════════════════════════════════════════════════════

Chaque use case documente :
  Action métier  →  Écriture comptable  →  Impact soldes

──── Plan comptable SYSCOHADA (extrait utilisé) ──────────────
  101    Capital social
  129    Résultat de l'exercice
  2xx    Immobilisations
  28x    Amortissements
  31x    Stocks
  401    Fournisseurs
  404    Fournisseurs d'immobilisations
  411    Clients
  419    Avances clients
  421    Personnel – rémunérations dues
  425    Personnel – avances
  431    Organismes sociaux (CNPS)
  443    TVA collectée
  447    État – impôts
  521    Banque
  571    Caisse
  57x    Caisse/Guichet
  6xx    Charges
  603    Variation de stocks
  658    Charges diverses
  661    Charges de personnel
  68x    Dotations aux amortissements
  70x    Produits des ventes
  706    Prestations de services
  707    Ventes de marchandises
  758    Produits divers
  7xx    Produits

──── Codes journaux ──────────────────────────────────────────
  VN     Ventes
  AC     Achats
  CS     Caisse
  BQ     Banque
  TR     Transferts
  ST     Stock
  PA     Paie
  OD     Opérations diverses
  CL     Clôture
  INV    Investissements

═══════════════════════════════════════════════════════════════
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 1 : Vente comptant
# ─────────────────────────────────────────────────────────────
use_case_1 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 1 : Vente comptant (client passager)                    │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Client anonyme, commande au bar/restaurant.               │
│   Paiement immédiat en espèces.                             │
│   Montant : 50 000 FCFA                                     │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   571 Caisse             50 000   Débit                      │
│     707 Ventes                     Crédit   50 000           │
│                                                              │
│ Journal : VN (Ventes)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : +50 000                                        │
│   Client    : aucun (passager)                               │
│   Fournisseur: aucun                                         │
│   Résultat  : +50 000 (produit)                              │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 2 : Vente sur compte client (solde prépayé)
# ─────────────────────────────────────────────────────────────
use_case_2 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 2 : Vente sur compte client (solde prépayé)             │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Client A a déposé 100 000 FCFA sur son compte.            │
│   Il consomme 30 000 FCFA.                                  │
│   Aucun mouvement de caisse (déjà encaissé).                │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   419 Avances clients     30 000   Débit                     │
│     707 Ventes                     Crédit   30 000           │
│                                                              │
│ Journal : VN (Ventes)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : inchangée (déjà +100 000 au dépôt)             │
│   Client A  : solde passe de 100 000 → 70 000 FCFA          │
│   Fournisseur: aucun                                         │
│   Résultat  : +30 000 (produit)                              │
├──────────────────────────────────────────────────────────────┤
│ Note : On débite 419 (avances) car c'est une dette           │
│ envers le client qu'on diminue. Le client avait versé        │
│ 100 000 d'avance (crédit 419). Il consomme 30 000,           │
│ on réduit sa dette de 30 000 (débit 419).                    │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 3 : Dépôt client (approvisionnement compte)
# ─────────────────────────────────────────────────────────────
use_case_3 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 3 : Dépôt client (approvisionnement compte)              │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Client A verse 500 000 FCFA en espèces à l'hôtel          │
│   pour créditer son compte client interne.                   │
│   Il n'a pas encore consommé.                                │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   571 Caisse             500 000   Débit                     │
│     419 Avances clients             Crédit   500 000         │
│                                                              │
│ Journal : VN (Ventes)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : +500 000                                        │
│   Client A  : solde passe de 0 → 500 000 FCFA               │
│   Fournisseur: aucun                                         │
│   Résultat  : neutre (c'est une dette, pas un produit)       │
│                                                              │
│ Note : 419 = dette envers le client. Tant qu'il n'a pas      │
│ consommé, l'hôtel lui doit ce montant (passif).              │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 4 : Vente à crédit client
# ─────────────────────────────────────────────────────────────
use_case_4 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 4 : Vente à crédit client                                │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Client B consomme 50 000 FCFA.                             │
│   Son solde = 0. On lui accorde du crédit.                   │
│   Aucun encaissement immédiat.                               │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   411 Client              50 000   Débit                     │
│     707 Ventes                     Crédit   50 000           │
│                                                              │
│ Journal : VN (Ventes)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : inchangée                                       │
│   Client B  : créance = 50 000 FCFA (nous doit)              │
│   Fournisseur: aucun                                         │
│   Résultat  : +50 000 (produit)                              │
│                                                              │
│ Note : 411 = créance client. C'est un actif.                 │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 5 : Paiement d'une créance client (encaissement)
# ─────────────────────────────────────────────────────────────
use_case_5 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 5 : Paiement d'une créance client                        │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Client B rembourse 50 000 FCFA en espèces.                 │
│   Sa créance de 50 000 est soldée.                           │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   571 Caisse              50 000   Débit                     │
│     411 Client                     Crédit   50 000           │
│                                                              │
│ Journal : VN (Ventes)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : +50 000                                        │
│   Client B  : créance passe de 50 000 → 0 (soldé)           │
│   Fournisseur: aucun                                         │
│   Résultat  : neutre (déjà comptabilisé en cas 4)            │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 6 : Achat fournisseur comptant
# ─────────────────────────────────────────────────────────────
use_case_6 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 6 : Achat fournisseur comptant                           │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Achat de 100 000 FCFA de marchandises.                     │
│   Paiement immédiat en espèces.                              │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   31 Stocks             100 000   Débit                      │
│     571 Caisse                     Crédit   100 000          │
│                                                              │
│ Journal : AC (Achats)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : -100 000                                        │
│   Client    : aucun                                           │
│   Fournisseur: aucun (soldé)                                  │
│   Stock     : +100 000                                        │
│   Résultat  : neutre (l'achat devient charge à la vente)     │
├──────────────────────────────────────────────────────────────┤
│ Note : Certains préfèrent :                                   │
│   601 Achats  100 000  Débit                                  │
│     571 Caisse          Crédit  100 000                       │
│ Puis à la vente :                                             │
│   603 Variation stocks  100 000  Débit                        │
│     31 Stocks                   Crédit  100 000               │
│ Les deux sont valides selon le système d'inventaire.          │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 7 : Achat fournisseur à crédit
# ─────────────────────────────────────────────────────────────
use_case_7 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 7 : Achat fournisseur à crédit                           │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Achat de 100 000 FCFA non payé immédiatement.              │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   31 Stocks             100 000   Débit                      │
│     401 Fournisseur               Crédit   100 000           │
│                                                              │
│ Journal : AC (Achats)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : inchangée                                       │
│   Client    : aucun                                           │
│   Fournisseur: dette = 100 000 FCFA (on doit)                │
│   Stock     : +100 000                                        │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 8 : Paiement fournisseur
# ─────────────────────────────────────────────────────────────
use_case_8 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 8 : Paiement fournisseur                                 │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Paiement de 100 000 FCFA au fournisseur (dette cas 7).     │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   401 Fournisseur       100 000   Débit                      │
│     571 Caisse                     Crédit   100 000          │
│                                                              │
│ Journal : AC (Achats)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : -100 000                                        │
│   Client    : aucun                                           │
│   Fournisseur: dette passe de 100 000 → 0 (soldé)           │
│   Stock     : inchangé                                        │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 9 : Charge (dépense)
# ─────────────────────────────────────────────────────────────
use_case_9 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 9 : Charge (dépense d'exploitation)                      │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Achat de produits de nettoyage (savon) : 30 000 FCFA.      │
│   Paiement en espèces.                                       │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   604 Fournitures consommables   30 000   Débit              │
│     571 Caisse                           Crédit   30 000     │
│                                                              │
│   (Ou 658 Charges diverses si pas de compte dédié)           │
│                                                              │
│ Journal : CS (Caisse)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : -30 000                                        │
│   Client    : aucun                                           │
│   Fournisseur: aucun                                          │
│   Résultat  : -30 000 (charge)                                │
├──────────────────────────────────────────────────────────────┤
│ Variante par compte de charge :                               │
│   6041 Matières consommables     30 000   Débit              │
│   6222 Locations bâtiments                  Débit (si loyer)  │
│   6281 Téléphone                           Débit (si tel)     │
│   6411 Impôts fonciers                     Débit (si impôt)   │
│   6611 Salaires                             Débit (si paie)    │
│   etc. selon le plan comptable.                               │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 10 : Salaire (paie)
# ─────────────────────────────────────────────────────────────
use_case_10 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 10 : Salaire (paie mensuelle)                            │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Salaire brut = 200 000 FCFA                                │
│   CNPS = 10 000 FCFA                                         │
│   IRPP = 15 000 FCFA                                         │
│   Net à payer = 175 000 FCFA                                 │
│   Paiement en espèces.                                       │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable (constatation de la dette) :              │
│                                                              │
│   661 Charges personnel   200 000   Débit                    │
│     421 Personnel dues              Crédit   175 000         │
│     431 CNPS                        Crédit    10 000         │
│     447 État IRPP                   Crédit    15 000         │
│                                                              │
│ Journal : PA (Paie)                                          │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable (paiement effectif) :                     │
│                                                              │
│   421 Personnel dues     175 000   Débit                     │
│     571 Caisse                     Crédit   175 000          │
│                                                              │
│ Journal : CS (Caisse)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : -175 000                                        │
│   Dette CNPS: +10 000 (à payer plus tard)                    │
│   Dette IRPP: +15 000 (à reverser)                           │
│   Résultat  : -200 000 (charge)                               │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 11 : Transfert entre caisses
# ─────────────────────────────────────────────────────────────
use_case_11 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 11 : Transfert entre caisses                             │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Transfert de 50 000 FCFA de la caisse Bar vers             │
│   la caisse Centrale.                                        │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   571 Caisse Centrale   50 000   Débit                       │
│     571 Caisse Bar                 Crédit   50 000           │
│                                                              │
│ Journal : TR (Transferts)                                    │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse Bar       : -50 000                                  │
│   Caisse Centrale  : +50 000                                  │
│   Résultat         : neutre                                   │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 12 : Dépôt en banque
# ─────────────────────────────────────────────────────────────
use_case_12 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 12 : Dépôt en banque                                     │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Dépôt de 200 000 FCFA de la caisse vers le compte bancaire.│
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   521 Banque             200 000   Débit                     │
│     571 Caisse                     Crédit   200 000          │
│                                                              │
│ Journal : BQ (Banque)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : -200 000                                        │
│   Banque    : +200 000                                        │
│   Résultat  : neutre                                          │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 13 : Clôture de session POS
# ─────────────────────────────────────────────────────────────
use_case_13 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 13 : Clôture de session POS                              │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Session du jour au Bar.                                     │
│   Total ventes = 350 000 FCFA.                               │
│   Solde réel en caisse = 348 000 FCFA.                       │
│   Dépôt vers centrale = 300 000 FCFA.                        │
│   Écart = -2 000 FCFA (manquant).                            │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable (regroupement des ventes) :                │
│                                                              │
│   571 Caisse Bar          350 000   Débit                    │
│     707 Ventes                      Crédit   350 000         │
│                                                              │
│ Journal : CS (Caisse)                                        │
├──────────────────────────────────────────────────────────────┤
│ Écriture complémentaire (écart de caisse) :                   │
│ Si manquant :                                                 │
│   658 Charges diverses    2 000    Débit                      │
│     571 Caisse Bar                 Crédit     2 000          │
│                                                              │
│ Si excédent :                                                 │
│   571 Caisse Bar          2 000    Débit                      │
│     758 Produits divers            Crédit     2 000          │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ Note : Idéalement, chaque vente individuelle devrait être     │
│        comptabilisée en temps réel, pas en batch à la         │
│        clôture. Mais en pratique, le regroupement est         │
│        acceptable.                                            │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 14 : Réservation hôtel (arrhes)
# ─────────────────────────────────────────────────────────────
use_case_14 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 14 : Réservation hôtel avec arrhes                       │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Client réserve une chambre à 80 000 FCFA/nuit.             │
│   Verse 20 000 FCFA d'arrhes en espèces.                     │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable (arrhes) :                                │
│                                                              │
│   571 Caisse              20 000   Débit                     │
│     419 Avances clients             Crédit   20 000          │
│                                                              │
│ Journal : VN (Ventes)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : +20 000                                        │
│   Client    : solde = 20 000 (avoir chez l'hôtel)            │
│   Résultat  : neutre (dette envers client)                    │
├──────────────────────────────────────────────────────────────┤
│ À l'arrivée (check-in, solde de 60 000 payé) :               │
│   571 Caisse              60 000   Débit                     │
│   419 Avances clients     20 000   Débit                     │
│     707 Hébergement               Crédit   80 000            │
│                                                              │
│ Si crédit (pas de paiement à l'arrivée) :                     │
│   411 Client              60 000   Débit                     │
│   419 Avances clients     20 000   Débit                     │
│     707 Hébergement               Crédit   80 000            │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 15 : Vente avec TVA
# ─────────────────────────────────────────────────────────────
use_case_15 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 15 : Vente avec TVA                                      │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Vente de 118 000 FCFA TTC (TVA 18%).                       │
│   HT = 100 000, TVA = 18 000.                                │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   571 Caisse             118 000   Débit                     │
│     707 Ventes                     Crédit   100 000          │
│     443 TVA collectée              Crédit    18 000          │
│                                                              │
│ Journal : VN (Ventes)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : +118 000                                        │
│   État TVA  : dette +18 000 (à reverser)                     │
│   Résultat  : +100 000 (produit HT)                           │
├──────────────────────────────────────────────────────────────┤
│ Achat avec TVA déductible :                                   │
│   31 Stocks               100 000   Débit                     │
│   443 TVA déductible       18 000   Débit                     │
│     401 Fournisseur                Crédit   118 000           │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 16 : Remboursement / Annulation vente
# ─────────────────────────────────────────────────────────────
use_case_16 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 16 : Remboursement / Annulation vente                    │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Vente de 50 000 FCFA annulée, remboursement en espèces.    │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   707 Ventes              50 000   Débit                     │
│     571 Caisse                     Crédit   50 000           │
│                                                              │
│   (Ou via 658 Charges diverses si on préfère garder          │
│    le chiffre d'affaires intact)                              │
│                                                              │
│ Journal : VN (Ventes)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Caisse    : -50 000                                        │
│   Résultat  : -50 000 (annulation du produit)                 │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 17 : Règlement client par virement bancaire
# ─────────────────────────────────────────────────────────────
use_case_17 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 17 : Règlement client par virement bancaire              │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Client B paie sa créance de 50 000 FCFA par virement.     │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   521 Banque              50 000   Débit                     │
│     411 Client                     Crédit   50 000           │
│                                                              │
│ Journal : BQ (Banque)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Banque    : +50 000                                         │
│   Client B  : créance 50 000 → 0 (soldé)                     │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 18 : Vente via terminal carte bancaire
# ─────────────────────────────────────────────────────────────
use_case_18 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 18 : Vente par carte bancaire (TIP)                      │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Vente de 25 000 FCFA payée par carte bancaire.             │
│   Le montant sera viré par la banque sous 48h.               │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable (en attendant l'encaissement) :            │
│                                                              │
│   471 Compte d'attente      25 000   Débit                   │
│     707 Ventes                       Crédit   25 000         │
│                                                              │
│ Journal : VN (Ventes)                                        │
├──────────────────────────────────────────────────────────────┤
│ Au moment du virement banque réel :                           │
│   521 Banque               25 000   Débit                     │
│     471 Compte d'attente            Crédit   25 000          │
│                                                              │
│ Journal : BQ (Banque)                                        │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Banque    : +25 000 (après 48h)                             │
│   Résultat  : +25 000 (produit immédiat)                      │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 19 : Entrée en stock (inventaire)
# ─────────────────────────────────────────────────────────────
use_case_19 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 19 : Entrée en stock / Réception de marchandises         │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Réception de marchandises commandées : 100 000 FCFA.       │
│   Facture fournisseur jointe.                                │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   31 Marchandises         100 000   Débit                    │
│     603 Variation stocks            Crédit   100 000         │
│                                                              │
│ Journal : ST (Stock)                                         │
├──────────────────────────────────────────────────────────────┤
│ Note : Dans le système d'inventaire intermittent, on passe    │
│        par 601 Achats au moment de l'achat, puis 603/31       │
│        en fin de période pour ajuster le stock.               │
│        En inventaire permanent, on utilise 31 directement.     │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 20 : Sortie de stock (consommation)
# ─────────────────────────────────────────────────────────────
use_case_20 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 20 : Sortie de stock (consommation en cuisine/bar)       │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Sortie de stock pour production : 25 000 FCFA.             │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   603 Variation stocks     25 000   Débit                    │
│     31 Marchandises                Crédit   25 000           │
│                                                              │
│ Journal : ST (Stock)                                         │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Stock     : -25 000                                         │
│   Résultat  : impact via le coût des ventes                   │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 21 : Ajustement d'inventaire (surplus/perte)
# ─────────────────────────────────────────────────────────────
use_case_21 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 21 : Ajustement d'inventaire (surplus ou perte)          │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Inventaire : 5 000 FCFA de surplus constaté.               │
├──────────────────────────────────────────────────────────────┤
│ Écriture (surplus) :                                         │
│                                                              │
│   31 Marchandises          5 000   Débit                     │
│     758 Produits divers            Crédit    5 000           │
│                                                              │
│ Contexte : 3 000 FCFA de perte constatée.                    │
│ Écriture (perte) :                                           │
│                                                              │
│   658 Charges diverses     3 000   Débit                     │
│     31 Marchandises                Crédit    3 000           │
│                                                              │
│ Journal : ST (Stock)                                         │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 22 : Acquisition d'immobilisation
# ─────────────────────────────────────────────────────────────
use_case_22 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 22 : Acquisition d'immobilisation                        │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Achat d'un réfrigérateur à 500 000 FCFA.                   │
│   Paiement par chèque.                                       │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   218 Matériel             500 000   Débit                   │
│     521 Banque                      Crédit   500 000         │
│                                                              │
│ Journal : INV (Investissements)                              │
├──────────────────────────────────────────────────────────────┤
│ Si achat à crédit fournisseur d'immobilisation :              │
│                                                              │
│   218 Matériel             500 000   Débit                   │
│     404 Fournisseur immo.            Crédit   500 000        │
│                                                              │
│ Impacts :                                                    │
│   Banque    : -500 000                                        │
│   Immobilisation : +500 000                                   │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 23 : Amortissement mensuel
# ─────────────────────────────────────────────────────────────
use_case_23 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 23 : Amortissement mensuel                               │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Amortissement mensuel du réfrigérateur : 8 333 FCFA.      │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   681 Dot. amortissements    8 333   Débit                   │
│     2818 Amort. matériel              Crédit    8 333        │
│                                                              │
│ Journal : OD (Opérations Diverses)                            │
├──────────────────────────────────────────────────────────────┤
│ Impacts :                                                    │
│   Valeur nette immo : 500 000 → 491 667                      │
│   Résultat  : -8 333 (charge)                                │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 24 : Vente entre modules (Bar → Restaurant)
# ─────────────────────────────────────────────────────────────
use_case_24 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 24 : Cession interne entre points de vente               │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Le Bar cède 15 000 FCFA de boissons au Restaurant.         │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│   (Pas d'écriture externe — suivi interne)                   │
│   Mouvement de stock interne uniquement.                     │
│                                                              │
│   Stock Restaurant       15 000   Entrée                     │
│   Stock Bar              15 000   Sortie                     │
│                                                              │
│ Impacts :                                                    │
│   Résultat        : neutre                                    │
│   Stock Bar       : -15 000                                   │
│   Stock Restaurant: +15 000                                   │
└──────────────────────────────────────────────────────────────┘
"""

# ─────────────────────────────────────────────────────────────
# USE CASE 25 : Avoir client / Note de crédit
# ─────────────────────────────────────────────────────────────
use_case_25 = """
┌──────────────────────────────────────────────────────────────┐
│ CAS 25 : Avoir client (note de crédit)                       │
├──────────────────────────────────────────────────────────────┤
│ Contexte :                                                   │
│   Client C a été surfacturé de 10 000 FCFA.                 │
│   On émet un avoir.                                          │
├──────────────────────────────────────────────────────────────┤
│ Écriture comptable :                                         │
│                                                              │
│   707 Ventes              10 000   Débit                     │
│     411 Client (ou 419)             Crédit   10 000          │
│                                                              │
│ Journal : VN (Ventes)                                        │
├──────────────────────────────────────────────────────────────┤
│ Si l'avoir est remboursé en espèces :                         │
│                                                              │
│   411 Client              10 000   Débit                     │
│     571 Caisse                     Crédit   10 000           │
│                                                              │
│ Impacts :                                                    │
│   Résultat  : -10 000 (réduction du chiffre d'affaires)       │
│   Client    : dette réduite ou remboursée                     │
└──────────────────────────────────────────────────────────────┘
"""


# ─────────────────────────────────────────────────────────────
# SYNTHÈSE : MATRICE DES IMPACTS
# ─────────────────────────────────────────────────────────────
MATRICE_IMPACTS = """
═══════════════════════════════════════════════════════════════
MATRICE DES IMPACTS PAR OPÉRATION
═══════════════════════════════════════════════════════════════

OPÉRATION              │ CAISSE  │ BANQUE │CLIENT  │FOURNISSE│ STOCK │ RÉSULTAT
───────────────────────┼─────────┼────────┼────────┼─────────┼───────┼─────────
Vente comptant         │   +     │        │        │         │       │   +     
Vente compte client    │         │        │  -solde│         │       │   +     
Vente crédit           │         │        │Créance │         │       │   +     
Dépôt client           │   +     │        │  +solde│         │       │         
Paiement créance       │   +     │        │Créance↓│         │       │         
Achat comptant         │   -     │        │        │         │   +   │         
Achat crédit           │         │        │        │   +dette│   +   │         
Paiement fournisseur   │   -     │        │        │  -dette │       │         
Charge (exploitation)  │   -     │        │        │         │       │   -     
Salaire (charge)       │         │        │        │         │       │   -     
Salaire (paiement)     │   -     │        │        │         │       │         
Transfert caisse       │  +/-    │        │        │         │       │         
Dépôt banque           │   -     │   +    │        │         │       │         
Clôture session        │   +     │        │        │         │       │   +     
Arrhes réservation     │   +     │        │  +solde│         │       │         
Amortissement          │         │        │        │         │       │   -     
Avoir/remboursement    │   -     │        │Créance↓│         │       │   -     
Acquisition immo.      │   -     │   -    │        │         │       │         
Entrée stock           │         │        │        │         │   +   │         
Sortie stock           │         │        │        │         │   -   │         
───────────────────────┴─────────┴────────┴────────┴─────────┴───────┴─────────

Légende :
  +        = augmentation / encaissement / produit
  -        = diminution / décaissement / charge
  +solde   = augmentation du solde client (avoir chez nous)
  -solde   = diminution du solde client (consommation)
  Créance  = naissance d'une créance client (nous doit)
  Créance↓ = réduction de la créance client
  +dette   = augmentation de la dette fournisseur (nous devons)
  -dette   = réduction de la dette fournisseur
  +/-      = transfert entre comptes, neutre au global
"""


# ─────────────────────────────────────────────────────────────
# RÈGLES DE GESTION
# ─────────────────────────────────────────────────────────────
REGLES = """
═══════════════════════════════════════════════════════════════
RÈGLES DE GESTION COMPTABLE
═══════════════════════════════════════════════════════════════

R1 - Toujours équilibrer : Total débit = Total crédit
R2 - Une ligne ne peut avoir à la fois débit ET crédit
R3 - Le sens normal d'un compte définit où va l'augmentation :
       Actif/Charge → Débit (augmente au débit)
       Passif/Produit → Crédit (augmente au crédit)
R4 - L'écriture est horodatée à la date de l'opération
R5 - L'exercice comptable est déterminé par la date de l'opération
R6 - Une écriture validée ne peut plus être modifiée
R7 - L'annulation se fait par une écriture inverse (contrepassation)
R8 - Les écritures sont lettrées par compte de tiers (client/fournisseur)
R9 - Le journal est déterminé par la nature de l'opération :
       Ventes → VN, Achats → AC, Caisse → CS, Banque → BQ
       Paie → PA, Stock → ST, Investissements → INV
       Divers → OD, Clôture → CL, Transferts → TR
R10 - Chaque écriture a une référence unique et traçable
"""


if __name__ == '__main__':
    cases = [
        (1, use_case_1), (2, use_case_2), (3, use_case_3),
        (4, use_case_4), (5, use_case_5), (6, use_case_6),
        (7, use_case_7), (8, use_case_8), (9, use_case_9),
        (10, use_case_10), (11, use_case_11), (12, use_case_12),
        (13, use_case_13), (14, use_case_14), (15, use_case_15),
        (16, use_case_16), (17, use_case_17), (18, use_case_18),
        (19, use_case_19), (20, use_case_20), (21, use_case_21),
        (22, use_case_22), (23, use_case_23), (24, use_case_24),
        (25, use_case_25),
    ]
    print("=" * 70)
    print("USE CASE COMPTABLE — DOCUMENT DE SPÉCIFICATION")
    print("=" * 70)
    for num, texte in cases:
        print(texte)
    print(MATRICE_IMPACTS)
    print(REGLES)
    print(f"Total: {len(cases)} use cases documentés")
