"""Gestiona imágenes demo y referencias visuales de productos del catálogo ZLC.

Las referencias empaquetadas representan familias de producto concretas. Las
cargas reales de proveedores siempre conservan prioridad sobre estos recursos.
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, default_storage

from core.models import Product

log = logging.getLogger('tradeflow.demo_images')

PICSUM_SIZE = '400/300'

CATALOG_SEED_FILES = {
    'electronics': 'images/catalog-seeds/electronics.jpg',
    'textiles': 'images/catalog-seeds/textiles.jpg',
    'beauty': 'images/catalog-seeds/beauty.jpg',
    'home_appliances': 'images/catalog-seeds/home_appliances.jpg',
    'toys': 'images/catalog-seeds/toys.jpg',
    'general': 'images/catalog-seeds/general.jpg',
}

CATEGORY_ICON_FILES = {
    'electronics': 'images/category-icons/electronics.svg',
    'textiles': 'images/category-icons/textiles.svg',
    'beauty': 'images/category-icons/beauty.svg',
    'home_appliances': 'images/category-icons/home_appliances.svg',
    'toys': 'images/category-icons/toys.svg',
    'general': 'images/category-icons/general.svg',
}

CATEGORY_KEYWORDS = {
    'textiles': ['textile', 'fabric', 'clothing', 'uniform', 'apparel'],
    'electronics': ['electronic', 'gadget', 'computer', 'phone', 'tech'],
    'home_appliances': ['appliance', 'kitchen', 'home', 'household'],
    'beauty': ['beauty', 'cosmetic', 'perfume', 'fragrance', 'personal care'],
    'toys': ['toy', 'game', 'children'],
    'general': ['wholesale', 'bulk', 'merchandise', 'general'],
}

PRODUCT_REFERENCE_FILES = {
    'ups_1500va': 'assets/products/reference/ups-1500va.webp',
    'monitor_qhd_27': 'assets/products/reference/monitor-qhd-27.webp',
    'usb_c_hub': 'assets/products/reference/usb-c-hub.webp',
    'universal_docking_station': 'assets/products/reference/universal-docking-station.webp',
    'mechanical_keyboard': 'assets/products/reference/mechanical-keyboard.webp',
    'cat6_wiring_kit': 'assets/products/reference/cat6-wiring-kit.webp',
    'vertical_ergonomic_mouse': 'assets/products/reference/vertical-ergonomic-mouse.webp',
    'usb_condenser_microphone': 'assets/products/reference/usb-condenser-microphone.webp',
    'industrial_cargo_pants': (
        'assets/products/reference/industrial-cargo-pants.webp'
    ),
    'corporate_dry_fit_polo': (
        'assets/products/reference/corporate-dry-fit-polo.webp'
    ),
    'staff_waterproof_jacket': (
        'assets/products/reference/staff-waterproof-jacket.webp'
    ),
}

# Ordered from most specific to least specific. Values are normalized below.
PRODUCT_REFERENCE_MATCHES = (
    ('ups_1500va', ('1500va interactive ups', 'ups 1500va')),
    ('monitor_qhd_27', ('commercial 27" qhd led monitor', '27" qhd led monitor')),
    ('usb_c_hub', ('aluminum 11-in-1 usb-c hub', '11-in-1 usb-c hub')),
    ('universal_docking_station', ('universal docking station',)),
    ('mechanical_keyboard', ('hot-swap mechanical keyboard', 'mechanical keyboard')),
    ('cat6_wiring_kit', ('cat6 wiring kit',)),
    ('vertical_ergonomic_mouse', ('vertical ergonomic mouse',)),
    ('usb_condenser_microphone', ('usb condenser microphone',)),
    ('industrial_cargo_pants', ('industrial cargo pants',)),
    (
        'corporate_dry_fit_polo',
        ('corporate dry-fit polo', 'dry-fit polo'),
    ),
    (
        'staff_waterproof_jacket',
        ('staff waterproof jacket', 'waterproof staff jacket'),
    ),
)

DEMO_IMAGE_PREFIXES = (
    'products/demo/',
    'productos/placeholders/',
)

BRAND_COLORS = [
    (15, 42, 68),
    (27, 59, 99),
    (46, 91, 138),
    (242, 101, 34),
]


def category_keyword(product: Product) -> str:
    """Mapea un nombre de categoría a un bucket de palabra clave de imagen semilla."""
    if not product.category_id or not product.category:
        return 'general'
    cat_name = product.category.name.lower()
    for key, hints in CATEGORY_KEYWORDS.items():
        if key.replace('_', ' ') in cat_name or key in cat_name:
            return key
        if any(hint in cat_name for hint in hints):
            return key
    return 'general'


def seed_slug(product: Product) -> str:
    """Convierte texto a slug para nombres de archivo de imagen semilla."""
    raw = f'{product.pk}_{product.name[:40]}'
    return re.sub(r'[^a-zA-Z0-9_-]', '_', raw)


def picsum_url(product: Product) -> str:
    """Construye una URL Picsum determinista para imágenes demo."""
    return f'https://picsum.photos/seed/{seed_slug(product)}/{PICSUM_SIZE}'


def use_runtime_picsum() -> bool:
    """Devuelve True solo cuando Picsum remoto está explícitamente habilitado para demos."""
    return bool(getattr(settings, 'TRADEFLOW_USE_PICSUM_RUNTIME', False))


def catalog_seed_relative_path(keyword: str) -> str:
    """Devuelve la ruta relativa de un JPEG semilla de categoría empaquetado."""
    return CATALOG_SEED_FILES.get(keyword, CATALOG_SEED_FILES['general'])


def catalog_seed_static_path(product: Product) -> str:
    """Devuelve la ruta absoluta a la fotografía de categoría empaquetada para comandos seed."""
    return catalog_seed_relative_path(category_keyword(product))


def category_icon_static_path(product: Product) -> str:
    """Devuelve la ruta del icono SVG de categoría usado como último fallback de imagen pública."""
    keyword = category_keyword(product)
    return CATEGORY_ICON_FILES.get(keyword, CATEGORY_ICON_FILES['general'])


def _normalized_product_name(value: str) -> str:
    """Normaliza puntuación y espacios para resolver una familia de producto."""
    normalized = (value or '').lower()
    normalized = normalized.replace('“', '"').replace('”', '"').replace('″', '"')
    return re.sub(r'\s+', ' ', normalized).strip()


def product_reference_key(product: Product) -> str:
    """Devuelve la familia de referencia visual que coincide con el producto."""
    name = _normalized_product_name(getattr(product, 'name', ''))
    for key, phrases in PRODUCT_REFERENCE_MATCHES:
        if any(phrase in name for phrase in phrases):
            return key
    return ''


def product_reference_relative_path(product: Product) -> str:
    """Devuelve el WebP compartido para una familia de producto concreta."""
    return PRODUCT_REFERENCE_FILES.get(product_reference_key(product), '')


def product_reference_file_exists(product: Product) -> bool:
    """Devuelve True cuando la referencia concreta está empaquetada."""
    rel = product_reference_relative_path(product)
    return bool(rel and (Path(settings.BASE_DIR) / 'static' / rel).is_file())


def is_demo_generated_image(product: Product, rel_path: str = '') -> bool:
    """Identifica media generada por fixtures, sin marcar cargas de proveedores."""
    rel = (rel_path or '').replace('\\', '/').lstrip('/')
    if any(rel.startswith(prefix) for prefix in DEMO_IMAGE_PREFIXES):
        return True

    company = getattr(product, 'company', None)
    ruc = str(getattr(company, 'ruc', '') or '')
    return ruc.startswith('8-1Y-SIM-')


def should_use_product_reference(product: Product) -> bool:
    """Decide si una referencia puede sustituir media ausente o generada por demo."""
    if not product or not product_reference_file_exists(product):
        return False

    from core.utils.media_storage import is_remote_media_storage, local_media_file_exists

    rel = ''
    if getattr(product, 'image', None) and product.image.name:
        rel = product.image.name.replace('\\', '/')

    if not rel or is_demo_generated_image(product, rel):
        return True
    if is_remote_media_storage():
        return False
    return not local_media_file_exists(rel)


def ai_placeholder_relative_path(product: Product) -> str:
    """Devuelve una referencia familiar o el placeholder SKU heredado."""
    reference = product_reference_relative_path(product)
    if reference:
        return reference
    keyword = category_keyword(product)
    sku = re.sub(r'[^a-zA-Z0-9_-]', '-', (product.sku or f'p{product.pk}').lower())
    return f'assets/products/placeholder-ai/{keyword}-{sku}.webp'


def ai_placeholder_static_path(product: Product) -> str:
    """Devuelve la ruta estática de la referencia visual."""
    return ai_placeholder_relative_path(product)


def ai_placeholder_file_exists(product: Product) -> bool:
    """Devuelve True cuando existe la referencia familiar o SKU heredada."""
    rel = ai_placeholder_relative_path(product)
    return (Path(settings.BASE_DIR) / 'static' / rel).is_file()


def product_uses_ai_reference_image(product: Product) -> bool:
    """Devuelve True cuando la tarjeta pública mostrará un WebP de referencia."""
    if should_use_product_reference(product):
        return True
    if not product:
        return False

    from core.utils.media_storage import is_remote_media_storage, local_media_file_exists

    rel = ''
    if getattr(product, 'image', None) and product.image.name:
        rel = product.image.name.replace('\\', '/')
    if rel and not is_demo_generated_image(product, rel):
        if local_media_file_exists(rel) or is_remote_media_storage():
            return False
    return ai_placeholder_file_exists(product)


def catalog_seed_bytes(keyword: str) -> bytes:
    """Carga bytes JPEG empaquetados para una palabra clave de categoría."""
    rel = catalog_seed_relative_path(keyword)
    full = Path(settings.BASE_DIR) / 'static' / rel
    if not full.is_file():
        raise FileNotFoundError(f'Catalog seed missing: {full}')
    return full.read_bytes()


def variant_image_bytes(product: Product, *, width: int = 800, height: int = 600) -> bytes:
    """Recorta/redimensiona una semilla de categoría con offset por producto para variedad de SKU."""
    from PIL import Image

    keyword = category_keyword(product)
    source = Image.open(io.BytesIO(catalog_seed_bytes(keyword))).convert('RGB')
    src_w, src_h = source.size

    if src_w < width or src_h < height:
        source = source.resize((max(width, src_w), max(height, src_h)), Image.Resampling.LANCZOS)
        src_w, src_h = source.size

    # When the bundled seed matches the crop box, use a smaller window so PK offsets matter.
    crop_w, crop_h = width, height
    if src_w == width and src_h == height and src_w > 120:
        crop_w = max(120, int(src_w * 0.72))
        crop_h = max(90, int(src_h * 0.72))

    offset_x = ((product.pk * 47) + (product.pk ** 2)) % max(src_w - crop_w, 1)
    offset_y = ((product.pk * 31) + (product.pk * 19)) % max(src_h - crop_h, 1)
    cropped = source.crop((offset_x, offset_y, offset_x + crop_w, offset_y + crop_h))
    if crop_w != width or crop_h != height:
        cropped = cropped.resize((width, height), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    cropped.save(buffer, format='JPEG', quality=88, optimize=True)
    return buffer.getvalue()


def assign_catalog_seed_image(product: Product, *, log_fn=None) -> str:
    """Persiste una variante semilla de categoría como ImageField del producto."""
    if not product.pk:
        raise ValueError('Product must be saved before assigning an image')

    content = variant_image_bytes(product)
    rel_path = relative_image_path(product)
    write_local_image(rel_path, content)
    Product.objects.filter(pk=product.pk).update(image=rel_path)

    if log_fn:
        log_fn(f'Catalog seed image for {product.name} → {rel_path}')
    return rel_path


def extract_initials(name: str) -> str:
    """Devuelve las primeras letras de las dos primeras palabras, o las dos primeras de una sola."""
    words = [w for w in (name or '').split() if w]
    if len(words) >= 2:
        return f'{words[0][0]}{words[1][0]}'.upper()
    if len(words) == 1 and len(words[0]) >= 2:
        return words[0][:2].upper()
    if len(words) == 1 and len(words[0]) == 1:
        return words[0][0].upper()
    return 'NA'


def placeholder_relative_path(product: Product) -> str:
    """Devuelve la ruta relativa a MEDIA de un PNG placeholder de marca."""
    initials = extract_initials(product.name)
    return f'productos/placeholders/placeholder_{product.pk}_{initials}.png'


def assign_product_image(product: Product, *, log_fn=None) -> str:
    """Genera un PNG placeholder de marca bajo MEDIA_ROOT/productos/."""
    if not product.pk:
        raise ValueError('Product must be saved before assigning an image')

    content = generate_placeholder_bytes(product)
    if not content:
        raise ValueError(f'Empty image bytes for product {product.pk}')

    rel_path = placeholder_relative_path(product)
    write_local_image(rel_path, content)

    full_path = Path(settings.MEDIA_ROOT) / rel_path
    if not full_path.is_file() or full_path.stat().st_size == 0:
        raise OSError(f'Image file missing or empty after write: {full_path}')

    if log_fn:
        log_fn(f'Generated image for {product.name} → {rel_path}')
    return rel_path


def relative_image_path(product: Product) -> str:
    """Devuelve la ruta relativa de media para un nombre de imagen de producto."""
    return f'products/demo/product_{product.pk}.jpg'


def is_remote_storage() -> bool:
    """Devuelve True cuando el storage por defecto es un backend compatible con S3."""
    backend = settings.STORAGES.get('default', {}).get('BACKEND', '')
    return 's3boto3' in backend.lower() or 's3' in backend.lower()


def local_media_storage() -> FileSystemStorage:
    """Devuelve un FileSystemStorage con raíz en MEDIA_ROOT."""
    return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)


def write_local_image(rel_path: str, content: bytes) -> str:
    """Escribe bytes en MEDIA_ROOT/rel_path (sobrescribe si existe)."""
    full_path = Path(settings.MEDIA_ROOT) / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)
    return rel_path.replace('\\', '/')


def remote_command_storage():
    """Devuelve storage S3 para management commands (omite HeadObject vía archivo)."""
    backend = settings.STORAGES['default']['BACKEND']
    options = dict(settings.STORAGES['default'].get('OPTIONS', {}))
    options['file_overwrite'] = True
    options['default_acl'] = None
    from django.utils.module_loading import import_string

    storage_cls = import_string(backend)
    return storage_cls(**options)


def save_product_image_bytes(
    product: Product,
    content: bytes,
    *,
    storage_mode: str = 'local',
) -> str:
    """Persiste bytes de imagen y actualiza ``Product.image``."""
    rel_path = relative_image_path(product)
    file_obj = ContentFile(content)

    if storage_mode == 'local':
        saved = write_local_image(rel_path, content)
        Product.objects.filter(pk=product.pk).update(image=saved)
        return saved

    if storage_mode in ('remote', 'auto'):
        try:
            storage = remote_command_storage() if storage_mode == 'remote' else remote_command_storage()
            saved = storage.save(rel_path, file_obj)
            Product.objects.filter(pk=product.pk).update(image=saved)
            return saved
        except Exception as exc:
            if storage_mode == 'remote':
                raise
            log.warning('Remote storage failed for product %s (%s); using local.', product.pk, exc)
            saved = write_local_image(rel_path, content)
            Product.objects.filter(pk=product.pk).update(image=saved)
            return saved

    raise ValueError(f'Unknown storage_mode: {storage_mode}')


def generate_placeholder_bytes(product: Product) -> bytes:
    """Construye un PNG 400×400 con gradiente de marca e iniciales blancas centradas."""
    from PIL import Image, ImageDraw, ImageFont

    size = 400
    top_rgb = (0x1B, 0x3B, 0x63)
    bottom_rgb = (0x2E, 0x5B, 0x8A)
    initials = extract_initials(product.name)

    img = Image.new('RGB', (size, size), top_rgb)
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(size - 1, 1)
        color = tuple(
            int(top_rgb[i] + (bottom_rgb[i] - top_rgb[i]) * t)
            for i in range(3)
        )
        draw.line([(0, y), (size, y)], fill=color)

    font_candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    ]
    font = ImageFont.load_default()
    for path in font_candidates:
        if Path(path).is_file():
            font = ImageFont.truetype(path, 120)
            break

    bbox = draw.textbbox((0, 0), initials, font=font)
    x = (size - (bbox[2] - bbox[0])) / 2
    y = (size - (bbox[3] - bbox[1])) / 2
    draw.text((x, y), initials, fill=(255, 255, 255), font=font)

    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()


def save_placeholder_for_product(
    product: Product,
    content: bytes,
    *,
    storage_mode: str = 'local',
) -> str:
    """Guarda el PNG placeholder y asigna ``product.image`` (ruta idempotente)."""
    rel_path = placeholder_relative_path(product)

    if storage_mode == 'local':
        write_local_image(rel_path, content)
        Product.objects.filter(pk=product.pk).update(image=rel_path)
        return rel_path

    if storage_mode in ('remote', 'auto'):
        try:
            storage = remote_command_storage()
            saved = storage.save(rel_path, ContentFile(content))
            Product.objects.filter(pk=product.pk).update(image=saved)
            return saved
        except Exception as exc:
            if storage_mode == 'remote':
                raise
            log.warning('Remote storage failed for product %s (%s); using local.', product.pk, exc)
            write_local_image(rel_path, content)
            Product.objects.filter(pk=product.pk).update(image=rel_path)
            return rel_path

    raise ValueError(f'Unknown storage_mode: {storage_mode}')


def storage_mode_help() -> str:
    """Devuelve un texto corto de ayuda que describe el storage de media activo."""
    if is_remote_storage():
        return (
            'local (default): write to MEDIA_ROOT — safe in Docker/CI. '
            'remote: upload to Supabase/S3 (needs bucket permissions). '
            'auto: remote with local fallback.'
        )
    return 'local (default). remote/auto only apply when S3 storage is configured.'

