# apps/stock/views/rapports.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from datetime import date, timedelta
from ..models import Produit, MouvementStock, Lot, Debiteur, StockDebiteur


@login_required
def rapport_stock(request):
    """Rapport dÃ©taillÃ© du stock"""
    
    # Filtres
    categorie_id = request.GET.get('categorie')
    type_article = request.GET.get('type_article')
    statut = request.GET.get('statut')
    
    produits = Produit.objects.filter(actif=True)
    
    if categorie_id:
        produits = produits.filter(categorie_id=categorie_id)
    if type_article:
        produits = produits.filter(type_article=type_article)
    if statut == 'rupture':
        produits = produits.filter(quantite_stock__lte=0)
    elif statut == 'alerte':
        produits = produits.filter(quantite_stock__gt=0, quantite_stock__lte=5)
    
    # Statistiques
    stats = {
        'total_produits': produits.count(),
        'valeur_totale': sum(float(p.quantite_stock) * float(p.prix_achat) for p in produits),
        'total_quantite': produits.aggregate(total=Sum('quantite_stock'))['total'] or 0,
        'produits_rupture': produits.filter(quantite_stock__lte=0).count(),
        'produits_alerte': produits.filter(quantite_stock__gt=0, quantite_stock__lte=5).count(),
    }
    
    context = {
        'produits': produits,
        'stats': stats,
        'type_article_filter': type_article,
        'statut_filter': statut,
    }
    return render(request, 'stock/rapports/stock.html', context)


@login_required
def rapport_mouvements(request):
    """Rapport des mouvements de stock"""
    
    today = date.today()
    date_debut = request.GET.get('date_debut', (today - timedelta(days=30)).isoformat())
    date_fin = request.GET.get('date_fin', today.isoformat())
    type_mouvement = request.GET.get('type_mouvement')
    produit_id = request.GET.get('produit')
    
    mouvements = MouvementStock.objects.filter(
        date_mouvement__date__gte=date_debut,
        date_mouvement__date__lte=date_fin
    )
    
    if type_mouvement:
        mouvements = mouvements.filter(type_mouvement=type_mouvement)
    if produit_id:
        mouvements = mouvements.filter(produit_id=produit_id)
    
    # Statistiques
    stats = {
        'total_mouvements': mouvements.count(),
        'total_entrees': mouvements.filter(type_mouvement='ENTREE').aggregate(total=Sum('quantite'))['total'] or 0,
        'total_sorties': mouvements.filter(type_mouvement='SORTIE').aggregate(total=Sum('quantite'))['total'] or 0,
        'total_transferts': mouvements.filter(type_mouvement='TRANSFERT').aggregate(total=Sum('quantite'))['total'] or 0,
    }
    
    # Groupement par jour
    mouvements_par_jour = mouvements.values('date_mouvement__date').annotate(
        total=Sum('quantite')
    ).order_by('-date_mouvement__date')[:30]
    
    context = {
        'mouvements': mouvements,
        'stats': stats,
        'mouvements_par_jour': mouvements_par_jour,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'type_mouvement_filter': type_mouvement,
        'produit_filter': produit_id,
        'produits': Produit.objects.filter(actif=True),
        'types_mouvement': MouvementStock.TYPE_MOUVEMENT_CHOICES,
    }
    return render(request, 'stock/rapports/mouvements.html', context)


@login_required
def alerte_stock(request):
    """Rapport des alertes stock (rupture et stock bas)"""
    
    # Produits en rupture (stock = 0)
    produits_rupture = Produit.objects.filter(
        actif=True,
        quantite_stock__lte=0
    ).order_by('nom')
    
    # Produits en alerte (stock bas)
    produits_alerte = Produit.objects.filter(
        actif=True,
        quantite_stock__gt=0,
        quantite_stock__lte=5
    ).order_by('quantite_stock', 'nom')
    
    # Lots expirant bientÃ´t
    date_limite = date.today() + timedelta(days=30)
    lots_expirant = Lot.objects.filter(
        actif=True,
        date_peremption__lte=date_limite,
        date_peremption__gte=date.today(),
        quantite_restante__gt=0
    ).order_by('date_peremption')[:20]
    
    # Lots pÃ©rimÃ©s
    lots_perimes = Lot.objects.filter(
        actif=True,
        date_peremption__lt=date.today(),
        quantite_restante__gt=0
    ).order_by('date_peremption')[:20]
    
    context = {
        'produits_rupture': produits_rupture,
        'produits_alerte': produits_alerte,
        'lots_expirant': lots_expirant,
        'lots_perimes': lots_perimes,
        'total_rupture': produits_rupture.count(),
        'total_alerte': produits_alerte.count(),
        'total_lots_expirant': lots_expirant.count(),
        'total_lots_perimes': lots_perimes.count(),
    }
    return render(request, 'stock/rapports/alertes.html', context)


@login_required
def export_stock_csv(request):
    """Export du stock en CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="stock_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Code', 'Nom', 'CatÃ©gorie', 'Type', 'Stock', 'UnitÃ©', 'Prix achat', 'Valeur'])
    
    for produit in Produit.objects.filter(actif=True).order_by('nom'):
        writer.writerow([
            produit.code,
            produit.nom,
            produit.categorie.nom if produit.categorie else '',
            produit.get_type_article_display(),
            produit.quantite_stock,
            produit.unite_base,
            produit.prix_achat,
            float(produit.quantite_stock) * float(produit.prix_achat)
        ])
    
    return response




