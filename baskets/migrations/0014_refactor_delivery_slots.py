from django.db import migrations, models
import django.db.models.deletion

import math
from datetime import timedelta
from django.db.models import IntegerField, ExpressionWrapper, F, Min, Max


def copy_slots(apps, schema_editor):
    Delivery = apps.get_model('baskets', 'Delivery')
    DeliverySlot = apps.get_model('baskets', 'DeliverySlot')
    # Models return by get_model are built from migration data and lack
    # custom class methods. Hence the remake of Delivery.slots():
    for d in Delivery.objects.all():
        if d.interval == 0:
            # Slots are disabled, i.e. there's a single slot
            DeliverySlot(start=d.start, end=d.end, delivery=d).save()
        else:
            # number of slots
            n = math.ceil((d.end-d.start).seconds/60/d.interval)
            for i in range(n):
                s = DeliverySlot(
                        start=d.start + timedelta(minutes=i*d.interval),
                        end=min(d.end,
                                d.start + timedelta(minutes=(i+1)*d.interval)),
                        delivery=d)
                s.save()
                # attach carts
                for c in d.carts.filter(start__gte=s.start, start__lt=s.end):
                    c.slot = s
                    c.save()


def copy_slots_reverse(apps, schema_editor):
    # detach carts
    Cart = apps.get_model('baskets', 'Cart')
    for c in Cart.objects.all():
        c.delivery = c.slot.delivery
        c.start = c.slot.start
        c.save()
    # retrieve interval, start and end from slots
    Delivery = apps.get_model('baskets', 'Delivery')
    expr_interval = ExpressionWrapper(
                        (F('end')-F('start'))/10**6/60,
                        output_field=IntegerField())
    for d in Delivery.objects.all():
        res = d.slots.aggregate(
                            start=Min('start'), end=Max('end'),
                            interval=Max(expr_interval))
        d.start = res['start']
        d.end = res['end']
        d.interval = res['interval']
        d.save()


class Migration(migrations.Migration):

    dependencies = [
        ('baskets', '0013_add_delivery_slots'),
    ]

    operations = [
        # add a slot model
        migrations.CreateModel(
            name='DeliverySlot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                serialize=False, verbose_name='ID')),
                ('start', models.DateTimeField(verbose_name='start at')),
                ('end', models.DateTimeField(verbose_name='end at')),
                ('delivery', models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='slots',
                                verbose_name='delivery',
                                to='baskets.Delivery')),
            ],
            options={
                'verbose_name': 'delivery time slot',
                'verbose_name_plural': 'delivery time slots',
            },
        ),
        # rename old slot field, so we can use this name for the new FK
        migrations.RenameField(
            model_name='cart',
            old_name='slot',
            new_name='start',
        ),
        # temporarily make old fields nullable (will help reverse migrations)
        migrations.AlterField(
            model_name='cart',
            name='start',
            field=models.DateTimeField(null=True,
                                verbose_name='chosen time slot'),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='start',
            field=models.DateTimeField(null=True,
                                verbose_name='start at'),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='end',
            field=models.DateTimeField(null=True,
                                verbose_name='end at'),
        ),
        # new slot field is an FK to DeliverySlot
        migrations.AddField(
            model_name='cart',
            name='slot',
            field=models.ForeignKey(null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            related_name='carts',
                            verbose_name='slot',
                            to='baskets.DeliverySlot'),
        ),
        # copy data
        migrations.RunPython(code=copy_slots,
                             reverse_code=copy_slots_reverse),
        # clean-up old fields on cart and delivery
        migrations.RemoveField(
            model_name='cart',
            name='start',
        ),
        migrations.RemoveField(
            model_name='cart',
            name='delivery',
        ),
        migrations.RemoveField(
            model_name='delivery',
            name='start',
        ),
        migrations.RemoveField(
            model_name='delivery',
            name='end',
        ),
        migrations.RemoveField(
            model_name='delivery',
            name='interval',
        ),
    ]
