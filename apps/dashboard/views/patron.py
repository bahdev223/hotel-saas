# apps/dashboard/views/patron.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import date, timedelta, datetime
from decimal import Decimal
from calendar import month_name

from apps.pos.models import Vente, LigneVente, Commande
from apps.hotel.models import LocationModel, UniteModel
from apps.clients.models import Client
from apps.restaurant.models import TableModel
from apps.stock.models import Produit, StockEntrepot, Entrepot
from apps.tresorerie.models import Caisse, MouvementCaisse
from apps.rh.models import Employe, Pointage
# from apps.depenses.models import DepenseModel  # ← SUPPRIMÉ (n'existe pas)


def is_patron(user):
    return user.is_authenticated and user.groups.filter(name='PATRON').exists()


@login_required
@user_passes_test(is_patron)
def patron_dashboard(request):
    """Dashboard patron - Vue stratégique complète"""
    
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    first_day_month = date(today.year, today.month, 1)
    last_month = today.replace(day=1) - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    # ========== 1. CARTES KPI PRINCIPALES ==========
    
    # CA du jour
    ca_today = Vente.objects.filter(
        created_at__date=today,
        statut='PAYEE'
    ).aggregate(total=Sum('montant_total'))['total'] or Decimal(0)
    
    # CA de la semaine
    ca_week = Vente.objects.filter(
        created_at__date__gte=week_ago,
        statut='PAYEE'
    ).aggregate(total=Sum('montant_total'))['total'] or Decimal(0)
    
    # Dépenses du jour (à remplacer par une vraie source plus tard)
    # TODO: Créer un modèle Dépense ou utiliser les sorties de caisse
    depenses_today = MouvementCaisse.objects.filter(
        date__date=today,
        type_mouvement='SORTIE'
    ).aggregate(total=Sum('montant'))['total'] or Decimal(0)
    
    # Bénéfice estimé (CA - dépenses)
    benefice_estime = ca_today - depenses_today
    
    # ========== 2. SITUATION HÔTEL ==========
    chambres = UniteModel.objects.filter(actif=True, type_unite='CHAMBRE')
    total_chambres = chambres.count()
    chambres_occupees = chambres.filter(statut='OCCUPEE').count()
    chambres_libres = chambres.filter(statut='DISPONIBLE').count()
    chambres_nettoyage = chambres.filter(statut='NETTOYAGE').count()
    
    taux_occupation = round((chambres_occupees / total_chambres * 100), 1) if total_chambres > 0 else 0
    
    # Locations en cours aujourd'hui
    locations_en_cours = LocationModel.objects.filter(
        date_debut__date=today,
        statut='CONFIRMEE'
    ).count()
    
    locations_terminees = LocationModel.objects.filter(
        date_fin__date=today,
        statut='TERMINEE'
    ).count()
    
    # ========== 3. SITUATION RESTAURANT ==========
    commandes_restaurant_jour = Commande.objects.filter(
        created_at__date=today,
        type_commande__in=['SUR_PLACE', 'EMPORTER']
    ).count()
    
    tables_occupees = TableModel.objects.filter(statut='OCCUPEE').count()
    tables_libres = TableModel.objects.filter(statut='LIBRE').count()
    total_tables = tables_occupees + tables_libres
    
    # ========== 4. SITUATION TRÉSORERIE ==========
    caisses = Caisse.objects.filter(actif=True)
    solde_caisses = sum(float(c.solde) for c in caisses if c.type_financier in ('ESPECES', 'MOBILE_MONEY'))
    solde_banques = sum(float(c.solde) for c in caisses if c.type_financier == 'BANQUE')
    solde_total = solde_caisses + solde_banques

    # Mouvements du jour (hors banques)
    flux_ajd = MouvementCaisse.objects.filter(date__date=today).exclude(caisse__type_financier='BANQUE')
    entrees_jour = flux_ajd.filter(type_mouvement='ENTREE').aggregate(total=Sum('montant'))['total'] or Decimal(0)
    sorties_jour = flux_ajd.filter(type_mouvement='SORTIE').aggregate(total=Sum('montant'))['total'] or Decimal(0)
    
    # ========== 5. ALERTES ==========
    alertes = []
    
    # Stock faible (entrepôt RESTAURANT)
    entrepot_restaurant = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
    if entrepot_restaurant:
        stocks_faibles = StockEntrepot.objects.filter(
            entrepot=entrepot_restaurant,
            quantite__lte=5,
            quantite__gt=0
        ).select_related('produit')[:5]
        
        for stock in stocks_faibles:
            alertes.append({
                'type': 'stock_faible',
                'niveau': 'warning',
                'message': f"⚠️ Stock faible: {stock.produit.nom} ({stock.quantite} {stock.produit.unite_base})",
                'lien': f"/stock/produits/{stock.produit.id}/"
            })
    
    # Stock rupture
    stocks_rupture = StockEntrepot.objects.filter(
        entrepot=entrepot_restaurant,
        quantite__lte=0
    ).select_related('produit')[:3]
    
    for stock in stocks_rupture:
        alertes.append({
            'type': 'rupture',
            'niveau': 'danger',
            'message': f"❌ Rupture: {stock.produit.nom}",
            'lien': f"/stock/produits/{stock.produit.id}/"
        })
    
    # Caisse faible
    for caisse in caisses:
        if caisse.solde < 50000:
            alertes.append({
                'type': 'caisse_faible',
                'niveau': 'warning',
                'message': f"⚠️ Caisse {caisse.nom} faible: {caisse.solde:,.0f} F",
                'lien': f"/tresorerie/caisses/{caisse.id}/"
            })
    
    # Chambres à nettoyer
    if chambres_nettoyage > 0:
        alertes.append({
            'type': 'menage',
            'niveau': 'info',
            'message': f"🧹 {chambres_nettoyage} chambre(s) à nettoyer",
            'lien': "/hotel/chambres/?statut=NETTOYAGE"
        })
    
    # ========== 6. TOP PRODUITS VENDUS ==========
    top_produits = LigneVente.objects.filter(
        vente__created_at__date__gte=week_ago,
        vente__statut='PAYEE'
    ).values(
        'produit__nom', 'menu__nom'
    ).annotate(
        total_quantite=Sum('quantite'),
        total_montant=Sum(F('quantite') * F('prix_unitaire'))
    ).order_by('-total_montant')[:5]
    
    top_produits_list = []
    for item in top_produits:
        nom = item.get('produit__nom') or item.get('menu__nom') or 'Inconnu'
        top_produits_list.append({
            'nom': nom,
            'quantite': float(item['total_quantite'] or 0),
            'montant': float(item['total_montant'] or 0)
        })
    
    # ========== 7. ACTIVITÉS RÉCENTES ==========
    activites_recentes = []
    
    # Dernières ventes
    dernieres_ventes = Vente.objects.filter(statut='PAYEE').order_by('-created_at')[:10]
    for vente in dernieres_ventes:
        activites_recentes.append({
            'heure': vente.created_at.strftime('%H:%M'),
            'action': 'Vente',
            'detail': f"Vente {vente.numero} - {vente.montant_total:,.0f} F",
            'type': 'success',
            'icone': '💰',
            'lien': f"/pos/ventes/{vente.id}/"
        })
    
    # Dernières sorties de caisse (dépenses)
    dernieres_depenses = MouvementCaisse.objects.filter(
        type_mouvement='SORTIE'
    ).order_by('-date')[:5]
    for depense in dernieres_depenses:
        activites_recentes.append({
            'heure': depense.date.strftime('%H:%M'),
            'action': 'Dépense',
            'detail': f"{depense.libelle} - {depense.montant:,.0f} F",
            'type': 'warning',
            'icone': '📤',
            'lien': f"/tresorerie/mouvements/{depense.id}/"
        })
    
    # Dernières locations
    dernieres_reservations = LocationModel.objects.filter(
        statut='CONFIRMEE'
    ).select_related('client', 'unite').order_by('-created_at')[:5]
    for res in dernieres_reservations:
        activites_recentes.append({
            'heure': res.created_at.strftime('%H:%M'),
            'action': 'Réservation',
            'detail': f"Chambre {res.unite.code} - {res.client.nom} {res.client.prenom}",
            'type': 'info',
            'icone': '📅',
            'lien': f"/hotel/locations/{res.id}/"
        })
    
    # Trier par heure
    activites_recentes.sort(key=lambda x: x['heure'], reverse=True)
    activites_recentes = activites_recentes[:15]
    
    # ========== 8. EMPLOYÉS PRÉSENTS ==========
    employes_presents = Pointage.objects.filter(
        date_pointage=today,
        heure_entree__isnull=False,
        heure_sortie__isnull=True
    ).select_related('employe')[:10]
    
    # ========== 9. GRAPHIQUES ==========
    
    # CA 7 derniers jours
    ca_7_jours = []
    for i in range(6, -1, -1):
        jour = today - timedelta(days=i)
        ca_jour = Vente.objects.filter(
            created_at__date=jour,
            statut='PAYEE'
        ).aggregate(total=Sum('montant_total'))['total'] or Decimal(0)
        ca_7_jours.append({
            'date': jour.strftime('%d/%m'),
            'total': float(ca_jour)
        })
    
    # CA par mois (12 derniers mois)
    ca_par_mois = []
    for i in range(11, -1, -1):
        mois_date = today.replace(day=1) - timedelta(days=i*30)
        annee = mois_date.year
        mois = mois_date.month
        
        date_debut = date(annee, mois, 1)
        if mois == 12:
            date_fin = date(annee + 1, 1, 1) - timedelta(days=1)
        else:
            date_fin = date(annee, mois + 1, 1) - timedelta(days=1)
        
        ca_mois = Vente.objects.filter(
            created_at__date__gte=date_debut,
            created_at__date__lte=date_fin,
            statut='PAYEE'
        ).aggregate(total=Sum('montant_total'))['total'] or 0
        
        ca_par_mois.append({
            'mois': month_name[mois][:3] + f" {annee}",
            'total': float(ca_mois)
        })
    
    # Répartition CA par type de produit
    ca_produits = LigneVente.objects.filter(
        vente__created_at__date__gte=week_ago,
        vente__statut='PAYEE'
    ).values(
        'produit__type_article', 'menu__id'
    ).annotate(
        total=Sum(F('quantite') * F('prix_unitaire'))
    )
    
    total_produits = Decimal(0)
    total_menus = Decimal(0)
    
    for item in ca_produits:
        if item.get('produit__type_article') == 'MARCHANDISE' or item.get('produit__type_article') is not None:
            total_produits += item['total']
        elif item.get('menu__id') is not None:
            total_menus += item['total']
    
    repartition = [
        {'nom': '📦 Produits', 'montant': float(total_produits), 'couleur': '#0a7c6e'},
        {'nom': '🍽️ Menus', 'montant': float(total_menus), 'couleur': '#3b82f6'},
    ]
    
    # ========== CONTEXTE ==========
    context = {
        # KPI
        'ca_today': float(ca_today),
        'ca_week': float(ca_week),
        'depenses_today': float(depenses_today),
        'benefice_estime': float(benefice_estime),
        
        # Hôtel
        'total_chambres': total_chambres,
        'chambres_occupees': chambres_occupees,
        'chambres_libres': chambres_libres,
        'chambres_nettoyage': chambres_nettoyage,
        'taux_occupation': taux_occupation,
        'locations_en_cours': locations_en_cours,
        'locations_terminees': locations_terminees,
        
        # Restaurant
        'commandes_restaurant_jour': commandes_restaurant_jour,
        'tables_occupees': tables_occupees,
        'tables_libres': tables_libres,
        
        # Trésorerie
        'solde_caisses': solde_caisses,
        'solde_banques': solde_banques,
        'solde_total': solde_total,
        'entrees_jour': float(entrees_jour),
        'sorties_jour': float(sorties_jour),
        
        # Alertes
        'alertes': alertes,
        'nb_alertes': len(alertes),
        
        # Top produits
        'top_produits': top_produits_list,
        
        # Activités
        'activites_recentes': activites_recentes,
        
        # Employés
        'employes_presents': employes_presents,
        'nb_employes_presents': employes_presents.count(),
        
        # Graphiques
        'ca_7_jours': ca_7_jours,
        'ca_par_mois': ca_par_mois,
        'repartition': repartition,
        
        # Dates
        'today': today,
        'today_str': today.strftime('%d/%m/%Y'),
    }
    
    return render(request, 'dashboard/patron/home.html', context)