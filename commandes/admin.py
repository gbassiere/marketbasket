from django.contrib import admin
from .models import Article, Delivery, DeliveryLocation

admin.site.register(Article)
admin.site.register(Delivery)
admin.site.register(DeliveryLocation)
