# apps/tresorerie/services/compte_financier_service.py
from django.core.exceptions import ValidationError
from apps.comptabilite.models import CompteModel


class CompteFinancierService:
    CODES_FIXES = {
        ('ESPECES', 'CENTRALE'): '5711',
    }

    PLAGES = {
        ('ESPECES', 'POINT_VENTE'): {'prefix': '571', 'debut': 2, 'fin': 49},
        ('ESPECES', 'GUICHET'):     {'prefix': '571', 'debut': 50, 'fin': 99},
        ('BANQUE', None):            {'prefix': '521', 'debut': 1, 'fin': 99},
        ('MOBILE_MONEY', None):      {'prefix': '581', 'debut': 1, 'fin': 99},
    }

    EXCLUDES = ['57', '571', '5711']

    @classmethod
    def _trouver_ou_creer_parent(cls, code, libelle, parent=None, niveau=3, type_compte='compte'):
        compte = CompteModel.objects.filter(code=code).first()
        if not compte:
            compte = CompteModel.objects.create(
                code=code, libelle=libelle,
                nature='ACTIF', sens='DEBIT',
                parent=parent, niveau=niveau,
                type_compte=type_compte,
                categorie='bilan',
                est_mouvement=True, actif=True,
            )
        return compte

    @classmethod
    def _parent_57(cls):
        return cls._trouver_ou_creer_parent('57', 'CAISSES', niveau=2, type_compte='groupe')

    @classmethod
    def _parent_571(cls):
        return cls._trouver_ou_creer_parent('571', 'CAISSE SIEGE SOCIAL',
                                            parent=cls._parent_57(),
                                            niveau=3, type_compte='compte')

    @classmethod
    def _parent_52(cls):
        return cls._trouver_ou_creer_parent('52', 'BANQUES', niveau=2, type_compte='groupe')

    @classmethod
    def _parent_581(cls):
        return cls._trouver_ou_creer_parent('581', "REGIES D'AVANCE, ACCREDITIFS ET VIREMENTS INTERNES",
                                            niveau=3, type_compte='compte')

    @classmethod
    def _prochain_dans_plage(cls, prefix, debut, fin, parent):
        existants = CompteModel.objects.filter(
            code__startswith=prefix
        ).exclude(
            code__in=cls.EXCLUDES
        ).values_list('code', flat=True)

        max_trouve = debut - 1
        for code in existants:
            try:
                num = int(code[len(prefix):])
                if debut <= num <= fin:
                    max_trouve = max(max_trouve, num)
            except (ValueError, IndexError):
                pass

        if max_trouve >= fin:
            raise ValidationError(
                f"Plus de codes disponibles dans la plage {prefix}{debut}-{prefix}{fin} "
                f"pour ce type de compte financier"
            )

        return f"{prefix}{max_trouve + 1}"

    @classmethod
    def generer_compte_comptable(cls, caisse):
        cle = (caisse.type_financier, caisse.role)

        if cle in cls.CODES_FIXES:
            code = cls.CODES_FIXES[cle]
            parent = cls._parent_571()

        elif cle in cls.PLAGES:
            plage = cls.PLAGES[cle]
            parent = (
                cls._parent_571()
                if plage['prefix'] == '571'
                else cls._parent_52()
                if plage['prefix'] == '521'
                else cls._parent_581()
            )
            code = cls._prochain_dans_plage(
                plage['prefix'], plage['debut'], plage['fin'], parent
            )

        else:
            raise ValidationError(
                f"Type financier '{caisse.type_financier}' et rôle '{caisse.role}' "
                f"non supportés pour la génération automatique de compte comptable"
            )

        compte, cree = CompteModel.objects.get_or_create(
            code=code,
            defaults={
                'libelle': caisse.nom,
                'nature': 'ACTIF', 'sens': 'DEBIT',
                'parent': parent, 'niveau': 4,
                'type_compte': 'sous_compte',
                'categorie': 'bilan',
                'est_mouvement': True, 'actif': True,
            }
        )
        if not cree and compte.libelle != caisse.nom:
            compte.libelle = caisse.nom
            compte.save(update_fields=['libelle'])
        return compte
