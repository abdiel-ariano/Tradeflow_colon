"""Convert the legacy mixed order taxonomy to B2B-only orders."""

from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


def convert_orders_to_b2b(apps, schema_editor):
    """Relabel historical demo/legacy orders for the B2B-only marketplace."""
    Order = apps.get_model('core', 'Order')
    Order.objects.exclude(order_type='b2b').update(order_type='b2b')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_backfill_legacy_b2b_intent'),
    ]

    operations = [
        migrations.RunPython(convert_orders_to_b2b, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='order_type',
            field=models.CharField(
                choices=[('b2b', _('Business to business (B2B)'))],
                default='b2b',
                max_length=3,
            ),
        ),
    ]
