# apps/pos/views/point_vente.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib.auth.models import User, Group
from django.db import transaction, models
from django.urls import reverse
from django.http import JsonResponse
import json
from ..models import PointVente, SessionCaisse, PointVenteEntrepot, SessionPlanning, Vente
from ..constants import POINT_VENTE_GROUP_MAPPING
from apps.tresorerie.models import Caisse
from apps.rh.models import Employe
from apps.stock.models import Entrepot
from apps.authentication.groups import PATRON, MANAGER, COMPTABLE, RAF


def creer_utilisateur_pour_point_vente(point, password, emplacement):
    """Crée un utilisateur Django pour un point de vente"""
    
    username = f"pos_{point.code.lower()}"
    email = f"{point.code.lower()}@pos.hotel"
    
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=point.nom,
        last_name="POS"
    )
    
    # Déterminer le groupe selon l'emplacement
    group_name = POINT_VENTE_GROUP_MAPPING.get(emplacement, 'CAISSIER')
    try:
        group = Group.objects.get(name=group_name)
        user.groups.add(group)
    except Group.DoesNotExist:
        pass
    
    point.utilisateur = user
    return point


@login_required
def liste_points_vente(request):
    """Page d'accueil POS : admin → dashboard dynamique, employé → sélection PVs"""
    user_groups = list(request.user.groups.values_list('name', flat=True))
    is_admin = any(g in ['PATRON', 'MANAGER', 'COMPTABLE', 'RAF'] for g in user_groups)

    if not is_admin:
        employe = getattr(request.user, 'employe', None)
        if not employe:
            messages.error(request, "Aucun profil employé trouvé.")
            return redirect('dashboard:index')

        pv_ids = set()
        from django.utils import timezone
        aujourdhui = timezone.localtime().date()
        for pid in SessionPlanning.objects.filter(
            employe=employe, date=aujourdhui
        ).exclude(statut='ANNULE').values_list('point_vente_id', flat=True):
            pv_ids.add(pid)
        if employe.point_vente:
            pv_ids.add(employe.point_vente_id)

        if not pv_ids:
            messages.error(request, "Aucun point de vente trouvé. Vérifiez votre planning.")
            return redirect('pos:employe_dashboard')

        points = PointVente.objects.filter(id__in=pv_ids, actif=True).distinct()

        # Sélection obligatoire : l'employé choisit toujours son point de vente
        return render(request, 'pos/selection.html', {'points': points})

    context = {'is_admin': is_admin}
    return render(request, 'pos/liste.html', context)


@login_required
def api_point_vente_dashboard(request):
    """API JSON : retourne le dashboard dynamique des points de vente"""
    from django.db.models import Sum
    from datetime import date
    from django.utils import timezone

    user_groups = list(request.user.groups.values_list('name', flat=True))
    is_admin = any(g in ['PATRON', 'MANAGER', 'COMPTABLE', 'RAF'] for g in user_groups)
    employe = getattr(request.user, 'employe', None)

    today = date.today()

    if is_admin:
        points = PointVente.objects.filter(actif=True).prefetch_related('caisse', 'entrepot').order_by('nom')
    else:
        # Non-admin : uniquement les PVs où l'employé a un planning aujourd'hui ou est assigné directement
        pv_ids = set()
        if employe:
            if employe.point_vente_id:
                pv_ids.add(employe.point_vente_id)
            for pid in SessionPlanning.objects.filter(
                employe=employe, date=today
            ).exclude(statut='ANNULE').values_list('point_vente_id', flat=True):
                pv_ids.add(pid)
        points = PointVente.objects.filter(id__in=pv_ids, actif=True).prefetch_related('caisse', 'entrepot').order_by('nom')

    points_data = []
    for p in points:
        session = SessionCaisse.objects.filter(caisse=p.caisse, statut='OUVERTE').select_related('caissier_ouverture').first()
        today_sales = Vente.objects.filter(point_vente=p, created_at__date=today, statut='PAYEE').aggregate(t=Sum('montant_total'))['t'] or 0
        employes_planifies = SessionPlanning.objects.filter(point_vente=p, date=today).exclude(statut='ANNULE').count()

        points_data.append({
            'id': p.id,
            'code': p.code,
            'nom': p.nom,
            'emplacement': p.get_emplacement_display(),
            'actif': p.actif,
            'caisse_nom': p.caisse.nom if p.caisse else None,
            'caisse_solde': float(p.caisse.solde) if p.caisse else 0,
            'entrepot_nom': p.entrepot.nom if p.entrepot else None,
            'session_active': {
                'id': session.id,
                'caissier': session.caissier_ouverture.nom_complet if session.caissier_ouverture else None,
                'date_ouverture': session.date_ouverture.strftime('%d/%m %H:%M'),
                'total_ventes': float(session.total_ventes),
            } if session else None,
            'employes_planifies': employes_planifies,
            'today_sales': float(today_sales),
        })

    total_points = points.count()
    total_sales_today = Vente.objects.filter(created_at__date=today, statut='PAYEE').aggregate(t=Sum('montant_total'))['t'] or 0

    caisses_disponibles = list(Caisse.objects.filter(
        actif=True, point_vente_associe__isnull=True
    ).order_by('nom').values('id', 'nom', 'solde'))

    return JsonResponse({
        'success': True,
        'is_admin': is_admin,
        'stats': {
            'total': total_points,
            'actifs': total_points,
            'inactifs': 0,
            'today_sales': float(total_sales_today),
        },
        'points': points_data,
        'caisses_disponibles': caisses_disponibles,
    })


@login_required
@transaction.atomic
def ajouter_point_vente(request):
    """Ajouter un point de vente avec création automatique d'utilisateur"""
    
    if request.method == 'POST':
        try:
            nom = request.POST.get('nom')
            caisse_id = request.POST.get('caisse_id')
            password = request.POST.get('password', 'pos123456')
            
            if not nom or not caisse_id:
                messages.error(request, 'Le nom et la caisse sont obligatoires')
                return redirect('pos:ajouter_point_vente')
            
            caisse = get_object_or_404(Caisse, id=caisse_id)
            
            # Générer un code automatique (PV-XXX)
            prefixe = 'PV'
            dernier = PointVente.objects.filter(code__startswith=prefixe).order_by('code').last()
            if dernier:
                try:
                    num = int(dernier.code.replace(prefixe + '-', '')) + 1
                except ValueError:
                    num = PointVente.objects.count() + 1
            else:
                num = 1
            code = f"{prefixe}-{num:03d}"
            
            # Créer le point de vente
            point = PointVente.objects.create(
                code=code,
                nom=nom,
                emplacement='GUICHET',
                actif=True,
                caisse=caisse,
            )
            
            point = creer_utilisateur_pour_point_vente(point, password, 'GUICHET')
            
            messages.success(
                request, 
                f'✅ Point de vente "{point.nom}" créé.<br>'
                f'🔐 Login: <strong>{point.utilisateur.username}</strong><br>'
                f'🔑 Mot de passe: <strong>{password}</strong>'
            )
            return redirect('pos:detail_point_vente', point_id=point.id)
            
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
    
    # GET: caisses libres uniquement
    caisses_disponibles = Caisse.objects.filter(
        actif=True,
        point_vente_associe__isnull=True
    ).order_by('nom')
    
    context = {
        'caisses_disponibles': caisses_disponibles,
    }
    return render(request, 'pos/ajouter.html', context)


@login_required
def detail_point_vente(request, point_id):
    """Détail d'un point de vente — dynamique avec planning, session, ventes"""
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        messages.error(request, "Seuls la comptabilité et la direction peuvent voir les détails d'un point de vente.")
        return redirect('dashboard:index')
    point = get_object_or_404(PointVente, id=point_id)

    from django.db.models import Sum
    from datetime import date
    from django.utils import timezone

    today = date.today()
    now = timezone.localtime().time()

    # ─── Planning aujourd'hui ───
    plannings_ajd = SessionPlanning.objects.filter(
        point_vente=point, date=today
    ).exclude(statut='ANNULE').select_related('employe').order_by('heure_debut')

    # Responsable actif (celui dont le shift est en cours)
    responsable_actif = None
    for p in plannings_ajd:
        if p.heure_debut == p.heure_fin:
            responsable_actif = p.employe
            break
        if p.heure_debut <= now < p.heure_fin:
            responsable_actif = p.employe
            break

    # ─── Session active ───
    session_active = None
    if point.caisse:
        from ..services.caisse_session_service import CaisseSessionService
        session_active = CaisseSessionService.get_session_active(point.caisse)

    # ─── CA aujourd'hui ───
    today_sales = Vente.objects.filter(
        point_vente=point, created_at__date=today, statut='PAYEE'
    ).aggregate(t=Sum('montant_total'))['t'] or 0

    # ─── Caissier suggéré pour ouverture ───
    caissier_auto = responsable_actif or point.responsable or getattr(request.user, 'employe', None)

    # Gestion de la caisse
    if request.method == 'POST':
        if 'action_caisse' in request.POST:
            action = request.POST.get('action_caisse')
            if action == 'associer':
                caisse_id = request.POST.get('caisse_id')
                if caisse_id:
                    caisse = get_object_or_404(Caisse, id=caisse_id)
                    point.caisse = caisse
                    point.save()
                    messages.success(request, f'Caisse "{caisse.nom}" associée')
            elif action == 'dissocier':
                point.caisse = None
                point.save()
                messages.success(request, 'Caisse dissociée')
            return redirect('pos:detail_point_vente', point_id=point.id)

    caisses_disponibles = Caisse.objects.filter(
        actif=True, point_vente_associe__isnull=True
    )
    employes_disponibles = Employe.objects.filter(actif=True).select_related('poste', 'user')
    entrepots_disponibles = Entrepot.objects.filter(actif=True)
    entrepots_autorises = PointVenteEntrepot.objects.filter(
        point_vente=point
    ).select_related('entrepot')
    entrepots_lies_ids = set(entrepots_autorises.values_list('entrepot_id', flat=True))
    if point.entrepot:
        entrepots_lies_ids.add(point.entrepot_id)
    entrepots_ajoutables = entrepots_disponibles.exclude(id__in=entrepots_lies_ids)
    sessions_recentes = SessionCaisse.objects.filter(
        point_vente=point
    ).order_by('-date_ouverture')[:10]

    context = {
        'point': point,
        'responsable_actif': responsable_actif,
        'plannings_ajd': plannings_ajd,
        'today': today,
        'session_active': session_active,
        'today_sales': float(today_sales),
        'caissier_auto': caissier_auto,
        'caisses_disponibles': caisses_disponibles,
        'employes_disponibles': employes_disponibles,
        'entrepots_disponibles': entrepots_disponibles,
        'entrepots_autorises': entrepots_autorises,
        'entrepots_ajoutables': entrepots_ajoutables,
        'sessions_recentes': sessions_recentes,
    }
    return render(request, 'pos/detail.html', context)



@login_required
def modifier_point_vente(request, point_id):
    """Modifier un point de vente"""
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        messages.error(request, "Action non autorisée.")
        return redirect('dashboard:index')
    point = get_object_or_404(PointVente, id=point_id)
    
    if request.method == 'POST':
        try:
            point.nom = request.POST.get('nom')
            point.emplacement = request.POST.get('emplacement')
            point.actif = request.POST.get('actif') == 'on'
            point.save()
            
            # Gestion du mot de passe utilisateur
            password = request.POST.get('password')
            if password and point.utilisateur:
                point.utilisateur.set_password(password)
                point.utilisateur.save()
                messages.success(request, 'Mot de passe modifié avec succès')
            
            messages.success(request, f'Point de vente "{point.nom}" modifié')
            return redirect('pos:detail_point_vente', point_id=point.id)
            
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
    
    caisses_disponibles = Caisse.objects.filter(actif=True).exclude(id=point.caisse.id if point.caisse else None)
    context = {
        'point': point,
        'caisses_disponibles': caisses_disponibles,
        'emplacements': PointVente.EMPLACEMENT_CHOICES,
    }
    return render(request, 'pos/modifier.html', context)


@login_required
def supprimer_point_vente(request, point_id):
    """Désactiver un point de vente"""
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        messages.error(request, "Action non autorisée.")
        return redirect('dashboard:index')
    point = get_object_or_404(PointVente, id=point_id)
    
    if request.method == 'POST':
        point.actif = False
        point.save()
        messages.success(request, f'Point de vente "{point.nom}" désactivé')
        return redirect('pos:liste_points_vente')
    
    context = {'point': point}
    return render(request, 'pos/supprimer.html', context)


@login_required
def changer_mot_de_passe(request, point_id):
    """Changer le mot de passe d'un point de vente"""
    point = get_object_or_404(PointVente, id=point_id)
    
    if request.method == 'POST':
        password = request.POST.get('password')
        if password and point.utilisateur:
            point.utilisateur.set_password(password)
            point.utilisateur.save()
            messages.success(request, f'Mot de passe modifié pour {point.utilisateur.username}')
        else:
            messages.error(request, 'Aucun utilisateur associé à ce point de vente')
        
        return redirect('pos:detail_point_vente', point_id=point.id)
    
    context = {'point': point}
    return render(request, 'pos/changer_mot_de_passe.html', context)


@login_required
def changer_responsable(request, point_id):
    """Changer l'employé responsable du point de vente"""
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        messages.error(request, "Action non autorisée.")
        return redirect('dashboard:index')
    point = get_object_or_404(PointVente, id=point_id)
    
    if request.method == 'POST':
        responsable_id = request.POST.get('responsable_id')
        
        if responsable_id:
            responsable = get_object_or_404(Employe, id=responsable_id)
            point.responsable = responsable
            point.save()
            messages.success(request, f'✅ Responsable: {responsable.prenom} {responsable.nom}')
        else:
            messages.error(request, 'Veuillez sélectionner un employé')
        
        return redirect('pos:detail_point_vente', point_id=point.id)
    
    return redirect('pos:detail_point_vente', point_id=point.id)


@login_required
def liste_ventes(request):
    """Liste des ventes (historique unifié)"""
    from apps.rh.models import Employe
    from ..models import Vente, SessionCaisse
    from apps.stock.models import Produit

    points_vente = PointVente.objects.filter(actif=True)
    employe_ids = Vente.objects.filter(
        caissier__isnull=False
    ).values_list('caissier_id', flat=True).union(
        Vente.objects.filter(encaisse_par__isnull=False).values_list('encaisse_par_id', flat=True)
    )
    employes = Employe.objects.filter(id__in=employe_ids).order_by('nom', 'prenom')

    # Sessions récentes pour le filtre (les 100 dernières)
    sessions = SessionCaisse.objects.select_related(
        'point_vente', 'caissier_ouverture'
    ).order_by('-date_ouverture')[:100]

    # Produits réellement vendus (présents dans des lignes de vente)
    produit_ids = Vente.objects.filter(
        lignes__produit__isnull=False
    ).values_list('lignes__produit_id', flat=True).distinct()
    produits = Produit.objects.filter(id__in=produit_ids).order_by('nom')

    context = {
        'points_vente': points_vente,
        'employes': employes,
        'sessions': sessions,
        'produits': produits,
    }
    return render(request, 'pos/liste_ventes.html', context)


@login_required
@transaction.atomic
def changer_entrepot(request, point_id):
    """Changer l'entrepôt associé au point de vente"""
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        messages.error(request, "Action non autorisée.")
        return redirect('dashboard:index')
    point = get_object_or_404(PointVente, id=point_id)
    
    if request.method == 'POST':
        entrepot_id = request.POST.get('entrepot_id')
        
        if entrepot_id:
            entrepot = get_object_or_404(Entrepot, id=entrepot_id)
            point.entrepot = entrepot
        else:
            point.entrepot = None
        
        point.save()
        
        if point.entrepot:
            messages.success(request, f'✅ Entrepôt changé: {point.entrepot.nom}')
        else:
            messages.success(request, '✅ Entrepôt dissocié du point de vente')
        
        return redirect('pos:detail_point_vente', point_id=point.id)
    
    return redirect('pos:detail_point_vente', point_id=point.id)


@login_required
def api_ajouter_entrepot_pv(request, point_id):
    """API: Ajouter un entrepôt secondaire au point de vente"""
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        return JsonResponse({'success': False, 'error': 'Action non autorisée'}, status=403)
    point = get_object_or_404(PointVente, id=point_id)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            entrepot = get_object_or_404(Entrepot, id=data.get('entrepot_id'))
            pve, created = PointVenteEntrepot.objects.get_or_create(
                point_vente=point, entrepot=entrepot
            )
            return JsonResponse({
                'success': True,
                'created': created,
                'entrepot': {'id': entrepot.id, 'nom': entrepot.nom, 'type': entrepot.get_type_entrepot_display()}
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@login_required
def api_retirer_entrepot_pv(request, point_id):
    """API: Retirer un entrepôt secondaire du point de vente"""
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        return JsonResponse({'success': False, 'error': 'Action non autorisée'}, status=403)
    point = get_object_or_404(PointVente, id=point_id)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            entrepot_id = data.get('entrepot_id')
            PointVenteEntrepot.objects.filter(
                point_vente=point, entrepot_id=entrepot_id
            ).delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})

