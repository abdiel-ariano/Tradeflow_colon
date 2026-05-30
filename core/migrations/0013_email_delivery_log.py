# Generated manually for enterprise email audit trail

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_enterprise_saas_ads_api'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailDeliveryLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_type', models.CharField(db_index=True, max_length=40)),
                ('recipient', models.EmailField(max_length=254)),
                ('subject', models.CharField(max_length=255)),
                ('status', models.CharField(
                    choices=[('sent', 'Enviado'), ('failed', 'Fallido'), ('queued', 'En cola')],
                    default='queued',
                    max_length=12,
                )),
                ('error_message', models.TextField(blank=True)),
                ('backend', models.CharField(blank=True, max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Log de correo',
                'verbose_name_plural': 'Logs de correo',
                'ordering': ['-created_at'],
            },
        ),
    ]
