from datetime import date, timedelta
from decimal import Decimal
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction


class Command(BaseCommand):
    help = "Seed la base avec des donnees de demonstration"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Recreate all data")
        parser.add_argument("--articles", type=int, default=100, help="Nombre d'articles")
        parser.add_argument("--mouvements", type=int, default=1000, help="Nombre de mouvements")
        parser.add_argument("--inventaires", type=int, default=80, help="Nombre d'inventaires")
        parser.add_argument("--lots", type=int, default=200, help="Nombre de lots")

    def handle(self, *args, **options):
        from apps.stocks.models import (
            TypeArticle, CategorieArticle, Unite, ComportementArticle,
            Article, Depot, SourceOperation, Lot, MouvementStock,
            Inventaire, JournalStock, LigneInventaire, CoucheValorisation,
            Valorisation, NumeroSerie, Emplacement, Nomenclature,
            ComposantNomenclature,
        )
        from apps.stocks.services import MouvementStockService, InventaireService

        force = options["force"]
        nb_articles = options["articles"]
        nb_mouvements = options["mouvements"]
        nb_inventaires = options["inventaires"]
        nb_lots = options["lots"]

        if not force and Article.objects.exists():
            self.stdout.write("Donnees deja presentes. Utilisez --force pour reinitialiser.")
            return

        if force:
            self.stdout.write("Nettoyage...")
            with transaction.atomic():
                JournalStock.objects.all().delete()
                CoucheValorisation.objects.all().delete()
                Valorisation.objects.all().delete()
                MouvementStock.objects.all().delete()
                LigneInventaire.objects.all().delete()
                Inventaire.objects.all().delete()
                NumeroSerie.objects.all().delete()
                Lot.objects.all().delete()
                ComposantNomenclature.objects.all().delete()
                Nomenclature.objects.all().delete()
                Article.objects.all().delete()
                Emplacement.objects.all().delete()
                Depot.objects.all().delete()
                Unite.objects.all().delete()
                CategorieArticle.objects.all().delete()
                TypeArticle.objects.all().delete()
                ComportementArticle.objects.all().delete()
                SourceOperation.objects.all().delete()

        today = date.today()
        random.seed(42)

        SourceOperation.seed()
        self.stdout.write("[OK] Sources")

        type_mp, _ = TypeArticle.objects.get_or_create(code="MATIERE_PREMIERE", defaults={"libelle": "Matiere premiere"})
        type_pf, _ = TypeArticle.objects.get_or_create(code="PRODUIT_FINI", defaults={"libelle": "Produit fini"})
        type_c, _ = TypeArticle.objects.get_or_create(code="CONSOMMABLE", defaults={"libelle": "Consommable"})
        type_emb, _ = TypeArticle.objects.get_or_create(code="EMBALLAGE", defaults={"libelle": "Emballage"})
        type_pd, _ = TypeArticle.objects.get_or_create(code="PIECE_DETACHEE", defaults={"libelle": "Piece detachee"})
        types = [type_mp, type_pf, type_c, type_emb, type_pd]

        cat_mp, _ = CategorieArticle.objects.get_or_create(code="MATIERES", defaults={"nom": "Matieres premieres"})
        cat_pf, _ = CategorieArticle.objects.get_or_create(code="PRODUITS", defaults={"nom": "Produits finis"})
        cat_emb, _ = CategorieArticle.objects.get_or_create(code="EMBALLAGES", defaults={"nom": "Emballages"})
        cat_pd, _ = CategorieArticle.objects.get_or_create(code="PIECES", defaults={"nom": "Pieces detachees"})
        categories = [cat_mp, cat_pf, cat_emb, cat_pd]

        kg, _ = Unite.objects.get_or_create(code="KG", defaults={"libelle": "Kilogramme", "categorie": "MASSE"})
        l, _ = Unite.objects.get_or_create(code="L", defaults={"libelle": "Litre", "categorie": "VOLUME"})
        un, _ = Unite.objects.get_or_create(code="UN", defaults={"libelle": "Unite", "categorie": "UNITE"})
        m, _ = Unite.objects.get_or_create(code="M", defaults={"libelle": "Metre", "categorie": "LONGUEUR"})
        boite, _ = Unite.objects.get_or_create(code="BOITE", defaults={"libelle": "Boite", "categorie": "UNITE"})
        unites = [kg, l, un, m, boite]

        comp_defaut = ComportementArticle.creer_defaut()
        comp_perissable, _ = ComportementArticle.objects.get_or_create(
            stockable=True, vendable=True, achetable=True,
            perissable=True, lot_obligatoire=False,
            numero_serie=False, inventoriable=True,
        )
        comportements = [comp_defaut, comp_perissable]

        depots_data = [
            ("MAG", "Magasin principal"),
            ("BOU", "Boutique centre"),
            ("ATL", "Atelier de production"),
            ("DEP2", "Depot secondaire"),
            ("FRI", "Frigo stockage"),
        ]
        depots = []
        for code, lib in depots_data:
            d, _ = Depot.objects.get_or_create(code=code, defaults={"libelle": lib, "est_actif": True})
            depots.append(d)
        self.stdout.write("[OK] Depots")

        designations_mp = [
            "Farine de ble T55", "Sucre blanc", "Sel fin", "Huile de tournesol",
            "Beurre doux", "Oeufs frais", "Levure de boulanger", "Lait entier",
            "Creme fraiche", "Chocolat noir", "Vanille en poudre", "Cannelle moulue",
            "Noix de coco rapee", "Amandes effilees", "Raisins secs", "Miel d'acacia",
            "Confiture de fraise", "Pate d'amande", "Colorant alimentaire", "Eau de rose",
            "Farine de seigle", "Farine complete", "Sucre glace", "Cassonade",
            "Beurre sale", "Huile d'olive", "Vinaigre balsamique", "Moutarde ancienne",
            "Ketchup", "Mayonnaise", "Cornichons", "Olives vertes",
            "Tomates sechees", "Pesto genovese", "Tapenade", "Poivre noir moulu",
            "Curcuma", "Paprika", "Cumin", "Gingembre moulu",
            "Ail granule", "Oignon granule", "Herbes de Provence", "Laurier",
            "Thym", "Romarin", "Persil seche", "Basilic seche",
        ]
        designations_pf = [
            "Pain traditionnel 250g", "Pain complet 250g", "Baguette", "Croissant au beurre",
            "Pain au chocolat", "Brioche tressÃ©e", "Pain de mie", "Pain de seigle",
            "Pain aux noix", "Pain aux cereales", "Pain sans gluten", "Pain campagne",
            "Chausson aux pommes", "Tarte aux fraises", "Tarte au citron", "Eclair au chocolat",
            "Paris-Brest", "Mille-feuille", "Opera", "Tiramisu",
            "Flan patissier", "Creme brulee", "Mousse au chocolat", "Panna cotta",
            "Sable aux amandes", "Cookie", "Madeleine", "Cannele",
            "Pain d'epices", "Panettone", "Baba au rhum", "Tarte tatin",
        ]
        designations_c = [
            "Eau minerale 1.5L", "Eau minerale 50cL", "Jus d'orange", "Soda cola",
            "Lingettes", "Sac poubelle 50L", "Film etirable", "Papier cuisson",
            "Gants jetables", "Chariot de menage", "Balayette", "Serpilliere",
            "Savon liquide", "Essuie-tout", "Nappe jetable", "Pailles",
        ]
        designations_emb = [
            "Boite kraft 20x20", "Sac papier 500g", "Film plastique alimentaire",
            "Barquette alu", "Opercule", "Etiquette adhesive", "Ruban adhesif",
            "Carton demenagement", "Caisse plastique", "Sachet kraft",
        ]
        designations_pd = [
            "Roulement a billes", "Joint silicone", "Vanne 3/4", "Filtre a eau",
            "Courroie moteur", "Ampoule LED", "Interrupteur", "Prise electrique",
        ]

        all_designations = designations_mp + designations_pf + designations_c + designations_emb + designations_pd
        type_map = (
            [(type_mp, cat_mp, comp_perissable)] * len(designations_mp)
            + [(type_pf, cat_pf, comp_perissable)] * len(designations_pf)
            + [(type_c, None, comp_defaut)] * len(designations_c)
            + [(type_emb, cat_emb, comp_defaut)] * len(designations_emb)
            + [(type_pd, cat_pd, comp_defaut)] * len(designations_pd)
        )

        articles = []
        for i, (des, (t, cat, comp)) in enumerate(zip(all_designations, type_map), 1):
            prefix = "MP" if t == type_mp else "PF" if t == type_pf else "CS" if t == type_c else "EM" if t == type_emb else "PD"
            code = f"{prefix}-{i:04d}"
            art = Article(
                code=code,
                designation=des,
                type_article=t,
                categorie=cat,
                unite_defaut=random.choice(unites),
                comportement=comp,
                methode_valorisation=random.choice(["PMP", "FIFO"]),
                seuil_alerte=Decimal(random.randint(5, 100)),
                stock_min=Decimal(random.randint(2, 20)),
                stock_max=Decimal(random.randint(200, 2000)),
                actif=True,
            )
            articles.append(art)

        Article.objects.bulk_create(articles, ignore_conflicts=True)
        articles = list(Article.objects.filter(actif=True))
        self.stdout.write(f"[OK] {len(articles)} Articles")

        src_achat = SourceOperation.objects.get(code="ACHAT")
        src_vente = SourceOperation.objects.get(code="VENTE")
        src_prod = SourceOperation.objects.get(code="PRODUCTION")
        src_transfert = SourceOperation.objects.get(code="TRANSFERT")
        src_inventaire = SourceOperation.objects.get(code="INVENTAIRE")
        src_casse = SourceOperation.objects.get(code="CASSE")
        src_peremption = SourceOperation.objects.get(code="PEREMPTION")
        sources = [src_achat, src_vente, src_prod, src_transfert, src_inventaire, src_casse, src_peremption]

        lots = []
        lot_counter = 0
        for art in articles:
            nb = random.randint(1, 4)
            for _ in range(nb):
                if lot_counter >= nb_lots:
                    break
                lot_counter += 1
                qty = Decimal(random.randint(50, 2000))
                remaining = Decimal(random.randint(0, int(qty)))
                peremption = today + timedelta(days=random.randint(-30, 365))
                lots.append(Lot(
                    numero_lot=f"LOT-{art.code}-{lot_counter:04d}",
                    article=art,
                    date_fabrication=today - timedelta(days=random.randint(1, 180)),
                    date_peremption=peremption if peremption > today - timedelta(days=1) else None,
                    prix_revient_unitaire=Decimal(str(round(random.uniform(0.1, 50), 2))),
                    quantite_initiale=qty,
                    quantite_restante=remaining,
                    actif=True,
                ))
        Lot.objects.bulk_create(lots, ignore_conflicts=True)
        self.stdout.write(f"[OK] {Lot.objects.count()} Lots")

        labels_entree = [
            "Reception fournisseur", "Achat direct", "Retour client",
            "Production journee", "Transfert entrant", "Don recu",
        ]
        labels_sortie = [
            "Vente client", "Consommation production", "Transfert sortant",
            "Don", "Casse", "Peremption", "Echantillon",
        ]

        self.stdout.write("Creation des mouvements...")
        created = 0
        batch_size = 100
        while created < nb_mouvements:
            batch_target = min(batch_size, nb_mouvements - created)
            for _ in range(batch_target):
                art = random.choice(articles)
                depot_source = random.choice(depots)

                if random.random() < 0.35:
                    nature = "ENTREE"
                    qte = Decimal(random.randint(1, 500))
                    prix = Decimal(str(round(random.uniform(0.1, 50), 2)))
                    src = random.choice([src_achat, src_prod, src_inventaire])
                    lb = random.choice(labels_entree)
                    try:
                        MouvementStockService.entree_stock(
                            article=art, depot=depot_source, quantite=qte,
                            prix_unitaire=prix, source_operation=src,
                            libelle=lb, created_by="seed",
                        )
                    except Exception:
                        pass
                elif random.random() < 0.70:
                    nature = "SORTIE"
                    qte = Decimal(random.randint(1, 100))
                    src = random.choice([src_vente, src_prod, src_casse, src_peremption])
                    lb = random.choice(labels_sortie)
                    try:
                        MouvementStockService.sortie_stock(
                            article=art, depot=depot_source, quantite=qte,
                            source_operation=src, libelle=lb, created_by="seed",
                        )
                    except Exception:
                        pass
                else:
                    depot_dest = random.choice([d for d in depots if d != depot_source])
                    qte = Decimal(random.randint(1, 50))
                    try:
                        MouvementStockService.transferer(
                            article=art, depot_source=depot_source,
                            depot_destination=depot_dest, quantite=qte,
                            libelle="Transfert inter-depot", created_by="seed",
                        )
                    except Exception:
                        pass

                created += 1
            self.stdout.write(f"   {created}/{nb_mouvements} mouvements", ending="\r")
        self.stdout.write(f"\n[OK] {MouvementStock.objects.count()} Mouvements")

        self.stdout.write("Creation des inventaires...")
        inv_count = 0
        for i in range(nb_inventaires):
            depot_inv = random.choice(depots)
            ref = f"INV-{today.year}-{i+1:04d}"
            try:
                inv = InventaireService.creer_inventaire(
                    reference=ref, depot=depot_inv,
                    realise_par="seed",
                )
                sample = random.sample(articles, min(random.randint(3, 15), len(articles)))
                for art in sample:
                    theorique = Decimal(random.randint(0, 500))
                    reelle = theorique + Decimal(random.randint(-10, 10))
                    InventaireService.ajouter_ligne(inv, art, max(reelle, Decimal("0")))
                inv_count += 1
            except Exception:
                pass
        self.stdout.write(f"[OK] {inv_count} Inventaires")

        self.stdout.write(self.style.SUCCESS(
            f"\n[OK] Seed termine !"
            f"\n   - {Article.objects.count()} articles"
            f"\n   - {Depot.objects.count()} depots"
            f"\n   - {MouvementStock.objects.count()} mouvements"
            f"\n   - {Lot.objects.count()} lots"
            f"\n   - {inv_count} inventaire(s)"
        ))
