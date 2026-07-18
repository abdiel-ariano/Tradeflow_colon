"""Optional staff TOTP MFA fields on UserProfile."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_gdpr_privacy_and_secret_hashes'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='staff_totp_secret',
            field=models.CharField(
                blank=True,
                default='',
                max_length=255,
                verbose_name='Staff TOTP secret (encrypted)',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='staff_totp_enabled',
            field=models.BooleanField(
                default=False,
                verbose_name='Staff TOTP MFA enabled',
            ),
        ),
    ]
