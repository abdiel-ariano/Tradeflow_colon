"""Add SEO slugs for Product and Company; backfill existing rows."""

from django.db import migrations, models
from django.utils.text import slugify


def _unique_slug(model, value, exclude_pk=None):
    base = slugify(value)[:192] or 'item'
    slug = base
    n = 2
    qs = model.objects.all()
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(slug=slug).exists():
        suffix = f'-{n}'
        slug = f'{base[: 220 - len(suffix)]}{suffix}'
        n += 1
    return slug


def backfill_slugs(apps, schema_editor):
    Company = apps.get_model('core', 'Company')
    Product = apps.get_model('core', 'Product')
    for company in Company.objects.all().only('id', 'name', 'slug'):
        if not company.slug:
            company.slug = _unique_slug(Company, company.name or f'company-{company.pk}', company.pk)
            company.save(update_fields=['slug'])
    for product in Product.objects.all().only('id', 'name', 'slug'):
        if not product.slug:
            product.slug = _unique_slug(Product, product.name or f'product-{product.pk}', product.pk)
            product.save(update_fields=['slug'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_staff_mfa_backup_codes'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='slug',
            field=models.SlugField(blank=True, default='', max_length=220, verbose_name='URL slug'),
        ),
        migrations.AddField(
            model_name='product',
            name='slug',
            field=models.SlugField(blank=True, default='', max_length=220, verbose_name='URL slug'),
        ),
        migrations.RunPython(backfill_slugs, noop_reverse),
        migrations.AlterField(
            model_name='company',
            name='slug',
            field=models.SlugField(
                blank=True, default='', max_length=220, unique=True, verbose_name='URL slug'
            ),
        ),
        migrations.AlterField(
            model_name='product',
            name='slug',
            field=models.SlugField(
                blank=True, default='', max_length=220, unique=True, verbose_name='URL slug'
            ),
        ),
    ]
