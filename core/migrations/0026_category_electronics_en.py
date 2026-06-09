"""Rename Spanish electronics category label to English for storefront UI."""
from django.db import migrations


def forwards(apps, schema_editor):
    Category = apps.get_model('core', 'Category')
    for old in ('Electrónica', 'Electronica', 'electronica', 'ELECTRÓNICA'):
        Category.objects.filter(name=old).update(name='Electronics')


def backwards(apps, schema_editor):
    Category = apps.get_model('core', 'Category')
    Category.objects.filter(name='Electronics').update(name='Electrónica')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_cotizacion_es_automatica_cotizacion_lote'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
