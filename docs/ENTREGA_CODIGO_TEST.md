# Entrega del código para evaluación externa

Guía para compartir el repositorio **sin exponer secretos de producción** ni
cuentas administrativas preconfiguradas.

---

## 1. Qué incluir en el paquete

Exporte solo el árbol versionado en git:

```bash
git archive --format=zip HEAD -o tradeflow-colon-eval.zip
```

**No incluya** (aunque existan en su máquina local):

| Archivo / carpeta | Motivo |
|-------------------|--------|
| `.env` | `SECRET_KEY`, `DATABASE_URL`, API keys reales |
| `db.sqlite3` | Datos y sesiones locales |
| `media/` | Uploads locales |
| `android/*.keystore`, `*.jks` | Firma de APK |
| `node_modules/`, `.venv/` | Dependencias (reinstalar) |

---

## 2. Configuración mínima del evaluador

```bash
cp .env.example .env
# Completar SECRET_KEY (generar una nueva) y DEBUG=True
# Opcional: DATABASE_URL vacío → SQLite local

export DEMO_USER_PASSWORD='clave-local-solo-para-pruebas'
python manage.py migrate
python manage.py cargar_demo
python manage.py runserver
```

- **No hay contraseñas en el repositorio.** `DEMO_USER_PASSWORD` define la clave
  de `demo_buyer` y `demo_seller`.
- **No se crea cuenta admin demo.** Para `/admin/` use
  `python manage.py createsuperuser`.

---

## 3. Cuentas demo incluidas por `cargar_demo`

| Rol | Usuario |
|-----|---------|
| Comprador | `demo_buyer` |
| Vendedor | `demo_seller` |

La contraseña es la que el evaluador definió en `DEMO_USER_PASSWORD`.

---

## 4. Variables sensibles (solo en entorno, nunca en git)

| Variable | Uso |
|----------|-----|
| `SECRET_KEY` | Sesiones Django |
| `DATABASE_URL` | Postgres (Supabase/RDS) |
| `RESEND_API_KEY` | Correo transaccional |
| `GROQ_API_KEY` | Asistente / búsqueda IA |
| `SUPABASE_*` | Storage y Realtime |
| `GOOGLE_CLIENT_*`, `MICROSOFT_*`, `LINKEDIN_*` | OAuth |
| `ANDROID_KEYSTORE_*` | Firma APK (CI) |
| `DEMO_USER_PASSWORD` | Semilla local buyer/seller |

Plantillas vacías: `.env.example`, `.env.demo`.

---

## 5. Comprobaciones antes de enviar

- [ ] `git archive` sin `.env` ni `db.sqlite3`
- [ ] Documentación sin filas de admin ni contraseñas literales
- [ ] Evaluador instruido a usar su propio `.env` y `DEMO_USER_PASSWORD`
- [ ] Sin acceso a Railway / Resend / Supabase / GitHub Secrets de producción

---

## 6. Referencias

- [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md)
- [SECURITY_OPS.md](SECURITY_OPS.md)
- [DEMO_DATA_POLICY.md](DEMO_DATA_POLICY.md)
