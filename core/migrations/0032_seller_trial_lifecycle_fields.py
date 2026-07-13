# Generated migration — seller trial lifecycle fields on CompanySubscription.

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_alter_product_sku'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysubscription',
            name='trial_volume_usd',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='USD vendidos durante el trial; fijado al finalizar el periodo.',
                max_digits=14,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='companysubscription',
            name='recommended_plan',
            field=models.ForeignKey(
                blank=True,
                help_text='Plan mínimo tras el trial según volumen; bloquea planes inferiores.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='recommended_for_subscriptions',
                to='core.saasplan',
            ),
        ),
        migrations.AddField(
            model_name='companysubscription',
            name='grace_ends_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Último día para activar plan antes de cancelación automática.',
                null=True,
            ),
        ),
    ]
