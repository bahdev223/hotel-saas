from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.db import transaction, models
from django.http import JsonResponse
import json
from ..models import PointVente, SessionCaisse, PointVenteEntrepot, Vente, CaissePointVente, AffectationPointVente, ShiftEmploye
from apps.tresorerie.models import Caisse
from apps.rh.models import Employe
from apps.stock.models import Entrepot
from apps.authentication.groups import PATRON, MANAGER, COMPTABLE, RAF


def _get_employe_pv_ids(employe):
    if not employe:
        return []
    return list(AffectationPointVente.objects.filter(employe=employe, actif=True).values_list('point_vente_id', flat=True))


@login_required
def liste_points_vente(request):
    user_groups = list(request.user.groups.values_list('name', flat=True))
    is_admin = any(g in ['PATRON', 'MANAGER', 'COMPTABLE', 'RAF'] for g in user_groups)

    if not is_admin:
        employe = getattr(request.user, 'employe', None)
        if not employe:
            messages.error(request, "Aucun profil employ\u00e9 trouv\u00e9.")
            return redirect('dashboard:index')
        pv_ids = _get_employe_pv_ids(employe)
        for s in ShiftEmploye.objects.filter(
            affectation__employe=employe
        ).exclude(statut='ANNULE').select_related('affectation'):
            if s.affectation and s.affectation.point_vente_id:
                pv_ids.append(s.affectation.point_vente_id)
        pv_ids = list(set(pv_ids))
        if not pv_ids:
            messages.error(request, "Aucun point de vente trouv\u00e9.")
            return redirect('pos:employe_dashboard')
        points = PointVente.objects.filter(id__in=pv_ids, actif=True).distinct()
        return render(request, 'pos/selection.html', {'points': points})

    context = {'is_admin': is_admin}
    return render(request, 'pos/liste.html', context)


@login_required
def api_point_vente_dashboard(request):
    from django.db.models import Sum
    from datetime import date
    from django.utils import timezone

    user_groups = list(request.user.groups.values_list('name', flat=True))
    is_admin = any(g in ['PATRON', 'MANAGER', 'COMPTABLE', 'RAF'] for g in user_groups)
    employe = getattr(request.user, 'employe', None)
    today = date.today()

    if is_admin:
        points = PointVente.objects.filter(actif=True).order_by('nom')
    else:
        pv_ids = _get_employe_pv_ids(employe)
        for s in ShiftEmploye.objects.filter(
            affectation__employe=employe, debut_prevu__date=today
        ).exclude(statut='ANNULE').select_related('affectation'):
            if s.affectation and s.affectation.point_vente_id:
                pv_ids.append(s.affectation.point_vente_id)
        pv_ids = list(set(pv_ids))
        points = PointVente.objects.filter(id__in=pv_ids, actif=True).order_by('nom')

    points_data = []
    for p in points:
        cpv = CaissePointVente.objects.filter(point_vente=p, actif=True).select_related('caisse').first()
        caisse = cpv.caisse if cpv else None
        session = SessionCaisse.objects.filter(caisse=caisse, statut='OUVERTE').select_related('ouverte_par').first() if caisse else None
        today_sales = Vente.objects.filter(point_vente=p, created_at__date=today, statut='PAYEE').aggregate(t=Sum('montant_total'))['t'] or 0
        employes_planifies = ShiftEmploye.objects.filter(
            affectation__point_vente=p, debut_prevu__date=today
        ).exclude(statut='ANNULE').count()
        pve = p.entrepots_autorises.filter(principal=True, actif=True).select_related('entrepot').first()
        points_data.append({
            'id': p.id, 'code': p.code, 'nom': p.nom,
            'emplacement': p.get_type_display(),
            'actif': p.actif,
            'caisse_nom': caisse.nom if caisse else None,
            'caisse_solde': float(caisse.solde) if caisse else 0,
            'entrepot_nom': pve.entrepot.nom if pve else None,
            'session_active': {
                'id': session.id,
                'caissier': session.ouverte_par.nom_complet if session.ouverte_par else None,
                'date_ouverture': session.date_ouverture.strftime('%d/%m %H:%M'),
                'total_ventes': float(session.total_ventes),
            } if session else None,
            'employes_planifies': employes_planifies,
            'today_sales': float(today_sales),
        })

    total_points = points.count()
    total_sales_today = Vente.objects.filter(created_at__date=today, statut='PAYEE').aggregate(t=Sum('montant_total'))['t'] or 0
    caisses_ids = CaissePointVente.objects.filter(actif=True).values_list('caisse_id', flat=True)
    caisses_libres = Caisse.objects.exclude(id__in=caisses_ids).filter(actif=True)
    caisses_disponibles = list(caisses_libres.order_by('nom').values('id', 'nom', 'solde'))

    return JsonResponse({
        'success': True, 'is_admin': is_admin,
        'stats': {
            'total': total_points, 'actifs': total_points,
            'inactifs': 0, 'today_sales': float(total_sales_today),
        },
        'points': points_data, 'caisses_disponibles': caisses_disponibles,
    })


@login_required
@transaction.atomic
def ajouter_point_vente(request):
    if request.method == 'POST':
        try:
            nom = request.POST.get('nom')
            caisse_id = request.POST.get('caisse_id')
            if not nom or not caisse_id:
                messages.error(request, 'Le nom et la caisse sont obligatoires')
                return redirect('pos:ajouter_point_vente')
            caisse = get_object_or_404(Caisse, id=caisse_id)
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
            point = PointVente.objects.create(code=code, nom=nom, type='AUTRE', actif=True)
            CaissePointVente.objects.create(point_vente=point, caisse=caisse, principale=True)
            messages.success(request, f'\u2705 Point de vente "{point.nom}" cr\u00e9\u00e9.')
            return redirect('pos:detail_point_vente', point_id=point.id)
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')

    caisses_ids = CaissePointVente.objects.filter(actif=True).values_list('caisse_id', flat=True)
    caisses_disponibles = Caisse.objects.exclude(id__in=caisses_ids).filter(actif=True).order_by('nom')
    context = {'caisses_disponibles': caisses_disponibles}
    return render(request, 'pos/ajouter.html', context)


@login_required
def detail_point_vente(request, point_id):
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        messages.error(request, "Seuls la comptabilit\u00e9 et la direction peuvent voir les d\u00e9tails d'un point de vente.")
        return redirect('dashboard:index')
    point = get_object_or_404(PointVente, id=point_id)
    from django.db.models import Sum as SumM
    from datetime import date
    from django.utils import timezone

    today = date.today()
    shifts_ajd = ShiftEmploye.objects.filter(
        affectation__point_vente=point, debut_prevu__date=today
    ).exclude(statut='ANNULE').select_related('affectation__employe').order_by('debut_prevu')

    responsable_actif = None
    now = timezone.localtime()
    for s in shifts_ajd:
        if s.debut_prevu <= now <= s.fin_prevue:
            responsable_actif = s.affectation.employe if s.affectation else None
            break

    cpv = CaissePointVente.objects.filter(point_vente=point, actif=True).select_related('caisse').first()
    caisse = cpv.caisse if cpv else None
    session_active = None
    if caisse:
        from ..services.caisse_session_service import CaisseSessionService
        session_active = CaisseSessionService.get_session_active(caisse)

    today_sales = Vente.objects.filter(
        point_vente=point, created_at__date=today, statut='PAYEE'
    ).aggregate(t=SumM('montant_total'))['t'] or 0
    caissier_auto = responsable_actif or getattr(request.user, 'employe', None)

    if request.method == 'POST':
        if 'action_caisse' in request.POST:
            action = request.POST.get('action_caisse')
            if action == 'associer':
                caisse_id = request.POST.get('caisse_id')
                if caisse_id:
                    caisse_obj = get_object_or_404(Caisse, id=caisse_id)
                    CaissePointVente.objects.get_or_create(point_vente=point, caisse=caisse_obj, defaults={'principale': True})
                    messages.success(request, f'Caisse "{caisse_obj.nom}" associ\u00e9e')
            elif action == 'dissocier':
                cpv_obj = CaissePointVente.objects.filter(point_vente=point).first()
                if cpv_obj:
                    cpv_obj.delete()
                    messages.success(request, 'Caisse dissoci\u00e9e')
            return redirect('pos:detail_point_vente', point_id=point.id)

    caisses_ids = CaissePointVente.objects.filter(actif=True).exclude(point_vente=point).values_list('caisse_id', flat=True)
    caisses_disponibles = Caisse.objects.exclude(id__in=caisses_ids).filter(actif=True)
    employes_disponibles = Employe.objects.filter(actif=True).select_related('poste', 'user')
    entrepots_disponibles = Entrepot.objects.filter(actif=True)
    entrepots_autorises = PointVenteEntrepot.objects.filter(point_vente=point).select_related('entrepot')
    entrepots_lies_ids = set(entrepots_autorises.values_list('entrepot_id', flat=True))
    pve = point.entrepots_autorises.filter(principal=True, actif=True).first()
    if pve:
        entrepots_lies_ids.add(pve.entrepot_id)
    entrepots_ajoutables = entrepots_disponibles.exclude(id__in=entrepots_lies_ids)
    sessions_recentes = SessionCaisse.objects.filter(point_vente=point).order_by('-date_ouverture')[:10]

    context = {
        'point': point, 'responsable_actif': responsable_actif,
        'plannings_ajd': shifts_ajd, 'today': today,
        'session_active': session_active,
        'today_sales': float(today_sales), 'caissier_auto': caissier_auto,
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
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        messages.error(request, "Action non autoris\u00e9e.")
        return redirect('dashboard:index')
    point = get_object_or_404(PointVente, id=point_id)
    if request.method == 'POST':
        try:
            point.nom = request.POST.get('nom')
            point.type = request.POST.get('type', point.type)
            point.actif = request.POST.get('actif') == 'on'
            point.save()
            messages.success(request, f'Point de vente "{point.nom}" modifi\u00e9')
            return redirect('pos:detail_point_vente', point_id=point.id)
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')

    from ..constants import TypePointVente
    context = {
        'point': point,
        'type_choices': TypePointVente.choices,
    }
    return render(request, 'pos/modifier.html', context)


@login_required
def supprimer_point_vente(request, point_id):
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        messages.error(request, "Action non autoris\u00e9e.")
        return redirect('dashboard:index')
    point = get_object_or_404(PointVente, id=point_id)
    if request.method == 'POST':
        point.actif = False
        point.save()
        messages.success(request, f'Point de vente "{point.nom}" d\u00e9sactiv\u00e9')
        return redirect('pos:liste_points_vente')
    context = {'point': point}
    return render(request, 'pos/supprimer.html', context)


@login_required
def changer_mot_de_passe(request, point_id):
    point = get_object_or_404(PointVente, id=point_id)
    messages.warning(request, "Les points de vente n'ont plus de compte s\u00e9par\u00e9. Connectez-vous avec votre compte personnel.")
    return redirect('pos:detail_point_vente', point_id=point.id)


@login_required
def changer_responsable(request, point_id):
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        messages.error(request, "Action non autoris\u00e9e.")
        return redirect('dashboard:index')
    point = get_object_or_404(PointVente, id=point_id)
    if request.method == 'POST':
        responsable_id = request.POST.get('responsable_id')
        if responsable_id:
            responsable = get_object_or_404(Employe, id=responsable_id)
            AffectationPointVente.objects.get_or_create(
                employe=responsable, point_vente=point,
                defaults={'role': 'RESPONSABLE', 'peut_vendre': True, 'peut_encaisser': True,
                          'peut_ouvrir_caisse': True, 'peut_fermer_caisse': True,
                          'peut_annuler_vente': True, 'peut_consulter_rapports': True,
                          'principal': True, 'actif': True},
            )
            messages.success(request, f'\u2705 Responsable: {responsable.prenom} {responsable.nom}')
        else:
            messages.error(request, 'Veuillez s\u00e9lectionner un employ\u00e9')
        return redirect('pos:detail_point_vente', point_id=point.id)
    return redirect('pos:detail_point_vente', point_id=point.id)


@login_required
def liste_ventes(request):
    from apps.rh.models import Employe as RhEmp
    from ..models import Vente as VenteM, SessionCaisse as SC
    from apps.stock.models import Produit as Prod

    points_vente = PointVente.objects.filter(actif=True)
    employe_ids = VenteM.objects.filter(caissier__isnull=False).values_list('caissier_id', flat=True).union(
        VenteM.objects.filter(encaisse_par__isnull=False).values_list('encaisse_par_id', flat=True)
    )
    employes = RhEmp.objects.filter(id__in=employe_ids).order_by('nom', 'prenom')
    sessions = SC.objects.select_related('point_vente', 'ouverte_par').order_by('-date_ouverture')[:100]
    produit_ids = VenteM.objects.filter(lignes__produit__isnull=False).values_list('lignes__produit_id', flat=True).distinct()
    produits = Prod.objects.filter(id__in=produit_ids).order_by('nom')

    context = {
        'points_vente': points_vente, 'employes': employes,
        'sessions': sessions, 'produits': produits,
    }
    return render(request, 'pos/liste_ventes.html', context)


@login_required
@transaction.atomic
def changer_entrepot(request, point_id):
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        messages.error(request, "Action non autoris\u00e9e.")
        return redirect('dashboard:index')
    point = get_object_or_404(PointVente, id=point_id)
    if request.method == 'POST':
        entrepot_id = request.POST.get('entrepot_id')
        if entrepot_id:
            entrepot = get_object_or_404(Entrepot, id=entrepot_id)
            PointVenteEntrepot.objects.update_or_create(
                point_vente=point, entrepot=entrepot,
                defaults={'principal': True, 'actif': True},
            )
            messages.success(request, f'\u2705 Entrep\u00f4t associ\u00e9: {entrepot.nom}')
        else:
            messages.error(request, 'Veuillez s\u00e9lectionner un entrep\u00f4t')
        return redirect('pos:detail_point_vente', point_id=point.id)
    return redirect('pos:detail_point_vente', point_id=point.id)


@login_required
def api_ajouter_entrepot_pv(request, point_id):
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        return JsonResponse({'success': False, 'error': 'Action non autoris\u00e9e'}, status=403)
    point = get_object_or_404(PointVente, id=point_id)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            entrepot = get_object_or_404(Entrepot, id=data.get('entrepot_id'))
            pve, created = PointVenteEntrepot.objects.get_or_create(point_vente=point, entrepot=entrepot)
            return JsonResponse({
                'success': True, 'created': created,
                'entrepot': {'id': entrepot.id, 'nom': entrepot.nom, 'type': entrepot.get_type_entrepot_display()},
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@login_required
def api_retirer_entrepot_pv(request, point_id):
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        return JsonResponse({'success': False, 'error': 'Action non autoris\u00e9e'}, status=403)
    point = get_object_or_404(PointVente, id=point_id)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            PointVenteEntrepot.objects.filter(point_vente=point, entrepot_id=data.get('entrepot_id')).delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})
