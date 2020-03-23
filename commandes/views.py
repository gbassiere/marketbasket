import datetime
from django.shortcuts import render
from django.db.models import Sum

from .models import Delivery, UnitTypes


def needed_quantities(request):
    """Quantities needed for each delivery"""
    deliveries = Delivery.objects.filter(slot_date__gte=datetime.date.today()) \
                                 .values("location__name", "slot_date") \
                                 .distinct()
    context = {'deliveries': []}
    units = dict(UnitTypes.choices)
    for d in deliveries:
        context['deliveries'].append({
            "location": d['location__name'],
            "date": d['slot_date'],
            "orders": [{"label": l, "unit": units[u], "quantity": q} for (l, u, q) in
                       Delivery.objects.filter(location__name=d['location__name'],
                                              slot_date=d['slot_date']) \
                                       .values_list("carts__items__label",
                                               "carts__items__unit_type") \
                                       .annotate(quantity=Sum("carts__items__quantity"))]})


    return render(request, "commandes/index.html", context)
