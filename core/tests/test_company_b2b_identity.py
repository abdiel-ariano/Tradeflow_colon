"""Tests for real B2B company identity and membership rules."""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import Company, CompanyMembership


class CompanyB2BIdentityTests(TestCase):
    """Company capabilities and manual verification are explicit."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner_company',
            email='owner@empresa.pa',
            password='SecurePass1!',
        )
        self.reviewer = User.objects.create_user(
            username='reviewer',
            email='reviewer@tradeflowcolon.com',
            password='SecurePass1!',
            is_staff=True,
        )

    def _complete_company(self, **overrides):
        data = {
            'name': 'Importadora Istmo',
            'legal_name': 'Importadora Istmo, S.A.',
            'ruc': ' 1556-123456-789 ',
            'dv': ' 12 ',
            'business_email': 'compras@istmo.pa',
            'business_phone': '+507 6000-0000',
            'business_role': 'both',
            'owner': self.owner,
            'verification_document': 'companies/verification/aviso-operacion.pdf',
        }
        data.update(overrides)
        return Company.objects.create(**data)

    def test_company_capabilities_support_buyer_seller_or_both(self):
        buyer = Company.objects.create(name='Buyer Corp', business_role='buyer')
        seller = Company.objects.create(name='Seller Corp', business_role='seller')
        both = Company.objects.create(name='Both Corp', business_role='both')

        self.assertTrue(buyer.can_buy)
        self.assertFalse(buyer.can_sell)
        self.assertFalse(seller.can_buy)
        self.assertTrue(seller.can_sell)
        self.assertTrue(both.can_buy)
        self.assertTrue(both.can_sell)

    def test_ruc_and_dv_are_normalized_without_claiming_external_validation(self):
        company = self._complete_company()
        self.assertEqual(company.ruc, '1556-123456-789')
        self.assertEqual(company.dv, '12')
        self.assertFalse(company.is_verified)
        self.assertEqual(company.verification_status, 'draft')

    def test_complete_company_can_be_submitted_and_manually_verified(self):
        company = self._complete_company()
        company.submit_for_verification()
        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'pending')
        self.assertIsNotNone(company.verification_submitted_at)
        self.assertFalse(company.is_verified)

        company.mark_verified(self.reviewer)
        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'verified')
        self.assertTrue(company.is_verified)
        self.assertEqual(company.verified_by, self.reviewer)
        self.assertIsNotNone(company.verified_at)

    def test_verified_company_can_return_to_pending_review(self):
        company = self._complete_company()
        company.submit_for_verification()
        company.mark_verified(self.reviewer)

        company.return_to_pending_review()
        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'pending')
        self.assertFalse(company.is_verified)
        self.assertIsNone(company.verified_by)
        self.assertIsNone(company.verified_at)

    def test_incomplete_company_cannot_enter_verification(self):
        company = Company.objects.create(
            name='Incomplete Corp',
            legal_name='Incomplete Corp, S.A.',
            business_role='buyer',
        )
        with self.assertRaises(ValidationError) as exc:
            company.submit_for_verification()

        self.assertIn('RUC', str(exc.exception))
        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'draft')
        self.assertFalse(company.is_verified)


class CompanyMembershipTests(TestCase):
    """A user has one auditable membership per company."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='member',
            email='member@empresa.pa',
            password='SecurePass1!',
        )
        self.company = Company.objects.create(name='Empresa Mixta', business_role='both')

    def test_active_owner_can_manage_company(self):
        membership = CompanyMembership.objects.create(
            company=self.company,
            user=self.user,
            role='owner',
            status='active',
        )
        self.assertTrue(membership.can_manage_company)
        self.assertIn(self.user, self.company.members.all())

    def test_duplicate_company_membership_is_rejected(self):
        CompanyMembership.objects.create(
            company=self.company,
            user=self.user,
            role='member',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompanyMembership.objects.create(
                    company=self.company,
                    user=self.user,
                    role='admin',
                )

