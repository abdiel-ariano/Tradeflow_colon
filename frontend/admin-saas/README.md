# Panel Admin SaaS (React)

Stack: React 19, TypeScript, Tailwind v4, shadcn-style UI, Recharts, Sonner.

## Desarrollo

```bash
cd frontend/admin-saas
npm install
npm run dev
```

## Build para Django

```bash
npm run build
```

Genera assets en `static/admin-saas/` (servidos en `/saas/`).

Datos: `GET /api/admin/saas-stats/` (ORM/Supabase). Acciones: `POST /api/admin/saas-requests/<pk>/`.
