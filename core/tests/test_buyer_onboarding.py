"""
Wizard onboarding comprador — 3 pasos post-registro (intención, categorías, Deep Search).
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Category, Company, Product, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    AUTHENTICATION_BACKENDS=['django.contrib.auth.backends.ModelBackend'],
)
class BuyerOnboardingWizardTests(TestCase):
    def setUp(self):
        """Setup."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='new_buyer',
            email='new@test.pa',
            password='TestPass123!',
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='buyer',
            email_verificado=True,
            onboarding_completed_at=None,
        )
        self.company = Company.objects.create(name='CFZ Co', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
        Product.objects.create(
            company=self.company,
            category=self.category,
            name='Widget A',
            sku='WA-01',
            unit_price='10.00',
            currency='USD',
            is_active=True,
        )
        self.client.force_login(self.user)

    def test_pending_buyer_redirected_from_tienda_to_step1(self):
        """Test pending buyer redirected from tienda to step1."""
        resp = self.client.get('/tienda/', follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/onboarding/comprador', resp['Location'])

    def test_step1_renders(self):
        """Test step1 renders."""
        resp = self.client.get('/onboarding/comprador/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '¿Para qué estás usando TradeFlow Colón?')

    def test_full_wizard_flow(self):
        """Test full wizard flow."""
        resp = self.client.post(
            '/onboarding/comprador/paso-1/',
            {'purchase_intent': 'business'},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.purchase_intent, 'business')

        resp = self.client.get('/onboarding/comprador/categorias/')
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(
            '/onboarding/comprador/categorias/guardar/',
            {'categories': [str(self.category.pk)]},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.profile.preferred_categories.count(), 1)

        resp = self.client.get('/onboarding/comprador/busqueda/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Deep Search')

        resp = self.client.post('/onboarding/comprador/finalizar/', follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/catalogo', resp['Location'])
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.onboarding_completed_at)

    def test_skip_marks_complete(self):
        """Test skip marks complete."""
        resp = self.client.post('/onboarding/comprador/omitir/', follow=False)
        self.assertEqual(resp.status_code, 302)
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.onboarding_completed_at)

    def test_grandfathered_buyer_redirected_to_catalog(self):
        """Test grandfathered buyer redirected to catalog."""
        from django.utils import timezone

        self.profile.onboarding_completed_at = timezone.now()
        self.profile.save(update_fields=['onboarding_completed_at'])
        resp = self.client.get('/tienda/', follow=False)
        self.assertEqual(resp.status_code, 301)
        self.assertIn('/catalogo/', resp['Location'])
