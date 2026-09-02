"""Add hashed staff MFA backup codes on UserProfile."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_staff_totp_mfa'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='staff_totp_backup_hashes',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='SHA-256 hashes of one-time backup codes (survive SECRET_KEY rotation).',
                verbose_name='Staff MFA backup code hashes',
            ),
        ),
    ]
