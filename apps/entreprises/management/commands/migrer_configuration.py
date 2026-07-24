from django.core.management.base import BaseCommand
from apps.comptabilite.models import ConfigurationEntreprise as AncienneConfig
from apps.entreprises.models import (
    Entreprise,
    Etablissement,
    ConfigurationEntreprise,
    ConfigurationHoteliere,
    ModuleEntreprise,
    SequenceDocument,
)
from django.utils import timezone


class Command(BaseCommand):
    help = "Migre les données de l'ancienne ConfigurationEntreprise vers la nouvelle app entreprises"

    def handle(self, *args, **options):
        ancienne = AncienneConfig.objects.first()
        if not ancienne:
            self.stdout.write(self.style.WARNING("Aucune ancienne configuration trouvée."))
            return

        if Entreprise.objects.filter(actif=True).exists():
            self.stdout.write(self.style.WARNING("Des entreprises existent déjà. Migration ignorée."))
            return

        entreprise = Entreprise.objects.create(
            nom=ancienne.nom or "Mon Entreprise",
            nom_commercial=ancienne.nom or "",
            code="default",
            nif=ancienne.nif or "",
            rccm=ancienne.rccm or "",
            telephone=ancienne.telephone or "",
            email=ancienne.email or "",
            site_web=ancienne.site_web or "",
            adresse=ancienne.adresse or "",
        )
        ConfigurationEntreprise.objects.create(
            entreprise=entreprise,
            devise=ancienne.devise or "XOF",
        )

        etablissement = Etablissement.objects.create(
            entreprise=entreprise,
            nom=entreprise.nom,
            code="hotel-default",
            telephone=entreprise.telephone,
            email=entreprise.email,
            adresse=entreprise.adresse,
        )
        ConfigurationHoteliere.objects.create(etablissement=etablissement)

        for code, _ in ModuleEntreprise.CodeModule.choices:
            ModuleEntreprise.objects.create(
                entreprise=entreprise,
                code=code,
                actif=True,
            )

        annee = timezone.now().year
        sequences = [
            ("RESERVATION", "RES"),
            ("SEJOUR", "SEJ"),
            ("FACTURE", "FAC"),
            ("RECU", "REC"),
            ("AVOIR", "AVR"),
            ("COMMANDE", "CMD"),
            ("ACHAT", "ACH"),
            ("INVENTAIRE", "INV"),
            ("BON_LIVRAISON", "BL"),
            ("DEPENSE", "DEP"),
            ("TRANSFERT", "TRF"),
        ]
        for type_doc, prefixe in sequences:
            SequenceDocument.objects.create(
                entreprise=entreprise,
                type_document=type_doc,
                prefixe=prefixe,
                annee=annee,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Migration terminée. Entreprise créée : {entreprise.nom}"
        ))
