"""
TradeFlow Colón — wizard de onboarding comprador (3 pasos post-registro).

Flujo inspirado en marketplaces B2B:
  1. Intención de compra (negocio vs personal)
  2. Selección de categorías de interés
  3. Deep Search — sugerencias iniciales de búsqueda / catálogo

Solo aplica a compradores nuevos (``onboarding_completed_at`` null).
Las cuentas existentes se marcan completas en la migración 0029.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models import Category, UserProfile
from core.utils.access_gating import buyer_onboarding_pending

# Claves de sesión — progreso del wizard entre pasos
SESSION_ONBOARDING_INTENT = 'buyer_onboarding_intent'
SESSION_ONBOARDING_CATEGORIES = 'buyer_onboarding_category_ids'


def _get_buyer_profile(user) -> UserProfile | None:
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None
    if profile.role != 'buyer':
        return None
    return profile


def _wizard_base_context(step: int, total: int = 3) -> dict:
    return {
        'onboarding_step': step,
        'onboarding_total': total,
        'onboarding_progress_pct': int((step / total) * 100),
    }


def _category_icon_name(category_name: str) -> str:
    """Icono Material Symbols según palabras clave del nombre de categoría."""
    name = (category_name or '').lower()
    rules = (
        (('electr', 'tech', 'office', 'computer'), 'devices'),
        (('textil', 'ropa', 'moda', 'uniform'), 'checkroom'),
        (('deport', 'sport', 'fitness'), 'sports_soccer'),
        (('hogar', 'home', 'jard', 'appliance'), 'home'),
        (('beauty', 'belleza', 'cosm'), 'spa'),
        (('food', 'aliment', 'bebida'), 'restaurant'),
        (('auto', 'vehic', 'motor'), 'directions_car'),
        (('salud', 'medico', 'health'), 'medical_services'),
    )
    for keywords, icon in rules:
        if any(k in name for k in keywords):
            return icon
    return 'category'


def _complete_onboarding(profile: UserProfile) -> None:
    """Marca el wizard como terminado (completado u omitido)."""
    profile.onboarding_completed_at = timezone.now()
    profile.save(update_fields=['onboarding_completed_at'])


@login_required
@require_GET
def buyer_onboarding_step1(request: HttpRequest) -> HttpResponse:
    """Paso 1/3 — ¿Compra para negocio o personal?"""
    profile = _get_buyer_profile(request.user)
    if not profile:
        return redirect('tienda')
    if not buyer_onboarding_pending(request.user):
        return redirect('tienda')

    ctx = {
        **_wizard_base_context(1),
        'purchase_intent': profile.purchase_intent or request.session.get(SESSION_ONBOARDING_INTENT, ''),
    }
    return render(request, 'core/onboarding/buyer_step1.html', ctx)


@login_required
@require_POST
def buyer_onboarding_step1_post(request: HttpRequest) -> HttpResponse:
    profile = _get_buyer_profile(request.user)
    if not profile or not buyer_onboarding_pending(request.user):
        return redirect('tienda')

    intent = (request.POST.get('purchase_intent') or '').strip()
    if intent not in ('business', 'personal'):
        messages.error(request, 'Elige una opción para continuar.')
        return redirect('buyer_onboarding_step1')

    profile.purchase_intent = intent
    profile.save(update_fields=['purchase_intent'])
    request.session[SESSION_ONBOARDING_INTENT] = intent
    request.session.modified = True
    return redirect('buyer_onboarding_step2')


@login_required
@require_GET
def buyer_onboarding_step2(request: HttpRequest) -> HttpResponse:
    """Paso 2/3 — grid de categorías (multi-select)."""
    profile = _get_buyer_profile(request.user)
    if not profile:
        return redirect('tienda')
    if not buyer_onboarding_pending(request.user):
        return redirect('tienda')
    if not profile.purchase_intent:
        return redirect('buyer_onboarding_step1')

    from core import merchandising as merch

    categories = merch.buyer_onboarding_category_choices(limit=12)
    selected_ids = set(profile.preferred_categories.values_list('pk', flat=True))
    if not selected_ids:
        session_ids = request.session.get(SESSION_ONBOARDING_CATEGORIES) or []
        selected_ids = {int(x) for x in session_ids if str(x).isdigit()}

    for row in categories:
        row['icon'] = _category_icon_name(row['category'].name)

    ctx = {
        **_wizard_base_context(2),
        'category_rows': categories,
        'selected_category_ids': selected_ids,
    }
    return render(request, 'core/onboarding/buyer_step2.html', ctx)


@login_required
@require_POST
def buyer_onboarding_step2_post(request: HttpRequest) -> HttpResponse:
    profile = _get_buyer_profile(request.user)
    if not profile or not buyer_onboarding_pending(request.user):
        return redirect('tienda')

    raw_ids = request.POST.getlist('categories')
    cat_ids = []
    for raw in raw_ids:
        if str(raw).isdigit():
            cat_ids.append(int(raw))

    if not cat_ids:
        messages.error(request, 'Selecciona al menos una categoría.')
        return redirect('buyer_onboarding_step2')

    valid_ids = list(
        Category.objects.filter(pk__in=cat_ids).values_list('pk', flat=True)
    )
    if not valid_ids:
        messages.error(request, 'Las categorías seleccionadas no son válidas.')
        return redirect('buyer_onboarding_step2')

    profile.preferred_categories.set(valid_ids[:6])
    request.session[SESSION_ONBOARDING_CATEGORIES] = valid_ids[:6]
    request.session.modified = True
    return redirect('buyer_onboarding_step3')


@login_required
@require_GET
def buyer_onboarding_step3(request: HttpRequest) -> HttpResponse:
    """Paso 3/3 — Deep Search: sugerencias según categorías elegidas."""
    profile = _get_buyer_profile(request.user)
    if not profile:
        return redirect('tienda')
    if not buyer_onboarding_pending(request.user):
        return redirect('tienda')
    if not profile.preferred_categories.exists():
        return redirect('buyer_onboarding_step2')

    from core import merchandising as merch

    seed = int(request.GET.get('seed', '0') or 0)
    suggestions = merch.buyer_deep_search_suggestions(profile, limit=4, seed=seed)

    ctx = {
        **_wizard_base_context(3),
        'suggestions': suggestions,
        'shuffle_seed': seed + 1,
        'purchase_intent': profile.get_purchase_intent_display(),
    }
    return render(request, 'core/onboarding/buyer_step3.html', ctx)


@login_required
@require_POST
def buyer_onboarding_finish(request: HttpRequest) -> HttpResponse:
    """Finaliza wizard — redirige al catálogo personalizado."""
    profile = _get_buyer_profile(request.user)
    if not profile:
        return redirect('tienda')

    suggestion_pk = (request.POST.get('suggestion_category') or '').strip()
    buscar = (request.POST.get('buscar') or '').strip()

    _complete_onboarding(profile)

    if buscar:
        return redirect(f"{reverse('tienda')}?buscar={buscar}")
    if suggestion_pk.isdigit():
        return redirect(f"{reverse('tienda')}?categoria={suggestion_pk}")
    first_cat = profile.preferred_categories.first()
    if first_cat:
        return redirect(f"{reverse('tienda')}?categoria={first_cat.pk}")
    return redirect('tienda')


@login_required
@require_POST
def buyer_onboarding_skip(request: HttpRequest) -> HttpResponse:
    """Omitir wizard — Alibaba-style skip link."""
    profile = _get_buyer_profile(request.user)
    if not profile:
        return redirect('tienda')
    if buyer_onboarding_pending(request.user):
        _complete_onboarding(profile)
        messages.info(request, 'Puedes personalizar tu experiencia más tarde desde tu perfil.')
    return redirect('tienda')
