from django.db import migrations


def appliquer_presets_compatibilite(apps, schema_editor):
    Affectation = apps.get_model("pos", "AffectationPointVente")

    # Les anciens écrans considéraient le rôle CAISSIER comme implicitement
    # autorisé à exploiter sa caisse. Avec POSAccessService, ces droits deviennent
    # explicites pour éviter qu'une migration coupe les caissiers existants.
    Affectation.objects.filter(role="CAISSIER").update(
        peut_vendre=True,
        peut_encaisser=True,
        peut_ouvrir_caisse=True,
        peut_fermer_caisse=True,
    )

    Affectation.objects.filter(role="SERVEUR").update(
        peut_vendre=True,
    )

    Affectation.objects.filter(role__in=["RESPONSABLE", "SUPERVISEUR"]).update(
        peut_vendre=True,
        peut_encaisser=True,
        peut_ouvrir_caisse=True,
        peut_fermer_caisse=True,
        peut_annuler_vente=True,
        peut_accorder_remise=True,
        peut_consulter_rapports=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0007_pos_access_modes_and_horaires"),
    ]

    operations = [
        migrations.RunPython(
            appliquer_presets_compatibilite,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
