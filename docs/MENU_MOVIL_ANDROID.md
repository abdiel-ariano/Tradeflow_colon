# Menú móvil Android — diagnóstico y verificación

Documentación operativa del menú hamburguesa compacto en marketplace público y
shell de comprador. Formato alineado con **PEP 8** / **PEP 257** en código;
este archivo describe comportamiento, causa raíz de fallos y pruebas.

---

## 1. Componentes

| Pieza | Archivo | IDs principales |
|-------|---------|-----------------|
| Script unificado | `static/js/tf-mobile-pwa.js` | — |
| Estilos móvil / PWA | `static/css/tf-mobile-pwa.css` | `body.tf-market-menu-open` |
| Nav invitado / vendedor | `templates/core/includes/marketplace_public_navbar.html` | `#cat-nav-hamburger`, `#cat-nav-secondary` |
| Nav comprador | `templates/core/includes/buyer/buyer_navbar.html` | `#bn-mobile-toggle`, `#bn-l2` |
| Filtros catálogo | `static/js/catalogo-publico.js` | `#cat-filter-open` (no hamburger) |

El menú secundario en viewports compactos usa `position: fixed` y solo se
muestra cuando **ambas** condiciones se cumplen:

1. Clase `is-open` en el panel (`#cat-nav-secondary` o `#bn-l2`).
2. Clase `tf-market-menu-open` en `document.body`.

---

## 2. Causa raíz del fallo en Android real

Los videos de verificación previos mostraban éxito porque:

- Se probaba **home como invitado** (`page.click` en escritorio emulado).
- No se cubría **comprador autenticado** ni **catálogo**.

### 2.1 Comprador autenticado (caso más frecuente en app/TWA)

`tf-mobile-pwa.css` oculta `.navbar-secondary` con `display: none !important`
en pantallas &lt; 1200px. La regla de apertura exige `body.tf-market-menu-open`.

El script inline en `buyer_navbar.html` solo alternaba `is-open` en `#bn-l2`
**sin** añadir `tf-market-menu-open` al body. Resultado: el panel seguía oculto
en Android aunque el botón respondiera.

**Corrección:** `tf-mobile-pwa.js` inicializa ambos shells (público y buyer) y
aplica la misma clase en `body`.

### 2.2 Catálogo como invitado

`catalogo-publico.js` enlazaba `#cat-nav-hamburger` para abrir el **sidebar de
filtros**, compitiendo con el menú de navegación. El usuario veía filtros (o
nada útil) en lugar del menú.

**Corrección:** el hamburger queda exclusivo para navegación; filtros usan
`#cat-filter-open` y «Todas las categorías».

### 2.3 CSS duplicado en buyer shell

`tf-buyer-shell.css` definía `.bn-l2.is-open { display: flex }` sin la clase
del body, en conflicto con `!important` de `tf-mobile-pwa.css`.

**Corrección:** visibilidad móvil delegada a `tf-mobile-pwa.css`.

### 2.4 Por qué los videos parecían correctos

Puppeteer en home invitado ejecutaba un único `click` sobre `#cat-nav-hamburger`
donde solo existía el listener de `tf-mobile-pwa.js`. No había conflicto de
roles ni de catálogo.

---

## 3. Pruebas

### 3.1 Django

```bash
python manage.py test core.tests.test_mobile_menu -v 2
```

Valida marcado por rol y ausencia del hijack del hamburger en catálogo.

### 3.2 Matriz multi-viewport (Puppeteer + touch)

Con el servidor en `127.0.0.1:8000`, cuenta demo cargada y `DEMO_USER_PASSWORD` exportada:

```bash
export DEMO_USER_PASSWORD='su-clave-local'
node scripts/test_mobile_menu_matrix.js
```

---

## 4. Caché de activos

Tras desplegar, confirmar versión de caché en `templates/core/base.html`:

- `tf-mobile-pwa.css?v=6`
- `tf-mobile-pwa.js?v=6`

El service worker **no** cachea CSS/JS de menú; un bump de `v=` fuerza
recarga en clientes con HTML en caché.

---

## 5. Checklist manual Android / TWA

1. Invitado: home → hamburger → enlaces visibles y navegables.
2. Invitado: catálogo → hamburger → menú nav (no solo filtros).
3. Comprador: home y catálogo → `#bn-mobile-toggle` abre `#bn-l2`.
4. Deslizar horizontal: sin franja blanca ni desalineación.
5. Menú abierto: scroll vertical del panel; cierre al tocar fuera o enlace.

---

## 6. Referencias

- Overflow horizontal: rama `cursor/android-overflow-fix-73ca`, PR #559.
- PWA / asset links: `docs/ANDROID_APK.md`, `core/tests/test_pwa_android.py`.
