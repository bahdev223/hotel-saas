# Règles de Déstockage (Restaurant & POS)

Ce document définit les règles strictes d'interaction entre le module de vente (POS) / production (Restaurant) et le moteur de stock, suite à la refonte de l'architecture.

## 1. Règle d'or : Isolation

**Le POS et le Restaurant ne doivent JAMAIS manipuler directement le modèle `StockEntrepot` ou créer des `MouvementStock`.**

Toute modification de stock doit passer **uniquement** par les services dédiés du module `stock` :
- `MouvementStockService.entree_stock`
- `MouvementStockService.sortie_stock`
- `TransfertService.transfert_entre_entrepots`

## 2. Déstockage lors d'une Vente (POS)

Lorsqu'une commande est validée dans le POS, le déstockage doit s'effectuer de la manière suivante :

1. **Identification du produit et de l'entrepôt :** Le POS doit identifier le `Produit` vendu et l' `Entrepot` source (généralement le magasin du point de vente).
2. **Appel au service :** Appeler `MouvementStockService.sortie_stock` avec :
   - `motif=SourceOperationType.VENTE`
   - La référence de la commande.
3. **Allocation FEFO :** Si le produit est géré en lots, le `MouvementStockService` (via `LotAllocationService`) se chargera automatiquement d'allouer les lots disponibles en respectant la méthode FEFO (First Expired, First Out).

## 3. Déstockage lors d'une Production (Restaurant)

La production d'un plat implique de déstocker les ingrédients définis dans sa fiche technique (Recette) pour créer un produit fini.

1. **Orchestration :** L'orchestration de la production doit être déléguée au `ProductionService` (dans l'app `restaurant`). Les modèles `Production` et `Recette` ne doivent contenir que de la donnée, pas de logique de déstockage.
2. **Sortie des ingrédients :** Pour chaque ingrédient de la recette, appeler `MouvementStockService.sortie_stock` avec :
   - `motif=SourceOperationType.PRODUCTION`
   - La référence de l'ordre de production.
   - Les conversions d'unités doivent être appliquées **avant** l'appel au service de stock. Le service de stock attend des quantités dans l'**unité de base** du produit.
3. **Entrée du produit fini (Optionnel) :** Si la production crée un stock physique de produit fini, appeler `MouvementStockService.entree_stock` pour le produit fini.

## 4. Conversion d'Unités

Le risque financier le plus important réside dans les erreurs de conversion.
Toute conversion entre l'unité d'achat, l'unité de recette et l'unité de base doit utiliser le `ConversionUniteService` (ou les facteurs définis dans le modèle `ConversionUnite`) et **jamais** de logique hardcodée.

## 5. Valorisation

La valorisation des sorties (ventes, production, pertes) se fait par défaut au CUMP (Coût Unitaire Moyen Pondéré) via le `ValorisationStockService`. Le POS n'a pas à calculer le coût des marchandises vendues (COGS) ; il lui suffit de récupérer la valeur générée par le mouvement de stock.
