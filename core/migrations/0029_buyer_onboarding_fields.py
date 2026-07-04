# Generated manually — buyer onboarding wizard (purchase intent + categories).

from django.db import migrations, models
from django.utils import timezone


def grandfather_existing_buyer_profiles(apps, schema_editor):
    """Cuentas creadas antes del wizard no deben ver el flujo obligatorio."""
    UserProfile = apps.get_model('core', 'UserProfile')
    UserProfile.objects.filter(onboarding_completed_at__isnull=True).update(
        onboarding_completed_at=timezone.now(),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_buyer_cart_reminder_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='purchase_intent',
            field=models.CharField(
                blank=True,
                choices=[
                    ('business', 'Business purchase'),
                    ('personal', 'Personal purchase'),
                ],
                help_text='Step 1 — wholesale vs personal shopping.',
                max_length=16,
                verbose_name='Purchase intent',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='onboarding_completed_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Null = wizard pending (new accounts only; existing users grandfathered).',
                null=True,
                verbose_name='Buyer onboarding completed',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='preferred_categories',
            field=models.ManyToManyField(
                blank=True,
                help_text='Step 2 — category interests for personalization.',
                related_name='buyer_profiles',
                to='core.category',
                verbose_name='Preferred categories',
            ),
        ),
        migrations.RunPython(grandfather_existing_buyer_profiles, migrations.RunPython.noop),
    ]
