from django.contrib import admin
from .models import Article, Merchant, Delivery, DeliveryLocation, URL

admin.site.register(Merchant)
admin.site.register(URL)
admin.site.register(Article)
admin.site.register(Delivery)
admin.site.register(DeliveryLocation)
