from django.db import migrations, models
from datetime import datetime
from django.utils import timezone


def copy_dates(apps, schema_editor):
    Delivery = apps.get_model('baskets', 'Delivery')
    tz = timezone.utc
    for deliv in Delivery.objects.all():
        deliv.start = timezone.make_aware(
                datetime.combine(deliv.slot_date, deliv.slot_from), tz)
        deliv.end = timezone.make_aware(
                datetime.combine(deliv.slot_date, deliv.slot_to), tz)
        deliv.save()

def copy_dates_reverse(apps, schema_editor):
    Delivery = apps.get_model('baskets', 'Delivery')
    for deliv in Delivery.objects.all():
        deliv.slot_date = deliv.start.date()
        deliv.slot_from = deliv.start.time()
        deliv.slot_to = deliv.end.time()
        deliv.save()


class Migration(migrations.Migration):

    dependencies = [
        ('baskets', '0011_add_annotations_to_cart'),
    ]

    operations = [
        migrations.AlterField(
            model_name='delivery',
            name='slot_date',
            field=models.DateField(null=True),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='slot_from',
            field=models.TimeField(null=True),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='slot_to',
            field=models.TimeField(null=True),
        ),
        migrations.AddField(
            model_name='delivery',
            name='start',
            field=models.DateTimeField(null=True, verbose_name='start at'),
        ),
        migrations.AddField(
            model_name='delivery',
            name='end',
            field=models.DateTimeField(null=True, verbose_name='end at'),
        ),
        migrations.RunPython(copy_dates, copy_dates_reverse),
        migrations.RemoveField(
            model_name='delivery',
            name='slot_date',
        ),
        migrations.RemoveField(
            model_name='delivery',
            name='slot_from',
        ),
        migrations.RemoveField(
            model_name='delivery',
            name='slot_to',
        ),
        migrations.AlterField(
            model_name='delivery',
            name='start',
            field=models.DateTimeField(verbose_name='start at'),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='end',
            field=models.DateTimeField(verbose_name='end at'),
        ),
    ]
