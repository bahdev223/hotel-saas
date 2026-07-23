from django import forms
from apps.stocks.models import Article, Depot, MouvementStock, Inventaire, Lot, Emplacement


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = [
            "code", "designation", "description", "type_article",
            "categorie", "unite_defaut", "comportement",
            "methode_valorisation", "seuil_alerte", "stock_min",
            "stock_max", "actif",
        ]


class DepotForm(forms.ModelForm):
    class Meta:
        model = Depot
        fields = ["code", "libelle", "adresse", "est_actif"]


class MouvementForm(forms.ModelForm):
    class Meta:
        model = MouvementStock
        fields = [
            "nature", "article", "depot", "emplacement", "lot",
            "quantite", "prix_unitaire", "cout_total",
            "source_operation", "reference_externe", "libelle",
        ]


class InventaireForm(forms.ModelForm):
    class Meta:
        model = Inventaire
        fields = ["reference", "depot", "date_inventaire", "realise_par", "notes"]
        widgets = {
            "date_inventaire": forms.DateInput(attrs={"type": "date"}),
        }


class LotForm(forms.ModelForm):
    class Meta:
        model = Lot
        fields = [
            "numero_lot", "article", "date_fabrication",
            "date_peremption", "prix_revient_unitaire",
            "quantite_initiale", "quantite_restante", "actif",
        ]
        widgets = {
            "date_fabrication": forms.DateInput(attrs={"type": "date"}),
            "date_peremption": forms.DateInput(attrs={"type": "date"}),
        }
