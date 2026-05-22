# Logos oficiales TradeFlow Colón

Archivos PNG **oficiales** (no regenerar ni sustituir por SVG generados).

| Archivo | Uso |
|---------|-----|
| `logo-icon-color.png` | Icono TF azul/naranja — **navbar**, dashboard público, favicon, loader, emails, PDFs, auth |
| `logo-icon-white.png` | Icono TF blanco — fondos muy oscuros (opcional) |
| `logo-wordmark-white.png` | Wordmark blanco (TradeFlow + COLÓN) — footer navy, fondos oscuros |
| `logo-wordmark-dark.png` | Alias legacy del wordmark blanco (mismo asset) |
| `logo.png` | Alias de `logo-icon-color.png` |
| `logo-white.png` | Alias de `logo-icon-white.png` |
| `logo.svg` / `logo-white.svg` | Fallback vectorial legacy |

## Plantilla Django

```django
{% include "core/includes/tf_logo.html" with variant="icon-color" size="nav" %}
```

Variantes: `icon-color`, `icon-white`, `wordmark-white` (alias `wordmark-dark`)  
Tamaños: `sm`, `nav`, `auth`, `sidebar`, `wordmark`, `loader`, `footer`

No estirar ni recolorear los PNG oficiales.
