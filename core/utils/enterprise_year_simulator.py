"""
Simulación ORM de ~12 meses de operación marketplace (ZLC) para demos enterprise.

Marcadores de limpieza:
  - Empresas: RUC con prefijo ``8-1Y-SIM-``
  - Órdenes: ``order_number`` con prefijo ``TF-1YSIM-``
  - Usuarios: ``username`` con prefijo ``sim1y_``
  - Home promos: ``slug`` con prefijo ``eyear-``
"""
from __future__ import annotations

import logging
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Sequence

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection, transaction
from django.db.models import Sum
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from django.utils.crypto import get_random_string

from core.enterprise_models import (
    AdCampaign,
    CompanyPredictiveSnapshot,
    CompanySubscription,
    LogisticsEvent,
    SaasPlan,
    SubscriptionUpgradeLog,
)
from core.models import (
    Address,
    Category,
    Company,
    HomePromoSection,
    Inventory,
    Order,
    OrderItem,
    Payment,
    Product,
    Shipment,
    TransportCarrier,
    UserProfile,
)
from core.utils.demo_product_images import assign_product_image
from core.utils.product_seed_naming import build_seed_product_name
from core.utils.product_stock_seed import realistic_stock_qty
from core.utils.ads_ranking import ensure_ad_credits
from core.utils.predictive_insights import get_predictive_dashboard
from core.utils.saas_billing import get_or_create_subscription, refresh_billing_usage
from core.utils.saas_platform import bootstrap_saas_datastore

log = logging.getLogger('tradeflow.platform')

# Tablas mínimas antes de sembrar (evita "no such table: core_order" sin migrate).
REQUIRED_TABLES = (
    'core_order',
    'core_product',
    'core_company',
    'core_userprofile',
    'core_inventory',
    'core_saasplan',
    'core_companysubscription',
)

class DatabaseSchemaNotReadyError(RuntimeError):
    """La base no tiene migraciones aplicadas."""


def ensure_database_schema_ready() -> None:
    """
    Comprueba que existan tablas core. Si no, indica ejecutar migrate primero.
    """
    try:
        tables = set(connection.introspection.table_names())
    except (OperationalError, ProgrammingError) as exc:
        raise DatabaseSchemaNotReadyError(
            'Could not inspect the database. '
            'Run: python manage.py migrate'
        ) from exc

    missing = [t for t in REQUIRED_TABLES if t not in tables]
    if missing:
        raise DatabaseSchemaNotReadyError(
            'Missing database tables (pending migrations): '
            f'{", ".join(missing)}. '
            'Run first: python manage.py migrate'
        )


SIM_RUC_PREFIX = '8-1Y-SIM-'
ORDER_NUM_PREFIX = 'TF-1YSIM-'
USER_PREFIX = 'sim1y_'
PROMO_SLUG_PREFIX = 'eyear-'

TRANSPORT_DEFAULTS = [
    {'code': 'zlc-express', 'name': 'ZLC Express', 'cost': '18.00', 'order': 1},
    {'code': 'colon-freight', 'name': 'Colón Freight', 'cost': '22.50', 'order': 2},
    {'code': 'panama-logistics', 'name': 'Panamá Logistics Hub', 'cost': '15.00', 'order': 3},
]


@dataclass(frozen=True)
class ScaleConfig:
    companies: int
    products_min: int
    products_max: int
    buyers: int
    orders: int


SCALES: dict[str, ScaleConfig] = {
    'demo': ScaleConfig(companies=5, products_min=6, products_max=14, buyers=10, orders=80),
    'standard': ScaleConfig(
        companies=14, products_min=35, products_max=140, buyers=45, orders=900
    ),
    'stress': ScaleConfig(
        companies=22, products_min=90, products_max=220, buyers=85, orders=2400
    ),
}


# Empresas ficticias creíbles (ZLC / importación) — nombres genéricos, no marcas registradas ajenas.
COMPANY_BLUEPRINTS: list[dict] = [
    {
        'name': 'CaribeTech Distribution ZLC',
        'tagline_es': 'Components and peripherals for corporate retail',
        'tier': 1,
        'cats': (0, 4),
    },
    {
        'name': 'MetroOffice Supply Colón',
        'tagline_es': 'B2B office furniture and equipment',
        'tier': 2,
        'cats': (0, 6),
    },
    {
        'name': 'Atlantic Textiles Wholesale',
        'tagline_es': 'Uniforms, denim, and hospitality linens',
        'tier': 2,
        'cats': (1,),
    },
    {
        'name': 'ZLC Gaming Imports',
        'tagline_es': 'Gaming peripherals and workstations',
        'tier': 1,
        'cats': (4, 0),
    },
    {
        'name': 'HomePro Caribe',
        'tagline_es': 'Appliances and white goods',
        'tier': 2,
        'cats': (3,),
    },
    {
        'name': 'Logistics Express Free Zone',
        'tagline_es': 'Packaging, pallets, and logistics consumables',
        'tier': 3,
        'cats': (5,),
    },
    {
        'name': 'Roosevelt Accessories Group',
        'tagline_es': 'Leather goods, luggage, and premium accessories',
        'tier': 2,
        'cats': (2, 1),
    },
    {
        'name': 'Panamax Electronics B2B',
        'tagline_es': 'Audio, video, and networking for integrators',
        'tier': 1,
        'cats': (0,),
    },
    {
        'name': 'Coco del Mar Imports',
        'tagline_es': 'Mixed retail and back-to-school season',
        'tier': 3,
        'cats': (6, 1, 2),
    },
    {
        'name': 'Fort Sherman Trading',
        'tagline_es': 'General imports and wholesale assortment',
        'tier': 3,
        'cats': (6,),
    },
    {
        'name': 'Isla Margarita Wholesale',
        'tagline_es': 'Textiles and industrial workwear',
        'tier': 2,
        'cats': (1,),
    },
    {
        'name': 'Cristóbal Tech Hub',
        'tagline_es': 'Edge servers, UPS, and structured cabling',
        'tier': 1,
        'cats': (0, 6),
    },
    {
        'name': 'Bay Cativá Home & Living',
        'tagline_es': 'Decor, lighting, and housewares',
        'tier': 2,
        'cats': (3, 2),
    },
    {
        'name': 'Colón Norte Industrial Supply',
        'tagline_es': 'PPE, tools, and industrial supplies',
        'tier': 2,
        'cats': (6, 5),
    },
    {
        'name': 'Silver Anchor Merchandising',
        'tagline_es': 'Promotional items and point-of-sale',
        'tier': 3,
        'cats': (2, 6),
    },
    {
        'name': 'Diablo Heights Distribution',
        'tagline_es': 'Consumer electronics and mobile accessories',
        'tier': 1,
        'cats': (0, 2),
    },
    {
        'name': 'Veraguas Shield Imports',
        'tagline_es': 'School supplies and institutional stationery',
        'tier': 3,
        'cats': (6, 1),
    },
    {
        'name': 'Pier 6 Global Trade',
        'tagline_es': 'Cross-docking and multichannel assortment',
        'tier': 2,
        'cats': (6, 5),
    },
    {
        'name': 'Free Port Digital',
        'tagline_es': 'Tablets, readers, and educational hardware',
        'tier': 2,
        'cats': (0, 4),
    },
    {
        'name': 'Free Zone Retail Partners',
        'tagline_es': 'Broad catalog for regional chains',
        'tier': 1,
        'cats': (6, 1, 3),
    },
    {
        'name': 'Barú Peak Logistics',
        'tagline_es': 'Kitting, labeling, and ZLC dispatch',
        'tier': 3,
        'cats': (5,),
    },
    {
        'name': 'Canal Side Accessories',
        'tagline_es': 'Cables, hubs, and connectivity solutions',
        'tier': 2,
        'cats': (0, 2),
    },
    {
        'name': 'TradeWind Colón Wholesale',
        'tagline_es': 'Multi-brand operator with B2B focus',
        'tier': 1,
        'cats': (6, 0, 1),
    },
]

CATEGORY_NAMES = [
    'Electronics & Office',
    'Textiles & Uniforms',
    'Accessories & Leather Goods',
    'Home & Appliances',
    'Gaming & Peripherals',
    'Logistics & Packaging',
    'General Imports',
]

# Plantillas de producto: (nombre base, descripción corta, precio_min, precio_max)
PRODUCT_TEMPLATES: dict[int, list[tuple[str, str, float, float]]] = {
    0: [
        ('Commercial 27" QHD LED Monitor', 'IPS panel, thin bezel, B2B warranty.', 189.0, 429.0),
        ('Aluminum 11-in-1 USB-C Hub', 'HDMI, RJ45, 100W PD, SD reader.', 45.0, 119.0),
        ('1500VA Interactive UPS', 'Automatic voltage regulation, monitoring software.', 220.0, 520.0),
        ('Cat6 Wiring Kit', '305m CCA-certified for installations.', 95.0, 185.0),
        ('Universal Docking Station', 'Dual display, fast laptop charging.', 129.0, 279.0),
    ],
    1: [
        ('Industrial Cargo Pants', 'Reinforced fabric, sizes 28-44.', 24.0, 48.0),
        ('Corporate Dry-Fit Polo', 'Embroidery included on orders of 200+ units.', 12.0, 28.0),
        ('Staff Waterproof Jacket', 'Hidden hood, reflective accents.', 38.0, 79.0),
        ('300-Thread Hospitality Set', 'Queen sheets, optical white.', 55.0, 110.0),
    ],
    2: [
        ('Rigid Executive Briefcase', 'TSA compartment, silent wheels.', 89.0, 189.0),
        ('Top-Grain Leather Belt', 'Minimalist buckle, black/brown.', 28.0, 65.0),
        ('Travel Organizer Set', '6 pieces, recycled material.', 18.0, 42.0),
    ],
    3: [
        ('2L Industrial Blender', 'Copper motor, steel blades.', 79.0, 159.0),
        ('8L Digital Air Fryer', '12 programs, retail certification.', 95.0, 185.0),
        ('Adjustable LED Floor Lamp', 'Adjustable color temperature.', 45.0, 120.0),
    ],
    4: [
        ('Hot-Swap Mechanical Keyboard', 'Linear switches, software RGB.', 65.0, 149.0),
        ('Vertical Ergonomic Mouse', '2400 DPI, USB-A/C receiver.', 32.0, 72.0),
        ('USB Condenser Microphone', 'Cardioid, anti-vibration mount.', 48.0, 129.0),
        ('XL Stitched Edge Pad', 'Hybrid surface 900x400mm.', 22.0, 55.0),
    ],
    5: [
        ('48mm x 150m Clear PP Tape', 'Pack of 36 pallet rolls.', 0.85, 1.4),
        ('20" Manual Stretch Film', '80 gauge, high elongation.', 18.0, 32.0),
        ('L-Shaped Cardboard Corner Protectors', 'Box of 500 units, pallet protection.', 0.12, 0.22),
    ],
    6: [
        ('Q4 Retail Assortment Kit', 'Promotional mix by season.', 120.0, 450.0),
        ('Modular Point-of-Sale Display', '3 tiers, acrylic + metal.', 65.0, 140.0),
        ('Assorted SKU Master Carton', 'Category-controlled assortment.', 200.0, 900.0),
    ],
}


def clear_enterprise_year_simulation() -> dict[str, int]:
    """Elimina filas generadas por esta simulación (orden seguro FK/PROTECT)."""
    ensure_database_schema_ready()
    deleted: dict[str, int] = {}

    order_qs = Order.objects.filter(order_number__startswith=ORDER_NUM_PREFIX)
    n_orders = order_qs.count()
    order_qs.delete()
    deleted['orders'] = n_orders

    prod_qs = Product.objects.filter(company__ruc__startswith=SIM_RUC_PREFIX)
    n_prod = prod_qs.count()
    prod_qs.delete()
    deleted['products'] = n_prod

    n_promo, _ = HomePromoSection.objects.filter(slug__startswith=PROMO_SLUG_PREFIX).delete()
    deleted['home_promo_sections'] = n_promo

    Company.objects.filter(ruc__startswith=SIM_RUC_PREFIX).update(owner=None)
    u_qs = User.objects.filter(username__startswith=USER_PREFIX)
    n_users = u_qs.count()
    u_qs.delete()
    deleted['users'] = n_users

    c_qs = Company.objects.filter(ruc__startswith=SIM_RUC_PREFIX)
    n_co = c_qs.count()
    c_qs.delete()
    deleted['companies'] = n_co

    return deleted


def _ensure_transport_carriers() -> list[TransportCarrier]:
    out: list[TransportCarrier] = []
    for t in TRANSPORT_DEFAULTS:
        obj, _ = TransportCarrier.objects.get_or_create(
            code=t['code'],
            defaults={
                'name': t['name'],
                'base_shipping_cost': Decimal(t['cost']),
                'sort_order': t['order'],
                'description': 'Colón Free Zone — B2B logistics',
            },
        )
        out.append(obj)
    return out


def _ensure_categories() -> list[Category]:
    cats: list[Category] = []
    for name in CATEGORY_NAMES:
        c, _ = Category.objects.get_or_create(name=name)
        cats.append(c)
    return cats


def _generate_product_image(product: Product) -> str | None:
    """Generate a local PNG under MEDIA_ROOT/productos/ and return the relative ImageField path."""
    try:
        return assign_product_image(product)
    except Exception as exc:
        log.warning('seed_image_generation_failed product=%s err=%s', product.pk, exc)
        return None


def _tier_weight(tier: int) -> float:
    return {1: 3.5, 2: 2.0, 3: 1.0}.get(tier, 1.0)


def _pick_company_index(rng: random.Random, tiers: Sequence[int]) -> int:
    weights = [_tier_weight(t) for t in tiers]
    return rng.choices(range(len(tiers)), weights=weights, k=1)[0]


def _random_timestamp_in_year(rng: random.Random, start: datetime, end: datetime) -> datetime:
    """Distribución beta (sesgo hacia fechas recientes) + horario comercial."""
    span_days = max(1, (end.date() - start.date()).days)
    u = rng.betavariate(2.0, 4.2)
    day_i = min(span_days - 1, int(u * span_days))
    d = start.date() + timedelta(days=day_i)
    hour = rng.randint(8, 19)
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    naive = datetime.combine(d, datetime.min.time().replace(hour=hour, minute=minute, second=second))
    if settings.USE_TZ:
        return timezone.make_aware(naive, timezone.get_current_timezone())
    return naive


def _status_for_timestamp(
    rng: random.Random, created_at: datetime, now: datetime
) -> tuple[str, str, bool | None]:
    """
    Retorna (order_status, seller_confirmation_status, confirmado_por_empresa).
    Órdenes recientes incluyen pipeline incompleto.
    """
    age_days = (now - created_at).total_seconds() / 86400.0
    if age_days < 10 and rng.random() < 0.18:
        return 'awaiting_seller', 'pending', None
    if age_days < 21 and rng.random() < 0.08:
        return 'pending', 'accepted', True
    if age_days < 35 and rng.random() < 0.06:
        return 'paid', 'accepted', True
    if age_days < 45 and rng.random() < 0.05:
        return 'packed', 'accepted', True
    if age_days < 60 and rng.random() < 0.04:
        return 'shipped', 'accepted', True

    roll = rng.random()
    if roll < 0.72:
        return 'delivered', 'accepted', True
    if roll < 0.82:
        return 'shipped', 'accepted', True
    if roll < 0.88:
        return 'packed', 'accepted', True
    if roll < 0.93:
        return 'paid', 'accepted', True
    return 'cancelled', rng.choice(['pending', 'rejected']), False


def run_enterprise_year_seed(
    *,
    scale: str = 'standard',
    seed: int = 42,
    skip_images: bool = True,
    clear: bool = False,
    stdout_write: Callable[[str], None] | None = None,
) -> dict:
    """
    Ejecuta la simulación completa. Devuelve estadísticas agregadas.
    """
    out: dict = {'ok': True, 'scale': scale, 'errors': []}

    def logmsg(msg: str) -> None:
        if stdout_write:
            stdout_write(msg)
        else:
            log.info(msg)

    if scale not in SCALES:
        out['ok'] = False
        out['errors'].append(f'escala_invalida:{scale}')
        return out

    cfg = SCALES[scale]
    rng = random.Random(seed)

    try:
        ensure_database_schema_ready()
    except DatabaseSchemaNotReadyError as exc:
        out['ok'] = False
        out['errors'].append(str(exc))
        logmsg(str(exc))
        return out

    if not skip_images and scale == 'stress':
        skip_images = True
        logmsg(
            '[images] Stress scale skips images by default; use --scale=demo or --scale=standard --with-images.'
        )
    elif skip_images:
        logmsg(
            '[images] Skipped (fast). Use --with-images to generate local placeholders under media/productos/. '
            'After --clear you must pass --with-images again to recreate images.'
        )
    else:
        logmsg('[images] Generating local PNG placeholders (media/productos/) for all seeded products.')

    if clear:
        d = clear_enterprise_year_simulation()
        logmsg(f'[clear] removed: {d}')
        logmsg(
            '[clear] Product image files under media/productos/ are not deleted automatically. '
            'Re-run with --with-images to assign fresh images to newly seeded products.'
        )

    carriers = _ensure_transport_carriers()
    categories = _ensure_categories()
    health = bootstrap_saas_datastore(seed_subscriptions=False)
    if not health.get('ok'):
        out['ok'] = False
        out['errors'].append(f'saas_health:{health.get("issues")}')
        return out

    now = timezone.now()

    with transaction.atomic():
        year_start = now - timedelta(days=365)

        blueprints = COMPANY_BLUEPRINTS[: cfg.companies]
        tiers = [b['tier'] for b in blueprints]

        companies: list[Company] = []

        for i, bp in enumerate(blueprints):
            su = User.objects.create_user(
                username=f'{USER_PREFIX}seller_{i}',
                email=f'{USER_PREFIX}seller_{i}@seed.tradeflow.pa',
                password=get_random_string(20),
                first_name='Seller',
                last_name=f'ZLC {i + 1}',
            )
            UserProfile.objects.create(user=su, role='seller', email_verificado=True)

            lat_j = 9.35 + rng.uniform(-0.04, 0.04)
            lng_j = -79.88 + rng.uniform(-0.05, 0.05)
            is_feat = bp['tier'] == 1 and rng.random() < 0.65
            co = Company.objects.create(
                name=bp['name'],
                ruc=f'{SIM_RUC_PREFIX}{i + 1:04d}',
                address_text=f'Colón Free Zone — {bp["name"]} — Building {rng.randint(1, 40)}, Unit {rng.randint(1, 120)}',
                is_verified=True,
                owner=su,
                latitud=lat_j,
                longitud=lng_j,
                is_featured=is_feat,
                carousel_priority=rng.randint(0, 100) if is_feat else rng.randint(0, 30),
                tagline_es=bp['tagline_es'],
                tagline_en='',
            )
            companies.append(co)

        buyers: list[User] = []
        buyer_addresses: dict[int, Address] = {}
        for j in range(cfg.buyers):
            bu = User.objects.create_user(
                username=f'{USER_PREFIX}buyer_{j}',
                email=f'{USER_PREFIX}buyer_{j}@seed.tradeflow.pa',
                password=get_random_string(20),
                first_name=rng.choice(['María', 'Luis', 'Andrea', 'Carlos', 'Sofía', 'Diego', 'Valentina', 'Jorge']),
                last_name=rng.choice(['Pérez', 'González', 'Herrera', 'Castillo', 'Vargas', 'Mendoza', 'Rojas', 'Silva']),
            )
            UserProfile.objects.create(user=bu, role='buyer', email_verificado=True)
            buyers.append(bu)
            addr = Address.objects.create(
                user=bu,
                label='Primary',
                country='Panamá',
                city=rng.choice(['Ciudad de Panamá', 'Colón', 'David', 'Chitré', 'Santiago']),
                line1=f'{rng.choice(["Brisas", "Costa Verde", "Los Pinos", "Centro"])} Residential Area, Street {rng.randint(1, 80)}',
                line2='',
                postal_code='',
                is_default=True,
            )
            buyer_addresses[bu.id] = addr

        # Productos por empresa (más productos en tier 1)
        products_by_company: dict[int, list[Product]] = {c.id: [] for c in companies}
        images_generated = 0
        products_pending_images: list[Product] = []
        for ci, co in enumerate(companies):
            tier = blueprints[ci]['tier']
            n_lo = cfg.products_min + (8 if tier == 1 else 0)
            n_hi = cfg.products_max + (25 if tier == 1 else 0)
            n_prod = rng.randint(n_lo, n_hi)
            cat_ixs = blueprints[ci]['cats']
            for p_idx in range(n_prod):
                cat = categories[rng.choice(cat_ixs)]
                templates = PRODUCT_TEMPLATES.get(cat_ixs[0], PRODUCT_TEMPLATES[6])
                base, desc, pmin, pmax = rng.choice(templates)
                name = build_seed_product_name(
                    company_name=co.name,
                    base_title=base,
                    description=desc,
                    product_index=p_idx,
                    rng=rng,
                )
                sku = f'1Y-{co.id:04d}-{p_idx:04d}'
                price = Decimal(str(round(rng.uniform(pmin, pmax), 2)))
                promo_price = None
                if rng.random() < 0.12:
                    promo_price = (price * Decimal('0.88')).quantize(Decimal('0.01'))

                pr = Product(
                    company=co,
                    category=cat,
                    name=name[:200],
                    description=(desc + ' ZLC import. Master pack available.')[:2000],
                    sku=sku[:100],
                    unit_price=price,
                    currency='USD',
                    is_active=True,
                    is_featured=tier == 1 and rng.random() < 0.08,
                    is_bestseller=False,
                    promo_price=promo_price,
                    promo_starts_at=now - timedelta(days=45) if promo_price else None,
                    promo_ends_at=now + timedelta(days=30) if promo_price else None,
                    merchandising_priority=rng.randint(0, 50) + (30 if tier == 1 else 0),
                )
                pr.save()
                if not skip_images:
                    products_pending_images.append(pr)
                stock_base = realistic_stock_qty(rng, tier=tier)
                Inventory.objects.create(
                    product=pr,
                    stock_qty=stock_base,
                    reserved_qty=0,
                    low_stock_alert=max(5, min(stock_base // 10, 25)),
                )
                products_by_company[co.id].append(pr)

        total_image_targets = len(products_pending_images)
        for idx, pr in enumerate(products_pending_images, start=1):
            rel_image = _generate_product_image(pr)
            if rel_image:
                Product.objects.filter(pk=pr.pk).update(image=rel_image)
                pr.image = rel_image
                images_generated += 1
                logmsg(f'[{idx}/{total_image_targets}] Generated image for {pr.name} → {rel_image}')
        if not skip_images:
            logmsg(f'[images] Generated {images_generated}/{total_image_targets} product image(s).')

        # SaaS: solo empresas simuladas (no toca otras empresas en la misma BD)
        seeded_subs = 0
        for co in companies:
            sub = get_or_create_subscription(co)
            ensure_ad_credits(co, sub.plan.ad_credits_monthly)
            seeded_subs += 1
        logmsg(f'[saas] subscriptions ensured for {seeded_subs} simulated companies')

        # Upgrades históricos (solo empresas grandes)
        plans = {p.slug: p for p in SaasPlan.objects.filter(is_active=True)}
        for ci, co in enumerate(companies):
            if blueprints[ci]['tier'] != 1:
                continue
            if not ('digitalizate' in plans and 'expansion' in plans):
                continue
            if rng.random() >= 0.55:
                continue
            sub = CompanySubscription.objects.filter(company=co).first()
            if sub and sub.plan_id == plans['digitalizate'].id:
                sub.plan = plans['expansion']
                sub.upgraded_at = year_start + timedelta(days=rng.randint(20, 120))
                sub.save(update_fields=['plan', 'upgraded_at'])
                SubscriptionUpgradeLog.objects.create(
                    company=co,
                    from_plan=plans['digitalizate'],
                    to_plan=plans['expansion'],
                    source='commercial',
                    activated_at=year_start + timedelta(days=rng.randint(30, 150)),
                    notes='Simulated operating-year upgrade',
                )

        # Órdenes
        company_products = products_by_company
        order_batch: list[Order] = []
        meta: list[dict] = []

        for _oi in range(cfg.orders):
            ci = _pick_company_index(rng, tiers)
            co = companies[ci]
            plist = company_products.get(co.id) or []
            if not plist:
                continue
            buyer = rng.choices(buyers, weights=[1.5 if k < len(buyers) // 5 else 1.0 for k in range(len(buyers))], k=1)[0]
            created_at = _random_timestamp_in_year(rng, year_start, now)
            status, sc_status, confirm_null = _status_for_timestamp(rng, created_at, now)
            carrier = rng.choice(carriers)
            ship_cost = carrier.base_shipping_cost + Decimal(str(rng.randint(0, 12)))

            n_lines = rng.choices([1, 2, 3, 4, 5], weights=[0.42, 0.32, 0.16, 0.07, 0.03], k=1)[0]
            chosen = rng.sample(plist, k=min(n_lines, len(plist)))

            subtotal = Decimal('0.00')
            lines_spec: list[tuple[Product, int, Decimal]] = []
            for pr in chosen:
                qty = rng.choices([1, 2, 3, 5, 8, 12], weights=[0.5, 0.22, 0.12, 0.08, 0.05, 0.03], k=1)[0]
                unit = pr.display_price if hasattr(pr, 'display_price') else pr.unit_price
                line_total = (unit * qty).quantize(Decimal('0.01'))
                subtotal += line_total
                lines_spec.append((pr, qty, unit))

            total = (subtotal + ship_cost).quantize(Decimal('0.01'))
            suffix = uuid.uuid4().hex[:6].upper()
            onum = f'{ORDER_NUM_PREFIX}{created_at.strftime("%Y%m")}-{suffix}'

            o = Order(
                buyer=buyer,
                ship_address=buyer_addresses[buyer.id],
                order_number=onum,
                status=status,
                order_type=rng.choices(['b2b', 'b2c'], weights=[0.35, 0.65], k=1)[0],
                subtotal=subtotal,
                shipping_cost=ship_cost,
                total=total,
                notes='',
                transport_carrier=carrier,
                buyer_latitude=Decimal(str(round(8.9 + rng.random() * 1.2, 6))),
                buyer_longitude=Decimal(str(round(-79.5 - rng.random() * 0.8, 6))),
                buyer_location_verified_at=created_at + timedelta(hours=rng.randint(1, 48))
                if status not in ('cancelled', 'awaiting_seller')
                else None,
                confirming_company=co,
                seller_confirmation_status=sc_status,
                seller_confirm_by=created_at + timedelta(hours=48) if status == 'awaiting_seller' else None,
                tiempo_confirmacion_horas=48,
                confirmado_por_empresa=confirm_null,
                created_at=created_at,
                updated_at=created_at + timedelta(hours=rng.randint(1, 120)),
            )
            order_batch.append(o)
            meta.append(
                {
                    'lines': lines_spec,
                    'status': status,
                    'created_at': created_at,
                    'company': co,
                    'carrier': carrier,
                }
            )

        # bulk_create orders
        Order.objects.bulk_create(order_batch, batch_size=400)

        # Map order_number -> id
        numbers = [o.order_number for o in order_batch]
        id_by_num = dict(Order.objects.filter(order_number__in=numbers).values_list('order_number', 'id'))

        order_items: list[OrderItem] = []
        payments: list[Payment] = []
        shipments: list[Shipment] = []
        logistics_rows: list[LogisticsEvent] = []

        for o, m in zip(order_batch, meta):
            oid = id_by_num[o.order_number]
            for pr, qty, unit in m['lines']:
                order_items.append(
                    OrderItem(
                        order_id=oid,
                        product_id=pr.id,
                        qty=qty,
                        unit_price_snapshot=unit,
                        line_total=(unit * qty).quantize(Decimal('0.01')),
                    )
                )

            st = m['status']
            if st != 'cancelled':
                pay_status = 'approved' if st in ('delivered', 'shipped', 'packed', 'paid', 'pending') else 'pending'
                if st == 'awaiting_seller':
                    pay_status = 'pending'
                payments.append(
                    Payment(
                        order_id=oid,
                        provider='mock',
                        status=pay_status,
                        amount=o.total,
                        currency='USD',
                        paid_at=m['created_at'] + timedelta(hours=rng.randint(2, 96))
                        if pay_status == 'approved'
                        else None,
                        txn_ref=f'SEED-{uuid.uuid4().hex[:12]}',
                    )
                )

            if st in ('shipped', 'delivered', 'packed'):
                co_m = m['company']
                car_m = m['carrier']
                ship_st = 'delivered' if st == 'delivered' else 'in_transit'
                delivered_at = None
                shipped_at = m['created_at'] + timedelta(hours=rng.randint(12, 96))
                if st == 'delivered':
                    delivered_at = shipped_at + timedelta(hours=rng.randint(24, 240))
                shipments.append(
                    Shipment(
                        order_id=oid,
                        courier_name=car_m.name,
                        tracking_number=f'ZLC-{uuid.uuid4().hex[:10].upper()}',
                        status=ship_st,
                        weight_kg=Decimal(str(round(rng.uniform(0.5, 45.0), 3))),
                        dimensions_cm=f'{rng.randint(20,120)}×{rng.randint(15,80)}×{rng.randint(10,60)}',
                        warehouse_code=f'WH-{rng.randint(1,9)}',
                        route_code=f'RT-{rng.choice(["ATL","PAC","URB"])}',
                        pickup_lat=Decimal(str(co_m.latitud)),
                        pickup_lng=Decimal(str(co_m.longitud)),
                        shipped_at=shipped_at,
                        delivered_at=delivered_at,
                    )
                )

            # Timeline logística
            t0 = m['created_at']
            if st != 'cancelled':
                logistics_rows.append(
                    LogisticsEvent(
                        order_id=oid,
                        event_type='order.received',
                        label='Order received at ZLC',
                        payload={'source': 'seed'},
                        source='seed',
                        created_at=t0,
                    )
                )
            if st in ('paid', 'packed', 'shipped', 'delivered'):
                logistics_rows.append(
                    LogisticsEvent(
                        order_id=oid,
                        event_type='payment.captured',
                        label='Payment confirmed',
                        payload={},
                        source='seed',
                        created_at=t0 + timedelta(hours=rng.randint(2, 24)),
                    )
                )
            if st in ('packed', 'shipped', 'delivered'):
                logistics_rows.append(
                    LogisticsEvent(
                        order_id=oid,
                        event_type='warehouse.packed',
                        label='ZLC warehouse — packed',
                        payload={},
                        source='seed',
                        created_at=t0 + timedelta(hours=rng.randint(8, 48)),
                    )
                )
            if st in ('shipped', 'delivered'):
                logistics_rows.append(
                    LogisticsEvent(
                        order_id=oid,
                        event_type='carrier.pickup',
                        label='Carrier dispatch',
                        payload={},
                        source='seed',
                        created_at=t0 + timedelta(hours=rng.randint(20, 72)),
                    )
                )

        OrderItem.objects.bulk_create(order_items, batch_size=800)
        Payment.objects.bulk_create(payments, batch_size=500)
        Shipment.objects.bulk_create(shipments, batch_size=500)
        LogisticsEvent.objects.bulk_create(logistics_rows, batch_size=800)

        # Ajuste de stock aproximado post-ventas (órdenes facturables)
        billable = ('paid', 'packed', 'shipped', 'delivered')
        usage = (
            OrderItem.objects.filter(order__order_number__startswith=ORDER_NUM_PREFIX, order__status__in=billable)
            .values('product_id')
            .annotate(sold=Sum('qty'))
        )
        sold_map = {r['product_id']: int(r['sold'] or 0) for r in usage}
        inv_updates: list[Inventory] = []
        for inv in Inventory.objects.filter(product_id__in=sold_map).select_related('product'):
            sold = sold_map.get(inv.product_id, 0)
            inv.stock_qty = max(35, inv.stock_qty - sold)
            inv_updates.append(inv)
        if inv_updates:
            Inventory.objects.bulk_update(inv_updates, ['stock_qty'], batch_size=500)

        # Best-sellers por volumen de líneas simuladas
        top_n = min(180, max(24, len(order_items) // 35))
        top_ids = (
            OrderItem.objects.filter(order__order_number__startswith=ORDER_NUM_PREFIX)
            .values('product_id')
            .annotate(units=Sum('qty'))
            .order_by('-units')[:top_n]
        )
        hot = {r['product_id'] for r in top_ids}
        Product.objects.filter(id__in=hot).update(is_bestseller=True)

        # Campañas publicitarias (elegantes, pocas por empresa tier 1-2)
        campaigns: list[AdCampaign] = []
        for ci, co in enumerate(companies):
            if blueprints[ci]['tier'] == 3 and rng.random() < 0.4:
                continue
            picks = company_products[co.id][:8]
            for pr in picks:
                if rng.random() > 0.45:
                    continue
                campaigns.append(
                    AdCampaign(
                        company=co,
                        product=pr,
                        name=f'Sponsorship {pr.name[:40]}',
                        placement=rng.choice(['search', 'home', 'category']),
                        boost_weight=Decimal(str(round(rng.uniform(1.2, 2.4), 2))),
                        credits_budget=rng.randint(200, 2000),
                        credits_spent=rng.randint(50, 800),
                        starts_at=year_start,
                        ends_at=now + timedelta(days=60),
                        is_active=True,
                        impressions=rng.randint(500, 50000),
                        clicks=rng.randint(20, 2000),
                    )
                )
        if campaigns:
            AdCampaign.objects.bulk_create(campaigns, batch_size=200)

        # Home promo: bestsellers del seed
        best_products = list(Product.objects.filter(company__ruc__startswith=SIM_RUC_PREFIX, is_bestseller=True)[:24])
        if best_products:
            sec, _ = HomePromoSection.objects.get_or_create(
                slug=f'{PROMO_SLUG_PREFIX}bestsellers',
                defaults={
                    'section_type': 'bestsellers',
                    'title_es': 'ZLC bestsellers — verified sellers',
                    'title_en': 'ZLC bestsellers — verified sellers',
                    'subtitle_es': 'Curated from 12-month simulated commercial volume',
                    'subtitle_en': 'Curated from 12-month commercial volume',
                    'is_active': True,
                    'sort_order': 2,
                    'starts_at': year_start,
                    'ends_at': None,
                    'max_items': min(16, len(best_products)),
                },
            )
            sec.products.set(best_products[: sec.max_items])

        # Persistir snapshots predictivos desde datos reales ORM
        for co in companies:
            try:
                CompanyPredictiveSnapshot.objects.filter(company=co).delete()
                get_predictive_dashboard(co, force_refresh=True)
            except Exception as exc:
                log.warning('predictive_snapshot_seed_failed company=%s err=%s', co.id, exc)

        for co in companies:
            try:
                refresh_billing_usage(co, now=now)
            except Exception as exc:
                log.warning('billing_usage_seed_failed company=%s err=%s', co.id, exc)

    # estadísticas fuera de atomic (solo lectura)
    out['companies'] = Company.objects.filter(ruc__startswith=SIM_RUC_PREFIX).count()
    out['products'] = Product.objects.filter(company__ruc__startswith=SIM_RUC_PREFIX).count()
    out['orders'] = Order.objects.filter(order_number__startswith=ORDER_NUM_PREFIX).count()
    out['buyers'] = User.objects.filter(username__startswith=f'{USER_PREFIX}buyer_').count()
    logmsg(
        f'[ok] companies={out["companies"]} products={out["products"]} '
        f'orders={out["orders"]} buyers={out["buyers"]}'
    )
    return out
