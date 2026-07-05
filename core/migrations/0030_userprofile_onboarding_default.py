# Default onboarding_completed_at=timezone.now so test/legacy profiles skip the wizard.

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0029_buyer_onboarding_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='onboarding_completed_at',
            field=models.DateTimeField(
                blank=True,
                default=timezone.now,
                help_text='Null = wizard pending for new buyer signups; default now for legacy/test profiles.',
                null=True,
                verbose_name='Buyer onboarding completed',
            ),
        ),
    ]
