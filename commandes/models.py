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
