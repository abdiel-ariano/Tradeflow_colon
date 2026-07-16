#!/usr/bin/env python3
"""Audit and auto-fix missing documentation headers in TradeFlow.

Scans Python, JS, CSS, and templates under the marketplace tree so DOC
coverage stays consistent without hand-editing every file.

Usage:
    python3 scripts/document_codebase.py audit
    python3 scripts/document_codebase.py fix [--dry-run]
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {'migrations', '__pycache__', 'node_modules', '.git', 'staticfiles'}
PYTHON_ROOTS = [ROOT / 'core', ROOT / 'tradeflow_colon']
JS_DIR = ROOT / 'static' / 'js'
CSS_DIR = ROOT / 'static' / 'css'
TEMPLATE_DIR = ROOT / 'templates'


def _should_skip(path: Path) -> bool:
    """Return True if any path segment is in SKIP_DIRS."""
    return any(part in SKIP_DIRS for part in path.parts)


def _humanize_name(name: str) -> str:
    """Turn snake_case identifiers into spaced words for guessed docs."""
    return name.replace('_', ' ').strip()


def _guess_python_module_doc(path: Path) -> str:
    """Infer a one-line module docstring from file location and name."""
    rel = path.relative_to(ROOT).as_posix()
    if 'tests/test_' in rel:
        test_name = path.stem.replace('test_', '').replace('_', ' ')
        return f'Tests for {test_name}.'
    if rel.startswith('core/management/commands/'):
        cmd = path.stem.replace('_', ' ')
        return f'Django management command: {cmd}.'
    if rel.startswith('core/templatetags/'):
        return f'Django template tags/filters — {path.stem}.'
    if rel.startswith('core/middleware/'):
        return f'Django middleware — {path.stem.replace("_", " ")}.'
    if rel.startswith('core/utils/'):
        return f'Utility module — {path.stem.replace("_", " ")}.'
    if rel.startswith('core/views'):
        return f'View handlers — {path.stem.replace("_", " ")}.'
    if path.name == 'urls.py':
        return 'URL routing table for this package.'
    if path.name == 'models.py':
        return 'Django ORM models for the core domain.'
    if path.name == 'forms.py':
        return 'Django forms for buyer, seller, and admin flows.'
    if path.name == 'admin.py':
        return 'Django admin registrations.'
    if path.name == '__init__.py':
        return f'Package marker for {path.parent.relative_to(ROOT).as_posix()}.'
    return f'Module {rel}.'


def _guess_function_doc(name: str, module_path: str) -> str:
    """Infer a one-line function docstring from naming conventions."""
    if name.endswith('_view'):
        action = _humanize_name(name[:-5])
        return f'HTTP view: {action}.'
    if name.startswith('api_'):
        return f'JSON API endpoint: {_humanize_name(name[4:])}.'
    if name.startswith('seller_'):
        return f'Seller portal view: {_humanize_name(name[7:])}.'
    if module_path.endswith('views.py'):
        return f'View handler: {_humanize_name(name)}.'
    return f'{_humanize_name(name).capitalize()}.'


def _has_module_docstring(text: str) -> bool:
    """Return True if the file already starts with a string literal docstring."""
    stripped = text.lstrip()
    for prefix in ('"""', "'''", 'r"""', "r'''"):
        if stripped.startswith(prefix):
            return True
    return False


def _python_files() -> list[Path]:
    """Collect project Python files under PYTHON_ROOTS, skipping SKIP_DIRS."""
    files: list[Path] = []
    for base in PYTHON_ROOTS:
        if not base.exists():
            continue
        for path in base.rglob('*.py'):
            if _should_skip(path):
                continue
            files.append(path)
    return sorted(files)


def _parse_functions(path: Path) -> list[tuple[str, int, bool]]:
    """List public functions with lineno and whether a docstring exists."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith('_'):
                continue
            out.append((node.name, node.lineno, ast.get_docstring(node) is not None))
    return out


def audit() -> int:
    """Print missing-doc counts across Python, JS, CSS, and templates.

    Returns the total issue count (0 means fully documented).
    """
    issues = 0
    py_missing_mod: list[str] = []
    py_missing_fn: list[str] = []
    for path in _python_files():
        text = path.read_text(encoding='utf-8', errors='replace')
        rel = path.relative_to(ROOT).as_posix()
        if not _has_module_docstring(text):
            py_missing_mod.append(rel)
            issues += 1
        for name, line, has_doc in _parse_functions(path):
            if not has_doc:
                py_missing_fn.append(f'{rel}:{line} {name}()')
                issues += 1

    js_missing: list[str] = []
    if JS_DIR.exists():
        for path in sorted(JS_DIR.glob('*.js')):
            head = path.read_text(encoding='utf-8', errors='replace')[:120].lstrip()
            if not head.startswith('/**') and not head.startswith('/*'):
                js_missing.append(path.relative_to(ROOT).as_posix())
                issues += 1

    css_missing: list[str] = []
    if CSS_DIR.exists():
        for path in sorted(CSS_DIR.glob('*.css')):
            head = path.read_text(encoding='utf-8', errors='replace')[:80].lstrip()
            if not head.startswith('/*'):
                css_missing.append(path.relative_to(ROOT).as_posix())
                issues += 1

    tpl_missing: list[str] = []
    if TEMPLATE_DIR.exists():
        for path in sorted(TEMPLATE_DIR.rglob('*.html')):
            text = path.read_text(encoding='utf-8', errors='replace')
            stripped = text.lstrip()
            has_header = (
                stripped.startswith('{% comment %}')
                or stripped.startswith('{#')
                or stripped.startswith('<!--')
            )
            if not has_header and stripped.startswith('{% extends'):
                # Comment may legally sit on line 2 after extends
                second = stripped.split('\n', 2)[1].strip() if '\n' in stripped else ''
                has_header = second.startswith('{% comment %}') or second.startswith('{#')
            if not has_header:
                tpl_missing.append(path.relative_to(ROOT).as_posix())
                issues += 1

    print('=== Documentation audit ===')
    print(f'Python modules missing docstring: {len(py_missing_mod)}')
    for m in py_missing_mod:
        print(f'  - {m}')
    print(f'Python public functions missing docstring: {len(py_missing_fn)}')
    for f in py_missing_fn[:30]:
        print(f'  - {f}')
    if len(py_missing_fn) > 30:
        print(f'  ... and {len(py_missing_fn) - 30} more')
    print(f'JS files missing header: {len(js_missing)}')
    for m in js_missing:
        print(f'  - {m}')
    print(f'CSS files missing header: {len(css_missing)}')
    for m in css_missing:
        print(f'  - {m}')
    print(f'Templates missing header comment: {len(tpl_missing)}')
    for m in tpl_missing[:20]:
        print(f'  - {m}')
    if len(tpl_missing) > 20:
        print(f'  ... and {len(tpl_missing) - 20} more')
    print(f'Total issues: {issues}')
    return issues


def _insert_module_docstring(text: str, doc: str) -> str:
    """Prepend a module docstring after shebang/coding cookies if missing."""
    if _has_module_docstring(text):
        return text
    block = f'"""\n{doc}\n"""\n'
    lines = text.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#!') or stripped.startswith('# -*-') or stripped.startswith('# coding'):
            insert_at = i + 1
            continue
        break
    return ''.join(lines[:insert_at]) + block + ''.join(lines[insert_at:])


def _insert_function_docstrings(text: str, path: Path) -> str:
    """Insert guessed one-line docs on public functions that lack them."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    lines = text.splitlines(keepends=True)
    rel = path.relative_to(ROOT).as_posix()
    inserts: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith('_'):
            continue
        if ast.get_docstring(node):
            continue
        doc = _guess_function_doc(node.name, rel)
        indent = ' ' * (getattr(node, 'col_offset', 0) or 0)
        if not indent:
            # Estimate from source line
            line_idx = node.lineno - 1
            if line_idx < len(lines):
                indent = re.match(r'\s*', lines[line_idx]).group(0)
        block = f'{indent}    """{doc}"""\n'
        inserts.append((node.body[0].lineno - 1, block))
    if not inserts:
        return text
    for line_no, block in sorted(inserts, key=lambda x: x[0], reverse=True):
        lines.insert(line_no, block)
    return ''.join(lines)


def _js_header(path: Path) -> str:
    """Build a JS block-comment header naming the TradeFlow client script."""
    name = path.stem.replace('_', ' ')
    return (
        f'/**\n'
        f' * TradeFlow Colón — {name}\n'
        f' * Client script: {path.relative_to(ROOT).as_posix()}\n'
        f' */\n'
    )


def _css_header(path: Path) -> str:
    """Build a CSS block-comment header naming the stylesheet."""
    name = path.stem.replace('_', ' ')
    return (
        f'/*\n'
        f' * TradeFlow Colón — {name}\n'
        f' * Stylesheet: {path.relative_to(ROOT).as_posix()}\n'
        f' */\n\n'
    )


def _template_header(path: Path) -> str:
    """Build a Django comment header naming the template relative path."""
    rel = path.relative_to(TEMPLATE_DIR).as_posix()
    return f'{{% comment %}}Template: {rel} — review purpose and context vars.{{% endcomment %}}\n'


def _apply_template_header(text: str, path: Path) -> str:
    """Insert a header without breaking Django's extends-first rule."""
    stripped = text.lstrip()
    if stripped.startswith('{% comment %}') or stripped.startswith('{#') or stripped.startswith('<!--'):
        return text
    header = _template_header(path)
    if stripped.startswith('{% extends'):
        end = stripped.find('%}')
        if end != -1:
            extends_line = stripped[: end + 2]
            remainder = stripped[end + 2 :].lstrip('\n')
            return extends_line + '\n' + header + remainder
    return header + text


def fix(dry_run: bool = False) -> int:
    """Insert missing headers/docstrings; optionally report without writing.

    Returns the number of files that would change or were written.
    """
    changed = 0
    for path in _python_files():
        original = path.read_text(encoding='utf-8', errors='replace')
        updated = original
        if not _has_module_docstring(updated):
            updated = _insert_module_docstring(updated, _guess_python_module_doc(path))
        updated = _insert_function_docstrings(updated, path)
        if updated != original:
            changed += 1
            if not dry_run:
                path.write_text(updated, encoding='utf-8')
            print(f'[python] {path.relative_to(ROOT)}')

    if JS_DIR.exists():
        for path in sorted(JS_DIR.glob('*.js')):
            text = path.read_text(encoding='utf-8', errors='replace')
            head = text.lstrip()[:80]
            if head.startswith('/**') or head.startswith('/*'):
                continue
            updated = _js_header(path) + text
            changed += 1
            if not dry_run:
                path.write_text(updated, encoding='utf-8')
            print(f'[js] {path.relative_to(ROOT)}')

    if CSS_DIR.exists():
        for path in sorted(CSS_DIR.glob('*.css')):
            text = path.read_text(encoding='utf-8', errors='replace')
            if text.lstrip().startswith('/*'):
                continue
            updated = _css_header(path) + text
            changed += 1
            if not dry_run:
                path.write_text(updated, encoding='utf-8')
            print(f'[css] {path.relative_to(ROOT)}')

    if TEMPLATE_DIR.exists():
        for path in sorted(TEMPLATE_DIR.rglob('*.html')):
            text = path.read_text(encoding='utf-8', errors='replace')
            updated = _apply_template_header(text, path)
            if updated == text:
                continue
            changed += 1
            if not dry_run:
                path.write_text(updated, encoding='utf-8')
            print(f'[template] {path.relative_to(ROOT)}')

    mode = 'would change' if dry_run else 'changed'
    print(f'\n{mode} {changed} files')
    return changed


def main() -> int:
    """Parse CLI args and run audit or fix; exit 1 when audit finds issues."""
    parser = argparse.ArgumentParser(description='TradeFlow documentation audit/fix')
    parser.add_argument('command', choices=['audit', 'fix'])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.command == 'audit':
        return 0 if audit() == 0 else 1
    fix(dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())
