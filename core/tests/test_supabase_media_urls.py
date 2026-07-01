"""Tests for Supabase native media URL generation."""
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
    def test_public_url_uses_native_endpoint(self):
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
        url = supabase_media_url('productos/foo.png')
        self.assertIn('/storage/v1/object/public/media/', url)

    def test_storage_backend_url_override(self):
        storage = SupabaseMediaStorage()
        url = storage.url('productos/placeholders/placeholder_1_SS.png')
        self.assertIn('/storage/v1/object/public/media/', url)
        self.assertNotIn('service_role', url)
