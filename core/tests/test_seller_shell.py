"""Seller dashboard shell routes under /mi-tienda/.

Trialing sellers reach Stripe-inspired catalog and analytics
pages; guests must be sent to login.
"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import Company, UserProfile
from core.utils.saas_billing import ensure_default_plans
from core.utils.seller_lifecycle import start_seller_trial


@override_settings(
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
)
class TestSellerShellPages(TestCase):
    """Assert shell page status codes and catalog layout copy."""

    def setUp(self):
        """Attach seller as owner and start a Digitalízate trial."""
        ensure_default_plans()
        self.company = Company.objects.create(name='Demo Co', ruc='999', is_verified=True)
        self.seller = User.objects.create_user(
            username='shell_seller',
            email='shell@seller.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.seller, role='seller', email_verificado=True)
        self.company.owner = self.seller
        self.company.save(update_fields=['owner'])
        # Portal exige suscripción trialing/active (gates de seller_required).
        start_seller_trial(self.company)

    def _login(self):
        """Log in as the shell seller fixture."""
        self.client.login(username='shell_seller', password='TestPass123!')

    def test_seller_shell_routes_return_200(self):
        """Return 200 for core /mi-tienda/ shell paths."""
        self._login()
        paths = [
            '/mi-tienda/',
            '/mi-tienda/balances/',
            '/mi-tienda/clientes/',
            '/mi-tienda/impuestos/',
            '/mi-tienda/datos/',
            '/mi-tienda/disputas/',
            '/mi-tienda/apps/',
            '/mi-tienda/configuracion/',
            '/mi-tienda/buscar/',
            '/mi-tienda/reportes/',
            '/mi-tienda/analitica/',
            '/mi-tienda/qr/',
        ]
        for path in paths:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, msg=path)

    def test_guest_redirected_from_seller_shell(self):
        """Redirect anonymous users from shell to login."""
        r = self.client.get('/mi-tienda/balances/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r.url)

    def test_product_catalog_stripe_layout(self):
        """Render product catalog headings and create CTA."""
        self._login()
        r = self.client.get('/mi-tienda/productos/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Product catalog')
        self.assertContains(r, 'All products')
        self.assertContains(r, 'Create product')

    def test_payments_analytics_stripe_layout(self):
        """Render payments analytics metrics sections."""
        self._login()
        r = self.client.get('/mi-tienda/reportes/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Payments analytics')
        self.assertContains(r, 'Key metrics')
        self.assertContains(r, 'Acceptance')

    def test_catalog_features_tab(self):
        """Open pricing tab with pricing tables copy."""
        self._login()
        r = self.client.get('/mi-tienda/productos/?tab=pricing')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Pricing tables')
