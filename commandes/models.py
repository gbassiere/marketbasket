import math
from datetime import timedelta
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.formats import date_format
from django.utils import timezone
from django.contrib.auth.models import User


class CartStatuses(models.IntegerChoices):
    # Customer placed an order online, not yet processed
    RECEIVED = 10, _('received')
    # A packer starts to put items together
    PREPARING = 20, _('preparation in progress')
    # Basket is waiting for pickup
    PREPARED = 30, _('prepared')
    # Over, customer got his basket
    DELIVERED = 40, _('delivered')
    # Over, but not delivered, for some reason...
    ABANDONED = 50, _('abandoned')

class UnitTypes(models.TextChoices):
    UNIT = 'U', _('unit(s)')
    WEIGHT = 'W', _('Kg')

class URLTypes(models.TextChoices):
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
            choices=UnitTypes.choices,
            default=UnitTypes.WEIGHT)
    # category: food vs non-food, etc. May be useful later to emit invoices or
    # to decide which payment method is allowed
    # tax_rate: may be useful later to emit invoices

    class Meta:
        verbose_name = _('article')
        verbose_name_plural = _('articles')

    def __str__(self):
        return self.label


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
            choices=URLTypes.choices,
            default=URLTypes.WEB)
    merchant = models.ForeignKey(Merchant,
                                 on_delete=models.CASCADE,
                                 verbose_name=_('merchant'),
                                 related_name='contact_details')

    class Meta:
        verbose_name = _('URL')
        verbose_name_plural = _('URLs')

    def __str__(self):
        if len(self.address) > 40:
            address = '%s...' % self.address[:37]
        else:
            address = self.address
        return '%s: %s' % (self.get_url_type_display(), address)


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
    start = models.DateTimeField(_('start at'))
    end = models.DateTimeField(_('end at'))
    interval = models.PositiveSmallIntegerField(
            _('time slot'),
            help_text='Slots duration in minutes or 0 to disable slots.',
            default=0)
    # available article quantity
    # cart max count

    class Meta:
        permissions = [('view_delivery_quantities',
                        'View needed quantities for a delivery')]
        verbose_name = _('delivery')
        verbose_name_plural = _('deliveries')

    def slots(self):
        if self.interval == 0:
            return [{'start': self.start, 'end': self.end}]
        delta = self.end - self.start
        slot_count = math.ceil(delta.seconds / 60 / self.interval)
        return [{
            'start': self.start + timedelta(minutes=i*self.interval),
            'end': min(self.end,
                       self.start + timedelta(minutes=(i+1)*self.interval))}
            for i in range(slot_count)]

    def get_active_carts_by_slot(self):
        groups = self.slots()
        for c in self.get_active_carts():
            for s in groups:
                if not 'baskets' in s:
                    s['baskets'] = []
                if c.slot >= s['start'] and c.slot< s['end']:
                    s['baskets'].append(c)
        return groups

    def get_active_carts(self):
        return self.carts.filter(status__lte=CartStatuses.PREPARED)

    def get_needed_quantities(self):
        """
        Return a queryset of dict with article label, unit type and the
        total quantity of this article ordered by customers for this delivery
        """
        return CartItem.objects.filter(cart__delivery__id=self.id) \
                               .values('label', 'unit_type') \
                               .annotate(quantity=models.Sum('quantity'))

    def __str__(self):
        start_dt = timezone.localtime(self.start)
        loc = self.location.name
        day = date_format(start_dt, 'SHORT_DATE_FORMAT')
        hour = date_format(start_dt, 'TIME_FORMAT')
        return f'{loc} ({day} {hour})'


class Cart(models.Model):
    user = models.ForeignKey(
            User,
            on_delete=models.PROTECT)
    delivery = models.ForeignKey(
            Delivery,
            on_delete=models.SET_NULL,
            null=True,
            related_name='carts')
    slot = models.DateTimeField(_('chosen time slot'))
    status = models.PositiveSmallIntegerField(
            _('status'),
            choices=CartStatuses.choices,
            default=CartStatuses.RECEIVED)
    annotation = models.TextField(
            _('annotation'),
            blank=True,
            default='')

    class Meta:
        permissions = [('prepare_basket', 'Prepare basket')]
        verbose_name = _('cart')
        verbose_name_plural = _('carts')

    def slot_interval(self):
        slot_filtered = [s for s in self.delivery.slots()
                           if self.slot >= s['start'] and self.slot< s['end']]
        if len(slot_filtered) == 0:
            return {'start': self.delivery.start, 'end': self.delivery.end}
        return slot_filtered[0]

    def get_total(self):
        total = 0
        for i in self.items.all():
            total = total + i.unit_price * i.quantity
        return total

    def is_prepared(self):
        return self.status == CartStatuses.PREPARED

    def __str__(self):
        day = date_format(timezone.localdate(self.delivery.start),
                            'SHORT_DATE_FORMAT')
        user = self.user.get_full_name()
        items = self.items.count()
        return f'{day}: {user!s} ({items} items)'


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
    unit_type = models.CharField(max_length=1, choices=UnitTypes.choices)
    quantity = models.DecimalField(max_digits=6, decimal_places=3)

    class Meta:
        verbose_name = _('item')
        verbose_name_plural = _('items')

    # Manager with prices computed automatically annotated
    objects = CartItemManager()

    def __str__(self):
        q = self.quantity
        u = self.get_unit_type_display()
        item = self.label
        return f'{item}: {q} {u}'
