from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_sprint_transportista_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='transportcarrier',
            name='transport_mode',
            field=models.CharField(
                choices=[
                    ('maritime', 'Marítimo'),
                    ('air', 'Aéreo'),
                    ('terrestrial', 'Terrestre'),
                    ('mixed', 'Mixto'),
                ],
                default='terrestrial',
                max_length=12,
                verbose_name='Modo de transporte',
            ),
        ),
    ]
