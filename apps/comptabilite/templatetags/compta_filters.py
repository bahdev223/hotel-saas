# apps/comptabilite/templatetags/compta_filters.py
from django import template

register = template.Library()

@register.filter
def map_attribute(liste, attr):
    """Extrait un attribut d'une liste de dictionnaires"""
    if not liste:
        return []
    return [item.get(attr, '') for item in liste]


@register.filter
def get_item(dictionary, key):
    """Récupère la valeur d'un dictionnaire par sa clé"""
    if dictionary is None:
        return 0
    return dictionary.get(str(key), 0)