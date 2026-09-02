# Caché de páginas públicas (TradeFlow Colón)

Documentación de la caché de servidor y HTTP para home, catálogo y merchandising
público. Objetivo: respuestas rápidas bajo carga **sin** romper carrito/sesión
de invitados ni personalización autenticada.

## Arquitectura

```
Vista (home / catálogo / marketing)
        │
        ▼
core.utils.tradeflow_cache  (get_or_set + claves merch:*)
        │
        ├── REDIS_URL definido     → RedisCache (compartido entre workers)
        ├── USE_DB_CACHE=true      → DatabaseCache (tabla `tradeflow_cache`)
        └── si no                  → LocMemCache (por proceso)
```

Si el backend falla (Redis caído, tabla DB ausente, etc.), los helpers
**degradan a ORM sin caché** y la página sigue respondiendo 200.

Código: `core/utils/tradeflow_cache.py`  
Señales de invalidación: `core/signals_cache.py`  
TTLs: `tradeflow_colon/settings.py` (`CACHE_TTL_*`)

## Claves de caché

| Clave | Contenido | TTL setting (default) |
|-------|-----------|------------------------|
| `merch:home_stats` | Contadores marketplace | `CACHE_TTL_STATS` (300 s) |
| `merch:home_ctx:{lang}` | Contexto plantilla home (`es` / `en`) | `CACHE_TTL_HOME` (120 s) |
| `merch:nav_categories` | Top categorías header | `CACHE_TTL_NAV` (600 s) |
| `merch:catalog_categories` | Categorías filtro catálogo | `CACHE_TTL_CATALOG_META` (300 s) |
| `merch:catalog_empresas` | Empresas visibles con productos | `CACHE_TTL_CATALOG_META` (300 s) |
| `merch:catalog_market_ctx` | Rail/modal categorías marketplace | `CACHE_TTL_CATALOG_META` (300 s) |
| `merch:verified_companies_count` | Conteo empresas verificadas con productos activos | `CACHE_TTL_CATALOG_META` (300 s) |
| `merch:api_home_v2` | JSON API home merchandising | `CACHE_TTL_HOME` (120 s) |
| `merch:active_company_ids` | Empresas visibles en marketplace | `CACHE_TTL_ACTIVE_COMPANIES` (120 s) |
| `merch:spotlights:{per}:{cats}` | Filas spotlight catálogo | `CACHE_TTL_SPOTLIGHTS` (120 s) |
| `merch:buyer_mega:{cats}:{per}` | Mega-menú buyer | `CACHE_TTL_MEGA_MENU` (180 s) |
| `seller:dash:{company_id}:{days}` | KPIs home `/mi-tienda/` | `CACHE_TTL_SELLER_DASH` (45 s) |

Prefijo Django adicional: con Redis, `KEY_PREFIX=tf` (settings).

## Sesión y latencia de origen

Por defecto `SESSION_SAVE_EVERY_REQUEST=false` (override con env). Así se evita
un `UPDATE` de sesión en Postgres remoto en **cada** HTML. La cookie sigue
caducando a `SESSION_COOKIE_AGE` (12 h) desde el último save (login, carrito, etc.).

Para sliding window estricto (reescribir sesión en cada request):

```bash
SESSION_SAVE_EVERY_REQUEST=true
```

**Producción:** definir `REDIS_URL` para que workers Gunicorn compartan `merch:*`
y `seller:dash:*`. Sin Redis, LocMem es por proceso y el warm-up se repite.

## Invalidación

`invalidate_merchandising_cache()` borra **todas** las claves de la tabla anterior.

Se dispara automáticamente ante:

- `post_save` / `post_delete` de `Product`, `Company`, `Category`, `HomePromoSection`
- Cambios M2M de secciones de promo (productos / empresas / categorías)
- `post_save` de `Order` cuando cambia el `status` (afecta rankings/merch)

También se invoca desde el comando `actualizar_merchandising`.

## Política HTTP Cache-Control

| Superficie | Política | Motivo |
|------------|----------|--------|
| Home invitados (`home_view`) | `private, max-age=60` | Carrito/sesión en cookie; **no** CDN compartida |
| Catálogo completo invitados | `private, max-age=30` | Idem; filtros por query string |
| Catálogo parcial (AJAX / `?partial=1`) | sin forzar private corto | Respuesta fragmentada |
| Redirects autenticados (home) | sin Cache-Control de página | No cachear redirecciones por rol |
| Legales / marketing (`@cache_control`) | `public, max-age=3600` | Contenido estático compartible |
| `api_home_merchandising` | `public, max-age=60` | JSON sin sesión |

**private vs public**

- `private` — solo el navegador del usuario; seguro con sesión/carrito.
- `public` — apto para CDN/proxy compartido; solo páginas sin datos de sesión.

La caché de **servidor** (Redis/DB/LocMem) es independiente del header HTTP:
acelera el render en el origen aunque el cliente no reutilice la respuesta.

## Ajuste por variables de entorno

```bash
# Backend
REDIS_URL=redis://...          # preferido en producción
USE_DB_CACHE=true              # sin Redis; requiere createcachetable

# TTLs (segundos)
CACHE_TTL_HOME=120
CACHE_TTL_STATS=300
CACHE_TTL_NAV=600
CACHE_TTL_CATALOG_META=300
CACHE_TTL_ACTIVE_COMPANIES=120
CACHE_TTL_SPOTLIGHTS=120
CACHE_TTL_MEGA_MENU=180
CACHE_TTL_SELLER_DASH=45
```

Recomendaciones:

- **Obligatorio en prod con varios workers:** `REDIS_URL=...`
- Subir `CACHE_TTL_CATALOG_META` si el catálogo meta cambia poco.
- Bajar `CACHE_TTL_HOME` durante campañas con promos muy dinámicas.
- Tras un deploy que cambie la forma del contexto, reiniciar workers o
  llamar `invalidate_merchandising_cache()` / esperar TTL.

## Qué no se cachea a nivel página

- Carrito, checkout, login, paneles buyer/seller (datos personalizados).
- Respuestas de home para usuarios autenticados (redirect por rol).
- Resultados de búsqueda/filtro del catálogo como documento CDN `public`
  (sí se cachean **metadatos** de categorías/empresas en servidor).
