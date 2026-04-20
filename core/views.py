"""
=============================================================================
TRADEFLOW COLÓN — core/views.py  (v4 — Roles + Signup)
=============================================================================
CAMBIOS en esta versión:
  - login_view: redirige según rol después del login
  - signup_view: registro público crea User + UserProfile
  - dashboard y vistas admin protegidas con @admin_required
=============================================================================
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .decorators import admin_required, buyer_required, seller_required
from .models import (
    UserProfile, Company, Category, Product, Inventory,
    Address, Order, OrderItem, Payment, Shipment, Document
)


# =============================================================================
# HELPERS
# =============================================================================

def _redirect_by_role(user):
    """Devuelve la URL de inicio según el rol del usuario."""
    try:
        role = user.profile.role
    except Exception:
        role = None

    if user.is_superuser or role == 'admin':
        return '/'
    if role == 'seller':
        return '/mi-tienda/'
    return '/tienda/'


# =============================================================================
# AUTENTICACIÓN
# =============================================================================

def login_view(request):
    """Login con redirección inteligente según rol."""
    if request.user.is_authenticated:
        return redirect(_redirect_by_role(request.user))

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido, {user.first_name or user.username}!')
            # Respeta ?next= si existe, sino redirige por rol
            next_url = request.GET.get('next', '')
            return redirect(next_url if next_url else _redirect_by_role(user))
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'core/login.html')


def logout_view(request):
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('login')


def signup_view(request):
    """Registro público: crea User + UserProfile."""
    if request.user.is_authenticated:
        return redirect(_redirect_by_role(request.user))

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        username   = request.POST.get('username', '').strip()
        email      = request.POST.get('email', '').strip()
        phone      = request.POST.get('phone', '').strip()
        role       = request.POST.get('role', 'buyer')
        password1  = request.POST.get('password1', '')
        password2  = request.POST.get('password2', '')

        # Validaciones
        if not all([first_name, username, email, password1, password2]):
            messages.error(request, 'Todos los campos marcados con * son obligatorios.')
        elif password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
        elif len(password1) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f'El usuario "{username}" ya existe. Elige otro.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Ya existe una cuenta con ese correo.')
        elif role not in ('buyer', 'seller'):
            messages.error(request, 'Tipo de cuenta no válido.')
        else:
            # Crear usuario
            user = User.objects.create_user(
                username   = username,
                email      = email,
                password   = password1,
                first_name = first_name,
                last_name  = last_name,
            )
            UserProfile.objects.create(user=user, role=role, phone=phone)

            # Login automático después del registro
            login(request, user)
            messages.success(request, f'¡Bienvenido a TradeFlow, {first_name}! Tu cuenta ha sido creada.')
            return redirect(_redirect_by_role(user))

    return render(request, 'core/signup.html', {
        'role_choices': [('buyer', 'Comprador'), ('seller', 'Vendedor')],
        'selected_role': request.POST.get('role', 'buyer'),
    })



def home_view(request):
        if request.user.is_authenticated:
            return redirect(_redirect_by_role(request.user))
        from .models import Product
        productos = Product.objects.filter(
            is_active=True
        ).select_related('company', 'category').order_by('?')[:6]
        return render(request, 'core/home.html', {'productos': productos})


# =============================================================================
# DASHBOARD (solo admin)
# =============================================================================

@admin_required
def dashboard(request):
    hoy         = timezone.now()
    hace_7_dias = hoy - timedelta(days=7)

    total_ordenes    = Order.objects.count()
    ordenes_semana   = Order.objects.filter(created_at__gte=hace_7_dias).count()
    ingresos_total   = Order.objects.filter(status='delivered').aggregate(t=Sum('total'))['t'] or 0
    ingresos_semana  = Order.objects.filter(
        status='delivered', created_at__gte=hace_7_dias
    ).aggregate(t=Sum('total'))['t'] or 0
    total_productos  = Product.objects.filter(is_active=True).count()
    total_empresas   = Company.objects.count()
    ordenes_recientes = Order.objects.select_related('buyer').order_by('-created_at')[:5]

    dias_semana     = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    ordenes_por_dia = []
    for i in range(7):
        dia   = hoy - timedelta(days=hoy.weekday() - i)
        count = Order.objects.filter(created_at__date=dia.date()).count()
        ordenes_por_dia.append(count)

    context = {
        'total_ordenes':     total_ordenes,
        'ordenes_semana':    ordenes_semana,
        'ingresos_total':    ingresos_total,
        'ingresos_semana':   ingresos_semana,
        'total_productos':   total_productos,
        'total_empresas':    total_empresas,
        'ordenes_recientes': ordenes_recientes,
        'dias_semana':       dias_semana,
        'ordenes_por_dia':   ordenes_por_dia,
        'titulo_pagina':     'Dashboard',
        'nav_activo':        'dashboard',
    }
    return render(request, 'core/dashboard.html', context)


# =============================================================================
# ÓRDENES (solo admin)
# =============================================================================

@admin_required
def lista_ordenes(request):
    ordenes = Order.objects.select_related('buyer').order_by('-created_at')
    buscar  = request.GET.get('buscar', '')
    estado  = request.GET.get('estado', '')

    if buscar:
        ordenes = ordenes.filter(
            Q(order_number__icontains=buscar) |
            Q(buyer__first_name__icontains=buscar) |
            Q(buyer__last_name__icontains=buscar) |
            Q(buyer__username__icontains=buscar)
        )
    if estado:
        ordenes = ordenes.filter(status=estado)

    paginator = Paginator(ordenes, 10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        'ordenes':        page_obj,
        'buscar':         buscar,
        'estado_actual':  estado,
        'status_choices': Order.STATUS_CHOICES,
        'titulo_pagina':  'Gestión de Órdenes',
        'nav_activo':     'ordenes',
    }
    return render(request, 'core/ordenes.html', context)


@admin_required
def detalle_orden(request, pk):
    orden = get_object_or_404(
        Order.objects.select_related('buyer', 'ship_address')
                     .prefetch_related('items__product', 'documents'),
        pk=pk
    )
    context = {
        'orden':         orden,
        'pago':          getattr(orden, 'payment',  None),
        'envio':         getattr(orden, 'shipment', None),
        'titulo_pagina': f'Orden {orden.order_number}',
        'nav_activo':    'ordenes',
    }
    return render(request, 'core/detalle_orden.html', context)


@admin_required
def cambiar_estado_orden(request, pk, estado):
    orden = get_object_or_404(Order, pk=pk)
    estados_validos = [e[0] for e in Order.STATUS_CHOICES]

    if estado in estados_validos:
        orden.status = estado
        orden.save(update_fields=['status', 'updated_at'])
        if estado == 'delivered':
            pago = getattr(orden, 'payment', None)
            if pago and pago.status == 'pending':
                pago.status  = 'approved'
                pago.paid_at = timezone.now()
                pago.save(update_fields=['status', 'paid_at'])
        messages.success(request, f'Orden actualizada a "{orden.get_status_display()}".')
    else:
        messages.error(request, 'Estado no válido.')

    return redirect('detalle_orden', pk=pk)


# =============================================================================
# WIZARD DE NUEVA ORDEN (solo admin)
# =============================================================================

@admin_required
def nueva_orden_paso1(request):
    request.session.pop('wizard_buyer_id',   None)
    request.session.pop('wizard_order_type', None)
    request.session.pop('wizard_items',      None)

    compradores = User.objects.filter(is_active=True).order_by('username')

    if request.method == 'POST':
        buyer_id   = request.POST.get('buyer_id')
        order_type = request.POST.get('order_type', 'b2c')
        if not buyer_id:
            messages.error(request, 'Debes seleccionar un comprador.')
        else:
            request.session['wizard_buyer_id']   = int(buyer_id)
            request.session['wizard_order_type'] = order_type
            return redirect('nueva_orden_paso2')

    return render(request, 'core/nueva_orden_paso1.html', {
        'compradores':   compradores,
        'order_types':   Order.ORDER_TYPE_CHOICES,
        'titulo_pagina': 'Nueva Orden — Paso 1',
        'nav_activo':    'ordenes',
        'paso_actual':   1,
    })


@admin_required
def nueva_orden_paso2(request):
    if not request.session.get('wizard_buyer_id'):
        messages.error(request, 'Debes completar el paso 1 primero.')
        return redirect('nueva_orden_paso1')

    productos  = Product.objects.filter(is_active=True).select_related(
        'category', 'company', 'inventory'
    ).order_by('name')
    categorias = Category.objects.all()

    buscar    = request.GET.get('buscar', '')
    categoria = request.GET.get('categoria', '')
    if buscar:
        productos = productos.filter(Q(name__icontains=buscar) | Q(sku__icontains=buscar))
    if categoria:
        productos = productos.filter(category__id=categoria)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'agregar':
            producto_id = request.POST.get('producto_id')
            cantidad    = int(request.POST.get('cantidad', 1))
            try:
                producto = Product.objects.select_related('inventory').get(
                    pk=producto_id, is_active=True
                )
            except Product.DoesNotExist:
                messages.error(request, 'Producto no encontrado.')
                return redirect('nueva_orden_paso2')

            disponible = producto.available_qty
            if cantidad < 1:
                messages.error(request, 'La cantidad debe ser al menos 1.')
            elif cantidad > disponible:
                messages.error(request, f'Stock insuficiente. Disponible: {disponible}.')
            else:
                items = request.session.get('wizard_items', [])
                encontrado = False
                for item in items:
                    if item['producto_id'] == int(producto_id):
                        nueva_cant = item['cantidad'] + cantidad
                        item['cantidad'] = min(nueva_cant, disponible)
                        item['subtotal'] = str(float(item['precio']) * item['cantidad'])
                        encontrado = True
                        break
                if not encontrado:
                    items.append({
                        'producto_id': int(producto_id),
                        'nombre':      producto.name,
                        'precio':      str(producto.unit_price),
                        'cantidad':    cantidad,
                        'subtotal':    str(float(producto.unit_price) * cantidad),
                    })
                request.session['wizard_items'] = items
                request.session.modified = True
                messages.success(request, f'"{producto.name}" agregado.')

        elif action == 'quitar':
            producto_id = int(request.POST.get('producto_id'))
            items = [
                i for i in request.session.get('wizard_items', [])
                if i['producto_id'] != producto_id
            ]
            request.session['wizard_items'] = items
            request.session.modified = True

        elif action == 'continuar':
            if not request.session.get('wizard_items'):
                messages.error(request, 'Agrega al menos un producto.')
            else:
                return redirect('nueva_orden_paso3')

        return redirect('nueva_orden_paso2')

    items_sesion  = request.session.get('wizard_items', [])
    total_carrito = sum(float(i['subtotal']) for i in items_sesion)

    return render(request, 'core/nueva_orden_paso2.html', {
        'productos':     productos,
        'categorias':    categorias,
        'buscar':        buscar,
        'cat_activa':    categoria,
        'items_carrito': items_sesion,
        'total_carrito': total_carrito,
        'titulo_pagina': 'Nueva Orden — Paso 2',
        'nav_activo':    'ordenes',
        'paso_actual':   2,
    })


@admin_required
def nueva_orden_paso3(request):
    from decimal import Decimal
    buyer_id   = request.session.get('wizard_buyer_id')
    order_type = request.session.get('wizard_order_type', 'b2c')
    items      = request.session.get('wizard_items', [])

    if not buyer_id or not items:
        messages.error(request, 'Sesión expirada. Inicia la orden de nuevo.')
        return redirect('nueva_orden_paso1')

    buyer       = get_object_or_404(User, pk=buyer_id)
    direcciones = Address.objects.filter(user=buyer)
    subtotal    = sum(float(i['subtotal']) for i in items)

    if request.method == 'POST':
        shipping_cost = Decimal(request.POST.get('shipping_cost', 0) or 0)
        address_id    = request.POST.get('address_id') or None
        notas         = request.POST.get('notas', '')
        metodo_pago   = request.POST.get('metodo_pago', 'mock')

        ship_address = None
        if address_id:
            try:
                ship_address = Address.objects.get(pk=address_id, user=buyer)
            except Address.DoesNotExist:
                pass

        orden = Order.objects.create(
            buyer=buyer, ship_address=ship_address,
            order_type=order_type, shipping_cost=shipping_cost,
            notes=notas, status='pending',
        )

        for item_data in items:
            try:
                producto = Product.objects.select_related('inventory').get(
                    pk=item_data['producto_id']
                )
                cantidad = item_data['cantidad']
                if producto.available_qty >= cantidad:
                    OrderItem.objects.create(
                        order=orden, product=producto,
                        qty=cantidad,
                        unit_price_snapshot=producto.unit_price,
                    )
                    if hasattr(producto, 'inventory'):
                        producto.inventory.reserve(cantidad)
                else:
                    messages.warning(
                        request,
                        f'Stock insuficiente para "{producto.name}", item omitido.'
                    )
            except Product.DoesNotExist:
                pass

        orden.recalculate_totals()
        orden.shipping_cost = shipping_cost
        orden.total = orden.subtotal + shipping_cost
        orden.save(update_fields=['shipping_cost', 'total'])

        Payment.objects.create(
            order=orden, provider=metodo_pago,
            status='approved' if metodo_pago == 'mock' else 'pending',
            amount=orden.total, currency='USD',
            paid_at=timezone.now() if metodo_pago == 'mock' else None,
            txn_ref=f'TF-{orden.order_number}',
        )
        if metodo_pago == 'mock':
            orden.status = 'paid'
            orden.save(update_fields=['status'])

        for key in ('wizard_buyer_id', 'wizard_order_type', 'wizard_items'):
            request.session.pop(key, None)

        messages.success(request, f'¡Orden {orden.order_number} creada exitosamente!')
        return redirect('detalle_orden', pk=orden.pk)

    return render(request, 'core/nueva_orden_paso3.html', {
        'buyer':         buyer,
        'order_type':    order_type,
        'items':         items,
        'subtotal':      subtotal,
        'direcciones':   direcciones,
        'metodos_pago':  Payment.PROVIDER_CHOICES,
        'titulo_pagina': 'Nueva Orden — Paso 3',
        'nav_activo':    'ordenes',
        'paso_actual':   3,
    })


# =============================================================================
# PRODUCTOS (admin)
# =============================================================================

@admin_required
def lista_productos(request):
    productos  = Product.objects.select_related(
        'company', 'category'
    ).prefetch_related('inventory').order_by('name')
    buscar    = request.GET.get('buscar', '')
    categoria = request.GET.get('categoria', '')

    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar) |
            Q(description__icontains=buscar) |
            Q(sku__icontains=buscar)
        )
    if categoria:
        productos = productos.filter(category__id=categoria)

    paginator  = Paginator(productos, 12)
    page_obj   = paginator.get_page(request.GET.get('page', 1))
    categorias = Category.objects.all()

    return render(request, 'core/productos.html', {
        'productos':     page_obj,
        'categorias':    categorias,
        'buscar':        buscar,
        'cat_activa':    categoria,
        'titulo_pagina': 'Catálogo de Productos',
        'nav_activo':    'productos',
    })


# =============================================================================
# EMPRESAS (admin)
# =============================================================================

@admin_required
def lista_empresas(request):
    empresas  = Company.objects.annotate(
        total_productos=Count('products')
    ).order_by('name')
    paginator = Paginator(empresas, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'core/empresas.html', {
        'empresas':      page_obj,
        'titulo_pagina': 'Empresas',
        'nav_activo':    'empresas',
    })


# =============================================================================
# PORTALES DE ROL (placeholder — se expanden el Día 3 y 4)
# =============================================================================

@buyer_required
def portal_buyer(request):
    """Portal del comprador — se completa el Lunes 14."""
    return render(request, 'core/portal_buyer_temp.html', {
        'titulo_pagina': 'Tienda TradeFlow',
    })


@seller_required
def portal_seller(request):
    """Portal del vendedor — se completa más adelante."""
    return render(request, 'core/portal_seller_temp.html', {
        'titulo_pagina': 'Mi Tienda',
    })


# =============================================================================
# API JSON
# =============================================================================

@login_required
def api_productos(request):
    productos = Product.objects.filter(is_active=True).select_related(
        'category', 'company', 'inventory'
    )
    buscar = request.GET.get('q', '')
    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar) | Q(sku__icontains=buscar)
        )
    data = [
        {
            'id':        p.id,
            'nombre':    p.name,
            'precio':    str(p.unit_price),
            'currency':  p.currency,
            'stock':     p.available_qty,
            'categoria': p.category.name if p.category else 'Sin categoría',
            'empresa':   p.company.name,
        }
        for p in productos[:20]
    ]
    return JsonResponse({'productos': data})

"""
=============================================================================
TRADEFLOW COLÓN — Vistas del portal comprador (buyer)
=============================================================================
Este bloque de vistas maneja el flujo completo de compra para usuarios
con rol 'buyer'. Debe agregarse al archivo core/views.py existente.

FLUJO COMPLETO:
    /tienda/        → tienda()       Catálogo con filtros
    /carrito/       → ver_carrito()  Ver y modificar el carrito
    /carrito/agregar/<id>/  → agregar_al_carrito()
    /carrito/quitar/<id>/   → quitar_del_carrito()
    /checkout/      → checkout()     Confirmación y pago
    /mis-ordenes/   → mis_ordenes()  Historial del comprador
    /mis-ordenes/<pk>/  → detalle_mi_orden()

CARRITO EN SESIÓN:
    El carrito se almacena en request.session['carrito'] como un
    diccionario con la siguiente estructura:
    {
        '<product_id>': {
            'nombre':   str,
            'precio':   str,   # Decimal como string para serialización
            'cantidad': int,
            'subtotal': str,
            'imagen':   str,   # URL relativa de la imagen
        }
    }

DEPENDENCIAS:
    - core/decorators.py → @buyer_required
    - core/models.py     → Product, Inventory, Order, OrderItem, Payment
=============================================================================
"""

from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

# Estos imports ya están en views.py — no los dupliques
# from .decorators import buyer_required
# from .models import Product, Category, Order, OrderItem, Payment, Address


# ---------------------------------------------------------------------------
# HELPERS DE CARRITO
# ---------------------------------------------------------------------------

def _get_carrito(request):
    """
    Recupera el carrito desde la sesión.
    Devuelve un diccionario vacío si no existe.
    El ID del producto se usa como clave (string por limitación de JSON).
    """
    return request.session.get('carrito', {})


def _save_carrito(request, carrito):
    """
    Guarda el carrito en la sesión y marca la sesión como modificada.
    Necesario para que Django persista los cambios en sesiones de tipo dict.
    """
    request.session['carrito'] = carrito
    request.session.modified = True


def _calcular_total(carrito):
    """
    Suma los subtotales de todos los items del carrito.
    Retorna un Decimal con 2 decimales.
    """
    total = Decimal('0.00')
    for item in carrito.values():
        total += Decimal(item['subtotal'])
    return total


def _contar_items(carrito):
    """
    Retorna la cantidad total de unidades en el carrito.
    Usado para mostrar el badge del carrito en el navbar.
    """
    return sum(item['cantidad'] for item in carrito.values())


# ---------------------------------------------------------------------------
# TIENDA — Catálogo principal del comprador
# ---------------------------------------------------------------------------

@buyer_required
def tienda(request):
    """
    Muestra el catálogo de productos disponibles para el comprador.

    Funcionalidades:
        - Búsqueda por nombre, descripción o SKU
        - Filtro por categoría
        - Paginación de 9 productos por página
        - Muestra solo productos activos con stock disponible

    Contexto enviado al template:
        productos    → QuerySet paginado de Product
        categorias   → QuerySet de Category para el filtro
        buscar       → Término de búsqueda actual
        cat_activa   → ID de categoría seleccionada
        carrito_count→ Cantidad de items en el carrito (para el badge)
    """
    # Obtener productos activos con sus relaciones en una sola consulta
    productos = (
        Product.objects
        .filter(is_active=True)
        .select_related('company', 'category', 'inventory')
        .order_by('name')
    )

    # Filtros de búsqueda
    buscar    = request.GET.get('buscar', '').strip()
    categoria = request.GET.get('categoria', '').strip()

    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar)        |
            Q(description__icontains=buscar) |
            Q(sku__icontains=buscar)
        )

    if categoria:
        productos = productos.filter(category__id=categoria)

    # Paginación
    paginator = Paginator(productos, 9)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    categorias = Category.objects.all().order_by('name')
    carrito    = _get_carrito(request)

    context = {
        'productos':     page_obj,
        'categorias':    categorias,
        'buscar':        buscar,
        'cat_activa':    categoria,
        'carrito_count': _contar_items(carrito),
        'titulo_pagina': 'Tienda TradeFlow',
        'nav_activo':    'tienda',
    }
    return render(request, 'core/tienda.html', context)


# ---------------------------------------------------------------------------
# CARRITO — Gestión del carrito de compras
# ---------------------------------------------------------------------------

@buyer_required
def agregar_al_carrito(request, producto_id):
    """
    Agrega un producto al carrito o incrementa su cantidad si ya existe.

    Método: POST únicamente (botón en la tarjeta del producto)
    Parámetro POST: cantidad (int, default=1)

    Validaciones:
        - Producto debe existir y estar activo
        - Cantidad debe ser >= 1
        - Cantidad total no puede superar el stock disponible

    Redirige de vuelta a la tienda después de agregar.
    """
    if request.method != 'POST':
        return redirect('tienda')

    cantidad = int(request.POST.get('cantidad', 1))

    # Obtener producto con su inventario en una sola consulta
    producto = get_object_or_404(
        Product.objects.select_related('inventory'),
        pk=producto_id,
        is_active=True
    )

    disponible = producto.available_qty

    # Validar cantidad
    if cantidad < 1:
        messages.error(request, 'La cantidad debe ser al menos 1.')
        return redirect('tienda')

    if disponible == 0:
        messages.error(request, f'"{producto.name}" no tiene stock disponible.')
        return redirect('tienda')

    # Actualizar carrito en sesión
    carrito     = _get_carrito(request)
    producto_key = str(producto_id)

    if producto_key in carrito:
        # El producto ya está en el carrito — sumar cantidades
        nueva_cantidad = carrito[producto_key]['cantidad'] + cantidad
        if nueva_cantidad > disponible:
            messages.warning(
                request,
                f'Solo hay {disponible} unidades disponibles de "{producto.name}".'
            )
            nueva_cantidad = disponible
        carrito[producto_key]['cantidad'] = nueva_cantidad
        carrito[producto_key]['subtotal'] = str(
            Decimal(carrito[producto_key]['precio']) * nueva_cantidad
        )
    else:
        # Producto nuevo en el carrito
        if cantidad > disponible:
            cantidad = disponible
            messages.warning(
                request,
                f'Solo hay {disponible} unidades disponibles. Se ajustó la cantidad.'
            )
        carrito[producto_key] = {
            'nombre':   producto.name,
            'precio':   str(producto.unit_price),
            'cantidad': cantidad,
            'subtotal': str(producto.unit_price * cantidad),
            'imagen':   producto.image.url if producto.image else '',
        }

    _save_carrito(request, carrito)
    messages.success(request, f'"{producto.name}" agregado al carrito.')
    return redirect('tienda')


@buyer_required
def quitar_del_carrito(request, producto_id):
    """
    Elimina un producto del carrito de compras.

    Método: POST (formulario con botón eliminar en carrito.html)
    Redirige de vuelta al carrito después de quitar.
    """
    if request.method != 'POST':
        return redirect('ver_carrito')

    carrito     = _get_carrito(request)
    producto_key = str(producto_id)

    if producto_key in carrito:
        nombre = carrito[producto_key]['nombre']
        del carrito[producto_key]
        _save_carrito(request, carrito)
        messages.info(request, f'"{nombre}" eliminado del carrito.')

    return redirect('ver_carrito')


@buyer_required
def ver_carrito(request):
    """
    Muestra el contenido actual del carrito de compras.

    Si el carrito está vacío, muestra un mensaje y un botón
    para volver a la tienda.

    Contexto:
        carrito      → dict con los items del carrito
        total        → Decimal con el total a pagar
        carrito_count→ Cantidad de unidades para el badge
    """
    carrito = _get_carrito(request)
    total   = _calcular_total(carrito)

    context = {
        'carrito':       carrito,
        'total':         total,
        'carrito_count': _contar_items(carrito),
        'titulo_pagina': 'Mi Carrito',
        'nav_activo':    'tienda',
    }
    return render(request, 'core/carrito.html', context)


# ---------------------------------------------------------------------------
# CHECKOUT — Confirmación de compra y creación de orden
# ---------------------------------------------------------------------------

@buyer_required
def checkout(request):
    """
    Proceso de confirmación de compra y generación de la orden.

    GET:  Muestra el formulario de checkout con resumen del carrito
          y opciones de dirección de envío.

    POST: Crea la orden, sus items, reserva el inventario y registra el pago.
          Limpia el carrito de la sesión al finalizar.
          Redirige a la confirmación de la orden creada.

    Campos del formulario POST:
        notas         → Instrucciones especiales (opcional)
        shipping_cost → Costo de envío en USD (default 0)

    Validaciones:
        - El carrito no puede estar vacío
        - Se verifica el stock disponible producto a producto al crear
        - Si un producto quedó sin stock, se omite con un warning
    """
    carrito = _get_carrito(request)

    # Redirigir si el carrito está vacío
    if not carrito:
        messages.warning(request, 'Tu carrito está vacío.')
        return redirect('tienda')

    subtotal = _calcular_total(carrito)

    if request.method == 'POST':
        notas         = request.POST.get('notas', '').strip()
        shipping_cost = Decimal(request.POST.get('shipping_cost', '0') or '0')

        # Crear la cabecera de la orden
        orden = Order.objects.create(
            buyer         = request.user,
            order_type    = 'b2c',
            shipping_cost = shipping_cost,
            notes         = notas,
            status        = 'pending',
        )

        # Crear los items y reservar inventario
        items_creados = 0
        for prod_id, item_data in carrito.items():
            try:
                producto = (
                    Product.objects
                    .select_related('inventory')
                    .get(pk=int(prod_id), is_active=True)
                )
                cantidad = item_data['cantidad']

                if producto.available_qty >= cantidad:
                    OrderItem.objects.create(
                        order                = orden,
                        product              = producto,
                        qty                  = cantidad,
                        unit_price_snapshot  = producto.unit_price,
                    )
                    # Reservar el stock para que otros no lo compren
                    if hasattr(producto, 'inventory'):
                        producto.inventory.reserve(cantidad)
                    items_creados += 1
                else:
                    messages.warning(
                        request,
                        f'Stock insuficiente para "{producto.name}" — item omitido.'
                    )

            except Product.DoesNotExist:
                # El producto fue desactivado entre que se agregó y el checkout
                messages.warning(
                    request,
                    f'Un producto ya no está disponible y fue omitido.'
                )

        if items_creados == 0:
            # Ningún item pudo procesarse — cancelar la orden
            orden.delete()
            messages.error(
                request,
                'No se pudo completar la orden. Verifica el stock de los productos.'
            )
            return redirect('ver_carrito')

        # Calcular totales finales
        orden.recalculate_totals()
        orden.shipping_cost = shipping_cost
        orden.total = orden.subtotal + shipping_cost
        orden.save(update_fields=['shipping_cost', 'total'])

        # Registrar el pago (mock para demo)
        Payment.objects.create(
            order    = orden,
            provider = 'mock',
            status   = 'approved',
            amount   = orden.total,
            currency = 'USD',
            paid_at=timezone.now(),
            txn_ref  = f'TF-MOCK-{orden.order_number}',
        )
        orden.status = 'paid'
        orden.save(update_fields=['status'])

        # Limpiar el carrito de la sesión
        _save_carrito(request, {})
        messages.success(
            request,
            f'Orden {orden.order_number} creada exitosamente. ¡Gracias por tu compra!'
        )
        return redirect('detalle_mi_orden', pk=orden.pk)

    context = {
        'carrito':       carrito,
        'subtotal':      subtotal,
        'carrito_count': _contar_items(carrito),
        'titulo_pagina': 'Confirmar Orden',
        'nav_activo':    'tienda',
    }
    return render(request, 'core/checkout.html', context)


# ---------------------------------------------------------------------------
# MIS ÓRDENES — Historial del comprador
# ---------------------------------------------------------------------------

@buyer_required
def mis_ordenes(request):
    """
    Muestra el historial de órdenes del comprador autenticado.

    Solo muestra las órdenes que pertenecen al usuario actual.
    Un buyer nunca puede ver las órdenes de otro usuario.

    Filtros disponibles (GET params):
        estado → Filtra por status de la orden

    Paginación: 8 órdenes por página.
    """
    ordenes = (
        Order.objects
        .filter(buyer=request.user)
        .select_related('buyer')
        .prefetch_related('items__product')
        .order_by('-created_at')
    )

    # Filtro opcional por estado
    estado = request.GET.get('estado', '').strip()
    if estado:
        ordenes = ordenes.filter(status=estado)

    paginator = Paginator(ordenes, 8)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        'ordenes':        page_obj,
        'estado_actual':  estado,
        'status_choices': Order.STATUS_CHOICES,
        'carrito_count':  _contar_items(_get_carrito(request)),
        'titulo_pagina':  'Mis Órdenes',
        'nav_activo':     'mis_ordenes',
    }
    return render(request, 'core/mis_ordenes.html', context)


@buyer_required
def detalle_mi_orden(request, pk):
    """
    Muestra el detalle de una orden específica del comprador.

    Seguridad: filtra por buyer=request.user para asegurarse
    de que el comprador solo pueda ver sus propias órdenes.
    Un usuario no puede acceder a la orden de otro con su ID.
    """
    orden = get_object_or_404(
        Order.objects
        .select_related('buyer', 'ship_address')
        .prefetch_related('items__product__company'),
        pk=pk,
        buyer=request.user   # Clave de seguridad
    )

    context = {
        'orden':         orden,
        'pago':          getattr(orden, 'payment', None),
        'carrito_count': _contar_items(_get_carrito(request)),
        'titulo_pagina': f'Orden {orden.order_number}',
        'nav_activo':    'mis_ordenes',
    }
    return render(request, 'core/detalle_mi_orden.html', context)