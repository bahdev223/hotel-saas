# apps/stock/templatetags/stock_filters.py
from django import template
from django.template.defaultfilters import floatformat

register = template.Library()

@register.filter
def sum_attribute(queryset, attribute):
    """
    Calcule la somme d'un attribut sur un queryset.
    Usage: {{ queryset|sum_attribute:'quantite' }}
    """
    if not queryset:
        return 0
    
    total = 0
    for item in queryset:
        try:
            # Gérer les attributs avec des underscores comme 'quantite'
            value = getattr(item, attribute, 0)
            if value is None:
                value = 0
            total += float(value)
        except (TypeError, ValueError):
            pass
    
    return total


