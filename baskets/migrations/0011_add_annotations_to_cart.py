# Generated by Django 3.0.4 on 2020-04-17 13:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('baskets', '0010_add_a_merchant_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='cart',
            name='annotation',
            field=models.TextField(blank=True, default='', verbose_name='annotation'),
        ),
    ]