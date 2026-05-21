# TradeFlow Colón — Guía de Inicio Rápido

Plataforma de gestión de e-commerce para la Zona Libre de Colón, Panamá.
Desarrollado para **Expo Supérate 2026**.

## Supabase + Gmail (demo inversores)

Configuración en **menos de 10 pasos**: [docs/SUPABASE_GMAIL.md](docs/SUPABASE_GMAIL.md)

```bash
cp .env.example .env
# Rellena DATABASE_URL (Supabase) y EMAIL_HOST_USER / EMAIL_HOST_PASSWORD (Gmail App Password)
python manage.py migrate
python manage.py cargar_demo
python manage.py verify_integrations --email tu@gmail.com
```

---

## Estructura del Proyecto

```
tradeflow_colon/
├── manage.py                    ← Herramienta de comandos Django
├── requirements.txt             ← Dependencias Python
├── db.sqlite3                   ← Base de datos (se crea al migrar)
│
├── tradeflow_colon/             ← Configuración del proyecto
│   ├── settings.py              ← Toda la configuración
│   ├── urls.py                  ← Enrutador principal
│   └── wsgi.py                  ← Servidor de producción
│
├── core/                        ← App principal con toda la lógica
│   ├── models.py                ← Tablas de BD (Cliente, Producto, Orden)
│   ├── views.py                 ← Lógica de cada página
│   ├── forms.py                 ← Formularios con validación
│   ├── urls.py                  ← URLs de la app
│   ├── admin.py                 ← Panel de administración
│   └── migrations/              ← Historial de cambios a la BD
│
├── templates/core/              ← Páginas HTML (Django Templates)
│   ├── base.html                ← Sidebar + Topbar (template padre)
│   ├── login.html               ← Inicio de sesión
│   ├── dashboard.html           ← Panel principal con KPIs
│   ├── ordenes.html             ← Lista de órdenes con filtros
│   ├── nueva_orden_paso1.html   ← Wizard: seleccionar cliente
│   ├── nueva_orden_paso2.html   ← Wizard: seleccionar productos
│   ├── nueva_orden_paso3.html   ← Wizard: confirmar y pagar
│   ├── productos.html           ← Catálogo de productos
│   ├── producto_form.html       ← Crear nuevo producto
│   └── usuarios.html            ← Gestión de usuarios
│
└── static/                      ← Archivos estáticos
    ├── css/
    │   ├── style.css            ← Variables globales + reset
    │   ├── navbar.css           ← Sidebar y topbar
    │   ├── dashboard.css        ← KPI cards y gráficos
    │   ├── ordenes.css          ← Tabla y filtros de órdenes
    │   ├── formularios.css      ← Wizard y formularios
    │   ├── productos.css        ← Grid de catálogo
    │   └── login.css            ← Página de login
    └── js/
        ├── main.js              ← Funciones globales (alertas, sidebar)
        ├── filtros.js           ← Interactividad de la tabla de órdenes
        └── formularios.js       ← Wizard y validación de forms
```

---

## Instalación paso a paso

### 1. Abrir en PyCharm

1. Abre PyCharm
2. `File → Open` → Selecciona la carpeta `tradeflow_colon`
3. PyCharm detectará `manage.py` y te preguntará si configurar Django → **Sí**
4. En `Settings → Languages & Frameworks → Django`:
   - Django project root: `ruta/a/tradeflow_colon`
   - Settings: `tradeflow_colon/settings.py`
   - Manage script: `manage.py`

### 2. Crear entorno virtual

En la terminal de PyCharm (`View → Tool Windows → Terminal`):

```bash
# Crear entorno virtual
python -m venv venv

# Activar (Windows)
venv\Scripts\activate

# Activar (Mac/Linux)
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Crear la base de datos

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Crear superusuario (administrador)

```bash
python manage.py createsuperuser
```
Ingresa usuario, email y contraseña cuando te lo pida.

### 6. Cargar datos de prueba (opcional)

Para tener datos de ejemplo en el dashboard:

```bash
python manage.py shell
```

```python
from core.models import Categoria, Producto, Cliente

# Crear categorías
elec = Categoria.objects.create(nombre="Electrónica", icono="📱")
acc  = Categoria.objects.create(nombre="Accesorios", icono="🎧")

# Crear productos
Producto.objects.create(nombre="Smartphone X12", precio=320, stock=24, categoria=elec)
Producto.objects.create(nombre="Laptop Pro 15",  precio=1250, stock=8, categoria=elec)
Producto.objects.create(nombre="Auriculares BT", precio=89,  stock=50, categoria=acc)
Producto.objects.create(nombre="Smart Watch S3", precio=210, stock=15, categoria=elec)

# Crear clientes
Cliente.objects.create(nombre="María López",  email="maria@email.com", telefono="+507 6100-0001")
Cliente.objects.create(nombre="Carlos Pinto", email="carlos@email.com", telefono="+507 6100-0002")
Cliente.objects.create(nombre="Ana Ramos",    email="ana@email.com",    telefono="+507 6100-0003")

exit()
```

### 7. Iniciar el servidor

```bash
python manage.py runserver
```

Abre el navegador en: **http://127.0.0.1:8000**

---

## URLs del sistema

| URL | Descripción |
|-----|-------------|
| `/login/` | Inicio de sesión |
| `/dashboard/` | Panel principal con KPIs |
| `/ordenes/` | Lista de órdenes con filtros |
| `/ordenes/nueva/` | Wizard: Paso 1 — Cliente |
| `/ordenes/nueva/productos/` | Wizard: Paso 2 — Productos |
| `/ordenes/nueva/confirmar/` | Wizard: Paso 3 — Confirmación |
| `/productos/` | Catálogo de productos |
| `/productos/nuevo/` | Crear nuevo producto |
| `/usuarios/` | Gestión de usuarios (solo admin) |
| `/admin/` | Panel de administración Django |

---

## Paleta de colores oficial

| Variable CSS | Hex | Uso |
|-------------|-----|-----|
| `--color-primary` | `#098698` | Teal — botones, links, activos |
| `--color-secondary` | `#404b57` | Azul grisáceo — sidebar |
| `--color-accent` | `#d9cab3` | Beige arena — detalles |
| `--color-bg` | `#f0f0f0` | Fondo de página |
| `--color-text` | `#2c3e50` | Texto principal |

---

## Preguntas frecuentes

**¿Cómo cambio a PostgreSQL?**
Edita `tradeflow_colon/settings.py` en el bloque `DATABASES` y cambia a PostgreSQL.
Luego instala: `pip install psycopg2-binary`

**¿Cómo agrego un nuevo campo a un modelo?**
1. Edita el modelo en `core/models.py`
2. Ejecuta `python manage.py makemigrations`
3. Ejecuta `python manage.py migrate`

**¿Cómo agrego una nueva página?**
1. Crea la vista en `core/views.py`
2. Agrega la URL en `core/urls.py`
3. Crea el template en `templates/core/`
4. Agrega el item al sidebar en `base.html`

---

*TradeFlow Colón — Expo Supérate 2026 · Panamá*
