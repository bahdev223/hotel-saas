# apps/dashboard/templatetags/dashboard_filters.py
from django import template

register = template.Library()


@register.filter
def ternary_if(value, args):
    """
    Filtre ternaire personnalisé
    Utilisation: {{ valeur|ternary_if:"si_vrai:si_faux" }}
    Exemple: {{ alerte.niveau|ternary_if:"text-red-700:text-gray-700" }}
    """
    try:
        true_value, false_value = args.split(':')
        if value:
            return true_value
        return false_value
    except (ValueError, AttributeError):
        return args


@register.filter
def get_item(dictionary, key):
    """Récupère une valeur d'un dictionnaire par sa clé"""
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None


@register.filter
def multiply(value, arg):
    """Multiplie deux valeurs"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    """Divise deux valeurs"""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def percentage(value, total):
    """Calcule le pourcentage"""
    try:
        if float(total) == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError):
        return 0
    
    