# Generated manually for signup terms acceptance fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_remove_consumer_profile_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='terms_accepted',
            field=models.BooleanField(
                default=False,
                verbose_name='Terms and security policy accepted',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='terms_accepted_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Terms accepted at',
            ),
        ),
    ]
