from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.http import HttpResponseRedirect
from django.core.exceptions import SuspiciousOperation
from django.urls import reverse_lazy
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib import messages
from django import forms

from .models import Article, UnitTypes, \
                    Delivery, \
                    Cart, CartItem, CartStatuses, \
                    Merchant, URLTypes


def merchant(request):
    # FIXME: switch to multi-merchant app and remove hard-coded merchant id
    merchant = get_object_or_404(Merchant, id=1)

    contacts = [(url.get_url_type_display(), url.address)
                            for url in merchant.contact_details.all()]
    contacts.append(
                (merchant.owner.email, 'mailto:%s' % merchant.owner.email))

    deliveries = Delivery.objects \
                            .filter(start__gte=now()) \
                            .order_by('start')
    return render(request, 'commandes/merchant.html', {
                                            'merchant': merchant,
                                            'contacts': contacts,
                                            'deliveries': deliveries})


@login_required
@permission_required('commandes.view_delivery_quantities')
def needed_quantities(request):
    """Quantities needed for each delivery"""
    deliveries = Delivery.objects \
                            .filter(start__gte=now()) \
                            .order_by('start')
    context = {'deliveries': []}
    units = dict(UnitTypes.choices)
    for delivery in deliveries:
        context['deliveries'].append({
            'location': delivery.location.name,
            'date': delivery.start.date(),
            'orders': [{
                            'label': quant['label'],
                            'unit_type': units[quant['unit_type']],
                            'quantity': quant['quantity']
                       } for quant in delivery.get_needed_quantities()]})

    return render(request, 'commandes/needed_quantities.html', context)


@login_required
def new_cart(request, id):
    """A buyer can start a new cart"""
    delivery = get_object_or_404(Delivery, id=id)
    cart = Cart(delivery=delivery, user=request.user, slot=delivery.start)
    cart.save()
    return HttpResponseRedirect(reverse_lazy('cart', args=[cart.id]))


class AnnotationForm(forms.ModelForm):
    class Meta:
        model = Cart
        fields = ['annotation']

class DelItemForm(forms.Form):
    del_submit = forms.IntegerField()

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

    # Default, for GET request or POST to the other form
    item_form = CartItemForm()
    annot_form = AnnotationForm(instance=cart)
    annot_timestamp = None

    if request.method == 'POST':
        if 'item_submit' in request.POST:
            item_form = CartItemForm(request.POST)
            if item_form.is_valid():
                a = item_form.cleaned_data['article']
                CartItem(cart=cart,
                         label=a.label,
                         unit_price=a.unit_price,
                         unit_type=a.unit_type,
                         quantity=item_form.cleaned_data['quantity']
                         ).save()
        elif 'del_submit' in request.POST:
            form = DelItemForm(request.POST)
            if form.is_valid():
                item_id = form.cleaned_data['del_submit']
                try:
                    ci = cart.items.get(id=item_id)
                except CartItem.DoesNotExist:
                    raise SuspiciousOperation()
                msg = _('Article "%(label)s" deleted') % {'label': ci.label}
                ci.delete()
                messages.success(request, msg)
        elif 'annot_submit' in request.POST:
            annot_form = AnnotationForm(request.POST, instance=cart)
            if annot_form.is_valid():
                annot_form.save()
                annot_timestamp = now()
        else:
            raise SuspiciousOperation()

    return render(request, 'commandes/cart.html', {
                                    'cart': cart,
                                    'annot_form': annot_form,
                                    'annot_timestamp': annot_timestamp,
                                    'item_form': item_form})


@login_required
@permission_required('commandes.prepare_basket')
def prepare_baskets(request, id):
    """A packer view baskets to be prepared"""
    delivery = get_object_or_404(Delivery, id=id)

    if request.method == 'POST' and 'delivered_cart' in request.POST:
        cart = get_object_or_404(Cart, id=request.POST['delivered_cart'])
        cart.status = CartStatuses.DELIVERED
        cart.save()

    return render(request, 'commandes/prepare_baskets.html',
                                            {'delivery': delivery})


@login_required
@permission_required('commandes.prepare_basket')
def prepare_basket(request, id):
    """A packer view a basket to be prepared"""
    basket = get_object_or_404(Cart, id=id)

    if request.method == 'POST':
        if 'ready' in request.POST:
            basket.status = CartStatuses.PREPARED
            basket.save()
            return HttpResponseRedirect(reverse_lazy('prepare_baskets',
                                                 args=[basket.delivery.id]))
        elif 'postpone' in request.POST:
            basket.status = CartStatuses.RECEIVED
            basket.save()
            return HttpResponseRedirect(reverse_lazy('prepare_baskets',
                                                 args=[basket.delivery.id]))
        elif 'start' in request.POST:
            basket.status = CartStatuses.PREPARING
            basket.save()

    return render(request,'commandes/prepare_basket.html',
                                 {'basket': basket, 'statuses': CartStatuses})
