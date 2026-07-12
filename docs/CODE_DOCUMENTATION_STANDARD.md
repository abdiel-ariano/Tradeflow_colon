# Code documentation standard — TradeFlow Colón

Every source file in this repository must be understandable without tribal knowledge.
Follow these rules for **all new and modified code**.

## Python (`.py`)

### Module docstring (required, first statement)

```python
"""
Short title — what this module does.

Optional: consumers, related URLs, env vars, side effects.
"""
```

### Public functions, classes, methods (required)

- One-line summary for simple helpers.
- Google-style sections (`Args`, `Returns`, `Raises`) when behavior is non-obvious.

```python
def build_search_response(scope: str, query: str, request, limit: int = 8) -> dict:
    """Assemble JSON for GET /api/search/suggest/."""
```

### Private helpers (`_prefix`)

- Docstring when logic is non-obvious or security-sensitive.
- Inline comment for a single tricky line is enough for trivial helpers.

### Django views

- Docstring: purpose, HTTP methods, role decorator, template name.
- Section banners in large files (`core/views.py`) group related views.

### Tests

- Module docstring: what behavior is covered.
- Test method name should describe the case; add docstring if the name is not enough.

## JavaScript (`.js`)

### File header (required)

```javascript
/**
 * TradeFlow Colón — <feature>
 * Purpose, DOM hooks (data-* / ids), Django endpoints used.
 */
```

### Functions

- JSDoc for exported/public helpers and non-trivial closures.
- Comment non-obvious DOM or CSP constraints.

## CSS (`.css`)

### File header (required)

```css
/*
 * TradeFlow Colón — <component/page>
 * Loaded by: <template or global>
 */
```

### Sections

- Use `/* ── Section name ── */` between major blocks in files > 100 lines.

## Django templates (`.html`)

### File comment (required)

```django
{% comment %}Purpose — extends/includes, main context vars{% endcomment %}
```

**Rule:** If the file uses `{% extends %}`, that tag must remain first — put the
comment on the **second line** immediately after `extends`.

Or `{# short purpose #}` for small includes without `extends`.

### Blocks

- Comment non-obvious `{% if %}` branches (role gates, feature flags).

## Running the audit

```bash
python3 scripts/document_codebase.py audit
python3 scripts/document_codebase.py fix --dry-run
python3 scripts/document_codebase.py fix
```

`fix` adds missing module/file headers and one-line docstrings where safe.
**Review the diff** — refine auto-generated text for public APIs.

## Related docs

- `docs/CODEBASE_DIAGNOSTIC.md` — project map
- `docs/AI_SEARCH.md` — search typeahead stack
- `docs/TEMPLATES.md` — template catalog
