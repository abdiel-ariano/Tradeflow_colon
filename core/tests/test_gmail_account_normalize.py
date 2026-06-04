from django.test import SimpleTestCase

from core.utils.email_config import (
    LEGACY_CONTACT_EMAIL,
    LEGACY_GMAIL_ACCOUNT,
    TRADEFLOW_GMAIL_ACCOUNT,
    normalize_contact_email,
    normalize_project_gmail,
)


class GmailAccountNormalizeTests(SimpleTestCase):
    def test_legacy_maps_to_official(self):
        self.assertEqual(
            normalize_project_gmail(LEGACY_GMAIL_ACCOUNT),
            TRADEFLOW_GMAIL_ACCOUNT,
        )
        self.assertEqual(
            normalize_project_gmail('  InfoTradeFlow@Gmail.COM  '),
            TRADEFLOW_GMAIL_ACCOUNT,
        )

    def test_legacy_footer_contact_maps_to_gmail(self):
        self.assertEqual(
            normalize_contact_email(LEGACY_CONTACT_EMAIL),
            TRADEFLOW_GMAIL_ACCOUNT,
        )

    def test_other_addresses_unchanged(self):
        self.assertEqual(
            normalize_project_gmail('demo.buyer@tradeflow.pa'),
            'demo.buyer@tradeflow.pa',
        )
