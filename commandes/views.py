import datetime
from django.shortcuts import get_object_or_404, render
from django.db.models import Sum
from django import forms

from .models import Article, Delivery, Cart, CartItem, UnitTypes


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


    return render(request, "commandes/needed_quantities.html", context)


class CartItemForm(forms.Form):
    article = forms.ModelChoiceField(queryset=Article.objects.all())
    quantity = forms.DecimalField(max_digits=6, decimal_places=5)


def cart(request, id):
    """A buyer can see or edit his orders"""
    cart = get_object_or_404(Cart, id=id)

    if request.method == "POST":
        form = CartItemForm(request.POST)
        if form.is_valid():
            a = form.cleaned_data['article']
            CartItem(cart=cart,
                     label=a.label,
                     unit_price=a.unit_price,
                     unit_type=a.unit_type,
                     quantity=form.cleaned_data['quantity']
                     ).save()
    else:
        form = CartItemForm()

    return render(request, "commandes/cart.html", {"cart": cart, "form": form})
