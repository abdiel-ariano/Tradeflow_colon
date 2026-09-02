# Generated migration — bank transfer checkout fields (no Stripe).

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0032_seller_trial_lifecycle_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='companyplancheckout',
            name='provider',
            field=models.CharField(
                choices=[
                    ('mock', 'Card (demo)'),
                    ('stripe', 'Stripe (disabled)'),
                    ('bank', 'Bank transfer'),
                ],
                default='bank',
                max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name='companyplancheckout',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Payment pending'),
                    ('paid', 'Paid'),
                    ('cancelled', 'Cancelled'),
                    ('expired', 'Expired'),
                    ('rejected', 'Rejected'),
                ],
                default='pending',
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name='companyplancheckout',
            name='transfer_reference',
            field=models.CharField(
                blank=True,
                help_text='Referencia / número de operación bancaria indicado por el seller.',
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name='companyplancheckout',
            name='seller_notes',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='companyplancheckout',
            name='proof_file',
            field=models.FileField(
                blank=True,
                help_text='Comprobante de transferencia (PDF/imagen).',
                null=True,
                upload_to='plan_receipts/',
            ),
        ),
        migrations.AddField(
            model_name='companyplancheckout',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='companyplancheckout',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_plan_checkouts',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='companyplancheckout',
            name='review_notes',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
