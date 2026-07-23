from django.db import migrations


def creer_domaines(apps, schema_editor):
    Domaine = apps.get_model('stock', 'Domaine')
    Produit = apps.get_model('stock', 'Produit')
    domaines_a_creer = [
        {'nom': 'HÔTEL', 'icone': 'fa-bed', 'ordre': 1},
        {'nom': 'RESTAURANT', 'icone': 'fa-utensils', 'ordre': 2},
        {'nom': 'BRASSERIE', 'icone': 'fa-beer', 'ordre': 3},
    ]
    for data in domaines_a_creer:
        Domaine.objects.get_or_create(nom=data['nom'], defaults={'icone': data['icone'], 'ordre': data['ordre']})

    # Auto-assigner les produits existants sans domaine au domaine BRASSERIE par défaut
    brasserie = Domaine.objects.filter(nom='BRASSERIE').first()
    if brasserie:
        Produit.objects.filter(domaine__isnull=True).update(domaine=brasserie)


def supprimer_domaines(apps, schema_editor):
    Domaine = apps.get_model('stock', 'Domaine')
    Domaine.objects.filter(nom__in=['HÔTEL', 'RESTAURANT', 'BRASSERIE']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('stock', '0016_ajout_prix_unitaire_ligneinventaire'),
    ]

    operations = [
        migrations.RunPython(creer_domaines, supprimer_domaines),
    ]
