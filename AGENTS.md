# Agent rules (TradeFlow Colón)

Este repositorio incluye reglas para el agente de Cursor en [`.cursor/rules/`](.cursor/rules/).

| Archivo | Alcance |
|---------|---------|
| `tradeflow-colon.mdc` | Siempre activo — producto, diseño, seguridad, calidad |
| `python-django.mdc` | Archivos `**/*.py` |
| `frontend-admin-saas.mdc` | `frontend/admin-saas/**` |

Para añadir reglas propias, crea otro `.mdc` en `.cursor/rules/` o edita los existentes. Formato:

```yaml
---
description: Breve descripción
alwaysApply: true          # o false + globs
globs: "**/*.py"           # opcional
---

# Contenido en Markdown
```

Las reglas se aplican automáticamente en Cursor Agent y Cloud Agents sobre este repo.
