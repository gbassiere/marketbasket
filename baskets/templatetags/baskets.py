import functools
from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from ..models import UnitTypes


register = template.Library()


def handle_typing_and_autoescaping(func):
    def _wrapper(value, unit_type, autoescape):

        if not isinstance(unit_type, UnitTypes):
            unit_type = UnitTypes(unit_type)

        res = func(value, unit_type, autoescape)

        # Escaping may seem overkill but the unit is actually a l10n string,
        # it could contain HTML-unsafe character
        if autoescape:
            res = conditional_escape(res)
        return mark_safe(res)
    return functools.wraps(func)(_wrapper)


@register.filter(needs_autoescape=True)
@handle_typing_and_autoescaping
def price(p, unit_type, autoescape=True):
    """ Human-readable price with localised unit """
    return unit_type.hr_price(p)


@register.filter(needs_autoescape=True)
@handle_typing_and_autoescaping
def quantity(q, unit_type, autoescape=True):
    """ Human-readable quantity with pluralized and localised unit """
    return unit_type.hr_quantity(q)
