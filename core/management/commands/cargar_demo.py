"""Load lightweight CFZ marketplace demo data for local development.

Creates categories, three ZLC companies, nine products (picsum images),
carrier options, and demo_buyer / demo_seller / demo_admin accounts.

Ops: local and disposable staging only. Do not run against production;
demo passwords and sparse catalog companies are for walkthroughs.
Idempotent: existing rows by name/SKU/username are skipped.
"""

import urllib.request
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings

from decimal import Decimal

from core.models import (
    UserProfile, Company, Category, Product, Inventory, TransportCarrier,
)

TRANSPORTISTAS = [
    {'code': 'zlc-express', 'name': 'ZLC Express', 'cost': '18.00', 'order': 1},
    {'code': 'colon-freight', 'name': 'Colón Freight', 'cost': '22.50', 'order': 2},
    {'code': 'panama-logistics', 'name': 'Panamá Logistics Hub', 'cost': '15.00', 'order': 3},
]


# ---------------------------------------------------------------------------
# Datos de demostración
# ---------------------------------------------------------------------------

CATEGORIAS = [
    'Electronics',
    'Textiles',
    'Perfumería y Cosméticos',
]

EMPRESAS = [
    {
        'name':         'TechZone Colón S.A.',
        'ruc':          '8-NT-2-123456',
        'address_text': 'Zona Libre de Colón, Edificio Tech Center, Local 12',
        'is_verified':  True,
    },
    {
        'name':         'Textiles Internacionales ZLC',
        'ruc':          '8-NT-2-234567',
        'address_text': 'Zona Libre de Colón, Avenida Roosevelt, Local 45',
        'is_verified':  True,
    },
    {
        'name':         'Fragancias del Mundo Ltda.',
        'ruc':          '8-NT-2-345678',
        'address_text': 'Zona Libre de Colón, Plaza Comercial Norte, Local 8',
        'is_verified':  True,
    },
]

# Cada producto tiene: nombre, descripción, SKU, precio, categoría (índice),
# empresa (índice), stock, imagen_seed (para picsum.photos), imagen_filename
PRODUCTOS = [
    {
        'name':        'Smartphone Samsung Galaxy A55',
        'description': 'Teléfono inteligente con pantalla AMOLED 6.6", cámara de 50MP y batería de 5000mAh. Importado directamente desde Samsung Electronics.',
        'sku':         'ELEC-SA55-001',
        'unit_price':  389.99,
        'categoria':   0,
        'empresa':     0,
        'stock':       45,
        'img_seed':    1,
        'img_file':    'samsung_a55.jpg',
    },
    {
        'name':        'Auriculares Sony WH-1000XM5',
        'description': 'Auriculares inalámbricos con cancelación de ruido líder en la industria. Autonomía de 30 horas. Incluye estuche de transporte.',
        'sku':         'ELEC-SONY-002',
        'unit_price':  249.00,
        'categoria':   0,
        'empresa':     0,
        'stock':       30,
        'img_seed':    20,
        'img_file':    'sony_wh1000.jpg',
    },
    {
        'name':        'Tablet Lenovo Tab P12',
        'description': 'Tablet de 12.7 pulgadas con pantalla LTPS, procesador MediaTek Dimensity 7050 y 8GB RAM. Ideal para trabajo y entretenimiento.',
        'sku':         'ELEC-LEN-003',
        'unit_price':  319.00,
        'categoria':   0,
        'empresa':     0,
        'stock':       20,
        'img_seed':    42,
        'img_file':    'lenovo_tab.jpg',
    },
    {
        'name':        'Conjunto de Lino Premium para Dama',
        'description': 'Conjunto de pantalón y blusa en lino 100% importado de Italia. Disponible en tallas S-XL. Colores: beige, blanco y azul marino.',
        'sku':         'TEXT-LINO-001',
        'unit_price':  89.50,
        'categoria':   1,
        'empresa':     1,
        'stock':       80,
        'img_seed':    64,
        'img_file':    'conjunto_lino.jpg',
    },
    {
        'name':        'Camisa Oxford Caballero',
        'description': 'Camisa de algodón Oxford de alta calidad. Corte slim fit. Disponible en blanco, azul celeste y gris. Tallas S al XXL.',
        'sku':         'TEXT-OXF-002',
        'unit_price':  45.00,
        'categoria':   1,
        'empresa':     1,
        'stock':       120,
        'img_seed':    85,
        'img_file':    'camisa_oxford.jpg',
    },
    {
        'name':        'Mochila Ejecutiva de Cuero',
        'description': 'Mochila de cuero genuino con compartimento para laptop de 15.6", puerto USB externo y sistema anti-robo. Importada de España.',
        'sku':         'TEXT-MCH-003',
        'unit_price':  129.00,
        'categoria':   1,
        'empresa':     1,
        'stock':       35,
        'img_seed':    100,
        'img_file':    'mochila_cuero.jpg',
    },
    {
        'name':        'Perfume Chanel N°5 Eau de Parfum',
        'description': 'Eau de Parfum 100ml. La fragancia más icónica del mundo. Notas florales con aldehídos. Presentación original con certificado de autenticidad.',
        'sku':         'PERF-CH5-001',
        'unit_price':  185.00,
        'categoria':   2,
        'empresa':     2,
        'stock':       25,
        'img_seed':    15,
        'img_file':    'chanel_n5.jpg',
    },
    {
        'name':        'Colonia Dior Sauvage EDT',
        'description': 'Eau de Toilette 200ml para caballero. Fragancia fresca y especiada con notas de bergamota y pimienta de Sichuan. 100% original.',
        'sku':         'PERF-DS-002',
        'unit_price':  145.00,
        'categoria':   2,
        'empresa':     2,
        'stock':       40,
        'img_seed':    33,
        'img_file':    'dior_sauvage.jpg',
    },
    {
        'name':        'Set de Maquillaje MAC Professional',
        'description': 'Kit profesional MAC con 24 sombras, base, corrector, rubor y labiales. Edición limitada importada directamente de los distribuidores oficiales.',
        'sku':         'PERF-MAC-003',
        'unit_price':  210.00,
        'categoria':   2,
        'empresa':     2,
        'stock':       18,
        'img_seed':    77,
        'img_file':    'mac_set.jpg',
    },
]

USUARIOS_DEMO = [
    {
        'username':   'demo_buyer',
        'first_name': 'Carlos',
        'last_name':  'Rodríguez',
        'email':      'demo.buyer@tradeflow.pa',
        'password':   'Demo1234!',
        'role':       'buyer',
        'phone':      '+507 6500-0001',
    },
    {
        'username':   'demo_seller',
        'first_name': 'Ana',
        'last_name':  'Martínez',
        'email':      'demo.seller@tradeflow.pa',
        'password':   'Demo1234!',
        'role':       'seller',
        'phone':      '+507 6500-0002',
    },
    {
        'username':   'demo_admin',
        'first_name': 'Patricia',
        'last_name':  'Vásquez',
        'email':      'demo.admin@tradeflow.pa',
        'password':   'Demo1234!',
        'role':       'admin',
        'phone':      '+507 6500-0003',
        'is_staff':   True,
    },
]


class Command(BaseCommand):
    """Seed demo catalog, ZLC companies, and fixed test users.

    Also links demo_seller to TechZone, ensures an active SaaS demo
    subscription, and repairs demo_admin staff/admin permissions.
    """

    help = 'Load demo data with images for TradeFlow Colón'

    def handle(self, *args, **options):
        """Create or skip demo entities and print login credentials."""
        self.stdout.write('=' * 60)
        self.stdout.write('TRADEFLOW — Cargando datos de demostración')
        self.stdout.write('=' * 60)

        # Asegura que la carpeta de imágenes existe
        media_products = os.path.join(settings.MEDIA_ROOT, 'products')
        os.makedirs(media_products, exist_ok=True)

        # 1. Categorías
        self.stdout.write('\n[1/6] Creando categorías...')
        categorias_obj = []
        for nombre in CATEGORIAS:
            cat, created = Category.objects.get_or_create(name=nombre)
            categorias_obj.append(cat)
            estado = 'CREADA' if created else 'ya existe'
            self.stdout.write(f'  {nombre} — {estado}')

        self.stdout.write('\n[2/7] Transportistas...')
        for t in TRANSPORTISTAS:
            obj, created = TransportCarrier.objects.get_or_create(
                code=t['code'],
                defaults={
                    'name': t['name'],
                    'base_shipping_cost': Decimal(t['cost']),
                    'sort_order': t['order'],
                    'description': 'Zona Libre de Colón — envío B2B',
                },
            )
            self.stdout.write(f'  {obj.name} — {"CREADO" if created else "ya existe"}')

        # 3. Empresas
        self.stdout.write('\n[3/7] Creando empresas...')
        empresas_obj = []
        for data in EMPRESAS:
            empresa, created = Company.objects.get_or_create(
                name=data['name'],
                defaults={
                    'ruc':          data['ruc'],
                    'address_text': data['address_text'],
                    'is_verified':  data['is_verified'],
                }
            )
            empresas_obj.append(empresa)
            estado = 'CREADA' if created else 'ya existe'
            self.stdout.write(f'  {empresa.name} — {estado}')

        # 4. Productos con imágenes
        self.stdout.write('\n[4/7] Creando productos e imágenes...')
        for data in PRODUCTOS:
            if Product.objects.filter(sku=data['sku']).exists():
                self.stdout.write(f'  {data["name"]} — ya existe, omitido')
                continue

            # Descarga la imagen
            img_path = os.path.join(media_products, data['img_file'])
            img_relative = f'products/{data["img_file"]}'
            if not os.path.exists(img_path):
                url = f'https://picsum.photos/seed/{data["img_seed"]}/600/600'
                try:
                    self.stdout.write(f'  Descargando imagen para {data["name"]}...')
                    urllib.request.urlretrieve(url, img_path)
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  No se pudo descargar imagen: {e}')
                    )
                    img_relative = ''

            # Crea el producto
            producto = Product.objects.create(
                company    = empresas_obj[data['empresa']],
                category   = categorias_obj[data['categoria']],
                name       = data['name'],
                description= data['description'],
                sku        = data['sku'],
                unit_price = data['unit_price'],
                currency   = 'USD',
                image      = img_relative,
                is_active  = True,
            )

            # Crea el inventario asociado
            Inventory.objects.create(
                product         = producto,
                stock_qty       = data['stock'],
                reserved_qty    = 0,
                low_stock_alert = 5,
            )

            self.stdout.write(
                self.style.SUCCESS(f'  {producto.name} — CREADO (stock: {data["stock"]})')
            )

        # 4. Usuarios de demo
        self.stdout.write('\n[4/6] Creando usuarios de demo...')
        for data in USUARIOS_DEMO:
            if User.objects.filter(username=data['username']).exists():
                self.stdout.write(f'  {data["username"]} — ya existe, omitido')
                continue

            user = User.objects.create_user(
                username   = data['username'],
                first_name = data['first_name'],
                last_name  = data['last_name'],
                email      = data['email'],
                password   = data['password'],
            )
            if data.get('is_staff'):
                user.is_staff = True
                user.save(update_fields=['is_staff'])
            UserProfile.objects.create(
                user=user,
                role=data['role'],
                phone=data['phone'],
                email_verificado=True,
                token_verificacion=None,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'  {data["username"]} ({data["role"]}) — CREADO | clave: {data["password"]}'
                )
            )

        # 5. Asociar vendedor demo a empresa TechZone (portal Mi Tienda)
        self.stdout.write('\n[5/6] Vinculando vendedor demo a empresa...')
        demo_seller = User.objects.filter(username='demo_seller').first()
        techzone = Company.objects.filter(name='TechZone Colón S.A.').first()
        if demo_seller and techzone:
            if techzone.owner_id != demo_seller.id:
                techzone.owner = demo_seller
                techzone.save(update_fields=['owner'])
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  {techzone.name} → propietario: {demo_seller.username}'
                    )
                )
            else:
                self.stdout.write(f'  {techzone.name} — ya vinculada a demo_seller')
            from core.utils.saas_billing import ensure_demo_subscription

            ensure_demo_subscription(techzone, status='active', plan_slug='digitalizate')
            self.stdout.write('  Suscripción demo_seller → active (Digitalízate)')
        else:
            self.stdout.write(
                self.style.WARNING('  No se pudo vincular demo_seller (usuario o empresa ausente).')
            )

        # 6. Configure demo_admin for Expo CRUD or protected read-only use.
        self.stdout.write(
            '\n[6/6] Ajustando cuenta demo_admin para la demostración...'
        )
        adm = User.objects.filter(username='demo_admin').first()
        if adm:
            prof = getattr(adm, 'profile', None)
            if prof and prof.role != 'admin':
                prof.role = 'admin'
                prof.save(update_fields=['role'])
                self.stdout.write(self.style.SUCCESS('  demo_admin → rol actualizado a admin'))
            elif not prof:
                UserProfile.objects.create(
                    user=adm,
                    role='admin',
                    phone='+507 6500-0003',
                    email_verificado=True,
                    token_verificacion=None,
                )
                self.stdout.write(self.style.SUCCESS('  demo_admin → perfil admin creado'))
            else:
                self.stdout.write('  demo_admin — rol admin OK')

            from core.utils.saas_demo import user_is_read_only_saas_demo

            if user_is_read_only_saas_demo(adm):
                if adm.is_staff:
                    adm.is_staff = False
                    adm.save(update_fields=['is_staff'])
                adm.groups.clear()
                adm.user_permissions.clear()
                self.stdout.write(
                    self.style.SUCCESS(
                        '  demo_admin → SaaS solo lectura; Django Admin bloqueado'
                    )
                )
            else:
                from core.utils.admin_permissions import sync_user_admin_access

                sync_user_admin_access(adm)
                self.stdout.write(
                    self.style.SUCCESS(
                        '  demo_admin → Django Admin integral habilitado'
                    )
                )

            prof = getattr(adm, 'profile', None)
            if prof and (not prof.email_verificado or prof.token_verificacion):
                prof.email_verificado = True
                prof.token_verificacion = None
                prof.save(update_fields=['email_verificado', 'token_verificacion'])
        else:
            self.stdout.write(self.style.WARNING('  demo_admin no existe; ejecuta de nuevo o crea el usuario en admin.'))

        for uname in ('demo_buyer', 'demo_seller', 'demo_admin'):
            u = User.objects.filter(username=uname).first()
            if not u:
                continue
            if not u.is_active:
                u.is_active = True
                u.save(update_fields=['is_active'])
            prof = getattr(u, 'profile', None)
            if prof and (not prof.email_verificado or prof.token_verificacion):
                prof.email_verificado = True
                prof.token_verificacion = None
                prof.save(update_fields=['email_verificado', 'token_verificacion'])

        # Resumen final
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('Datos de demo cargados correctamente.'))
        self.stdout.write(f'  Productos: {Product.objects.count()}')
        self.stdout.write(f'  Empresas:  {Company.objects.count()}')
        self.stdout.write(f'  Usuarios:  {User.objects.filter(is_superuser=False).count()}')
        self.stdout.write('\nAccesos de prueba:')
        self.stdout.write('  Buyer:  demo_buyer  / Demo1234!')
        self.stdout.write('  Seller: demo_seller / Demo1234! (Mi Tienda → TechZone Colón S.A.)')
        self.stdout.write(
            '  Admin:  demo_admin  / Demo1234! — /admin/ (Expo: CRUD completo)'
        )
        if getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', False):
            self.stdout.write(
                self.style.WARNING(
                    '\nREQUIRE_EMAIL_VERIFICATION está activo: las cuentas nuevas '
                    'deben verificar email. Las demo quedan con email_verificado=True.'
                )
            )
        backend = getattr(settings, 'EMAIL_BACKEND', '')
        if 'console' in backend:
            self.stdout.write(
                self.style.NOTICE(
                    'Los correos de prueba se imprimen en esta terminal (EMAIL_BACKEND consola).'
                )
            )
        self.stdout.write('=' * 60)
