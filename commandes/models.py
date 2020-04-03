from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.formats import date_format
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
    # TODO: refactor using a FK to a DeliverySlot model
    slot_date = models.DateField()
    slot_from = models.TimeField()
    slot_to = models.TimeField()
    # available article quantity
    # cart max count

    class Meta:
        permissions = [('view_delivery_quantities',
                        'View needed quantities for a delivery')]
        verbose_name = _('delivery')
        verbose_name_plural = _('deliveries')

    def get_active_carts(self):
        return self.carts.filter(status__lte=CartStatuses.PREPARED)

    def __str__(self):
        loc = self.location.name
        s_day = date_format(self.slot_date, 'SHORT_DATE_FORMAT')
        s_from = date_format(self.slot_from, 'TIME_FORMAT')
        return f'{loc} ({s_day} {s_from})'


class Cart(models.Model):
    user = models.ForeignKey(
            User,
            on_delete=models.PROTECT)
    delivery = models.ForeignKey(
            Delivery,
            on_delete=models.SET_NULL,
            null=True,
            related_name='carts')
    status = models.PositiveSmallIntegerField(
            _('status'),
            choices=CartStatuses.choices,
            default=CartStatuses.RECEIVED)

    class Meta:
        permissions = [('prepare_basket', 'Prepare basket')]
        verbose_name = _('cart')
        verbose_name_plural = _('carts')

    def get_total(self):
        total = 0
        for i in self.items.all():
            total = total + i.unit_price * i.quantity
        return total

    def __str__(self):
        day = date_format(self.delivery.slot_date, 'SHORT_DATE_FORMAT')
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
