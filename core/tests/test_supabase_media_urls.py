"""Supabase native public media URL builders.

Catalog images must use /storage/v1/object/public/ URLs, not
S3-signed query strings that leak credentials in HTML.
"""
from django.test import TestCase, override_settings

from core.storage.supabase_media import (
    SupabaseMediaStorage,
    supabase_media_url,
    supabase_public_url,
)


@override_settings(
    SUPABASE_URL='https://ayyukcenmtujsshzoebp.supabase.co',
    SUPABASE_STORAGE_BUCKET='media',
    SUPABASE_STORAGE_PUBLIC=True,
    STORAGES={
        'default': {
            'BACKEND': 'core.storage.supabase_media.SupabaseMediaStorage',
            'OPTIONS': {'bucket_name': 'media'},
        },
    },
)
class SupabaseMediaUrlTests(TestCase):
    """Assert public URL shape from helpers and storage backend."""

    def test_public_url_uses_native_endpoint(self):
        """Build native public object URL without AWS query params."""
        path = 'productos/placeholders/placeholder_714_1I.png'
        url = supabase_public_url(path)
        self.assertEqual(
            url,
            'https://ayyukcenmtujsshzoebp.supabase.co/storage/v1/object/public/media/'
            'productos/placeholders/placeholder_714_1I.png',
        )
        self.assertNotIn('AWSAccessKeyId', url)
        self.assertNotIn('/storage/v1/s3/', url)

    def test_supabase_media_url_delegates_to_public(self):
        """Delegate supabase_media_url to the public object path."""
        url = supabase_media_url('productos/foo.png')
        self.assertIn('/storage/v1/object/public/media/', url)

    def test_storage_backend_url_override(self):
        """Storage.url returns public media paths without service_role."""
        storage = SupabaseMediaStorage()
        url = storage.url('productos/placeholders/placeholder_1_SS.png')
        self.assertIn('/storage/v1/object/public/media/', url)
        self.assertNotIn('service_role', url)
