from django.db import migrations, models


def forwards(apps, schema_editor):
    UserApplication = apps.get_model('core', 'UserApplication')
    mapping = {
        'pendiente': 'pending',
        'en_revision': 'pending',
        'aprobada': 'approved',
        'rechazada': 'rejected',
    }
    for old, new in mapping.items():
        UserApplication.objects.filter(status=old).update(status=new)


def backwards(apps, schema_editor):
    UserApplication = apps.get_model('core', 'UserApplication')
    mapping = {
        'pending': 'pendiente',
        'approved': 'aprobada',
        'rejected': 'rechazada',
    }
    for old, new in mapping.items():
        UserApplication.objects.filter(status=old).update(status=new)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_merge_userapplication_and_english_labels'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name='userapplication',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='pending',
                max_length=12,
            ),
        ),
    ]
