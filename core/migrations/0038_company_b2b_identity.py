"""Add real B2B company identity, verification and memberships."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_company_identity_and_memberships(apps, schema_editor):
    """Preserve legacy sellers while creating explicit owner memberships."""
    Company = apps.get_model('core', 'Company')
    CompanyMembership = apps.get_model('core', 'CompanyMembership')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))

    for company in Company.objects.all().iterator():
        company.legal_name = company.name
        company.business_role = 'seller'
        if company.is_verified:
            company.verification_status = 'verified'
            company.verified_at = company.created_at or timezone.now()
        company.save(update_fields=[
            'legal_name', 'business_role', 'verification_status', 'verified_at',
        ])

        if company.owner_id and User.objects.filter(pk=company.owner_id).exists():
            CompanyMembership.objects.get_or_create(
                company_id=company.pk,
                user_id=company.owner_id,
                defaults={'role': 'owner', 'status': 'active'},
            )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_staff_mfa_backup_codes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name='company', name='business_email', field=models.EmailField(blank=True, max_length=254, verbose_name='Business email')),
        migrations.AddField(model_name='company', name='business_phone', field=models.CharField(blank=True, max_length=30, verbose_name='Business phone')),
        migrations.AddField(
            model_name='company',
            name='business_role',
            field=models.CharField(
                choices=[('buyer', 'Buyer'), ('seller', 'Seller'), ('both', 'Buyer and seller')],
                default='seller',
                max_length=10,
                verbose_name='Marketplace capability',
            ),
        ),
        migrations.AddField(model_name='company', name='dv', field=models.CharField(blank=True, max_length=20, verbose_name='Verification digit (DV)')),
        migrations.AddField(model_name='company', name='legal_name', field=models.CharField(blank=True, max_length=200, verbose_name='Registered legal name')),
        migrations.AddField(
            model_name='company',
            name='verification_document',
            field=models.FileField(
                blank=True,
                help_text='Aviso de operación, registro público or equivalent evidence for manual review.',
                null=True,
                upload_to='companies/verification/',
                verbose_name='Verification evidence',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='verification_notes',
            field=models.TextField(
                blank=True,
                help_text='Internal notes. Do not expose these notes in the public catalog.',
                verbose_name='Verification notes',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='verification_status',
            field=models.CharField(
                choices=[('draft', 'Draft'), ('pending', 'Pending review'), ('verified', 'Verified'), ('rejected', 'Rejected')],
                db_index=True,
                default='draft',
                max_length=12,
                verbose_name='Verification status',
            ),
        ),
        migrations.AddField(model_name='company', name='verification_submitted_at', field=models.DateTimeField(blank=True, null=True, verbose_name='Submitted for verification at')),
        migrations.AddField(model_name='company', name='verified_at', field=models.DateTimeField(blank=True, null=True, verbose_name='Verified at')),
        migrations.AddField(
            model_name='company',
            name='verified_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='companies_verified',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Verified by',
            ),
        ),
        migrations.AlterField(model_name='company', name='name', field=models.CharField(max_length=200, verbose_name='Trade name')),
        migrations.AlterField(
            model_name='company',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                help_text='Compatibility field; new access control uses company memberships.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='owned_companies',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Legacy owner',
            ),
        ),
        migrations.CreateModel(
            name='CompanyMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('owner', 'Owner'), ('admin', 'Company administrator'), ('member', 'Company member')], default='member', max_length=10)),
                ('status', models.CharField(choices=[('invited', 'Invited'), ('active', 'Active'), ('suspended', 'Suspended')], default='active', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='core.company')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='company_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Company membership',
                'verbose_name_plural': 'Company memberships',
                'ordering': ['company', 'role', 'user'],
                'indexes': [models.Index(fields=['user', 'status'], name='core_member_user_status_idx')],
                'constraints': [models.UniqueConstraint(fields=('company', 'user'), name='unique_company_user_membership')],
            },
        ),
        migrations.AddField(
            model_name='company',
            name='members',
            field=models.ManyToManyField(blank=True, related_name='member_companies', through='core.CompanyMembership', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddIndex(model_name='company', index=models.Index(fields=['ruc', 'dv'], name='core_company_ruc_dv_idx')),
        migrations.AddIndex(model_name='company', index=models.Index(fields=['business_role', 'verification_status'], name='core_company_role_status_idx')),
        migrations.RunPython(backfill_company_identity_and_memberships, migrations.RunPython.noop),
    ]
