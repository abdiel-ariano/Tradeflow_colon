"""Buyer preference wizard after signup and email OTP.

Three optional steps personalize the guest catalog: purchase intent,
preferred CFZ categories, and deep-search suggestions. Only buyers with
``onboarding_completed_at`` null enter the flow; skip is allowed.
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

# Session keys — wizard progress between steps
SESSION_ONBOARDING_INTENT = 'buyer_onboarding_intent'
SESSION_ONBOARDING_CATEGORIES = 'buyer_onboarding_category_ids'


def _get_buyer_profile(user) -> UserProfile | None:
    """Return the buyer profile, or None for non-buyers."""
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None
    if profile.role != 'buyer':
        return None
    return profile


def _wizard_base_context(step: int, total: int = 3) -> dict:
    """Progress metadata shared by all buyer onboarding templates."""
    return {
        'onboarding_step': step,
        'onboarding_total': total,
        'onboarding_progress_pct': int((step / total) * 100),
    }


def _category_icon_name(category_name: str) -> str:
    """Map category labels to Material Symbols icon names."""
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
    """Mark buyer onboarding finished (completed or skipped)."""
    profile.onboarding_completed_at = timezone.now()
    profile.save(update_fields=['onboarding_completed_at'])


@login_required
@require_GET
def buyer_onboarding_step1(request: HttpRequest) -> HttpResponse:
    """Step 1/3 — business vs personal purchase intent."""
    profile = _get_buyer_profile(request.user)
    if not profile:
        return redirect('catalogo_publico')
    if not buyer_onboarding_pending(request.user):
        return redirect('catalogo_publico')

    ctx = {
        **_wizard_base_context(1),
        'purchase_intent': profile.purchase_intent or request.session.get(SESSION_ONBOARDING_INTENT, ''),
    }
    return render(request, 'core/onboarding/buyer_step1.html', ctx)


@login_required
@require_POST
def buyer_onboarding_step1_post(request: HttpRequest) -> HttpResponse:
    """Persist purchase intent and advance to category selection."""
    profile = _get_buyer_profile(request.user)
    if not profile or not buyer_onboarding_pending(request.user):
        return redirect('catalogo_publico')

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
    """Step 2/3 — multi-select CFZ category preferences."""
    profile = _get_buyer_profile(request.user)
    if not profile:
        return redirect('catalogo_publico')
    if not buyer_onboarding_pending(request.user):
        return redirect('catalogo_publico')
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
    """Save preferred categories and advance to deep-search suggestions."""
    profile = _get_buyer_profile(request.user)
    if not profile or not buyer_onboarding_pending(request.user):
        return redirect('catalogo_publico')

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
    """Step 3/3 — deep-search catalog suggestions from preferences."""
    profile = _get_buyer_profile(request.user)
    if not profile:
        return redirect('catalogo_publico')
    if not buyer_onboarding_pending(request.user):
        return redirect('catalogo_publico')
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
    """Complete the wizard and open the personalized public catalog."""
    profile = _get_buyer_profile(request.user)
    if not profile:
        return redirect('catalogo_publico')

    suggestion_pk = (request.POST.get('suggestion_category') or '').strip()
    buscar = (request.POST.get('buscar') or '').strip()

    _complete_onboarding(profile)

    if buscar:
        return redirect(f"{reverse('catalogo_publico')}?buscar={buscar}")
    if suggestion_pk.isdigit():
        return redirect(f"{reverse('catalogo_publico')}?categoria={suggestion_pk}")
    first_cat = profile.preferred_categories.first()
    if first_cat:
        return redirect(f"{reverse('catalogo_publico')}?categoria={first_cat.pk}")
    return redirect('catalogo_publico')


@login_required
@require_POST
def buyer_onboarding_skip(request: HttpRequest) -> HttpResponse:
    """Skip the wizard and enter the guest catalog unpersonalized."""
    profile = _get_buyer_profile(request.user)
    if not profile:
        return redirect('catalogo_publico')
    if buyer_onboarding_pending(request.user):
        _complete_onboarding(profile)
        messages.info(request, 'Puedes personalizar tu experiencia más tarde desde tu perfil.')
    return redirect('catalogo_publico')
