from django.db import migrations
from django.core.management.sql import emit_post_migrate_signal


GROUPS = {
        'Merchant': (
            'add_article',
            'change_article',
            'delete_article',
            'view_article',
            'add_cart',
            'change_cart',
            'delete_cart',
            'view_cart',
            'add_cartitem',
            'change_cartitem',
            'delete_cartitem',
            'view_cartitem',
            'add_delivery',
            'change_delivery',
            'delete_delivery',
            'view_delivery',
            'view_delivery_quantities',
            'add_deliverylocation',
            'change_deliverylocation',
            'delete_deliverylocation',
            'view_deliverylocation',
            ),
        'Packer': (
            'view_article',
            'change_cart',
            'view_cart',
            'view_cartitem',
            'view_delivery',
            'view_deliverylocation'
            ),
        'Customer': (
            'view_article',
            'add_cart',
            'change_cart',
            'view_cart',
            'add_cartitem',
            'change_cartitem',
            'delete_cartitem',
            'view_cartitem',
            'view_delivery',
            'view_deliverylocation',
            )
        }

def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    # Force Django to create permissions (which are normally
    # created on 'post_migrate' signal
    emit_post_migrate_signal(0, False, schema_editor.connection.alias)
    for name, codenames in GROUPS.items():
        group = Group(name=name)
        group.save()
        perms = Permission.objects.filter(codename__in=codenames)
        group.permissions.set(perms, clear=True)

def delete_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    db_alias = schema_editor.connection.alias
    Group.objects.filter(name__in=GROUPS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '__latest__'),
        ('commandes', '0004_add_a_model_permission'),
    ]

    operations = [
        migrations.RunPython(create_groups, delete_groups),
    ]
