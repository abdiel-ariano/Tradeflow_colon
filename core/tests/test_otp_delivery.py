"""OTP delivery helper tests."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase, override_settings

from core.models import EmailVerification, UserProfile
from core.utils.otp_delivery import ensure_otp_sent, has_valid_otp


@override_settings(
    DEBUG=True,
    REQUIRE_EMAIL_VERIFICATION=True,
    RESEND_API_KEY='re_test',
)
class OtpDeliveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='otp_delivery_user',
            email='otp_delivery@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.user, role='buyer', email_verificado=False)
        self.factory = RequestFactory()

    @patch('core.utils.otp_delivery.enviar_codigo_verificacion')
    def test_ensure_otp_sent_generates_and_sends(self, mock_send):
        from core.email_service import EmailSendResult

        mock_send.return_value = EmailSendResult(ok=True, channel='resend')
        client = Client()
        client.force_login(self.user)
        request = self.factory.get('/verificar/')
        request.user = self.user
        request.session = client.session
        ok, status = ensure_otp_sent(request, self.user)
        self.assertTrue(ok)
        self.assertEqual(status, 'sent')
        mock_send.assert_called_once()
        self.assertTrue(has_valid_otp(self.user))

    @patch('core.utils.otp_delivery.enviar_codigo_verificacion')
    def test_ensure_otp_sent_reuses_valid_code(self, mock_send):
        from core.utils.otp_handler import generate_user_otp

        generate_user_otp(self.user)
        request = self.factory.get('/verificar/')
        request.session = {}
        ok, status = ensure_otp_sent(request, self.user)
        self.assertTrue(ok)
        self.assertEqual(status, 'existing')
        mock_send.assert_not_called()
