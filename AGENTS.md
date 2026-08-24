# Agent rules (TradeFlow Colón)

Reglas del agente en [`.cursor/rules/`](.cursor/rules/).

| Archivo | Alcance |
|---------|---------|
| **`cursor-tradeflow-metodologia.mdc`** | **Siempre activo** — metodología principal (análisis, implementación, verificación, comunicación) |
| `python-django.mdc` | Archivos `**/*.py` |
| `frontend-admin-saas.mdc` | `frontend/admin-saas/**` |

La metodología principal define rol, autorización por verbo del usuario, modos guiado/autónomo, protocolo pre-edición, seguridad, git, verificación y formato de respuesta. Las reglas con `globs` complementan convenciones por stack.

Para editar las reglas, modifica los `.mdc` en `.cursor/rules/`.
