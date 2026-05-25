# Generated for enterprise SaaS persistence

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_saas_predictive_ai'),
    ]

    operations = [
        migrations.AddField(
            model_name='userapplication',
            name='requested_plan_slug',
            field=models.CharField(blank=True, help_text='Plan SaaS solicitado (ej. ecosistema_enterprise)', max_length=40),
        ),
        migrations.CreateModel(
            name='SubscriptionUpgradeLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('self_serve', 'Activación seller'), ('commercial', 'Aprobación comercial'), ('admin', 'Administrador')], default='self_serve', max_length=20)),
                ('activated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('notes', models.CharField(blank=True, max_length=255)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscription_upgrades', to='core.company')),
                ('from_plan', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='upgrades_from', to='core.saasplan')),
                ('to_plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='upgrades_to', to='core.saasplan')),
            ],
            options={
                'verbose_name': 'Historial upgrade plan',
                'verbose_name_plural': 'Historial upgrades plan',
                'ordering': ['-activated_at'],
            },
        ),
        migrations.CreateModel(
            name='CompanyPlanCommercialRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('en_revision', 'En revisión'), ('approved', 'Aprobada'), ('rejected', 'Rechazada')], default='pending', max_length=16)),
                ('contact_name', models.CharField(max_length=120)),
                ('contact_email', models.EmailField(max_length=254)),
                ('company_legal_name', models.CharField(blank=True, max_length=200)),
                ('message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plan_commercial_requests', to='core.company')),
                ('requested_plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='commercial_requests', to='core.saasplan')),
                ('user_application', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='plan_commercial_requests', to='core.userapplication')),
            ],
            options={
                'verbose_name': 'Solicitud plan comercial',
                'verbose_name_plural': 'Solicitudes plan comercial',
                'ordering': ['-created_at'],
            },
        ),
    ]
