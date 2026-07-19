# Ciberseguridad en TradeFlow Colón  
### Guía sencilla para el equipo, inversores y personas no técnicas

**Última actualización:** julio 2026  
**Para quién es este documento:** cualquiera que necesite entender *qué protegemos, por qué importa y qué ya está hecho*, sin ser experto en seguridad.

---

## 1. ¿Qué es la ciberseguridad aquí?

En TradeFlow, ciberseguridad significa **proteger**:

1. **A las personas** — compradores, vendedores y staff (sus datos, contraseñas, ubicación, correos).  
2. **Al negocio** — pedidos, pagos, catálogo, cuentas de empresa.  
3. **A la plataforma** — que nadie use el sistema para atacar otros sitios o robar información.

No se trata solo de “no nos hackeen”. También incluye **privacidad** (usar los datos con consentimiento y transparencia) y **confianza** (que un inversor o un cliente B2B vea que el producto se tomó en serio).

### Analogía rápida

Imagina un almacén en la Zona Libre:

| En el almacén físico | En TradeFlow (digital) |
|----------------------|-------------------------|
| Candado en la puerta | Contraseña + verificación de email |
| Solo el dueño entra a la oficina | Roles: comprador / vendedor / admin |
| Cámaras y bitácora | Registros de seguridad y alertas |
| No dejar la llave bajo el felpudo | No guardar secretos en texto plano |
| No abrir la puerta trasera a desconocidos | No dejar que el servidor llame a sitios peligrosos |

---

## 2. Dos “mapas” que usamos (en palabras simples)

### OWASP Top 10
Es una lista mundial de los **10 tipos de fallos más comunes** en aplicaciones web (como dejar puertas abiertas, mezclar datos de un usuario con otro, o instalar software con agujeros conocidos).

TradeFlow se endureció siguiendo esa lista como checklist práctico.

### GDPR (y privacidad en general)
Son reglas (sobre todo europeas, pero buenas prácticas globales) sobre **cómo tratar datos personales**:

- Pedir permiso cuando hace falta.  
- Explicar para qué se usan.  
- Dejar que la persona **exporte** o **borre/anonimice** sus datos.  
- No mandar marketing sin consentimiento.

---

## 3. Glosario mínimo (conceptos que verás abajo)

| Término | Significado simple |
|---------|-------------------|
| **Autenticación** | Probar que *eres tú* (usuario + contraseña, o código). |
| **Autorización** | Aunque hayas entrado, *qué puedes hacer* (¿solo tu tienda? ¿todo el admin?). |
| **Hash** | Transformar un secreto (código OTP, contraseña) en una huella irreversible. Si alguien roba la base de datos, no ve el código original. |
| **Cifrado / encriptar** | Guardar un dato de forma ilegible sin una llave (ej. secreto MFA del staff). |
| **MFA / 2FA** | Segundo factor: además de la contraseña, un código de una app (Authenticator). |
| **CSRF** | Ataque que engaña tu navegador para que haga una acción sin que tú quieras. Se evita con tokens en formularios. |
| **XSS** | Inyectar código malicioso en una página para robar sesiones. Se evita escapando/filtrando HTML. |
| **Inyección SQL** | Meter comandos peligrosos en consultas a la base de datos. Django ORM y restricciones SELECT ayudan. |
| **SSRF** | Engañar al servidor para que llame a direcciones internas (ej. metadata de la nube). Se valida cada URL de salida. |
| **Cookie** | Pequeño dato en el navegador (sesión, idioma). Las “esenciales” hacen funcionar login/carrito; otras piden preferencia. |
| **Consentimiento** | Permiso explícito del usuario (privacidad, marketing, GPS). |
| **OTP** | Código de un solo uso (ej. verificar email). |
| **Webhook** | Aviso automático que TradeFlow envía a otro sistema (ej. logística del vendedor). |
| **Dependencia / CVE** | Librería de terceros; un CVE es un agujero de seguridad conocido en ella. |
| **Sentry** | Servicio opcional que avisa cuando la app falla en producción (sin enviar datos personales por defecto). |

---

## 4. Quién es quién en la plataforma

| Rol | Qué puede hacer (idea general) | Riesgo si se rompe el control |
|-----|--------------------------------|-------------------------------|
| **Comprador** | Catálogo, carrito, pedidos propios | Ver pedidos de otros |
| **Vendedor** | Su tienda, productos, ventas | Ver o editar otra empresa |
| **Staff / admin** | Revisar solicitudes, estados de órdenes | Acceso total al negocio |

La seguridad combina: **probar identidad** + **limitar permisos** + **registrar lo sensible**.

---

## 5. Qué protegemos (capa por capa)

### 5.1 Entrar a la cuenta (autenticación)

**Problema:** alguien adivina o roba una contraseña.  
**Qué hace TradeFlow:**

- Contraseñas fuertes y guardadas con **Argon2** (estándar moderno; no se guarda la contraseña en claro).  
- Tras varios intentos fallidos, **bloqueo temporal** (django-axes): evita “probar mil contraseñas”.  
- Verificación de email con **OTP** (código de un solo uso).  
- Los códigos OTP y los enlaces de “olvidé mi contraseña” se guardan como **hash**, no en texto legible.  
- Login social (Google, etc.) no se activa de forma insegura en un enlace “suelto”.

**En la práctica:** aunque alguien copie la base de datos, no debería poder leer los códigos de verificación como si fueran un Post-it.

---

### 5.2 Segundo factor para el equipo interno (MFA del staff)

**Problema:** la cuenta de un administrador vale mucho; una sola contraseña no basta.  
**Qué hace TradeFlow:**

- El **staff/admin** debe activar una app autenticadora (Google Authenticator, 1Password, etc.).  
- Tras el login, pide un **código de 6 dígitos** (o un **código de respaldo** de un solo uso).  
- Los códigos de respaldo sirven si pierdes el teléfono o si se rota la “llave maestra” del servidor (`SECRET_KEY`).  
- En modo demo para Expo (`EXPO_DEMO_MODE`) este requisito se relaja a propósito para no bloquear demos.  
- Si alguien se queda fuera del todo, operaciones puede resetear MFA con un comando controlado (`reset_staff_mfa`).

**En la práctica:** robar solo la contraseña del admin no alcanza para entrar al panel.

---

### 5.3 Permisos y acciones peligrosas

**Problema:** un enlace malicioso o un usuario “se cuela” en funciones de admin.  
**Qué hace TradeFlow:**

- Cada vista importante comprueba el **rol**.  
- Cambiar el estado de un pedido o aprobar una solicitud de acceso exige **POST + confirmación** (no basta con abrir un enlace del correo por accidente).  
- Un vendedor solo ve **su** empresa y **sus** datos (tenancy).

**Concepto CSRF (simple):**  
Sin protección, un sitio malo podría decirle a tu navegador: “mientras estás logueado en TradeFlow, cambia este pedido”. El token CSRF en los formularios evita eso.

---

### 5.4 Privacidad y GDPR (datos personales)

**Problema:** usar datos sin permiso, o no poder borrarlos.  
**Qué hace TradeFlow:**

| Momento | Control |
|---------|---------|
| Registro | Aceptar política de privacidad (obligatorio) |
| Marketing / carrito abandonado | Solo si marcó **opt-in** de marketing |
| Checkout | Casilla de **consentimiento de ubicación GPS** antes de guardar coordenadas |
| Chat con IA (Groq) | Aviso de que el mensaje puede ir a un proveedor de IA |
| Mi perfil | Exportar datos (JSON) y **anonimizar** la cuenta |
| Cookies | Banner: esenciales siempre; preferencias de interfaz solo si el usuario las acepta |

**Anonimizar** no es “borrar el historial contable a ciegas”: limpia lo personal identificable y deja la cuenta inutilizable para login normal.

---

### 5.5 Cookies (sin tecnicismos)

- **Esenciales:** login, carrito, seguridad. Sin ellas la tienda no funciona bien.  
- **Preferencias:** recordar idioma o avisos cerrados (solo first-party; TradeFlow no pone trackers de publicidad de terceros hoy).  
- El usuario puede elegir **“Solo esenciales”** o **guardar preferencias**.

---

### 5.6 Subida de archivos (logos, pruebas de pago, fotos de producto)

**Problema:** alguien sube un “.jpg” que en realidad es un programa o un PDF falso.  
**Qué hace TradeFlow:**

- Revisa extensión, tamaño y “firma” del archivo (magic bytes).  
- Las imágenes se validan de verdad (decodificación), no solo por el nombre.  
- Si la imagen de producto es inválida, **no se guarda** el producto con ese archivo.

---

### 5.7 Consultas a la base de datos y Analytics

**Problema:** una consulta maliciosa borra tablas o lee de más.  
**Qué hace TradeFlow:**

- El día a día usa el **ORM de Django** (no inventa SQL a mano en cada vista).  
- En Analytics, el SQL permitido es básicamente de **lectura (SELECT)**.  
- Las tablas HTML se arman escapando el contenido (evita XSS al mostrar datos).

---

### 5.8 Llamadas salientes y webhooks (SSRF)

**Problema:** un vendedor configura una URL de webhook hacia `http://169.254.169.254` (metadata de la nube) o hacia la red interna.  
**Qué hace TradeFlow:**

- Valida que la URL sea pública y razonable **antes** de guardar y **antes** de llamar.  
- “Clava” la IP resuelta (DNS-pin) para dificultar trucos de redirección DNS.  
- Firma los webhooks logísticos para que el receptor pueda comprobar que el mensaje viene de TradeFlow.

---

### 5.9 “¿El servidor está vivo?” sin filtrar secretos

**Problema:** un endpoint de salud que publica configuración interna.  
**Qué hace TradeFlow:**

- `/health/ready/` público solo dice lo mínimo (¿responde la DB?).  
- El detalle fino queda para staff o un token secreto de operaciones.

---

### 5.10 Software de terceros y revisión automática

**Problema:** una librería vieja tiene un agujero publicado.  
**Qué hace TradeFlow:**

- En cada cambio, CI ejecuta:
  - **Bandit** — busca patrones peligrosos en el código Python.  
  - **pip-audit** — revisa vulnerabilidades conocidas en dependencias.  
- **Dependabot** propone actualizaciones.  
- Se actualizaron piezas críticas (ej. Django, Pillow) cuando salieron avisos.

---

### 5.11 Registros, retención y alertas

**Problema:** no saber qué pasó, o guardar logs para siempre.  
**Qué hace TradeFlow:**

- Middleware de eventos de seguridad.  
- Comando para **purgar logs viejos** (`purge_security_logs`, tipicamente 90 días).  
- **Sentry opcional:** si se configura `SENTRY_DSN`, avisa errores en producción sin enviar PII por defecto.

---

### 5.12 Modo demo Expo (`EXPO_DEMO_MODE`)

**Para qué sirve:** demos a inversores / Expo sin trabar el flujo con todos los candados de producción.

**Importante:**

- Sigue **soportado**.  
- En revisión de release solo **advierte**, no bloquea el deploy.  
- Mientras esté activo, **no fuerza** MFA al staff (para no romper la demo).  
- En un entorno **solo producción real**, conviene apagarlo.

---

## 6. Mapa visual: del usuario al riesgo

```text
[Usuario en el navegador]
        │
        ▼
 Cookie banner / HTTPS / cabeceras de seguridad
        │
        ▼
 Login + (staff) MFA
        │
        ▼
 ¿Qué rol eres? ──► Comprador / Vendedor / Admin
        │
        ▼
 Acciones (carrito, pedido, admin) + CSRF
        │
        ▼
 Validaciones (archivos, GPS consent, marketing opt-in)
        │
        ▼
 Base de datos (hashes, sin secretos en claro)
        │
        ▼
 Salidas (email, webhooks) con controles SSRF
        │
        ▼
 Logs / Sentry / retención
```

---

## 7. Tabla resumen “amenaza → protección”

| Si alguien intenta… | TradeFlow responde con… |
|---------------------|-------------------------|
| Adivinar contraseñas | Bloqueo tras fallos + contraseñas hasheadas |
| Usar un OTP robado de la DB | OTP guardado como hash |
| Entrar como admin solo con password | MFA + códigos de respaldo |
| Cambiar un pedido con un enlace del correo | Confirmación POST + CSRF |
| Ver datos de otra empresa | Controles de rol / tenancy |
| Mandarte spam sin permiso | Marketing solo con opt-in |
| Guardar tu GPS sin avisar | Consentimiento en checkout |
| Subir un archivo malicioso | Validación de tipo/tamaño/contenido |
| Apuntar un webhook a la red interna | Validación SSRF + DNS-pin |
| Meter HTML peligroso en Analytics | Escape / HTML seguro |
| Usar librerías con CVE conocidos | pip-audit + actualizaciones |
| Enterarse de la config por `/health` | Health público mínimo |

---

## 8. Qué ya está hecho vs qué sigue siendo “humano / legal / ops”

### Hecho en el producto (código)
- Autenticación endurecida, OTP/reset hasheados  
- MFA staff + backup codes + recuperación ops  
- Consentimientos (privacidad, marketing, GPS, cookies, aviso IA)  
- Export / anonimizar en perfil  
- Validación de uploads, SSRF, SQL de solo lectura en Analytics  
- Hardening de admin (POST/confirm)  
- CI de seguridad, docs operativas  

### Sigue fuera del código (o es decisión de despliegue)
- Firmar contratos DPA con proveedores (Supabase, Resend, Groq, etc.)  
- Activar `SENTRY_DSN` real en producción  
- Programar el cron de purga de logs en el hosting  
- Apagar `EXPO_DEMO_MODE` cuando el entorno sea solo producción  
- Antivirus de archivos a nivel empresa (ClamAV u otro), si se exige  
- Elegir y migrar base de datos si el free de Supabase ya no alcanza (decisión de infra, no de este doc)

---

## 9. Cómo hablarlo en una demo o reunión (30 segundos)

> “TradeFlow no solo ‘tiene login’. Protegemos cuentas con bloqueo de fuerza bruta y códigos hasheados; el staff usa segundo factor; los datos personales piden consentimiento (privacidad, marketing, GPS); no dejamos que webhooks apunten a redes internas; validamos archivos; y el pipeline revisa vulnerabilidades en dependencias. El modo Expo existe para demos y se advierte aparte del endurecimiento de producción.”

---

## 10. Dónde profundizar (documentos técnicos)

| Documento | Contenido |
|-----------|-----------|
| `SECURITY.md` | Cómo reportar vulnerabilidades + tabla OWASP/GDPR |
| `docs/SECURITY_OPS.md` | Runbook ops (flags, cron, rotación de secretos, MFA recovery) |
| `docs/GDPR_DPA_DPIA.md` | Inventario de proveedores y checklist legal |

**Contacto de seguridad:** ver `SECURITY.md` (`security@tradeflow.pa`).

---

## 11. Mensaje final

La ciberseguridad en TradeFlow no es un interruptor único ni una promesa de “imposible de atacar”. Es un **conjunto de capas** — como varias cerraduras y cámaras en un almacén — pensadas para:

1. Hacer **difícil** el abuso cotidiano.  
2. **Limitar el daño** si algo falla.  
3. Respetar a las **personas** dueñas de los datos.  
4. Poder **demostrar** a terceros que hay un estándar serio (OWASP + buenas prácticas GDPR).

Si algo de este documento no queda claro, la pregunta correcta no es “¿qué CVE es?”, sino:  
**“¿Qué mal queremos evitar y cómo se nota eso en el producto?”**
