import numbers
from django.db import models
from django.utils.translation import gettext_lazy as _, gettext
from django.utils.formats import date_format
from django.utils import timezone
from django.contrib.auth.models import User


class CartStatus(models.IntegerChoices):
    # Customer placed an order online, not yet processed
    RECEIVED = 10, _('received')
    # A packer starts to put items together
    PREPARING = 20, _('preparation in progress')
    # Basket is waiting for pickup
    PREPARED = 30, _('prepared')
    # Over, customer got his basket
    DELIVERED = 40, _('delivered')
    # Over, but not delivered, for some reason...
    ABANDONED = 50, _('abandoned')

class UnitType(models.TextChoices):
    UNIT = 'U', _('unit(s)')
    WEIGHT = 'W', _('Kg')

    def hr_price(self, price):
        """
        Return human-readable price with localised unit
        """

        # non-numeric price would not make sense
        if not isinstance(price, numbers.Number):
            raise ValueError('A `price` should be numeric')

        if self.value == self.UNIT:
            unit = gettext('unit')
        elif self.value == self.WEIGHT:
            unit = gettext('Kg')
        else:
            return price

        return '{price:.2f} €/{unit}'.format(price=price, unit=unit)

    def hr_quantity(self, quantity):
        """
        Return human-readable quantity with pluralized and localised unit
        """

        # non-numeric quantity would not make sense
        if not isinstance(quantity, numbers.Number):
            raise ValueError('A `quantity` should be numeric')

        if self.value == self.UNIT:
            return '{0:n}'.format(int(quantity))
        elif self.value == self.WEIGHT:
            if 0 < quantity < 1:
                # Display weight in grams
                return '{0:.0f} {1}'.format(quantity*1000, gettext('g'))
            else:
                # Display weight in kilograms
                # Trailing 0 are not properly removed on `Decimal` instances...
                quantity = float(quantity)
                return '{0:n} {1}'.format(quantity, gettext('Kg'))
        else:
            # This is actually a misuse of this filter but sending back value
            # almost untouched seems like a reasonable fallback (cast to `str`
            # for consistency
            return str(quantity)

class URLType(models.TextChoices):
    FB = 'F', _('Facebook')
    EMAIL = 'E', _('Email address')
    PHONE = 'P', _('Phone number')
    WEB = 'W', _('Website')


class Article(models.Model):
    code = models.PositiveSmallIntegerField(_('code'), unique=True)
    label = models.CharField(_('name'), max_length=255)
    unit_price = models.DecimalField(_('unit price'), max_digits=5, decimal_places=2)
    unit_type = models.CharField(
            _('unit type'),
            max_length=1,
            choices=UnitType.choices,
            default=UnitType.WEIGHT)
    # category: food vs non-food, etc. May be useful later to emit invoices or
    # to decide which payment method is allowed
    # tax_rate: may be useful later to emit invoices

    class Meta:
        verbose_name = _('article')
        verbose_name_plural = _('articles')

    def hr_unit_price(self):
        return UnitType(self.unit_type).hr_price(self.unit_price)

    def __str__(self):
        return '{0}, {1}'.format(self.label, self.hr_unit_price())


class Merchant(models.Model):
    name = models.CharField(_('name'), max_length=255)
    owner = models.ForeignKey(User, on_delete=models.PROTECT,
                                                verbose_name=_('owner'))
    presentation = models.TextField(_('presentation'), blank=True, default='')
    picture = models.ImageField(null=True, blank=True)
    # Explicit ChoiceField for things like: organic or article categories?
    #  -> the merchant can just mention it in `presentation`
    # Payment method

    class Meta:
        verbose_name = _('merchant')
        verbose_name_plural = _('merchants')

    def __str__(self):
        return self.name


class URL(models.Model):
    address = models.URLField(_('URL'), max_length=255)
    url_type = models.CharField(
            _('URL type'),
            max_length=1,
            choices=URLType.choices,
            default=URLType.WEB)
    merchant = models.ForeignKey(Merchant,
                                 on_delete=models.CASCADE,
                                 verbose_name=_('merchant'),
                                 related_name='contact_details')

    class Meta:
        verbose_name = _('URL')
        verbose_name_plural = _('URLs')

    def __str__(self):
        if len(self.address) > 40:
            address = '{:s}...'.format(self.address[:37])
        else:
            address = self.address
        return '{:s}: {:s}'.format(self.get_url_type_display(), address)


class DeliveryLocation(models.Model):
    name = models.CharField(_('name'), max_length=255)
    # address full
    # lat lon

    class Meta:
        verbose_name = _('delivery location')
        verbose_name_plural = _('delivery locations')

    def __str__(self):
        return self.name


class Delivery(models.Model):
    location = models.ForeignKey(
            DeliveryLocation,
            on_delete=models.PROTECT,
            verbose_name=_('location'))
    max_per_slot = models.PositiveSmallIntegerField(
            _('maximum number of baskets per slot'),
            help_text=_('Set 0 for unlimited carts per slot'),
            default=0)
    # available article quantity

    class Meta:
        permissions = [('view_delivery_quantities',
                        'View needed quantities for a delivery')]
        verbose_name = _('delivery')
        verbose_name_plural = _('deliveries')

    def get_active_carts_by_slot(self):
        groups = {}
        for c in self.get_active_carts():
            k = c.slot.id
            if k not in groups:
                groups[k] = {'start': c.slot.start,
                             'end': c.slot.end,
                             'baskets': []}
            groups[k]['baskets'].append(c)
        return list(groups.values())

    def get_active_carts(self):
        return Cart.objects.filter(status__lte=CartStatus.PREPARED,
                            slot__delivery__id=self.id)

    def get_needed_quantities(self):
        """
        Return a queryset of dict with article label, unit type and the
        total quantity of this article ordered by customers for this delivery
        """
        return CartItem.objects.filter(cart__slot__delivery__id=self.id) \
                               .values('label', 'unit_type') \
                               .annotate(quantity=models.Sum('quantity'))

    def __str__(self):
        ctx = {'place': self.location.name}
        first_slot = self.slots.order_by('start').first()
        if first_slot:
            start_dt = timezone.localtime(first_slot.start)
            ctx['day'] = date_format(start_dt, 'SHORT_DATE_FORMAT')
            ctx['hour'] = date_format(start_dt, 'TIME_FORMAT')
            return '{place} ({day} {hour})'.format(**ctx)
        else:
            return gettext('{place} (undefined time slots)').format(**ctx)


class DeliverySlot(models.Model):
    start = models.DateTimeField(_('start at'))
    end = models.DateTimeField(_('end at'))
    delivery = models.ForeignKey(
            Delivery,
            related_name='slots',
            verbose_name=_('delivery'),
            on_delete=models.CASCADE)

    class Meta:
        verbose_name = _('delivery time slot')
        verbose_name_plural = _('delivery time slots')

    def __str__(self):
        ctx = {
            'day': date_format(self.start, 'SHORT_DATE_FORMAT'),
            'start': date_format(timezone.localtime(self.start), 'TIME_FORMAT'),
            'end': date_format(timezone.localtime(self.end), 'TIME_FORMAT')}
        return '{day} ({start}-{end})'.format(**ctx)


class Cart(models.Model):
    user = models.ForeignKey(
            User,
            on_delete=models.PROTECT)
    slot = models.ForeignKey(
            DeliverySlot,
            on_delete=models.SET_NULL,
            null=True,
            verbose_name='slot',
            related_name='carts')
    status = models.PositiveSmallIntegerField(
            _('status'),
            choices=CartStatus.choices,
            default=CartStatus.RECEIVED)
    annotation = models.TextField(
            _('annotation'),
            blank=True,
            default='')

    class Meta:
        permissions = [('prepare_basket', 'Prepare basket')]
        verbose_name = _('cart')
        verbose_name_plural = _('carts')

    def get_total(self):
        total = 0
        for i in self.items.all():
            total = total + i.unit_price * i.quantity
        return total

    def is_prepared(self):
        return self.status == CartStatus.PREPARED

    def __str__(self):
        ctx = {
            'day': date_format(timezone.localdate(self.slot.start),
                                                        'SHORT_DATE_FORMAT'),
            'user': self.user.get_full_name(),
            'items': self.items.count()}
        return '{day}: {user!s} ({items} items)'.format(**ctx)


class CartItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset() \
                      .annotate(price=models.F('unit_price') * models.F('quantity'))


class CartItem(models.Model):
    cart = models.ForeignKey(
            Cart,
            on_delete=models.CASCADE,
            related_name='items',
            verbose_name=_('cart'))
    # Duplicate article label and unit_price so we can keep consitent cart
    # history even when article definition is updated
    label = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=5, decimal_places=2)
    unit_type = models.CharField(max_length=1, choices=UnitType.choices)
    quantity = models.DecimalField(max_digits=6, decimal_places=3)

    class Meta:
        verbose_name = _('item')
        verbose_name_plural = _('items')

    # Manager with prices computed automatically annotated
    objects = CartItemManager()

    def hr_unit_price(self):
        return UnitType(self.unit_type).hr_price(self.unit_price)

    def hr_quantity(self):
        return UnitType(self.unit_type).hr_quantity(self.quantity)

    def __str__(self):
        return '{0}: {1}'.format(self.label, self.hr_quantity())
