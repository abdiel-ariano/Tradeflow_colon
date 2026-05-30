"""Permisos Django Admin para rol TradeFlow admin."""
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from core.admin import CompanyAdmin
from core.models import Company, UserProfile
from core.utils.admin_permissions import sync_user_admin_access


class AdminPermissionsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_user(
            'tf_admin',
            password='x',
            email='admin@test.com',
            is_staff=True,
        )
        UserProfile.objects.create(user=self.admin_user, role='admin')
        sync_user_admin_access(self.admin_user)
        self.company = Company.objects.create(name='Perm Co')

    def test_company_change_permission_for_tradeflow_admin(self):
        request = self.factory.get('/admin/core/company/1/change/')
        request.user = self.admin_user
        ma = CompanyAdmin(Company, admin.site)
        self.assertTrue(ma.has_change_permission(request, self.company))
        self.assertTrue(ma.has_view_permission(request, self.company))

    def test_staff_without_role_denied(self):
        user = User.objects.create_user('staff_only', password='x', is_staff=True)
        request = self.factory.get('/admin/')
        request.user = user
        ma = CompanyAdmin(Company, admin.site)
        self.assertFalse(ma.has_change_permission(request, self.company))
