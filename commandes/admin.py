from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Article, Merchant, Delivery, DeliveryLocation, URL
from django import forms


class DeliveryForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = '__all__'

    def clean(self):
        if self.cleaned_data.get('start') > self.cleaned_data.get('end'):
            msg = _('Delivery cannot end before it starts')
            raise forms.ValidationError(msg, code='invalid')
        return self.cleaned_data

class DeliveryAdmin(admin.ModelAdmin):
    form = DeliveryForm


admin.site.register(Merchant)
admin.site.register(URL)
admin.site.register(Article)
admin.site.register(Delivery, DeliveryAdmin)
admin.site.register(DeliveryLocation)
