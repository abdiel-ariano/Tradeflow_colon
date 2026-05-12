# Generated manually for TradeFlow Colón — seller portal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_category_company_remove_producto_categoria_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='owned_companies',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Propietario (vendedor)',
            ),
        ),
    ]
