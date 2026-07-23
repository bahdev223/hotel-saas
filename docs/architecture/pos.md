
---

# 📁 `docs/architecture/pos.md`

```markdown
# Module POS

## Fonctionnalités

- Vente rapide
- Paiements
- Impression ticket
- Déstockage automatique
- Gestion tables
- Menus restaurant

---

# Architecture POS

```mermaid
graph LR

    A[Interface POS]
    B[VenteService]
    C[StockService]
    D[PaiementService]
    E[Comptabilite]

    A --> B
    B --> C
    B --> D
    D --> E