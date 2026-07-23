from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
import json
from ..models import Employe
from ..permissions import user_can_gerer_rh


def _extract_data(request):
    """Extract data from request (JSON body or POST/GET)"""
    if request.content_type == 'application/json':
        return json.loads(request.body)
    return request.POST


@csrf_exempt
@login_required
def api_ajouter_employe(request):
    """API pour ajouter un employé"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    if request.method == 'POST':
        try:
            data = _extract_data(request)
            employe = Employe.objects.create(
                nom=data.get('nom'),
                prenom=data.get('prenom'),
                date_naissance=data.get('date_naissance'),
                email=data.get('email'),
                telephone=data.get('telephone'),
                adresse=data.get('adresse', ''),
                sexe=data.get('sexe', 'M'),
                date_embauche=data.get('date_embauche'),
                departement_id=data.get('departement') or None,
                poste_id=data.get('poste') or None,
                situation_familiale=data.get('situation_familiale', 'Celibataire'),
                nombre_enfants=int(data.get('nombre_enfants', 0)),
                diplome=data.get('diplome', ''),
                description=data.get('description', ''),
                conjoint_civilite=data.get('conjoint_civilite', ''),
                conjoint_nom=data.get('conjoint_nom', ''),
                conjoint_prenom=data.get('conjoint_prenom', ''),
                conjoint_contact=data.get('conjoint_contact', ''),
                personne_reference_nom=data.get('personne_reference_nom', ''),
                personne_reference_prenom=data.get('personne_reference_prenom', ''),
                personne_reference_contact=data.get('personne_reference_contact', ''),
                actif=True
            )
            if 'photo' in request.FILES:
                employe.photo = request.FILES['photo']
                employe.save(update_fields=['photo'])
            return JsonResponse({
                'success': True,
                'message': f'Employé {employe.nom} ajouté',
                'matricule': employe.matricule,
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@login_required
def api_prochain_matricule(request):
    """Retourne le prochain matricule disponible"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    return JsonResponse({'matricule': Employe.generer_prochain_matricule()})


@login_required
def api_detail_employe(request, matricule):
    """API détail employé pour modification"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    employe = get_object_or_404(Employe, matricule=matricule)
    return JsonResponse({
        'success': True,
        'employe': {
            'matricule': employe.matricule,
            'nom': employe.nom,
            'prenom': employe.prenom,
            'date_naissance': str(employe.date_naissance) if employe.date_naissance else '',
            'email': employe.email or '',
            'telephone': employe.telephone,
            'adresse': employe.adresse or '',
            'sexe': employe.sexe,
            'date_embauche': str(employe.date_embauche) if employe.date_embauche else '',
            'departement': employe.departement.libelle if employe.departement else '',
            'poste': employe.poste.intitule if employe.poste else '',
            'actif': employe.actif,
            'situation_familiale': employe.situation_familiale,
            'nombre_enfants': employe.nombre_enfants,
            'diplome': employe.diplome or '',
            'description': employe.description or '',
            'conjoint_civilite': employe.conjoint_civilite or '',
            'conjoint_nom': employe.conjoint_nom or '',
            'conjoint_prenom': employe.conjoint_prenom or '',
            'conjoint_contact': employe.conjoint_contact or '',
            'personne_reference_nom': employe.personne_reference_nom or '',
            'personne_reference_prenom': employe.personne_reference_prenom or '',
            'personne_reference_contact': employe.personne_reference_contact or '',
            'photo': employe.photo.url if employe.photo else '',
            'has_user': employe.user_id is not None,
            'user_is_active': employe.user.is_active if employe.user_id else False,
            'user_username': employe.user.username if employe.user_id else '',
        }
    })


@csrf_exempt
@login_required
def api_modifier_employe(request, matricule):
    """API pour modifier un employé"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    if request.method == 'POST':
        try:
            employe = get_object_or_404(Employe, matricule=matricule)
            data = _extract_data(request)
            employe.nom = data.get('nom')
            employe.prenom = data.get('prenom')
            employe.date_naissance = data.get('date_naissance')
            employe.email = data.get('email')
            employe.telephone = data.get('telephone')
            employe.adresse = data.get('adresse', '')
            employe.sexe = data.get('sexe', 'M')
            employe.date_embauche = data.get('date_embauche')
            employe.departement_id = data.get('departement') or None
            employe.poste_id = data.get('poste') or None
            employe.situation_familiale = data.get('situation_familiale', 'Celibataire')
            employe.nombre_enfants = int(data.get('nombre_enfants', 0))
            employe.diplome = data.get('diplome', '')
            employe.description = data.get('description', '')
            employe.conjoint_civilite = data.get('conjoint_civilite', '')
            employe.conjoint_nom = data.get('conjoint_nom', '')
            employe.conjoint_prenom = data.get('conjoint_prenom', '')
            employe.conjoint_contact = data.get('conjoint_contact', '')
            employe.personne_reference_nom = data.get('personne_reference_nom', '')
            employe.personne_reference_prenom = data.get('personne_reference_prenom', '')
            employe.personne_reference_contact = data.get('personne_reference_contact', '')
            if 'photo' in request.FILES:
                employe.photo = request.FILES['photo']
            employe.save()
            return JsonResponse({
                'success': True,
                'message': f'Employé {employe.nom} modifié',
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@csrf_exempt
@login_required
def api_supprimer_compte_employe(request, matricule):
    """Supprime le compte utilisateur d'un employé"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    try:
        employe = get_object_or_404(Employe, matricule=matricule)
        if not employe.user:
            return JsonResponse({'success': False, 'error': 'Aucun compte utilisateur associé'})
        user = employe.user
        employe.user = None
        employe.save()
        user.delete()
        return JsonResponse({'success': True, 'message': 'Compte utilisateur supprimé'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
def api_desactiver_compte_employe(request, matricule):
    """Désactive le compte utilisateur d'un employé"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    try:
        employe = get_object_or_404(Employe, matricule=matricule)
        if not employe.user:
            return JsonResponse({'success': False, 'error': 'Aucun compte utilisateur associé'})
        employe.user.is_active = False
        employe.user.save()
        return JsonResponse({'success': True, 'message': 'Compte utilisateur désactivé'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
def api_activer_compte_employe(request, matricule):
    """Active le compte utilisateur d'un employé"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    try:
        employe = get_object_or_404(Employe, matricule=matricule)
        if not employe.user:
            return JsonResponse({'success': False, 'error': 'Aucun compte utilisateur associé'})
        employe.user.is_active = True
        employe.user.save()
        return JsonResponse({'success': True, 'message': 'Compte utilisateur activé'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
def api_supprimer_employe(request, matricule):
    """Supprime un employé (hard delete)"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    try:
        employe = get_object_or_404(Employe, matricule=matricule)
        nom_complet = f"{employe.nom} {employe.prenom}"
        if employe.user:
            user = employe.user
            employe.user = None
            employe.save()
            user.delete()
        employe.delete()
        return JsonResponse({'success': True, 'message': f'Employé {nom_complet} supprimé'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
