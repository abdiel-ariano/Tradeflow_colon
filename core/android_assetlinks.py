"""Validate the Android Digital Asset Links production association.

The command is intentionally independent from Django so GitHub Actions can
compare the deployed association with the certificate that signs the APK.
No private key material or passwords are printed or stored by this module.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


HANDLE_ALL_URLS = 'delegate_permission/common.handle_all_urls'


def normalize_fingerprint(value: str) -> str:
    """Return an uppercase colon-delimited SHA-256 fingerprint."""
    compact = ''.join(character for character in value if character.isalnum())
    if len(compact) != 64:
        return ''

    try:
        bytes.fromhex(compact)
    except ValueError:
        return ''

    return ':'.join(
        compact[index:index + 2].upper()
        for index in range(0, len(compact), 2)
    )


def validate_asset_links(
    payload: object,
    package_name: str,
    fingerprint: str,
) -> tuple[bool, str]:
    """Confirm one statement delegates URLs to the signed Android package."""
    expected_fingerprint = normalize_fingerprint(fingerprint)
    if not expected_fingerprint:
        return False, 'The signing certificate fingerprint is invalid.'

    if not isinstance(payload, list) or not payload:
        return False, 'assetlinks.json has no Android association statements.'

    for statement in payload:
        if not isinstance(statement, dict):
            continue

        relations = statement.get('relation', [])
        target = statement.get('target', {})
        if not isinstance(relations, list) or not isinstance(target, dict):
            continue

        fingerprints = target.get('sha256_cert_fingerprints', [])
        normalized = {
            normalize_fingerprint(value)
            for value in fingerprints
            if isinstance(value, str)
        }
        package_matches = target.get('package_name') == package_name
        namespace_matches = target.get('namespace') == 'android_app'
        relation_matches = HANDLE_ALL_URLS in relations

        if (
            package_matches
            and namespace_matches
            and relation_matches
            and expected_fingerprint in normalized
        ):
            return (
                True,
                'Digital Asset Links matches the production signing key.',
            )

    return (
        False,
        'assetlinks.json does not match the package and signing certificate.',
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser used by the Android workflow."""
    parser = argparse.ArgumentParser(
        description='Validate the deployed TradeFlow Android association.',
    )
    parser.add_argument(
        '--path',
        type=Path,
        required=True,
        help='Path to the downloaded assetlinks.json file.',
    )
    parser.add_argument(
        '--package',
        dest='package_name',
        required=True,
        help='Immutable Android application ID.',
    )
    parser.add_argument(
        '--fingerprint',
        required=True,
        help='SHA-256 fingerprint derived from the signing certificate.',
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the association file and return a shell-compatible status."""
    arguments = build_parser().parse_args(argv)

    try:
        payload = json.loads(arguments.path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        print(f'Unable to read assetlinks.json: {error}')
        return 1

    is_valid, message = validate_asset_links(
        payload,
        arguments.package_name,
        arguments.fingerprint,
    )
    print(message)
    return 0 if is_valid else 1


if __name__ == '__main__':
    raise SystemExit(main())
