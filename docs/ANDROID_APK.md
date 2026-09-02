# Android APK and installable PWA

TradeFlow Colón uses a Trusted Web Activity (TWA) instead of duplicating the
Django application in a native client. Android opens the verified production
origin in Chrome, so login, OAuth, CSRF protection, sessions, catalog, orders,
and seller tools continue using the same backend and security controls.

The immutable Android application ID is:

```text
com.tradeflowcolon.app
```

Do not change it after the first Play Store publication.

## Components

| Component | Responsibility |
|-----------|----------------|
| `/manifest.webmanifest` | PWA name, scope, colors, and launcher icons |
| `/service-worker.js` | Network-first navigation with public offline fallback |
| `/pwa/icon-192.png` | Browser installation icon |
| `/pwa/icon-512.png` | Android launcher and splash icon |
| `/.well-known/assetlinks.json` | Verifies the website/app relationship |
| `android/twa-manifest.json` | Reproducible Bubblewrap configuration |
| `android-apk.yml` | Manual APK/AAB build in GitHub Actions |

The service worker deliberately caches only the public offline shell, manifest,
and icons. It does not cache authenticated pages, API responses, orders,
analytics, carts, or company information.

## Test APK

1. Merge and deploy the PWA endpoints.
2. Open **Actions → Build Android APK → Run workflow**.
3. Select `test`.
4. Download the `tradeflow-colon-android-test` artifact.
5. Install `tradeflow-colon.apk` with Android or:

```bash
adb install tradeflow-colon.apk
```

The test workflow creates a disposable signing key. The APK is installable, but
a later test build cannot update it in place and the TWA is not domain-verified.
Android may show the Custom Tab toolbar. Uninstall the previous test APK before
installing another one.

## Production signing

Create one protected upload key and keep it outside the repository. Losing it
can prevent future updates. Add these GitHub Actions secrets:

| Secret | Value |
|--------|-------|
| `ANDROID_KEYSTORE_BASE64` | Complete keystore encoded as Base64 |
| `ANDROID_KEYSTORE_PASSWORD` | Keystore password |
| `ANDROID_KEY_PASSWORD` | Private-key password |
| `ANDROID_KEY_ALIAS` | Alias inside the keystore |

Then run the workflow with `production`. It produces:

- `tradeflow-colon.apk` for controlled installation and testing;
- `tradeflow-colon.aab` for Google Play;
- `sha256-fingerprint.txt` for Digital Asset Links.

Never commit `.keystore`, `.jks`, APK, or AAB files. The repository ignores
these files explicitly.

## Domain verification

Copy the production SHA-256 certificate fingerprint into the Railway
environment:

```dotenv
ANDROID_APP_PACKAGE=com.tradeflowcolon.app
ANDROID_SHA256_CERT_FINGERPRINTS=AA:BB:...:FF
```

Multiple certificates are comma-separated. This is useful when Google Play App
Signing uses a different app-signing certificate from the upload certificate.

Redeploy and verify:

```bash
curl https://tradeflowcolon.com/.well-known/assetlinks.json
```

The response must contain the package ID and the exact certificate fingerprint.
Only then will Chrome remove the toolbar and trust the fullscreen TWA.

The production GitHub Actions build now derives the certificate fingerprint
from the configured keystore and compares it with the deployed association.
The build stops before producing an APK or AAB when the file is empty or the
package/fingerprint does not match. Test builds remain intentionally
unverified because they use a disposable certificate.

## Browser installation and responsive Android layout

On eligible Android browsers, the public marketplace shows **Install
App** inside the compact navigation. The control uses the browser
`beforeinstallprompt` event and remains hidden when installation is not
available or the application already runs in standalone mode.

The compact public shell is used through 1199 CSS pixels and on coarse
pointer tablets through 1366 CSS pixels. Search remains available on its
own row, navigation opens as a touch-friendly drawer, and product cards use
one, two, or three columns instead of forcing the desktop four-column grid.
Cards grow with translated or enlarged text so actions are not clipped.

## Release checklist

1. Run the Django CI checks, `core.tests.test_pwa_android`, and
   `core.tests.test_mobile_menu`.
2. Run `node scripts/test_mobile_menu_matrix.js` against the preview URL.
2. Deploy and verify manifest, 512 px icon, service worker, and offline page.
3. Build with the stable production key.
4. Configure the Play app-signing fingerprint in Railway.
5. Test login, logout, Google/Microsoft OAuth, product images, file selection,
   buyer checkout, seller dashboard, back navigation, and loss of connection.
6. Increase `appVersion` and `appVersionCode` for every Play release.
7. Publish the AAB first to Play Console's internal testing track.

## Current boundaries

- The APK still requires internet for business operations.
- Offline mode is informational and never exposes stale private data.
- Notifications are disabled until a permission, privacy, and backend delivery
  design is approved.
- The wrapper relies on an installed browser with TWA support and falls back to
  a Custom Tab when necessary.
- The workflow validates the deployed site, so it must run after the web release
   reaches `tradeflowcolon.com`.

## Mobile navigation

Diagnosis, root cause, and verification matrix:
[MENU_MOVIL_ANDROID.md](MENU_MOVIL_ANDROID.md).
