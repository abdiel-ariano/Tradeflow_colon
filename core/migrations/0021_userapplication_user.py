from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def add_user_fk_if_missing(apps, schema_editor):
    """Add core_userapplication.user_id only if it is not already present.

    Some production databases already contain this column (it was created by an
    earlier, since-restructured migration) while Django's migration history does
    not record this migration as applied. Re-adding the column would raise
    DuplicateColumn, so we add it conditionally and rely on the accompanying
    state operation to keep Django's model state correct.
    """
    table = 'core_userapplication'
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        existing = {
            col.name
            for col in connection.introspection.get_table_description(cursor, table)
        }
    if 'user_id' in existing:
        return
    user_application = apps.get_model('core', 'UserApplication')
    user_model = apps.get_model(settings.AUTH_USER_MODEL)
    field = models.ForeignKey(
        to=user_model,
        blank=True,
        null=True,
        on_delete=django.db.models.deletion.CASCADE,
        related_name='access_applications',
        verbose_name='User account',
    )
    field.contribute_to_class(user_application, 'user')
    schema_editor.add_field(user_application, field)


def remove_user_fk(apps, schema_editor):
    table = 'core_userapplication'
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        existing = {
            col.name
            for col in connection.introspection.get_table_description(cursor, table)
        }
    if 'user_id' not in existing:
        return
    user_application = apps.get_model('core', 'UserApplication')
    user_model = apps.get_model(settings.AUTH_USER_MODEL)
    field = models.ForeignKey(
        to=user_model,
        blank=True,
        null=True,
        on_delete=django.db.models.deletion.CASCADE,
        related_name='access_applications',
        verbose_name='User account',
    )
    field.contribute_to_class(user_application, 'user')
    schema_editor.remove_field(user_application, field)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0020_alter_address_options_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='userapplication',
                    name='user',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='access_applications',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='User account',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_user_fk_if_missing, remove_user_fk),
            ],
        ),
    ]
