from functools import reduce

from django.utils.timezone import now, localtime
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.http import HttpResponseRedirect, Http404
from django.core.exceptions import SuspiciousOperation
from django.urls import reverse_lazy
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib import messages
from django import forms
from django.db.models import Min, Count, Prefetch

from .models import Article, UnitTypes, \
                    Delivery, DeliverySlot, \
                    Cart, CartItem, CartStatuses, \
                    Merchant


def merchant(request):
    # FIXME: switch to multi-merchant app and remove hard-coded merchant id
    merchant = get_object_or_404(Merchant, id=1)

    contacts = [(url.get_url_type_display(), url.address)
                            for url in merchant.contact_details.all()]
    contacts.append(
                (merchant.owner.email, 'mailto:%s' % merchant.owner.email))

    # Can't find a way to annotate deliveries with an is_full field which would
    # be True when all slot have reached max_per_slot... Hence filtering and
    # computing on Python side.
    slots = DeliverySlot.objects.annotate(cart_count=Count('carts'))
    qs = Delivery.objects.annotate(start=Min('slots__start')) \
                        .filter(start__gte=now()) \
                        .prefetch_related(Prefetch('slots', queryset=slots)) \
                        .order_by('start')
    deliveries = [{
            'id': d.id,
            'loc_name': d.location.name,
            'start': d.start,
            'is_full': d.max_per_slot > 0 and reduce(
                        lambda x, y: x and y.cart_count >= d.max_per_slot,
                        d.slots.all(), True)
            } for d in qs]
    return render(request, 'commandes/merchant.html', {
                                            'merchant': merchant,
                                            'contacts': contacts,
                                            'deliveries': deliveries})


@login_required
@permission_required('commandes.view_delivery_quantities')
def needed_quantities(request):
    """Quantities needed for each delivery"""
    deliveries = Delivery.objects.annotate(start=Min('slots__start')) \
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
    # Retrieve delivery
    delivery = get_object_or_404(Delivery, id=id)

    if delivery.max_per_slot> 0:
        # Retrieve first slot not having reached max_per_slot
        slot = delivery.slots.annotate(cart_count=Count('carts')) \
                              .filter(cart_count__lt=delivery.max_per_slot) \
                              .order_by('start').first()
    else:
        # Retrieve first slot (cart limit being disabled)
        slot = delivery.slots.order_by('start').first()

    # No free time slot, return with an error message
    if slot is None:
        msg = _('This delivery is full and does not accept any new order.')
        messages.error(request, msg)
        return HttpResponseRedirect(reverse_lazy('merchant'))

    # Actually create cart
    cart = Cart(user=request.user, slot=slot)
    cart.save()

    return HttpResponseRedirect(reverse_lazy('cart', args=[cart.id]))


class SlotSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opt = super().create_option(name, value, label, selected, index, subindex, attrs)
        if label.endswith('[*]'):
            opt['label'] = opt['label'][0:-3]
            opt['attrs']['disabled'] = True
        return opt

class SlotChoiceField(forms.ModelChoiceField):
    widget = SlotSelect

    def label_from_instance(self, obj):
        lbl = _('between %(start)s and %(end)s') % {
                'start': date_format(localtime(obj.start), 'TIME_FORMAT'),
                'end': date_format(localtime(obj.end), 'TIME_FORMAT')}
        limit = obj.delivery.max_per_slot
        if limit > 0 and obj.cart_count >= limit:
            lbl = _('%(slot)s (full)' % {'slot': lbl})
            # Mark label as disabled (i18n-independant)
            # This is ugly but I have not found any better way to pass the
            # information to widget.create_option.
            lbl += '[*]'
        return lbl

class SlotForm(forms.Form):
    slot = SlotChoiceField(queryset=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slot'].queryset = self.initial['slot'].delivery.slots \
                                        .annotate(cart_count=Count('carts'))

    def clean_slot(self):
        slot = self.cleaned_data['slot']
        limit = slot.delivery.max_per_slot
        if limit > 0 and slot.id != self.initial['slot'].id and \
                                                   slot.cart_count >= limit:
            raise forms.ValidationError(
                        _('This delivery slot is full.'), code='full')
        return slot

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
    slot_form = SlotForm(initial={'slot': cart.slot})
    item_form = CartItemForm()
    annot_form = AnnotationForm(instance=cart)
    annot_timestamp = None

    # Process POSTed data
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
        elif 'slot_submit' in request.POST:
            slot_form = SlotForm(request.POST, initial={'slot': cart.slot})
            if slot_form.has_changed():
                if slot_form.is_valid():
                    cart.slot = slot_form.cleaned_data['slot']
                    cart.save()
                    msg = _('Time slot updated')
                    messages.success(request, msg)
                else:
                    for msg in slot_form.errors.values():
                        messages.error(request, msg)
        elif 'annot_submit' in request.POST:
            annot_form = AnnotationForm(request.POST, instance=cart)
            if annot_form.is_valid():
                annot_form.save()
                annot_timestamp = now()
        else:
            raise SuspiciousOperation()

    # Build context object
    context = {
            'cart': cart,
            'annot_form': annot_form,
            'annot_timestamp': annot_timestamp,
            'item_form': item_form}
    if cart.slot.delivery.slots.count() > 1:
        context['slot_form'] = slot_form

    return render(request, 'commandes/cart.html', context)


@login_required
@permission_required('commandes.prepare_basket')
def prepare_baskets(request, id):
    """A packer view baskets to be prepared"""
    try:
        delivery = Delivery.objects.annotate(start=Min('slots__start')).get(pk=id)
    except Delivery.DoesNotExist:
        raise Http404("No Delivery matches the given query.")

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
                                             args=[basket.slot.delivery.id]))
        elif 'postpone' in request.POST:
            basket.status = CartStatuses.RECEIVED
            basket.save()
            return HttpResponseRedirect(reverse_lazy('prepare_baskets',
                                             args=[basket.slot.delivery.id]))
        elif 'start' in request.POST:
            basket.status = CartStatuses.PREPARING
            basket.save()

    return render(request,'commandes/prepare_basket.html',
                                 {'basket': basket, 'statuses': CartStatuses})
