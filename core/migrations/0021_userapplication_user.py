from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0020_alter_address_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userapplication',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='access_applications',
                to=settings.AUTH_USER_MODEL,
                verbose_name='User account',
            ),
        ),
    ]
