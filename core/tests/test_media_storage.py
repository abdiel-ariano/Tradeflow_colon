"""Focused tests for local and remote product media behavior."""

from __future__ import annotations

from io import StringIO
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from core.management.commands.verify_media import _url_without_query
from core.templatetags.tf_media import product_image_src
from core.utils.demo_product_images import is_demo_generated_image
from core.utils.media_storage import product_image_url


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        }
    }
)
class MediaStorageCommandTests(SimpleTestCase):
    """Exercise the reversible storage probe without touching the database."""

    def test_write_probe_is_removed(self):
        """The explicit write test must leave no health object behind."""
        output = StringIO()

        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            call_command('check_media_storage', '--write-test', stdout=output)
            directories, files = default_storage.listdir('_health')

        self.assertIn('Media create/read/delete test: OK', output.getvalue())
        self.assertEqual((directories, files), ([], []))

    def test_require_remote_rejects_filesystem_storage(self):
        """Production validation must fail closed with local disk storage."""
        with self.assertRaisesMessage(CommandError, 'Remote media storage is required'):
            call_command('check_media_storage', '--require-remote')


class ProductImageUrlTests(SimpleTestCase):
    """Keep URL generation delegated to the active remote backend."""

    @override_settings(
        STORAGES={
            'default': {
                'BACKEND': 'storages.backends.s3.S3Storage',
            }
        }
    )
    def test_remote_backend_owns_url_generation(self):
        """AWS may return a signed URL, so do not rebuild it as /media/."""
        image = SimpleNamespace(
            name='productos/wolf.jpg',
            url='https://private-media.s3.amazonaws.com/productos/wolf.jpg?X-Amz-Signature=secret',
        )

        self.assertEqual(product_image_url(SimpleNamespace(image=image)), image.url)

    def test_signed_url_query_is_redacted_from_diagnostics(self):
        """Operational output may contain the object path, never the signature."""
        self.assertEqual(
            _url_without_query(
                'https://bucket.s3.amazonaws.com/productos/wolf.jpg?X-Amz-Signature=secret'
            ),
            'https://bucket.s3.amazonaws.com/productos/wolf.jpg',
        )

class ProductImageClassificationTests(SimpleTestCase):
    """Real seller uploads must win over demo fallbacks on every company."""

    @staticmethod
    def _product(path='products/seller-upload.jpg'):
        """Build a simulated-company product with a concrete remote upload."""
        image = SimpleNamespace(
            name=path,
            url=(
                'https://private-media.s3.amazonaws.com/'
                f'{path}?X-Amz-Signature=secret'
            ),
        )
        return SimpleNamespace(
            pk=1344,
            sku='AWS-S3-TEST-20260818B',
            name='PRUEBA AWS S3',
            image=image,
            company=SimpleNamespace(ruc='8-1Y-SIM-001'),
        )

    def test_real_upload_from_simulated_company_is_not_demo_media(self):
        """Company simulation metadata must not hide a real seller upload."""
        product = self._product()

        self.assertFalse(is_demo_generated_image(product, product.image.name))

    def test_known_generated_paths_remain_demo_media(self):
        """Only paths owned by demo generators may use reference fallbacks."""
        product = self._product()

        for path in (
            'products/demo/product_1344.jpg',
            'productos/placeholders/placeholder_1344.png',
        ):
            with self.subTest(path=path):
                self.assertTrue(is_demo_generated_image(product, path))

    @override_settings(
        STORAGES={
            'default': {
                'BACKEND': 'storages.backends.s3.S3Storage',
            }
        }
    )
    def test_template_filter_keeps_signed_s3_url_for_real_upload(self):
        """Catalog cards must render the valid S3 object instead of an icon."""
        product = self._product()

        self.assertEqual(product_image_src(product), product.image.url)
