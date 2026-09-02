# Calidad de código y documentación — TradeFlow Colón

Contrato mínimo de calidad para cambios en aplicación, pruebas, configuración y
documentación operativa. Alineado con **PEP 8** (estilo) y **PEP 257** (docstrings).

---

## 1. Estándar Python (PEP 8)

- Indentación de **4 espacios**; sin tabuladores.
- Líneas de **79 caracteres** o menos en código Python nuevo.
- Imports agrupados: stdlib → terceros → Django → locales; una línea en blanco
  entre grupos.
- Nombres: `snake_case` funciones/variables, `PascalCase` clases,
  `UPPER_SNAKE` constantes de módulo.
- Vistas delgadas: lógica reutilizable en `core/utils/` o servicios dedicados
  (p. ej. `core/email_service.py`).
- No reformatear código ajeno al cambio en curso.

---

## 2. Docstrings (PEP 257) — idioma español

### Módulos y paquetes

Primera línea: resumen en imperativo o descriptivo, **en español**.

```python
"""Servicio de correo transaccional vía Resend para TradeFlow Colón."""
```

### Clases

```python
class EmailSendResult:
    """Resultado de un intento de envío de correo saliente."""

    ok: bool
    channel: str
```

### Funciones y métodos públicos

```python
def send_verification_otp(email: str, code: str) -> EmailSendResult:
    """Envía el OTP de verificación de cuenta al correo indicado."""
```

### Comandos `manage.py`

```python
class Command(BaseCommand):
    """Carga el catálogo demo con empresas, productos y usuarios de prueba."""

    help = 'Carga datos demo para Expo y desarrollo local'
```

### Qué documentar

- Decisiones de seguridad y comportamiento ante fallo.
- Efectos secundarios (escribe BD, envía correo, invalida caché).
- Parámetros no obvios y unidades (segundos, USD, etc.).

### Qué no hace falta repetir

- Getters triviales cuyo nombre ya lo explica todo.
- Tests que solo afirman el comportamiento obvio del framework.

---

## 3. TypeScript y frontend (`frontend/admin-saas`)

PEP 8 no aplica. Obligatorio:

```bash
cd frontend/admin-saas
npm ci
npm run build
```

- TypeScript estricto y build Vite sin errores.
- El estado UI refleja la respuesta confirmada del servidor.
- Un error HTTP **nunca** muestra notificación de éxito.
- Acciones que modifican datos: deshabilitar botón mientras hay petición en vuelo.

---

## 4. Pruebas y CI

Cada cambio de comportamiento incluye la regresión más estrecha útil.

Antes de merge:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.tests
```

El workflow `.github/workflows/ci.yml` ejecuta además Bandit y `pip-audit`.

**Pruebas de API:** pueden desactivar middleware de seguridad no relacionado si
hay pruebas dedicadas de ese middleware; no debilitar `settings.py` global.

**Fixtures:** usuarios en rutas protegidas deben tener email verificado salvo que
la prueba sea de onboarding.

**i18n en tests:** activar y limpiar `translation.activate()` por prueba.

---

## 5. Documentación obligatoria en cada cambio

La descripción del PR debe incluir:

1. Problema y causa raíz.
2. Archivos y comportamiento modificados.
3. Impacto usuario, seguridad y operaciones.
4. Comandos de prueba ejecutados.
5. Instrucciones de despliegue o rollback si aplica.

**Nuevas variables** → `.env.example` + sección en `docs/DOCUMENTACION_TECNICA.md`
o runbook específico bajo `docs/`.

**Nuevos procedimientos ops** → `docs/SECURITY_OPS.md` o guía temática.

Índice general: [README.md](README.md).

---

## 6. Contrato de errores SaaS (admin API)

Desde 2026-07-22, aprobar/rechazar solicitudes comerciales SaaS:

- Solo una respuesta API exitosa actualiza el estado en BD.
- Errores API muestran notificación de error.
- Tras éxito o fallo se recargan datos del servidor.
- Botones deshabilitados durante la petición.
- Cobertura en `core/tests/test_saas_admin_api.py`.

---

## 7. Seguimiento de deuda técnica

- No se usan comentarios `TODO` / `FIXME` en el código de producción; el
  seguimiento va en issues de GitHub.
- Documentos históricos (snapshots de CHANGELOG) se conservan
  como archivo bajo `docs/README.md` → sección deprecados.

---

## 8. Referencia rápida PEP 8 (extracto)

| Tema | Regla |
|------|-------|
| Espacios | `a = 1`, no `a=1` (excepto kwargs) |
| Comas finales | Permitidas en listas multilínea |
| Comparaciones | `if x is None`, no `== None` |
| Excepciones | `raise ValueError('msg') from err` |
| Strings | f-strings preferidos; `_()` para UI traducible |

Documentación oficial: [PEP 8](https://peps.python.org/pep-0008/),
[PEP 257](https://peps.python.org/pep-0257/).
