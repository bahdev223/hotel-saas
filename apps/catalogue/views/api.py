from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from apps.stock.models import Produit
from apps.restaurant.models.menu import MenuModel
from apps.hotel.models import UniteModel


@login_required
def items(request):
    produits = Produit.objects.filter(est_vendable=True, actif=True).select_related('categorie', 'domaine').order_by('nom')
    menus = MenuModel.objects.filter(actif=True, visible_dans_pos=True).order_by('ordre_affichage', 'nom')
    chambres = UniteModel.objects.filter(actif=True).order_by('nom')

    # Collecter les catégories uniques
    categories_produits = sorted(set(
        p.categorie.nom for p in produits if p.categorie
    ))
    types_menus = sorted(set(
        m.get_type_menu_display() for m in menus
    ))

    return JsonResponse({
        'produits': [{
            'id': p.id,
            'code': p.code,
            'nom': p.nom,
            'categorie': p.categorie.nom if p.categorie else None,
            'domaine': p.domaine.nom if p.domaine else None,
            'domaine_id': str(p.domaine.id) if p.domaine else None,
            'unite_base': p.unite_base,
            'image_url': p.image.url if p.image else None,
            'description': p.description,
        } for p in produits],
        'menus': [{
            'id': m.id,
            'code': m.code,
            'nom': m.nom,
            'type_menu': m.get_type_menu_display(),
            'prix_vente': str(m.prix_vente),
            'image_url': m.image.url if m.image else None,
            'description': m.description,
        } for m in menus],
        'chambres': [{
            'id': c.id,
            'nom': c.nom,
            'type_chambre': c.get_type_unite_display() if hasattr(c, 'type_unite') else None,
            'capacite': c.capacite if hasattr(c, 'capacite') else None,
            'image_url': c.image.url if c.image else None,
            'description': c.description or '',
        } for c in chambres],
        'categories_produits': categories_produits,
        'types_menus': types_menus,
    })




