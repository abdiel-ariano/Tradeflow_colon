from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_enforce_b2b_orders'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userprofile',
            name='preferred_categories',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='purchase_intent',
        ),
    ]
