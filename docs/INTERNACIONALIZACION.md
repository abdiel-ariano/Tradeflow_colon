# Internacionalización (i18n) — TradeFlow Colón

## Comportamiento actual

| Aspecto | Configuración |
|---------|----------------|
| Idioma por defecto | Inglés (`LANGUAGE_CODE = 'en'` en `settings.py`) |
| Idiomas activos | Español (`es`), inglés (`en`) |
| URL español | Sin prefijo: `/catalogo/`, `/login/` |
| URL inglés | Prefijo `/en/`: `/en/catalogo/`, `/en/login/` |
| Archivos de traducción | `locale/es/LC_MESSAGES/django.po`, `locale/en/…` |
| Cambio de idioma | Formulario `POST /i18n/setlang/` + cookie `django_language` |

---

## Archivos clave

| Ruta | Rol |
|------|-----|
| `tradeflow_colon/settings.py` | `LANGUAGES`, `LOCALE_PATHS`, `LANGUAGE_CODE` |
| `tradeflow_colon/urls.py` | `i18n_patterns` envuelve rutas del marketplace |
| `core/middleware/tf_i18n.py` | Alinea cookie y prefijo URL |
| `core/views_i18n.py` | Vista `set_language` |
| `core/utils/i18n_urls.py` | Helpers para enlaces traducidos |
| `core/context_processors.py` | Diccionario JS `tf_i18n` para el front |
| `core/templatetags/tf_catalog.py` | `{% tf_language_next %}` en navbar |

---

## En plantillas Django

```django
{% load i18n %}
{% trans "Search catalog" %}
{% blocktrans with count=total %}Search {{ count }} products{% endblocktrans %}
```

Compilar tras editar `.po`:

```bash
python manage.py compilemessages
```

---

## Añadir o corregir cadenas

1. Marcar cadenas en templates/vistas con `gettext` / `{% trans %}`.
2. `python manage.py makemessages -l es -l en`
3. Editar `locale/*/LC_MESSAGES/django.po`
4. `python manage.py compilemessages`

Scripts de apoyo:

```bash
python scripts/i18n_audit.py              # detecta texto duro en templates
python scripts/fill_spanish_translations.py  # relleno asistido ES
```

---

## Pruebas

```bash
python manage.py test core.tests.test_i18n
python manage.py test core.tests.test_i18n_urls
```

Las pruebas activan y restauran el idioma esperado para no depender del orden
de ejecución.

---

## Navbar y PWA

- Selector ES | EN en `marketplace_public_navbar.html`
- Botón «Instalar app» traducido: `Instalar app` / `Install App`
- CSS móvil: `static/css/tf-mobile-pwa.css` (independiente del idioma)

---

## Convención para nuevas pantallas

- Texto visible al usuario: siempre envuelto en i18n.
- Mensajes de error al usuario: `_()` en vistas y `ValidationError` traducibles.
- URLs públicas: usar `reverse` con idioma activo o `tf_language_next`.
- No hardcodear español solo porque el equipo hable español; el default UI es EN.
