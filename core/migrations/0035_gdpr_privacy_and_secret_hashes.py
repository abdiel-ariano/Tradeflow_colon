"""GDPR profile fields + widen OTP column for SHA-256 digests."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_password_reset_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='marketing_opt_in',
            field=models.BooleanField(
                default=False,
                help_text='User consented to cart reminders / promotional emails.',
                verbose_name='Marketing emails opt-in',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='privacy_accepted_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Privacy policy accepted at',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='privacy_policy_version',
            field=models.CharField(
                blank=True,
                default='',
                max_length=32,
                verbose_name='Privacy policy version accepted',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='account_anonymized_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Account anonymized at',
            ),
        ),
        migrations.AlterField(
            model_name='emailverification',
            name='code',
            field=models.CharField(db_index=True, max_length=64),
        ),
        # Invalidate legacy plaintext OTP / reset rows (short TTL anyway).
        migrations.RunSQL(
            sql='DELETE FROM core_emailverification;',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql='DELETE FROM core_passwordresetlink;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
