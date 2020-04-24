from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Article, Merchant, URL
from .models import Delivery, DeliveryLocation, DeliverySlot
from django import forms


class DeliverySlotForm(forms.ModelForm):
    class Meta:
        model = DeliverySlot
        fields = '__all__'

    def clean(self):
        if self.cleaned_data.get('start') > self.cleaned_data.get('end'):
            msg = _('Delivery slot cannot end before it starts')
            raise forms.ValidationError(msg, code='invalid')
        return self.cleaned_data

class DeliverySlotAdmin(admin.ModelAdmin):
    form = DeliverySlotForm


admin.site.register(Merchant)
admin.site.register(URL)
admin.site.register(Article)
admin.site.register(Delivery)
admin.site.register(DeliverySlot, DeliverySlotAdmin)
admin.site.register(DeliveryLocation)
