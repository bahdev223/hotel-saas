# apps/authentication/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
import uuid

from .models import Profile, PasswordResetToken
from .decorators import role_required
from .utils import redirect_to_group_home, get_client_ip


def login_view(request):
    """Page de connexion"""
    if request.user.is_authenticated:
        return redirect_to_group_home(request.user)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                
                if hasattr(user, 'profile'):
                    user.profile.derniere_connexion_ip = get_client_ip(request)
                    user.profile.save()
                
                messages.success(request, f'Bienvenue {user.username} !')
                
                next_url = request.GET.get('next')
                if next_url and next_url != '/':
                    return redirect(next_url)
                
                return redirect_to_group_home(user)
                
            else:
                messages.error(request, 'Compte désactivé. Contactez l\'administrateur.')
        else:
            messages.error(request, 'Identifiants incorrects')
    
    return render(request, 'authentication/login.html')


def logout_view(request):
    """Déconnexion"""
    if request.user.is_authenticated:
        employe = getattr(request.user, 'employe', None)
        if employe:
            from apps.pos.models import SessionCaisse
            from django.utils import timezone
            sessions_ouvertes = SessionCaisse.objects.filter(
                caissier_ouverture=employe, statut='OUVERTE'
            )
            for session in sessions_ouvertes:
                session.statut = 'FERMEE'
                session.date_fermeture = timezone.now()
                session.caissier_fermeture = employe
                session.save()
    logout(request)
    messages.info(request, 'Vous avez été déconnecté')
    return redirect('authentication:login')


@login_required
def creer_utilisateur(request):
    """Créer un utilisateur (admin seulement)"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        group_id = request.POST.get('group')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        telephone = request.POST.get('telephone', '')
        matricule_employe = request.POST.get('matricule_employe', '')
        
        if password != password_confirm:
            messages.error(request, 'Les mots de passe ne correspondent pas')
            return redirect('authentication:creer_utilisateur')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Ce nom d\'utilisateur existe déjà')
            return redirect('authentication:creer_utilisateur')
        
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=True
            )
            
            # Ajouter au groupe
            if group_id:
                group = Group.objects.get(id=group_id)
                user.groups.add(group)
            
            # Mettre à jour le profil
            if hasattr(user, 'profile'):
                user.profile.telephone = telephone
                user.profile.matricule_employe = matricule_employe
                user.profile.save()
            
            messages.success(request, f'Utilisateur {username} créé avec succès')
            return redirect('admin:auth_user_changelist')
            
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
    
    groups = Group.objects.all().order_by('name')
    
    context = {
        'groups': groups,
        'titre': 'Créer un utilisateur'
    }
    return render(request, 'authentication/creer_utilisateur.html', context)


@login_required
def reinitialiser_mot_de_passe(request, user_id):
    """Réinitialiser le mot de passe d'un utilisateur"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if new_password != confirm_password:
            messages.error(request, 'Les mots de passe ne correspondent pas')
            return redirect('authentication:reinitialiser_mot_de_passe', user_id=user_id)
        
        user.set_password(new_password)
        user.save()
        
        messages.success(request, f'Mot de passe de {user.username} réinitialisé avec succès')
        return redirect('admin:auth_user_changelist')
    
    context = {
        'user': user,
        'titre': f'Réinitialiser mot de passe - {user.username}'
    }
    return render(request, 'authentication/reinitialiser_mdp.html', context)


@login_required
def mon_profil(request):
    """Page de profil utilisateur"""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        
        if hasattr(user, 'profile'):
            user.profile.telephone = request.POST.get('telephone', '')
            user.profile.save()
        
        if 'avatar' in request.FILES:
            profile = user.profile if hasattr(user, 'profile') else Profile.objects.get_or_create(user=user)[0]
            profile.avatar = request.FILES['avatar']
            profile.save()
        
        messages.success(request, 'Profil mis à jour')
        return redirect('authentication:mon_profil')
    
    context = {
        'titre': 'Mon profil'
    }
    return render(request, 'authentication/profil.html', context)


@login_required
def employe_accueil(request):
    """Page d'accueil dédiée aux employés — profil riche + accès POS"""

    try:
        employe = request.user.employe
    except Exception:
        return redirect('dashboard:index')
    if not employe:
        return redirect('dashboard:index')

    from apps.pos.models import PointVente, AffectationPointVente
    from apps.pos.services.caisse_session_service import get_planning_actif

    groupe = request.user.groups.first()

    a_un_acces_pos = False
    pv_unique = None

    affectations = AffectationPointVente.objects.filter(employe=employe, actif=True).select_related('point_vente')
    if affectations.exists():
        a_un_acces_pos = True
        pv_unique = affectations.first().point_vente if affectations.count() == 1 else None

    pvs_accessibles = list(PointVente.objects.filter(
        id__in=affectations.values_list('point_vente_id', flat=True), actif=True
    ))
    for pv in PointVente.objects.filter(actif=True).exclude(id__in=[p.id for p in pvs_accessibles]):
        if get_planning_actif(employe, pv):
            pvs_accessibles.append(pv)

    if pvs_accessibles:
        a_un_acces_pos = True
        pv_unique = pvs_accessibles[0] if len(pvs_accessibles) == 1 else None

    context = {
        'employe': employe,
        'groupe': groupe,
        'a_un_acces_pos': a_un_acces_pos,
        'pv_unique': pv_unique,
        'titre': 'Mon espace',
    }
    return render(request, 'authentication/employe_accueil.html', context)


@login_required
def changer_mot_de_passe(request):
    """Changer son mot de passe"""
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.user.check_password(old_password):
            messages.error(request, 'Mot de passe actuel incorrect')
            return redirect('authentication:changer_mot_de_passe')
        
        if new_password != confirm_password:
            messages.error(request, 'Les nouveaux mots de passe ne correspondent pas')
            return redirect('authentication:changer_mot_de_passe')
        
        request.user.set_password(new_password)
        request.user.save()
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Mot de passe modifié avec succès')
        return redirect('authentication:mon_profil')
    
    context = {
        'titre': 'Changer mon mot de passe'
    }
    return render(request, 'authentication/changer_mdp.html')


def mot_de_passe_oublie(request):
    """Demande de réinitialisation de mot de passe"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email)
            
            token = str(uuid.uuid4())
            expires_at = timezone.now() + timedelta(hours=24)
            
            PasswordResetToken.objects.create(
                user=user,
                token=token,
                expires_at=expires_at
            )
            
            reset_url = request.build_absolute_uri(f'/auth/reset/{token}/')
            print(f"URL de réinitialisation: {reset_url}")
            
            messages.success(request, 'Un email de réinitialisation vous a été envoyé')
            return redirect('authentication:login')
            
        except User.DoesNotExist:
            messages.warning(request, 'Aucun compte trouvé avec cet email')
    
    return render(request, 'authentication/mot_de_passe_oublie.html')


def reset_mot_de_passe(request, token):
    """Réinitialisation avec token"""
    try:
        reset_token = PasswordResetToken.objects.get(token=token, used=False)
        
        if not reset_token.is_valid():
            messages.error(request, 'Ce lien a expiré')
            return redirect('authentication:mot_de_passe_oublie')
        
        if request.method == 'POST':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if new_password != confirm_password:
                messages.error(request, 'Les mots de passe ne correspondent pas')
                return redirect('authentication:reset_mot_de_passe', token=token)
            
            user = reset_token.user
            user.set_password(new_password)
            user.save()
            
            reset_token.used = True
            reset_token.save()
            
            messages.success(request, 'Mot de passe réinitialisé avec succès')
            return redirect('authentication:login')
        
        context = {
            'token': token,
            'titre': 'Réinitialiser mon mot de passe'
        }
        return render(request, 'authentication/reset_mdp.html', context)
        
    except PasswordResetToken.DoesNotExist:
        messages.error(request, 'Token invalide')
        return redirect('authentication:mot_de_passe_oublie')
    
    
    