from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password


@receiver(post_save, sender='rh.Employe')
def auto_creer_utilisateur(sender, instance, created, **kwargs):
    if not created:
        return
    if not instance.matricule:
        return
    if instance.user:
        return
    user, user_created = User.objects.get_or_create(
        username=instance.matricule,
        defaults={
            'password': make_password(instance.matricule),
            'first_name': instance.prenom,
            'last_name': instance.nom,
            'email': instance.email or ''
        }
    )
    instance.user = user
    instance.save(update_fields=['user'])
    if user_created:
        instance._auto_password = True
