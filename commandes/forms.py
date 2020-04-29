from django import forms
from django.db.models import Count
from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

from .models import Article, Cart


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
