# Generated manually: simplifier MouvementStock (type_mouvement + motif)

from django.db import migrations, models


def mapper_ancien_vers_nouveau(apps, schema_editor):
    MouvementStock = apps.get_model('stock', 'MouvementStock')
    TYPE_TO_MOUVEMENT = {
        'ACHAT': ('ENTREE', 'achat'),
        'VENTE': ('SORTIE', 'vente'),
        'RETOUR_CLIENT': ('ENTREE', 'inventaire'),
        'RETOUR_FOURNISSEUR': ('SORTIE', 'inventaire'),
        'PRODUCTION': ('ENTREE', 'production'),
        'TRANSFERT': ('TRANSFERT', 'reapprovisionnement'),
        'PEREMPTION': ('SORTIE', 'perte'),
        'CASSE': ('SORTIE', 'perte'),
        'CONSOMMATION': ('SORTIE', 'consommation'),
        'DON': ('SORTIE', 'perte'),
        'DON_RECU': ('ENTREE', 'achat'),
        'CORRECTION_INVENTAIRE': ('ENTREE', 'inventaire'),
        'INVENTAIRE_INITIAL': ('ENTREE', 'inventaire'),
    }
    for mvt in MouvementStock.objects.iterator():
        type_mvt, motif = TYPE_TO_MOUVEMENT.get(mvt.type_mouvement_libelle, ('ENTREE', 'achat'))
        mvt.type_mouvement = type_mvt
        mvt.motif = motif
        mvt.save(update_fields=['type_mouvement', 'motif'])


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0007_enrichir_mouvement_stock'),
    ]

    operations = [
        # Ajouter le champ motif (temporaire sans contrainte)
        migrations.AddField(
            model_name='mouvementstock',
            name='motif',
            field=models.CharField(blank=True, max_length=30),
        ),
        # Renommer type_operation → type_mouvement pour préparer
        migrations.RenameField(
            model_name='mouvementstock',
            old_name='type_operation',
            new_name='type_mouvement_libelle',
        ),
        # Ajouter le vrai type_mouvement (ENTREE/SORTIE/TRANSFERT)
        migrations.AddField(
            model_name='mouvementstock',
            name='type_mouvement',
            field=models.CharField(
                choices=[('ENTREE', 'Entrée'), ('SORTIE', 'Sortie'), ('TRANSFERT', 'Transfert')],
                max_length=10, default='ENTREE'
            ),
        ),
        # Remplir type_mouvement et motif depuis l'ancienne valeur
        migrations.RunPython(mapper_ancien_vers_nouveau),
        # Supprimer l'ancien champ
        migrations.RemoveField(
            model_name='mouvementstock',
            name='type_mouvement_libelle',
        ),
        # Supprimer sens
        migrations.RemoveField(
            model_name='mouvementstock',
            name='sens',
        ),
        # Rendre motif non-blank avec choix
        migrations.AlterField(
            model_name='mouvementstock',
            name='motif',
            field=models.CharField(
                choices=[
                    ('achat', 'Achat'),
                    ('vente', 'Vente'),
                    ('consommation', 'Consommation'),
                    ('perte', 'Perte'),
                    ('production', 'Production'),
                    ('reapprovisionnement', 'Réapprovisionnement'),
                    ('inventaire', 'Inventaire'),
                ],
                max_length=30, default='achat'
            ),
            preserve_default=True,
        ),
        # Ajouter help_text sur reference
        migrations.AlterField(
            model_name='mouvementstock',
            name='reference',
            field=models.CharField(blank=True, help_text='Reference de la piece source (CMD-00045, FACT-001, etc.)', max_length=100, null=True),
        ),
    ]
