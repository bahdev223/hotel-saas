
---

## 📄 **FICHIER 4 : docs/architecture/stock.md**

```markdown
# Module Gestion des Stocks

## Architecture Multi-Entrepôts

### Entrepôts Configurés

| Code | Nom | Type | Utilisation |
|------|-----|------|-------------|
| STK001 | Stock Central | CENTRAL | Stock principal |
| BAR001 | Bar | BAR | Boissons, snacks |
| RST001 | Restaurant | RESTAURANT | Matières premières |
| CST001 | Cuisine | CUISINE | Produits frais |
| MNB001 | Mini-bar | MINIBAR | Mini-bars chambres |

## Modèles Principaux

### Produit
- code, nom, categorie
- type_gestion: TRACABLE / CONSOMMABLE
- unite_base: piece, kg, litre
- prix_achat, prix_vente
- seuil_alerte, budget_mensuel
- code_barre (scannable)
- image (upload)

### SousUnite (Conversion)
- Exemple: 1 caisse = 12 bouteilles
- nom: "caisse"
- facteur: 12
- prix: 5000 (optionnel)

### MouvementStock
- type_mouvement: ENTREE, SORTIE, TRANSFERT, CASSE, INVENTAIRE
- quantite
- entrepot_source, entrepot_dest
- reference, raison
- utilisateur, date_mouvement

## Flux de Gestion

### 1. Réception Marchandise

```mermaid
sequenceDiagram
    participant F as Fournisseur
    participant S as Stock Central
    participant M as MouvementStock
    participant C as Comptabilité
    
    F->>S: Livraison + facture
    S->>S: Vérifier quantités
    S->>M: Créer ENTREE
    M->>S: Mettre à jour stock
    S->>C: Générer écriture achat
    C-->>S: Écriture validée
    S->>F: Accusé réception