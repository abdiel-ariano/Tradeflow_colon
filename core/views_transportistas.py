"""Carrier applications, admin review, and order logistics assignment.

Public apply flow, admin approve/reject with account provisioning,
buyer pickup selection, and seller order accept/reject within the
CFZ confirmation deadline.
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .decorators import admin_required, buyer_required, seller_required
from .forms import AplicacionTransportistaForm
from .models import (
    AsignacionTransporte,
    Order,
    Transportista,
    UserProfile,
)
from .utils.email_sender import (
    enviar_aplicacion_transportista_recibida,
    enviar_resultado_aplicacion_transportista,
)
from .utils.order_workflow import (
    accept_seller_order,
    expire_pending_orders,
    reject_seller_order,
    release_order_inventory,
    seller_confirm_deadline,
)
from .utils.email_sender import enviar_cambio_estado

log = logging.getLogger(__name__)

_USERNAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9._]{2,29}$')


def aplicar_transportista(request):
    """Accept a public carrier application and email confirmation.

    Blocks duplicate pending rows for the same contact email. Saves
    the application even when outbound mail fails so logistics intake
    is not blocked by SMTP misconfiguration.
    """
    form = AplicacionTransportistaForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        if Transportista.objects.filter(email_contacto=email, estado='pendiente').exists():
            messages.warning(request, _('A pending application already exists with this email.'))
            return redirect('aplicar_transportista')

        t = Transportista.objects.create(
            empresa_nombre=form.cleaned_data['empresa_nombre'],
            licencia=form.cleaned_data['licencia'],
            telefono=form.cleaned_data['telefono'],
            email_contacto=email,
            vehiculo_tipo=form.cleaned_data['vehiculo_tipo'],
            vehiculo_placa=form.cleaned_data['vehiculo_placa'],
            cobertura_descripcion=form.cleaned_data['cobertura_descripcion'],
            tarifa_base=form.cleaned_data['tarifa_base'],
            foto_licencia=form.cleaned_data.get('foto_licencia'),
            estado='pendiente',
            activo=False,
        )
        try:
            enviar_aplicacion_transportista_recibida(t)
        except Exception:
            log.exception('Email aplicación transportista')
            messages.warning(
                request,
                _('Application saved. Configure Gmail in .env to receive email confirmation.'),
            )
        else:
            messages.success(
                request,
                _('Application submitted. We will contact you by email once it is reviewed.'),
            )
        return redirect('aplicar_transportista')

    return render(request, 'core/aplicar_transportista.html', {
        'form': form,
        'titulo_pagina': _('Apply as carrier'),
    })


@admin_required
def admin_transportistas(request):
    """List carrier applications filtered by review status."""
    estado = request.GET.get('estado', 'pendiente').strip()
    qs = Transportista.objects.select_related('user').order_by('-fecha_aplicacion')
    if estado:
        qs = qs.filter(estado=estado)
    return render(request, 'core/admin_transportistas.html', {
        'transportistas': qs,
        'estado_filtro': estado,
        'titulo_pagina': _('Carriers'),
        'nav_activo': 'carriers',
    })


@admin_required
@require_POST
def admin_aprobar_transportista(request, pk, decision):
    """Approve or reject a pending carrier; provision login on approve.

    Approved carriers get a User + ``transportista`` profile so they
    can participate in buyer pickup assignment for CFZ orders.
    Must be POST (CSRF) — GET is rejected.
    """
    t = get_object_or_404(Transportista, pk=pk)
    if t.estado != 'pendiente':
        messages.info(request, _('This application has already been reviewed.'))
        return redirect('admin_transportistas')

    aprobado = decision == 'aprobar'
    if aprobado:
        base_user = t.email_contacto.split('@')[0].lower()[:20]
        username = base_user
        n = 0
        while User.objects.filter(username=username).exists():
            n += 1
            username = f'{base_user}{n}'
        user = User.objects.create_user(
            username=username,
            email=t.email_contacto,
            password=get_random_string(14),
            first_name=t.empresa_nombre[:30],
        )
        UserProfile.objects.create(user=user, role='transportista', phone=t.telefono)
        t.user = user
        t.estado = 'aprobado'
        t.activo = True
    else:
        t.estado = 'rechazado'
        t.activo = False

    t.save()
    try:
        enviar_resultado_aplicacion_transportista(t, aprobado)
    except Exception:
        log.exception('Email resultado transportista')

    messages.success(request, _('Decision recorded.'))
    return redirect('admin_transportistas')


@buyer_required
def seleccionar_transportista(request, order_pk):
    """Let the buyer assign an approved carrier and pickup coordinates.

    Writes ``AsignacionTransporte`` and folds the carrier base tariff
    into order shipping/total before checkout continuation.
    """
    orden = get_object_or_404(Order, pk=order_pk, buyer=request.user)
    transportistas = Transportista.objects.filter(estado='aprobado', activo=True).order_by(
        'empresa_nombre',
    )

    if request.method == 'POST':
        tid = request.POST.get('transportista_id', '').strip()
        lat = request.POST.get('pickup_lat', '').strip()
        lng = request.POST.get('pickup_lng', '').strip()
        if not tid or not lat or not lng:
            messages.error(request, _('Select a carrier and mark your location.'))
            return redirect('seleccionar_transportista', order_pk=order_pk)
        try:
            t_obj = get_object_or_404(Transportista, pk=int(tid), activo=True, estado='aprobado')
            lat_d = Decimal(lat)
            lng_d = Decimal(lng)
        except (ValueError, InvalidOperation):
            messages.error(request, _('Invalid data.'))
            return redirect('seleccionar_transportista', order_pk=order_pk)

        desc = request.POST.get('pickup_descripcion', '').strip() or f'{lat},{lng}'
        costo = t_obj.tarifa_base
        AsignacionTransporte.objects.update_or_create(
            order=orden,
            defaults={
                'transportista': t_obj,
                'ubicacion_pickup_lat': lat_d,
                'ubicacion_pickup_lng': lng_d,
                'ubicacion_pickup_descripcion': desc[:300],
                'notas_buyer': request.POST.get('notas_buyer', '').strip(),
                'costo_transporte': costo,
            },
        )
        orden.shipping_cost = costo
        orden.recalculate_totals()
        orden.total = orden.subtotal + costo
        orden.save(update_fields=['shipping_cost', 'total', 'updated_at'])
        messages.success(request, _('Carrier assigned successfully.'))
        return redirect('detalle_mi_orden', pk=orden.pk)

    return render(request, 'core/seleccionar_transportista.html', {
        'order': orden,
        'transportistas': transportistas,
        'titulo_pagina': _('Select carrier'),
        'nav_activo': 'tienda',
    })


@seller_required
def confirmar_orden_empresa(request, order_pk, decision):
    """Accept or reject an order within the seller confirmation window.

    Sprint URL alias: enforces company line ownership, expires stale
    pending orders, and gates accept on SaaS monthly volume limits.
    """
    from .views import _get_seller_company

    company = _get_seller_company(request.user)
    orden = get_object_or_404(Order, pk=order_pk)
    if not company:
        messages.error(request, _('No linked company.'))
        return redirect('seller_mis_ventas')

    lineas = orden.items.filter(product__company=company).exists()
    if not lineas:
        raise Http404

    expire_pending_orders()
    if orden.seller_confirm_by and timezone.now() > orden.seller_confirm_by:
        reject_seller_order(orden)
        messages.error(request, _('Confirmation deadline expired. The order was cancelled.'))
        return redirect('seller_mis_ventas')

    if orden.status != 'awaiting_seller' or orden.seller_confirmation_status != 'pending':
        messages.warning(request, _('This order can no longer be confirmed.'))
        return redirect('seller_detalle_venta', pk=order_pk)

    prev = orden.status
    if decision == 'aceptar':
        from core.utils.saas_billing import VolumeLimitExceeded

        try:
            accept_seller_order(orden)
        except VolumeLimitExceeded as exc:
            messages.error(
                request,
                _(
                    'Monthly plan limit reached (USD %(limit)s). '
                    'Upgrade your plan to confirm this sale.'
                ) % {'limit': exc.limit},
            )
            return redirect('seller_plan_consumo')
        messages.success(
            request,
            _('Order accepted. Payment and logistics remain pending.'),
        )
    elif decision == 'rechazar':
        reject_seller_order(orden)
        messages.warning(request, _('Order rejected.'))
    else:
        raise Http404

    try:
        enviar_cambio_estado(orden, prev)
    except Exception:
        log.exception('Email cambio estado')
    return redirect('seller_detalle_venta', pk=order_pk)
