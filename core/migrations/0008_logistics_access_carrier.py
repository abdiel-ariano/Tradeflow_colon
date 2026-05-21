# Generated manually for PreExpo logistics + access requests

from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_merchandising_home_promo'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='order_confirm_hours',
            field=models.PositiveIntegerField(
                default=48,
                help_text='Plazo para que la empresa acepte o rechace una orden nueva.',
                verbose_name='Horas para confirmar pedido',
            ),
        ),
        migrations.CreateModel(
            name='TransportCarrier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='Nombre')),
                ('code', models.SlugField(max_length=40, unique=True, verbose_name='Código')),
                ('description', models.TextField(blank=True, verbose_name='Descripción')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='Orden')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('base_shipping_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Costo base envío (USD)')),
            ],
            options={
                'verbose_name': 'Transportista',
                'verbose_name_plural': 'Transportistas',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='UserApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=120, verbose_name='Nombre completo')),
                ('email', models.EmailField(max_length=254, verbose_name='Correo')),
                ('phone', models.CharField(blank=True, max_length=30, verbose_name='Teléfono')),
                ('role', models.CharField(choices=[('buyer', 'Comprador'), ('seller', 'Vendedor')], default='buyer', max_length=10)),
                ('company_name', models.CharField(blank=True, max_length=200, verbose_name='Empresa')),
                ('message', models.TextField(blank=True, verbose_name='Mensaje')),
                ('status', models.CharField(choices=[('pendiente', 'Pendiente'), ('aprobada', 'Aprobada'), ('rechazada', 'Rechazada')], default='pendiente', max_length=12)),
                ('review_token', models.CharField(editable=False, max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Solicitud de acceso',
                'verbose_name_plural': 'Solicitudes de acceso',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='order',
            name='buyer_latitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, verbose_name='Latitud comprador'),
        ),
        migrations.AddField(
            model_name='order',
            name='buyer_longitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, verbose_name='Longitud comprador'),
        ),
        migrations.AddField(
            model_name='order',
            name='buyer_location_verified_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Ubicación confirmada'),
        ),
        migrations.AddField(
            model_name='order',
            name='seller_confirmation_status',
            field=models.CharField(choices=[('pending', 'Pendiente'), ('accepted', 'Aceptada'), ('rejected', 'Rechazada'), ('expired', 'Expirada')], default='pending', max_length=12, verbose_name='Confirmación vendedor'),
        ),
        migrations.AddField(
            model_name='order',
            name='seller_confirm_by',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Confirmar antes de'),
        ),
        migrations.AddField(
            model_name='order',
            name='confirming_company',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders_to_confirm', to='core.company', verbose_name='Empresa que confirma'),
        ),
        migrations.AddField(
            model_name='order',
            name='transport_carrier',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='core.transportcarrier', verbose_name='Transportista'),
        ),
    ]
