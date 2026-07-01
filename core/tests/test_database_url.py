"""DATABASE_URL normalization for Supabase pooler deploys."""
import os
from unittest.mock import patch

from django.test import SimpleTestCase

from core.utils.database_url import (
    build_database_url_from_components,
    infer_supabase_project_ref,
    normalize_database_url,
)


class DatabaseUrlNormalizationTests(SimpleTestCase):
    def test_infer_project_ref_from_supabase_url(self):
        with patch.dict(os.environ, {'SUPABASE_URL': 'https://abcdefghijklmnop.supabase.co'}, clear=False):
            self.assertEqual(infer_supabase_project_ref(), 'abcdefghijklmnop')

    def test_pooler_user_postgres_gets_project_suffix(self):
        env = {
            'SUPABASE_URL': 'https://myprojectref12.supabase.co',
        }
        with patch.dict(os.environ, env, clear=False):
            url = normalize_database_url(
                'postgresql://postgres:secret@aws-1-us-east-1.pooler.supabase.com:5432/postgres'
            )
        self.assertIn('postgres.myprojectref12:', url)
        self.assertIn('pooler.supabase.com', url)

    def test_build_from_components_with_pooler(self):
        env = {
            'SUPABASE_DB_HOST': 'aws-1-us-east-1.pooler.supabase.com',
            'SUPABASE_DB_PASSWORD': 'p@ss:word',
            'SUPABASE_DB_PORT': '5432',
            'SUPABASE_PROJECT_REF': 'myprojectref12',
        }
        with patch.dict(os.environ, env, clear=False):
            url = build_database_url_from_components()
        self.assertIn('postgres.myprojectref12:', url)
        self.assertIn('p%40ss%3Aword', url)

    def test_database_password_override(self):
        with patch.dict(os.environ, {'DATABASE_PASSWORD': 'new$ecret'}, clear=False):
            url = normalize_database_url(
                'postgresql://postgres:old@db.example.com:5432/postgres'
            )
        self.assertIn('new%24ecret', url)
