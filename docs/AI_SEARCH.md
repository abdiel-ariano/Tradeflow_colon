# TradeFlow AI Search

> **Vista API:** `api_search_suggest` en `core/views/home_map.py` (reexportada desde
> `core/views/__init__.py`). Motor: `core/utils/ai_search.py`.

Google-style typeahead suggestions while the user types in any search bar.

## Flow

```
[Search input data-tf-ai-search="public"]
        │
        ▼ focus / input (debounced 220ms)
[tf-ai-search.js] ──GET──► /api/search/suggest/?q=…&scope=…
        │                        │
        │                        ▼
        │              [core/utils/ai_search.py]
        │                 ORM match + optional Groq tip
        ▼
[Floating panel on document.body]
  • Connected to orange search shell when in navbar
  • Product cards: thumbnail, price, company/category chips
```

## Files

| Layer | Path | Role |
|-------|------|------|
| Client JS | `static/js/tf-ai-search.js` | Bind inputs, fetch API, render panel, keyboard nav |
| Client CSS | `static/css/tf-ai-search.css` | Connected shell + product card layout |
| Assets include | `templates/core/includes/tf_ai_search_assets.html` | CSS/JS + `TF_AI_SEARCH_URL` |
| API view | `core/views/home_map.py` → `api_search_suggest` | Auth by scope, rate limits, JSON response |
| Engine | `core/utils/ai_search.py` | `search_public`, `search_buyer`, `search_seller`, `search_admin` |
| URL | `core/urls.py` | `api/search/suggest/` |
| Tests | `core/tests/test_ai_search.py` | Public/seller API smoke tests |

## Template integration

Add `data-tf-ai-search` to any search input:

```html
<input type="search" name="buscar" data-tf-ai-search="public" autocomplete="off">
```

Scopes:

- `public` — catalog (home, marketplace navbar, guest)
- `buyer` — authenticated buyer navbar; empty query may return personalized picks
- `seller` — seller portal (requires seller auth)
- `admin` — staff product lookup

Include assets once per page (navbars already do this):

```django
{% include "core/includes/tf_ai_search_assets.html" %}
```

Re-init after dynamic DOM:

```javascript
window.TFAiSearch.init(document.getElementById('root'));
```

## API response shape

```json
{
  "ok": true,
  "query": "laptop",
  "scope": "public",
  "suggestions": [
    {
      "type": "product",
      "label": "Laptop Pro 15",
      "url": "/catalogo/?buscar=Laptop+Pro+15",
      "icon": "inventory_2",
      "score": 100,
      "image_url": "/static/…",
      "meta": {
        "sku": "LP-15",
        "company": "Search Co",
        "category": "Electronics",
        "price": "999.00",
        "currency": "USD"
      }
    }
  ],
  "tip": "",
  "related": [],
  "ai_enabled": false
}
```

## Visual behavior (navbar)

1. Panel is portaled to `<body>` so parent `overflow: hidden` does not clip it.
2. When open, the orange shell (`.search-bar` / `.tf-hdr-search`) gets `.is-suggesting`:
   - Bottom corners flatten
   - Panel attaches flush below with shared orange border (no gap / double line)

## Optional Groq enrichment

When `GROQ_API_KEY` is set, queries with 2+ characters may include:

- `tip` — one helpful sentence
- `related` — up to 4 related search phrases

Local ORM suggestions work without Groq.

## i18n

Client strings use `window.TF_I18N` keys (`aiSearchProducts`, `aiSearchPopular`, …) from `core/context_processors.tf_i18n`.

## Extending

1. Add a new scope in `ai_search.py` (`search_*` + branch in `build_search_response`).
2. Allow the scope in `api_search_suggest` (auth rules).
3. Map `data-tf-ai-search="your_scope"` on the input.
4. Optionally extend `groupLabel()` and item rendering in `tf-ai-search.js`.
