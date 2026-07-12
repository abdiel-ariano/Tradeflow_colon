"""
=============================================================================
ACCIÓN: CREAR
DESTINO: core/management/commands/cargar_demo_merchandising.py
=============================================================================
Datos demo PreExpo: promos, destacados y secciones HomePromoSection.
=============================================================================
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from core.models import Category, Company, HomePromoSection, Product


class Command(BaseCommand):
    help = 'Configura merchandising demo para PreExpo (promos, secciones home).'

    def handle(self, *args, **options):
        """Handle."""
        now = timezone.now()
        ends = now + timedelta(days=45)

        companies = list(Company.objects.all()[:6])
        for i, c in enumerate(companies):
            c.is_featured = i < 4
            c.carousel_priority = (4 - i) * 10
            if not c.tagline_es:
                c.tagline_es = f'Proveedor líder en {c.name} — ZLC'
            if not c.tagline_en:
                c.tagline_en = f'Leading supplier at ZLC — {c.name}'
            c.save()

        products = list(
            Product.objects.filter(is_active=True).select_related('company')[:24]
        )
        for i, p in enumerate(products):
            p.is_featured = i < 8
            p.merchandising_priority = 100 - i
            if i < 6:
                p.promo_price = (p.unit_price * Decimal('0.85')).quantize(Decimal('0.01'))
                p.promo_starts_at = now
                p.promo_ends_at = ends
            if i < 4:
                p.is_bestseller = True
            p.save()

        sections_spec = [
            (
                'preexpo-season',
                'seasonal_banner',
                'PreExpo ZLC 2026',
                'PreExpo CFZ 2026',
                'Ofertas y catálogo para inversores y compradores internacionales.',
                'Deals and catalog for investors and international buyers.',
            ),
            (
                'daily-deals',
                'daily_deals',
                'Ofertas del día',
                'Daily deals',
                'Precios promocionales vigentes en la Zona Libre.',
                'Active promotional prices in the Free Zone.',
            ),
            (
                'bestsellers-zlc',
                'bestsellers',
                'Más vendidos ZLC',
                'ZLC bestsellers',
                'Lo que más mueven las empresas del corredor.',
                'Top movers among corridor businesses.',
            ),
        ]
        for sort_i, (slug, stype, tes, ten, ses, sen) in enumerate(sections_spec):
            sec, _ = HomePromoSection.objects.update_or_create(
                slug=slug,
                defaults={
                    'section_type': stype,
                    'title_es': tes,
                    'title_en': ten,
                    'subtitle_es': ses,
                    'subtitle_en': sen,
                    'is_active': True,
                    'sort_order': sort_i,
                    'starts_at': now - timedelta(days=1),
                    'ends_at': ends,
                    'max_items': 8,
                },
            )
            if stype == 'daily_deals':
                sec.products.set([p for p in products if p.is_on_promo_now][:8])
            elif stype == 'bestsellers':
                sec.products.set([p for p in products if p.is_bestseller][:8])
            else:
                sec.products.set(products[:6])

        self.stdout.write(self.style.SUCCESS('Merchandising demo cargado.'))
