from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_logistics_access_carrier'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('awaiting_seller', 'Esperando confirmación'),
                    ('pending', 'Pendiente'),
                    ('paid', 'Pagado'),
                    ('packed', 'Empacado'),
                    ('shipped', 'Enviado'),
                    ('delivered', 'Entregado'),
                    ('cancelled', 'Cancelado'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]
