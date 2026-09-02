"""Migrate legacy marketplace roles into the unified B2B company flow."""

from django.db import migrations
from django.utils import timezone


def backfill_legacy_business_intent(apps, schema_editor):
    """Preserve account capability while retiring the consumer wizard."""
    UserProfile = apps.get_model('core', 'UserProfile')
    now = timezone.now()

    for role in ('buyer', 'seller'):
        UserProfile.objects.filter(
            business_role_intent='',
            role=role,
        ).update(
            business_role_intent=role,
            onboarding_completed_at=now,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_company_b2b_identity'),
    ]

    operations = [
        migrations.RunPython(
            backfill_legacy_business_intent,
            migrations.RunPython.noop,
        ),
    ]
