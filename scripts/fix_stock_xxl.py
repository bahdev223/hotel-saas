"""
Fix stock XXL + produits transferes invisibles
Usage: python manage.py shell < scripts/fix_stock_xxl.py
"""
from decimal import Decimal
from apps.stock.models import Produit, Entrepot, StockEntrepot, MouvementStock
from apps.stock.services.mouvement_service import MouvementStockService
from django.db import transaction

# ── 1. TROUVER XXL ──
produit = Produit.objects.filter(nom__icontains='XXL').first()
if not produit:
    # chercher avec un nom approchant
    produit = Produit.objects.filter(nom__icontains='xxl').first()
if not produit:
    print(f"ERREUR: produit XXL introuvable")
    print("Produits disponibles contenant 'XL':")
    for p in Produit.objects.filter(nom__icontains='XL'):
        print(f"  ID={p.id} nom={p.nom}")
    exit(1)

print(f"Produit: ID={produit.id} nom={produit.nom} unite_base={produit.unite_base}")
print(f"  seuil_alerte={produit.seuil_alerte} prix_achat={produit.prix_achat}")

# ── 2. STOCK PAR ENTREPOT ──
print(f"\n{'='*60}")
print("STOCK PAR ENTREPOT (StockEntrepot)")
print(f"{'='*60}")
stocks = StockEntrepot.objects.filter(produit=produit).select_related('entrepot')
for s in stocks:
    print(f"  Entrepot: {s.entrepot.nom:20s} | qte={s.quantite:>8} | prix_achat={s.prix_achat}")

# ── 3. MOUVEMENTS RECENTS ──
print(f"\n{'='*60}")
print("DERNIERS MOUVEMENTS (MouvementStock)")
print(f"{'='*60}")
mouvs = MouvementStock.objects.filter(produit=produit).order_by('-date_mouvement')[:20]
for m in mouvs:
    src = m.entrepot_source.nom if m.entrepot_source else "-"
    dst = m.entrepot_dest.nom if m.entrepot_dest else "-"
    print(f"  {m.date_mouvement.strftime('%d/%m %H:%M'):14s} | {m.type_mouvement:8s} | {str(m.quantite):>5s} | {src:15s} -> {dst:15s} | {m.motif:15s} | {m.reference or ''}")

# ── 4. VERIFIER LA COHERENCE ──
print(f"\n{'='*60}")
print("VERIFICATION COHERENCE")
print(f"{'='*60}")

# Calculer le stock attendu par entrepot a partir des mouvements
from decimal import Decimal
from django.db.models import Sum, Q

entrepots = Entrepot.objects.filter(actif=True)
print(f"\nStock attendu (recalcul depuis MouvementStock):")
for e in entrepots:
    entrees = MouvementStock.objects.filter(
        produit=produit, entrepot_dest=e
    ).aggregate(total=Sum('quantite'))['total'] or Decimal('0')

    sorties = MouvementStock.objects.filter(
        produit=produit, entrepot_source=e
    ).aggregate(total=Sum('quantite'))['total'] or Decimal('0')

    attendu = entrees - sorties

    # StockEntrepot actuel
    try:
        stock_actuel = StockEntrepot.objects.get(produit=produit, entrepot=e)
        actuel_qte = stock_actuel.quantite
    except StockEntrepot.DoesNotExist:
        actuel_qte = Decimal('0')

    if attendu != actuel_qte:
        marqueur = " *** INCOHERENT ***"
    else:
        marqueur = ""
    print(f"  {e.nom:20s} | entrees={str(entrees):>8} | sorties={str(sorties):>8} | attendu={str(attendu):>8} | actuel={str(actuel_qte):>8}{marqueur}")

# ── 5. CORRECTION ──
print(f"\n{'='*60}")
print("CORRECTION AUTOMATIQUE")
print(f"{'='*60}")

corrections = []
for e in entrepots:
    entrees = MouvementStock.objects.filter(
        produit=produit, entrepot_dest=e
    ).aggregate(total=Sum('quantite'))['total'] or Decimal('0')

    sorties = MouvementStock.objects.filter(
        produit=produit, entrepot_source=e
    ).aggregate(total=Sum('quantite'))['total'] or Decimal('0')

    attendu = entrees - sorties

    try:
        stock_actuel = StockEntrepot.objects.get(produit=produit, entrepot=e)
        actuel_qte = stock_actuel.quantite
    except StockEntrepot.DoesNotExist:
        actuel_qte = Decimal('0')
        stock_actuel = None

    if attendu != actuel_qte:
        corrections.append((e, attendu, actuel_qte, stock_actuel))

if corrections:
    print(f"Corrections necessaires pour {len(corrections)} entrepot(s):")
    for e, attendu, actuel_qte, stock_actuel in corrections:
        print(f"  {e.nom}: attendu={attendu}, actuel={actuel_qte}")
        try:
            with transaction.atomic():
                if stock_actuel:
                    stock_actuel.quantite = attendu
                    stock_actuel.save()
                else:
                    StockEntrepot.objects.create(
                        entrepot=e, produit=produit,
                        quantite=attendu,
                        prix_achat=produit.prix_achat or 0
                    )
            print(f"    -> CORRIGE")
        except Exception as ex:
            print(f"    -> ERREUR: {ex}")
else:
    print("Aucune correction necessaire.")

# ── 6. PRODUITS TRANSFERES INVISIBLES ──
print(f"\n{'='*60}")
print("DIAG: Produits transferes invisibles dans le stock bar")
print(f"{'='*60}")
bar = Entrepot.objects.filter(type_entrepot='BAR', actif=True).first()
central = Entrepot.objects.filter(type_entrepot='CENTRAL', actif=True).first()
if bar and central:
    # Produits qui ont des mouvements de transfert CENTRAL -> BAR
    # mais qui n'ont PAS de StockEntrepot dans BAR
    transferes = MouvementStock.objects.filter(
        type_mouvement='ENTREE',
        motif='reapprovisionnement',
        entrepot_dest=bar,
        entrepot_source=central
    ).values_list('produit_id', flat=True).distinct()

    for pid in transferes:
        has_stock = StockEntrepot.objects.filter(produit_id=pid, entrepot=bar).exists()
        if not has_stock:
            p = Produit.objects.get(id=pid)
            print(f"  {p.nom:30s} (ID={pid}) transfert central->bar mais StockEntrepot[bar] manquant !")
            # Quantite totale transferee
            total = MouvementStock.objects.filter(
                produit_id=pid, type_mouvement='ENTREE',
                motif='reapprovisionnement', entrepot_dest=bar
            ).aggregate(total=Sum('quantite'))['total'] or Decimal('0')
            sorties_bar = MouvementStock.objects.filter(
                produit_id=pid, entrepot_source=bar
            ).aggregate(total=Sum('quantite'))['total'] or Decimal('0')
            attendu_bar = total - sorties_bar
            print(f"    Total transfere={total}, sorties bar={sorties_bar}, attendu={attendu_bar}")

    print(f"\nVerifiez aussi avec: python manage.py pos_healthcheck")
    print(f"(regarde les stocks incoherents entre mouvements et StockEntrepot)")

print(f"\n{'='*60}")
print("RESUME FINAL")
print(f"{'='*60}")
stocks = StockEntrepot.objects.filter(produit=produit).select_related('entrepot')
for s in stocks:
    print(f"  {s.entrepot.nom:20s} | qte={s.quantite}")
print(f"\nSi le stock est toujours a 0 dans l'entrepot que vous consultez,")
print(f"c'est que le produit a ete stocke dans un autre entrepot (BRASSERIE, RESTAURANT).")
print(f"Utilisez l'interface Transfert pour deplacer le stock vers l'entrepot souhaite.")