from django.db import models


class UnitTypes(models.TextChoices):
    UNIT = "U", "unit(s)"
    WEIGHT = "W", "Kg"


class Article(models.Model):
    code = models.PositiveSmallIntegerField(unique=True)
    label = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=5, decimal_places=2)
    unit_type = models.CharField(
            max_length=1,
            choices=UnitTypes.choices,
            default=UnitTypes.WEIGHT)
    # category: food vs non-food, etc. May be useful later to emit invoices or
    # to decide which payment method is allowed
    # tax_rate: may be useful later to emit invoices

    def __str__(self):
        return self.label


class DeliveryLocation(models.Model):
    name = models.CharField(max_length=255)
    # address full
    # lat lon

    def __str__(self):
        return self.name


class Delivery(models.Model):
    location = models.ForeignKey(
            DeliveryLocation,
            on_delete=models.PROTECT)
    # TODO: refactor using a FK to a DeliverySlot model
    slot_date = models.DateField()
    slot_from = models.TimeField()
    slot_to = models.TimeField()
    # available article quantity
    # cart max count

    class Meta:
        verbose_name_plural = "deliveries"

    def __str__(self):
        loc = self.location.name
        s_day = self.slot_date
        s_from = self.slot_from
        return f"{loc} ({s_day:%d-%b-%Y} {s_from:%H:%M})"


class Cart(models.Model):
    # TODO refactor using Django auth module
    user = models.CharField(max_length=127)
    #status choices
    delivery = models.ForeignKey(
            Delivery,
            on_delete=models.SET_NULL,
            null=True,
            related_name="carts")

    def get_total(self):
        total = 0
        for i in self.items.all():
            total = total + i.unit_price * i.quantity
        return total

    def __str__(self):
        day = self.delivery.slot_date
        user = self.user
        items = self.items.count()
        return f"{day:%d-%b-%Y}: {user!s} ({items} items)"


class CartItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset() \
                      .annotate(price=models.F('unit_price') * models.F('quantity'))


class CartItem(models.Model):
    cart = models.ForeignKey(
            Cart,
            on_delete=models.CASCADE,
            related_name="items")
    # Duplicate article label and unit_price so we can keep consitent cart
    # history even when article definition is updated
    label = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=5, decimal_places=2)
    unit_type = models.CharField(max_length=1, choices=UnitTypes.choices)
    quantity = models.DecimalField(max_digits=6, decimal_places=3)

    # Manager with prices computed automatically annotated
    objects = CartItemManager()

    def __str__(self):
        q = self.quantity
        u = self.get_unit_type_display()
        item = self.label
        return f"{item}: {q} {u}"
