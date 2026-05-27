# Generated manually for email OTP verification

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_plan_checkout'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='codigo_verificacion_email',
            field=models.CharField(
                blank=True,
                max_length=6,
                verbose_name='Código verificación email',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='codigo_verificacion_expira',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Expiración código email',
            ),
        ),
    ]
