# apps/authentication/models.py
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """Profil utilisateur - Données supplémentaires"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    telephone = models.CharField(max_length=20, blank=True, null=True)
    matricule_employe = models.CharField(max_length=20, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name='Photo de profil')
    theme = models.CharField(max_length=10, default='light')
    notifications_email = models.BooleanField(default=True)
    derniere_connexion_ip = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'auth_profiles'
        verbose_name = 'Profil'
        verbose_name_plural = 'Profils'
    
    def __str__(self):
        groups = ", ".join([g.name for g in self.user.groups.all()])
        return f"{self.user.username} - ({groups or 'Aucun groupe'})"
    
    @property
    def role(self):
        group = self.user.groups.first()
        return group.name if group else "AUCUN"


class PasswordResetToken(models.Model):
    """Token pour réinitialisation de mot de passe"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # 🔥 CORRECTION: UUIDField au lieu de CharField
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'auth_password_reset_tokens'
    
    def is_valid(self):
        from django.utils import timezone
        return not self.used and self.expires_at > timezone.now()
    
    def __str__(self):
        return f"{self.user.username} - {self.token}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
        
        
        