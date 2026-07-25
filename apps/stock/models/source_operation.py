from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from ..enums.sources import SourceOperationType

class SourceOperation(models.Model):
    """Source d'une ou plusieurs opérations de stock (Achat, Vente, Production, etc.)"""
    
    type_source = models.CharField(
        max_length=30,
        choices=SourceOperationType.choices,
    )
    reference = models.CharField(max_length=100)
    
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    object_id = models.CharField(
        max_length=50, # Support UUIDs/string IDs as seen in other modules
        null=True,
        blank=True,
    )
    objet_source = GenericForeignKey(
        "content_type",
        "object_id",
    )
    
    notes = models.TextField(blank=True, null=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'stock_source_operations'
        verbose_name = 'Source d\'opération'
        verbose_name_plural = 'Sources d\'opérations'
        ordering = ['-cree_le']
        indexes = [
            models.Index(fields=['type_source']),
            models.Index(fields=['reference']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.get_type_source_display()} - {self.reference}"
