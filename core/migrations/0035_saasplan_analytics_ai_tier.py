# Generated manually for analytics AI plan tiers

from django.db import migrations, models


def seed_analytics_tiers(apps, schema_editor):
    SaasPlan = apps.get_model('core', 'SaasPlan')
    mapping = {
        'digitalizate': 'company',
        'expansion': 'company',
        'corporativo_pro': 'market',
        'ecosistema_enterprise': 'enterprise',
    }
    for slug, tier in mapping.items():
        SaasPlan.objects.filter(slug=slug).update(analytics_ai_tier=tier)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_password_reset_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='saasplan',
            name='analytics_ai_tier',
            field=models.CharField(
                choices=[
                    ('company', 'Company AI (own data only)'),
                    ('market', 'Market AI (own + ZLC benchmarks)'),
                    ('enterprise', 'Ecosystem AI (market + predictive)'),
                ],
                default='company',
                help_text='Scope of seller analytics IA (no analytics API yet).',
                max_length=20,
            ),
        ),
        migrations.RunPython(seed_analytics_tiers, migrations.RunPython.noop),
    ]
