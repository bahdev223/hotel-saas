# apps/tresorerie/templatetags/tresorerie_filters.py
from django import template

register = template.Library()

@register.filter
def div(value, arg):
    """Divise la valeur par l'argument"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
    
    