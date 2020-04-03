from django.db import migrations
from django.core.management.sql import emit_post_migrate_signal


def add_permission(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    # Force Django to create permissions (which are normally
    # created on 'post_migrate' signal
    emit_post_migrate_signal(0, False, schema_editor.connection.alias)
    perm = Permission.objects.get(codename='prepare_basket')
    for group in Group.objects.filter(name__in=('Merchant', 'Packer')):
        group.permissions.add(perm)


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '__latest__'),
        ('commandes', '0008_add_a_model_permission'),
    ]

    operations = [
        migrations.RunPython(add_permission, migrations.RunPython.noop),
    ]
