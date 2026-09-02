# Changelog — TradeFlow Colón

Historial de cambios relevantes del marketplace B2B ZLC. Para detalle de cada PR,
consultar GitHub.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

---

## [Sin etiquetar] — 2026-09

### Añadido
- Documentación técnica consolidada en español (`docs/DOCUMENTACION_TECNICA.md`, índice
  `docs/README.md`, guías BD/correo/i18n/PEP 8).
- Bloqueo de overflow horizontal en Android (`tf-mobile-pwa.css/js`).
- Botón PWA «Instalar app» en navbar marketplace con i18n.
- Auditoría i18n (es/en) y pruebas `core.tests.test_i18n`.
- Privacidad PDP: stock exacto oculto a compradores; descripción estructurada.

### Corregido
- Menú compacto hamburguesa en móvil tras fix de overflow (panel `position: fixed`).
- Layout responsive Android en home y catálogo.
- Perfil: estilo Sign out y eliminación de duplicados en layout.

### Documentación
- Correo oficial documentado como **Resend**; deprecadas guías Gmail/Supabase Edge.
- Inventario de módulos: `docs/INVENTARIO_MODULOS.md`.
- Estándar PEP 8/257 en español: `docs/CALIDAD_CODIGO.md`.

---

## [2026-05] — Landing pública unificada (rama histórica)

Snapshot de la rama `cursor/tf-public-landing-ae01`: shell público en inglés,
`tf-home-v2.css`, secciones home modularizadas. Ver commits de mayo 2026 en GitHub
para detalle; no refleja necesariamente el estado actual de `master`.

---

## Convenciones

- **Añadido** — funcionalidad nueva.
- **Cambiado** — cambios en comportamiento existente.
- **Deprecado** — se eliminará pronto.
- **Eliminado** — ya retirado.
- **Corregido** — corrección de errores.
- **Seguridad** — parches de vulnerabilidades.
