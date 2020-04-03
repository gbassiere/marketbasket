import datetime
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.db.models import Sum
from django.contrib.auth.decorators import permission_required, login_required
from django import forms

from .models import Article, Delivery, Cart, CartItem, UnitTypes


def next_deliveries(request):
    deliveries = Delivery.objects \
                            .filter(slot_date__gte=datetime.date.today()) \
                            .order_by('slot_date')
    return render(request,
                  'commandes/next_deliveries.html',
                  {'deliveries': deliveries})


@login_required
@permission_required('commandes.view_delivery_quantities')
def needed_quantities(request):
    """Quantities needed for each delivery"""
    deliveries = Delivery.objects.filter(slot_date__gte=datetime.date.today()) \
                                 .values('location__name', 'slot_date') \
                                 .order_by('slot_date') \
                                 .distinct()
    context = {'deliveries': []}
    units = dict(UnitTypes.choices)
    for d in deliveries:
        context['deliveries'].append({
            'location': d['location__name'],
            'date': d['slot_date'],
            'orders': [{'label': l, 'unit': units[u], 'quantity': q} for (l, u, q) in
                       Delivery.objects.filter(location__name=d['location__name'],
                                              slot_date=d['slot_date']) \
                                       .exclude(carts__items__isnull=True) \
                                       .values_list('carts__items__label',
                                               'carts__items__unit_type') \
                                       .annotate(quantity=Sum('carts__items__quantity'))]})

    return render(request, 'commandes/needed_quantities.html', context)


@login_required
def new_cart(request, id):
    """A buyer can start a new cart"""
    delivery = get_object_or_404(Delivery, id=id)
    cart = Cart(delivery=delivery, user=request.user)
    cart.save()
    return HttpResponseRedirect(reverse('cart', args=[cart.id]))


class CartItemForm(forms.Form):
    article = forms.ModelChoiceField(queryset=Article.objects.all())
    quantity = forms.DecimalField(max_digits=6, decimal_places=5)


@login_required
def cart(request, id):
    """A buyer can see or edit his orders"""
    cart = get_object_or_404(Cart, id=id)

    if cart.user.id != request.user.id:
        return HttpResponseRedirect(
                '%s?next=%s' % (settings.LOGIN_URL, request.path))

    if request.method == 'POST':
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

    return render(request, 'commandes/cart.html', {'cart': cart, 'item_form': form})


@login_required
@permission_required('commandes.prepare_basket')
def prepare_baskets(request, id):
    """A packer view baskets to be prepared"""
    delivery = get_object_or_404(Delivery, id=id)
    return render(request, 'commandes/prepare_baskets.html',
                                            {'delivery': delivery})
