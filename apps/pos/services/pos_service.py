from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from apps.stock.models import Produit, StockEntrepot, Entrepot
from apps.stock.services.mouvement_service import MouvementStockService
from apps.restaurant.models import MenuModel
from apps.hotel.models import UniteModel


@transaction.atomic
def deduire_stock_commande(commande, entrepot_id=None):
    """Déduire le stock de l'entrepôt lié au point de vente.
    Si entrepot_id est fourni, déduire de celui-là précisément.
    Idempotent : une commande déjà déduite (SERVIE/LIVREE) ne l'est jamais deux fois."""
    from apps.stock.models import MouvementStock
    if MouvementStock.objects.filter(
        reference=commande.numero, type_mouvement='SORTIE', motif='vente'
    ).exists():
        return

    pv = commande.point_vente
    entrepot = pv.entrepot

    if entrepot_id:
        entrepots_autorises = [entrepot_id]
    elif entrepot:
        entrepots_autorises = [entrepot.id]
    else:
        entrepots_autorises = PointVenteService.get_entrepot_ids(pv)
    if not entrepots_autorises:
        return

    for ligne in commande.lignes.all():
        if not ligne.produit:
            continue

        quantite = Decimal(str(ligne.quantite or 0))
        if quantite <= 0:
            continue

        # Trier les entrepôts : celui avec le plus de stock en premier
        stocks_dispo = StockEntrepot.objects.filter(
            produit=ligne.produit,
            entrepot_id__in=entrepots_autorises,
            quantite__gt=0
        ).select_related('entrepot').order_by('-quantite')

        deduit = False
        for stock in stocks_dispo:
            try:
                qte_a_deduire = min(quantite, stock.quantite)
                valeur = float(stock.prix_achat or ligne.produit.prix_achat or 0)
                MouvementStockService.sortie_stock(
                    produit=ligne.produit,
                    entrepot=stock.entrepot,
                    quantite=qte_a_deduire,
                    valeur_unitaire=valeur,
                    utilisateur=commande.created_by.user.username if commande.created_by and commande.created_by.user else 'POS',
                    reference=commande.numero,
                    raison=f"Vente {commande.numero} - {pv.nom}"
                )
                quantite -= qte_a_deduire
                deduit = True
                if quantite <= 0:
                    break
            except ValueError:
                continue

        if quantite > 0 and not deduit:
            raise ValueError(f"Stock insuffisant pour {ligne.produit.nom} dans tous les entrepôts")


class PointVenteService:
    """Service partagé pour les opérations du Point de Vente"""

    @staticmethod
    def get_entrepot_ids(point_vente):
        """Retourne la liste des IDs d'entrepôts liés à un point de vente"""
        from ..models import PointVenteEntrepot
        entrepot_ids = []
        if point_vente.entrepot:
            entrepot_ids.append(point_vente.entrepot_id)
        pve_ids = list(PointVenteEntrepot.objects.filter(
            point_vente=point_vente
        ).values_list('entrepot_id', flat=True))
        return list(set(entrepot_ids + pve_ids))

    @staticmethod
    def get_entrepot_utilise(point_vente, entrepot_id_from_request=None):
        """Détermine l'entrepôt à utiliser (celui demandé ou le premier disponible)"""
        entrepot_ids = PointVenteService.get_entrepot_ids(point_vente)
        if entrepot_id_from_request and int(entrepot_id_from_request) in entrepot_ids:
            return int(entrepot_id_from_request)
        return entrepot_ids[0] if entrepot_ids else None

    @staticmethod
    def get_stocks_dict(entrepot_ids, entrepot_id_param=None):
        """Construit un dict {produit_id: stock_quantite} pour les entrepôts donnés"""
        stocks_dict = {}
        if entrepot_id_param:
            eid = int(entrepot_id_param)
            if eid in entrepot_ids:
                stock_qs = StockEntrepot.objects.filter(entrepot_id=eid)
                stocks_agg = stock_qs.values('produit_id', 'quantite')
                stocks_dict = {s['produit_id']: float(s['quantite']) for s in stocks_agg}
        elif entrepot_ids:
            stock_qs = StockEntrepot.objects.filter(entrepot_id__in=entrepot_ids)
            stocks_agg = stock_qs.values('produit_id').annotate(total=Sum('quantite'))
            stocks_dict = {s['produit_id']: float(s['total']) for s in stocks_agg}
        return stocks_dict

    @staticmethod
    def get_stocks_par_entrepot(entrepot_ids):
        """Construit un dict {entrepot_id: {produit_id: quantite}}"""
        stocks_par_entrepot = {}
        for eid in entrepot_ids:
            st = StockEntrepot.objects.filter(entrepot_id=eid)
            stocks_par_entrepot[eid] = {
                s['produit_id']: float(s['quantite'])
                for s in st.values('produit_id', 'quantite')
            }
        return stocks_par_entrepot

    @staticmethod
    def build_categories_dict(produits, menus, unites, stocks_dict):
        """Construit le dictionnaire des catégories pour le POS"""
        categories = {}
        for p in produits:
            cat = p.domaine.nom.upper() if p.domaine else 'BRASSERIE'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                'id': p.id, 'nom': p.nom, 'prix': float(p.prix_vente),
                'code': p.code, 'image': p.image.url if p.image else None,
                'type': cat, 'article_type': 'PRODUIT',
                'stock': stocks_dict.get(p.id, 0), 'unite': p.unite_base,
                'sous_categorie': p.categorie.nom if p.categorie else None,
            })

        for m in menus:
            cat = 'RESTAURANT'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                'id': m.id, 'nom': m.nom, 'prix': float(m.prix_vente),
                'code': m.code, 'image': m.image.url if m.image else None,
                'type': cat, 'article_type': 'MENU', 'description': m.description or '',
                'sous_categorie': m.get_type_menu_display(),
            })

        for u in unites:
            cat = 'LOCATION'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                'id': u.id, 'nom': f"{u.code} - {u.nom}", 'prix': float(u.prix),
                'prix_jour': float(u.prix_jour) if u.prix_jour else 0,
                'code': u.code, 'image': None,
                'type': cat, 'article_type': 'UNITE',
                'type_unite': u.type_unite, 'capacite': u.capacite,
                'statut_unite': u.statut,
                'sous_categorie': None,
            })
        return categories

    @staticmethod
    def build_sous_categories(categories):
        """Extrait les sous-catégories disponibles depuis les catégories"""
        sous_categories = {}
        for cat, items in categories.items():
            scs = sorted(set(it['sous_categorie'] for it in items if it['sous_categorie']))
            if scs:
                sous_categories[cat] = scs
        return sous_categories
