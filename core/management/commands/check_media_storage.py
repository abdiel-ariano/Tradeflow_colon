"""Validate the configured Django media backend without exposing signed URLs."""

from __future__ import annotations

import uuid
from urllib.parse import urlsplit

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from core.utils.media_storage import is_remote_media_storage


class Command(BaseCommand):
    """Report media configuration and optionally run a reversible write test."""

    help = 'Check the media backend; --write-test creates, reads, and deletes one probe object'

    def add_arguments(self, parser):
        """Register explicit mutation and production-safety switches."""
        parser.add_argument(
            '--write-test',
            action='store_true',
            help='Create, read, and delete a temporary media object.',
        )
        parser.add_argument(
            '--require-remote',
            action='store_true',
            help='Fail unless the default storage backend is remote/S3-compatible.',
        )

    def handle(self, *args, **options):
        """Validate backend selection and exercise storage only when requested."""
        backend_name = f'{default_storage.__class__.__module__}.{default_storage.__class__.__name__}'
        remote = is_remote_media_storage()
        self.stdout.write(f'Media backend: {backend_name}')
        self.stdout.write(f'Remote storage: {remote}')

        if options['require_remote'] and not remote:
            raise CommandError('Remote media storage is required but FileSystemStorage is active.')

        if not options['write_test']:
            self.stdout.write('Write test skipped. Pass --write-test to test create/read/delete.')
            return

        key = f'_health/media-{uuid.uuid4().hex}.txt'
        payload = b'tradeflow-media-storage-ok\n'
        saved_name = ''
        try:
            saved_name = default_storage.save(key, ContentFile(payload))
            if not default_storage.exists(saved_name):
                raise CommandError('Probe object was saved but storage.exists() returned False.')
            with default_storage.open(saved_name, 'rb') as probe:
                if probe.read() != payload:
                    raise CommandError('Probe object content did not match the uploaded bytes.')
            url = default_storage.url(saved_name)
            parsed = urlsplit(url)
            if remote and (not parsed.scheme or not parsed.netloc):
                raise CommandError('Remote storage returned an invalid absolute media URL.')
            if not remote and not parsed.path.startswith('/'):
                raise CommandError('Local storage returned an invalid media URL.')
            # Never print the query string: AWS presigned URLs contain
            # temporary credential material that does not belong in CI logs.
            if remote:
                self.stdout.write(f'Read URL origin: {parsed.scheme}://{parsed.netloc}')
            else:
                self.stdout.write(f'Read URL path: {parsed.path}')
        finally:
            if saved_name:
                default_storage.delete(saved_name)

        if default_storage.exists(saved_name):
            raise CommandError('Probe object still exists after cleanup.')
        self.stdout.write(self.style.SUCCESS('Media create/read/delete test: OK'))
