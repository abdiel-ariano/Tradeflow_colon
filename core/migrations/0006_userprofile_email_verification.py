"""
Migración: verificación de email en UserProfile.
Marca perfiles existentes como verificados para no bloquear cuentas demo.
"""
from django.db import migrations, models


def marcar_perfiles_verificados(apps, schema_editor):
    """Cuentas ya registradas antes de esta migración pueden iniciar sesión."""
    UserProfile = apps.get_model('core', 'UserProfile')
    UserProfile.objects.all().update(email_verificado=True, token_verificacion=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_company_lat_lng'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='email_verificado',
            field=models.BooleanField(default=False, verbose_name='Email verificado'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='token_verificacion',
            field=models.CharField(
                blank=True,
                help_text='Token UUID para verificación de email',
                max_length=64,
                null=True,
            ),
        ),
        migrations.RunPython(
            marcar_perfiles_verificados,
            migrations.RunPython.noop,
        ),
    ]
