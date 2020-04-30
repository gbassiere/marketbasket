from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from ..models import UnitTypes


register = template.Library()

@register.filter(needs_autoescape=True)
def quantity(q, unit_type, autoescape=True):
    """ Human-readable quantity with pluralized and localised unit """

    if not isinstance(unit_type, UnitTypes):
        unit_type = UnitTypes(unit_type)

    res = unit_type.hr_quantity(q)

    # Escaping may seem overkill but the unit is actually a l10n string, it
    # could contain HTML-unsafe character
    if autoescape:
        res = conditional_escape(res)
    return mark_safe(res)
