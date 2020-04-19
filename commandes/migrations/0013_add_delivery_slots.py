from django.db import migrations, models


def set_default_slots(apps, schema_editor):
    Cart = apps.get_model('commandes', 'Cart')
    for cart in Cart.objects.all():
        # Default to first slot for older data
        cart.slot = cart.delivery.start
        cart.save()

class Migration(migrations.Migration):

    dependencies = [
        ('commandes', '0012_refactor_delivery_dates'),
    ]

    operations = [
        migrations.AddField(
            model_name='delivery',
            name='interval',
            field=models.PositiveSmallIntegerField(default=0,
                help_text='Slots duration in minutes or 0 to disable slots.',
                verbose_name='time slot'),
        ),
        migrations.AddField(
            model_name='cart',
            name='slot',
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(
                    code=set_default_slots,
                    reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='cart',
            name='slot',
            field=models.DateTimeField(verbose_name='chosen time slot'),
        ),
    ]
