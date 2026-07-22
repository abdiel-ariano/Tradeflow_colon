# Code quality and change documentation

This document defines the minimum quality contract for new TradeFlow Colón
changes. It applies to application code, tests, configuration, and operational
documentation.

## 1. Python standard

- Follow PEP 8 for layout, imports, naming, whitespace, and readable functions.
- Follow PEP 257 for modules, classes, public methods, tests, and commands.
- Prefer lines of 79 characters or fewer in new Python code.
- Use descriptive names that express business intent.
- Keep views thin by moving reusable logic to `core/utils/` or a focused
  service module.
- Document security-sensitive decisions and failure behavior.
- Do not reformat unrelated legacy code in a focused change.

## 2. TypeScript and frontend standard

PEP 8 is specific to Python. TypeScript must instead pass the project's strict
TypeScript check and Vite production build:

```bash
cd frontend/admin-saas
npm ci
npm run build
```

Frontend state must reflect confirmed server state. A failed HTTP response must
never produce a success notification or an optimistic status transition.
Actions that modify business data must also prevent accidental duplicate
submissions.

## 3. Tests and CI

Each behavior change must include the narrowest useful regression test.

Before merging:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.tests.test_saas_admin_api
```

The GitHub workflow also runs Bandit and `pip-audit`. Security or test failures
must be corrected or documented before a pull request is ready.

## 4. Documentation required for changes

A pull request description must state:

1. The problem and root cause.
2. The files and behavior changed.
3. User, security, and operational impact.
4. Tests and build commands executed.
5. Deployment or rollback instructions, when applicable.

New settings must be added to `.env.example`. New operational procedures must
be added to the corresponding runbook under `docs/`.

## 5. SaaS action error contract

As of 2026-07-22, approving or rejecting a SaaS commercial request follows this
contract:

- Only a successful API response may update the row to approved or rejected.
- API errors display an error notification.
- The dashboard reloads authoritative server data after success or failure.
- Action buttons are disabled while a request is being processed.
- Invalid actions, unknown request IDs, and non-POST methods have regression
  coverage in `core/tests/test_saas_admin_api.py`.

This rule prevents the interface from reporting a successful business change
when the database was not updated.
