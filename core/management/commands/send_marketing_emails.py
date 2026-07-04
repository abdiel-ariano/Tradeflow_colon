"""
Envía correos de marketing del marketplace: carrito abandonado y promociones CFZ.

Uso programado (cron/Railway):
  python manage.py send_marketing_emails --cart-hours=1
  python manage.py send_marketing_emails --promotions
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import UserProfile
from core.utils.email_sender import enviar_carrito_abandonado, enviar_promociones_empresas


class Command(BaseCommand):
    help = 'Send cart abandonment and company promotion emails via Resend.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cart-hours',
            type=float,
            default=1.0,
            help='Hours of cart inactivity before sending reminder (default: 1).',
        )
        parser.add_argument(
            '--promotions',
            action='store_true',
            help='Send company promotions to verified buyers (weekly-style).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List recipients without sending.',
        )

    def handle(self, *args, **options):
        sent_cart = self._send_cart_reminders(
            hours=options['cart_hours'],
            dry_run=options['dry_run'],
        )
        sent_promo = 0
        if options['promotions']:
            sent_promo = self._send_promotions(dry_run=options['dry_run'])
        self.stdout.write(
            self.style.SUCCESS(
                f'Cart reminders: {sent_cart} · Promotions: {sent_promo}'
            )
        )

    def _send_cart_reminders(self, *, hours: float, dry_run: bool) -> int:
        cutoff = timezone.now() - timedelta(hours=hours)
        profiles = UserProfile.objects.filter(
            role='buyer',
            email_verificado=True,
            cart_items_count__gt=0,
            cart_last_activity_at__lte=cutoff,
        ).select_related('user')

        sent = 0
        for profile in profiles:
            if profile.cart_reminder_sent_at and profile.cart_reminder_sent_at >= profile.cart_last_activity_at:
                continue
            user = profile.user
            if not (user.email or '').strip() or not user.is_active:
                continue
            carrito = self._load_user_cart(user)
            if not carrito:
                profile.cart_items_count = 0
                profile.cart_last_activity_at = None
                profile.save(update_fields=['cart_items_count', 'cart_last_activity_at'])
                continue
            if dry_run:
                self.stdout.write(f'[dry-run] cart reminder → {user.email}')
                sent += 1
                continue
            if enviar_carrito_abandonado(user, carrito):
                profile.cart_reminder_sent_at = timezone.now()
                profile.save(update_fields=['cart_reminder_sent_at'])
                sent += 1
        return sent

    def _send_promotions(self, *, dry_run: bool) -> int:
        buyers = User.objects.filter(
            is_active=True,
            profile__role='buyer',
            profile__email_verificado=True,
        ).select_related('profile')
        sent = 0
        for user in buyers:
            if not (user.email or '').strip():
                continue
            if dry_run:
                self.stdout.write(f'[dry-run] promotions → {user.email}')
                sent += 1
                continue
            if enviar_promociones_empresas(user):
                sent += 1
        return sent

    def _load_user_cart(self, user: User) -> dict:
        """Best-effort cart read from the user's session store."""
        from django.contrib.sessions.models import Session

        for session in Session.objects.filter(expire_date__gte=timezone.now()).iterator():
            data = session.get_decoded()
            uid = data.get('_auth_user_id')
            if str(uid) != str(user.pk):
                continue
            carrito = data.get('carrito') or {}
            if carrito:
                return carrito
        return {}
