# Logos oficiales TradeFlow Colón

| Archivo | Uso |
|---------|-----|
| `logo-icon-color.png` | Icono TF colorido — login secundario, loader, favicon, cards |
| `logo-icon-white.png` | Icono blanco — navbar oscuro, emails (header) |
| `logo-wordmark-dark.png` | Wordmark negro (TradeFlow + COLÓN) — auth, sidebar seller, footer |
| `logo.png` | Alias de `logo-icon-color.png` (compatibilidad) |
| `logo-white.png` | Alias de `logo-icon-white.png` (compatibilidad) |
| `logo.svg` / `logo-white.svg` | Fallback vectorial legacy |

## Plantilla Django

```django
{% include "core/includes/tf_logo.html" with variant="wordmark-dark" size="auth" %}
```

Variantes: `icon-color`, `icon-white`, `wordmark-dark`  
Tamaños: `sm`, `nav`, `auth`, `sidebar`, `wordmark`, `loader`, `footer`

No estirar ni recolorear los PNG oficiales.
