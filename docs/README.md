# Documentación TradeFlow Colón

Índice oficial de la documentación técnica y operativa del marketplace B2B de la
Zona Libre de Colón (Panamá). Todo el material nuevo se redacta en **español**;
las guías en inglés en la raíz (`PRODUCT.md`, `DESIGN.md`) se mantienen como
referencia de producto y diseño hasta su fusión.

**Última revisión:** septiembre 2026.

---

## Empezar aquí

| Documento | Para quién | Contenido |
|-----------|------------|-----------|
| [../README.md](../README.md) | Desarrolladores | Arranque local, arquitectura, stack, comandos |
| [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md) | Desarrolladores / DevOps | Vista completa: BD, correo, i18n, PWA, despliegue |
| [../.env.example](../.env.example) | Desarrolladores | Plantilla canónica de variables de entorno |
| [CALIDAD_CODIGO.md](CALIDAD_CODIGO.md) | Contribuidores | PEP 8, PEP 257, pruebas y contrato de PR |
| [INVENTARIO_MODULOS.md](INVENTARIO_MODULOS.md) | Desarrolladores | Mapa de paquetes Python y comandos `manage.py` |

---

## Infraestructura y operaciones

| Documento | Tema |
|-----------|------|
| [BASE_DE_DATOS.md](BASE_DE_DATOS.md) | PostgreSQL (Supabase/RDS), SQLite local, migraciones |
| [CORREO_TRANSACCIONAL.md](CORREO_TRANSACCIONAL.md) | **Resend** (producción), OTP, reset de contraseña |
| [SUPABASE_STORAGE.md](SUPABASE_STORAGE.md) | Bucket de imágenes y URLs firmadas |
| [PAGE_CACHE.md](PAGE_CACHE.md) | Redis, TTLs, invalidación |
| [SECURITY_OPS.md](SECURITY_OPS.md) | Flags de producción, cron, secretos |
| [MIGRACION_DB_AWS_RDS.md](MIGRACION_DB_AWS_RDS.md) | Plan de migración a AWS (alternativa) |
| [ANDROID_APK.md](ANDROID_APK.md) | PWA, TWA, APK, `assetlinks.json` |

---

## Producto, seguridad y cumplimiento

| Documento | Tema |
|-----------|------|
| [../PRODUCT.md](../PRODUCT.md) | Propósito, usuarios, principios de producto |
| [../DESIGN.md](../DESIGN.md) | Tokens visuales (navy, orange, tipografía) |
| [../SECURITY.md](../SECURITY.md) | Reporte de vulnerabilidades |
| [CIBERSEGURIDAD_EXPLICADA.md](CIBERSEGURIDAD_EXPLICADA.md) | Seguridad en lenguaje no técnico |
| [GDPR_DPA_DPIA.md](GDPR_DPA_DPIA.md) | Procesadores, DPA, retención |
| [DEMO_DATA_POLICY.md](DEMO_DATA_POLICY.md) | Catálogo simulado y avisos DEMO |

---

## Funcionalidades de plataforma

| Documento | Tema |
|-----------|------|
| [INTERNACIONALIZACION.md](INTERNACIONALIZACION.md) | Español / inglés, URLs, `locale/` |
| [AI_SEARCH.md](AI_SEARCH.md) | Búsqueda con IA y typeahead |
| [ADMIN_VISUAL_CONTINUITY.md](ADMIN_VISUAL_CONTINUITY.md) | Shell admin unificado |
| [ENTERPRISE_YEAR_SEED.md](ENTERPRISE_YEAR_SEED.md) | Seed masivo de catálogo demo |

---

## Documentos históricos o deprecados

| Documento | Estado |
|-----------|--------|
| [SUPABASE_GMAIL.md](SUPABASE_GMAIL.md) | **Deprecado** — solo desarrollo local sin Resend; ver [CORREO_TRANSACCIONAL.md](CORREO_TRANSACCIONAL.md) |
| [ENTERPRISE_EMAIL.md](ENTERPRISE_EMAIL.md) | **Deprecado** — describía Supabase Edge + Gmail; no refleja el código actual |
| [../CHANGELOG.md](../CHANGELOG.md) | Historial de cambios (ver también releases en GitHub) |
| [../DIAGNOSIS.md](../DIAGNOSIS.md) | Auditoría de mayo 2026 (archivo) |

---

## Convenciones de documentación en código (PEP 257)

- **Módulos y paquetes:** docstring en español en la primera línea del archivo.
- **Clases:** resumen en una línea; párrafo opcional con responsabilidad de negocio.
- **Funciones públicas:** qué hace, parámetros relevantes y efectos secundarios si no son obvios.
- **Comandos `manage.py`:** docstring de clase `help` en español.
- **Línea máxima:** 79 caracteres en código Python nuevo (PEP 8).
- **TODO en código:** no hay marcadores `TODO`/`FIXME` pendientes en el repositorio;
  el deber de seguimiento está en issues/PRs y en este índice.

Ver detalle completo en [CALIDAD_CODIGO.md](CALIDAD_CODIGO.md).
