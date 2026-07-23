# apps/pos/models/verifier_lock.py
from django.db import models


class VerifierLoopLock(models.Model):
    """Verrou distribue en base : garantit qu'un seul worker/instance execute
    la boucle de verification des sessions a la fois, meme avec plusieurs
    workers Gunicorn ou plusieurs instances deployees en parallele."""

    cle = models.CharField(max_length=50, unique=True, default='session_verifier')
    detenteur = models.CharField(max_length=200, blank=True, help_text="hostname:pid du worker qui detient le verrou")
    heartbeat = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'pos_verifier_loop_lock'
        verbose_name = 'Verrou boucle de verification'
        verbose_name_plural = 'Verrous boucle de verification'

    def __str__(self):
        return f"{self.cle} — {self.detenteur or 'libre'}"
