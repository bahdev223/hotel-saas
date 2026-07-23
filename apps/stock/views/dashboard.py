# apps/stock/views/dashboard.py
import json
from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from ..constants import ALLOWED_STOCK_GROUPS
from django.db.models import Sum, Q, F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from datetime import date, timedelta

from ..models import Produit, Entrepot, StockEntrepot, MouvementStock, CategorieProduit, Domaine
from ..constants import ALLOWED_STOCK_GROUPS


@login_required
def dashboard(request):
    """Dashboard du stock central - SPA unifiee"""
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(group in ALLOWED_STOCK_GROUPS for group in user_groups):
        messages.error(request, "Acces refuse.")
        return redirect('admin:index')

    today = date.today()
    central = Entrepot.objects.filter(type_entrepot='CENTRAL').first()
    if not central:
        central = Entrepot.objects.create(code='STK001', nom='STOCK CENTRAL', type_entrepot='CENTRAL', actif=True)

    stocks_central = StockEntrepot.objects.filter(entrepot=central).select_related('produit')
    total_produits = stocks_central.count()
    valeur_stock = float(sum(
        Decimal(str(s.quantite)) * Decimal(str(s.prix_achat or s.produit.prix_achat or 0))
        for s in StockEntrepot.objects.select_related('produit').all()
    ))
    produits_rupture = stocks_central.filter(quantite__lte=0).count()
    produits_alerte = stocks_central.filter(quantite__lte=F('produit__seuil_alerte'), quantite__gt=0).count()

    alertes_stock = []
    for s in stocks_central:
        if 0 < s.quantite <= s.produit.seuil_alerte:
            alertes_stock.append({'produit': s.produit, 'quantite': s.quantite, 'seuil': s.produit.seuil_alerte})

    derniers_mouvements = MouvementStock.objects.select_related('produit').order_by('-date_mouvement')[:15]

    entrepots = Entrepot.objects.filter(actif=True)
    entrepots_data = []
    for e in entrepots:
        stocks = StockEntrepot.objects.filter(entrepot=e).select_related('produit')
        entrepots_data.append({
            'id': e.id,
            'code': e.code,
            'nom': e.nom,
            'type_display': e.get_type_entrepot_display(),
            'produits_count': stocks.count(),
            'valeur': sum(float(s.quantite) * float(s.prix_achat or s.produit.prix_achat or 0) for s in stocks),
            'actif': e.actif,
        })

    categories = list(CategorieProduit.objects.filter(actif=True).values('id', 'nom'))
    domaines = list(Domaine.objects.filter(actif=True).values('id', 'nom', 'icone'))
    types = Entrepot.TYPE_CHOICES

    context = {
        'total_produits': total_produits,
        'valeur_stock': valeur_stock,
        'produits_rupture': produits_rupture,
        'produits_alerte': produits_alerte,
        'alertes_stock': alertes_stock,
        'entrepots': entrepots_data,
        'produits': Produit.objects.filter(actif=True).order_by('nom'),
        'derniers_mouvements': derniers_mouvements,
        'categories': categories,
        'domaines': domaines,
        'types': types,
        'types_article': Produit.TYPE_ARTICLE_CHOICES,
        'categories_json': json.dumps(list(CategorieProduit.objects.filter(actif=True).values('id', 'nom').order_by('nom')), ensure_ascii=False),
        'domaines_json': json.dumps(list(Domaine.objects.filter(actif=True).values('id', 'nom').order_by('ordre', 'nom')), ensure_ascii=False),
    }
    return render(request, 'stock/dashboard.html', context)

