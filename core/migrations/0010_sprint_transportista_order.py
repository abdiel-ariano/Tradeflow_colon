from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0009_order_status_max_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='tiempo_confirmacion_horas',
            field=models.PositiveIntegerField(default=24, verbose_name='Horas para confirmación empresa'),
        ),
        migrations.AddField(
            model_name='order',
            name='confirmado_por_empresa',
            field=models.BooleanField(blank=True, help_text='True=aceptado, False=rechazado, None=pendiente', null=True, verbose_name='Confirmación empresa'),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=models.CharField(choices=[('buyer', 'Comprador'), ('seller', 'Vendedor'), ('admin', 'Administrador'), ('transportista', 'Transportista')], default='buyer', max_length=14, verbose_name='Rol'),
        ),
        migrations.CreateModel(
            name='Transportista',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('empresa_nombre', models.CharField(max_length=200)),
                ('licencia', models.CharField(max_length=100)),
                ('telefono', models.CharField(max_length=30)),
                ('email_contacto', models.EmailField(blank=True, max_length=254)),
                ('vehiculo_tipo', models.CharField(max_length=100)),
                ('vehiculo_placa', models.CharField(max_length=30)),
                ('cobertura_descripcion', models.TextField(help_text='Ciudades o zonas que cubre')),
                ('tarifa_base', models.DecimalField(decimal_places=2, max_digits=10)),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente de revisión'), ('aprobado', 'Aprobado'), ('rechazado', 'Rechazado')], default='pendiente', max_length=20)),
                ('fecha_aplicacion', models.DateTimeField(auto_now_add=True)),
                ('foto_licencia', models.ImageField(blank=True, null=True, upload_to='transportistas/')),
                ('calificacion_promedio', models.DecimalField(decimal_places=2, default=Decimal('5.00'), max_digits=3)),
                ('activo', models.BooleanField(default=False)),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='transportista', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Transportista',
                'verbose_name_plural': 'Transportistas',
            },
        ),
        migrations.CreateModel(
            name='AsignacionTransporte',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ubicacion_pickup_lat', models.DecimalField(decimal_places=7, max_digits=10)),
                ('ubicacion_pickup_lng', models.DecimalField(decimal_places=7, max_digits=10)),
                ('ubicacion_pickup_descripcion', models.CharField(blank=True, max_length=300)),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente confirmación'), ('confirmado', 'Transportista confirmó'), ('en_camino', 'En camino'), ('entregado', 'Entregado'), ('cancelado', 'Cancelado')], default='pendiente', max_length=20)),
                ('notas_buyer', models.TextField(blank=True)),
                ('costo_transporte', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('fecha_asignacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_confirmacion', models.DateTimeField(blank=True, null=True)),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='asignacion_transporte', to='core.order')),
                ('transportista', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='asignaciones', to='core.transportista')),
            ],
            options={
                'verbose_name': 'Asignación de transporte',
                'verbose_name_plural': 'Asignaciones de transporte',
            },
        ),
    ]
