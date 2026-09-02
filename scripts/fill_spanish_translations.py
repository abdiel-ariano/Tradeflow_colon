#!/usr/bin/env python3
"""Fill Spanish msgstr entries in locale/es/LC_MESSAGES/django.po."""
from __future__ import annotations

import re
from pathlib import Path

try:
    import polib
except ImportError as exc:  # pragma: no cover
    raise SystemExit('polib required: pip install polib') from exc

ROOT = Path(__file__).resolve().parents[1]
PO_PATH = ROOT / 'locale' / 'es' / 'LC_MESSAGES' / 'django.po'

SPANISH_CHARS = re.compile(r'[áéíóúñÁÉÍÓÚÑ¿¡]')

# Professional SaaS Spanish for English msgids (extend as needed).
EN_TO_ES: dict[str, str] = {
    'Sign in': 'Iniciar sesión',
    'Sign in to your account': 'Inicia sesión en tu cuenta',
    'Sign in — TradeFlow Colón': 'Iniciar sesión — TradeFlow Colón',
    'Sign out': 'Cerrar sesión',
    'Create account': 'Crear cuenta',
    'Create an account': 'Crear una cuenta',
    'Personal information': 'Información personal',
    'Privacy & data': 'Privacidad y datos',
    'Security': 'Seguridad',
    'Your activity': 'Tu actividad',
    'Quick access': 'Acceso rápido',
    'Orders placed': 'Pedidos realizados',
    'Last order:': 'Último pedido:',
    'Active products in catalog': 'Productos activos en catálogo',
    'Registered users': 'Usuarios registrados',
    'Orders in period': 'Pedidos en el período',
    'Go to store': 'Ir a la tienda',
    'My orders': 'Mis pedidos',
    'My Dashboard': 'Mi panel',
    'Products': 'Productos',
    'My sales': 'Mis ventas',
    'Dashboard': 'Panel',
    'Orders': 'Pedidos',
    'Profile sections': 'Secciones del perfil',
    'First name': 'Nombre',
    'Last name': 'Apellido',
    'Email address': 'Correo electrónico',
    'Phone': 'Teléfono',
    'Save changes': 'Guardar cambios',
    'Current password': 'Contraseña actual',
    'New password': 'Nueva contraseña',
    'Confirm new password': 'Confirmar nueva contraseña',
    'Change password': 'Cambiar contraseña',
    'Staff MFA': 'MFA para personal',
    'Configure MFA': 'Configurar MFA',
    'Communication preferences': 'Preferencias de comunicación',
    'Save preferences': 'Guardar preferencias',
    'Export your data': 'Exportar tus datos',
    'Export my data': 'Exportar mis datos',
    'Anonymize account': 'Anonimizar cuenta',
    'Confirmation': 'Confirmación',
    'My Profile': 'Mi perfil',
    'Your email is not verified yet.': 'Tu correo aún no está verificado.',
    'Resend verification email': 'Reenviar correo de verificación',
    'Member since %(joined)s': 'Miembro desde %(joined)s',
    'Activity and shortcuts': 'Actividad y accesos directos',
    'Optional. Used for order updates when provided.': 'Opcional. Se usa para actualizaciones de pedidos cuando se proporciona.',
    'Authenticator app (TOTP) for staff/admin sign-in. Required outside Expo demo mode.': 'Aplicación autenticadora (TOTP) para el acceso de personal/administradores. Obligatoria fuera del modo demo Expo.',
    'Choose whether TradeFlow may send cart reminders and occasional marketplace promotions.': 'Elige si TradeFlow puede enviar recordatorios de carrito y promociones ocasionales del marketplace.',
    'Send me cart reminders and occasional marketplace promotions.': 'Enviarme recordatorios de carrito y promociones ocasionales del marketplace.',
    'Download a JSON copy of your profile, addresses, and orders.': 'Descarga una copia JSON de tu perfil, direcciones y pedidos.',
    'This permanently anonymizes your account. Orders are retained without your personal details. Type <strong>DELETE</strong> to confirm.': 'Esto anonimiza tu cuenta de forma permanente. Los pedidos se conservan sin tus datos personales. Escribe <strong>DELETE</strong> para confirmar.',
    'This anonymizes your account permanently. Continue?': 'Esto anonimizará tu cuenta de forma permanente. ¿Continuar?',
    'Demonstration catalog.': 'Catálogo de demostración.',
    'Companies, inventory, prices, and performance metrics are simulated; they do not yet represent active commercial suppliers.': 'Las empresas, el inventario, los precios y las métricas son simulados; aún no representan proveedores comerciales activos.',
    'Simulated data notice': 'Aviso de datos simulados',
    'Language selection': 'Selección de idioma',
    'Spanish': 'Español',
    'English': 'Inglés',
    'Business verification required': 'Verificación empresarial requerida',
    'Registered legal name': 'Razón social registrada',
    'Sign out': 'Cerrar sesión',
    'Full catalog': 'Catálogo completo',
    'Catalog filters': 'Filtros del catálogo',
    'Filters': 'Filtros',
    'Search': 'Buscar',
    'Category': 'Categoría',
    'All categories': 'Todas las categorías',
    'Apply filters': 'Aplicar filtros',
    'Clear filters': 'Limpiar filtros',
    'Results': 'Resultados',
    'Catalog': 'Catálogo',
    'Deals': 'Ofertas',
    'Best sellers': 'Más vendidos',
    'Featured': 'Destacados',
    'Store': 'Tienda',
    'Buyer': 'Comprador',
    'Seller': 'Vendedor',
    'Administrator': 'Administrador',
    'Pending': 'Pendiente',
    'Paid': 'Pagado',
    'Packed': 'Empacado',
    'Shipped': 'Enviado',
    'Delivered': 'Entregado',
    'Cancelled': 'Cancelado',
    'Awaiting seller': 'En espera del vendedor',
    'Close': 'Cerrar',
    'Cart': 'Carrito',
    'Loading...': 'Cargando...',
    'Processing…': 'Procesando…',
    'No results': 'Sin resultados',
    'Save': 'Guardar',
    'Cancel': 'Cancelar',
    'Delete': 'Eliminar',
    'Edit': 'Editar',
    'View details': 'Ver detalles',
    'Previous': 'Anterior',
    'Next': 'Siguiente',
    'Profile updated successfully.': 'Perfil actualizado correctamente.',
    'Password changed successfully.': 'Contraseña cambiada correctamente.',
    'Communication preferences saved.': 'Preferencias de comunicación guardadas.',
    'Could not change password. Check the fields below.': 'No se pudo cambiar la contraseña. Revisa los campos a continuación.',
    'Current password is incorrect.': 'La contraseña actual es incorrecta.',
    'Password must be at least 8 characters.': 'La contraseña debe tener al menos 8 caracteres.',
    'New passwords do not match.': 'Las contraseñas nuevas no coinciden.',
    'Type DELETE to confirm account anonymization.': 'Escribe DELETE para confirmar la anonimización de la cuenta.',
    'Company registered successfully.': 'Empresa registrada correctamente.',
    'Existing company linked to your account.': 'Empresa existente vinculada a tu cuenta.',
    'Social sign-in is not configured yet.': 'El inicio de sesión social aún no está configurado.',
    'Select how your company will use TradeFlow.': 'Selecciona cómo usará TradeFlow tu empresa.',
    'Verified company': 'Empresa verificada',
    'Business identity approved': 'La identidad empresarial fue aprobada',
    'TradeFlow recorded the review and will enable only the capabilities approved for this company.': 'TradeFlow registró la revisión y habilitará únicamente las capacidades aprobadas para esta empresa.',
    'Continue': 'Continuar',
    'Your company was verified.': 'Tu empresa fue verificada.',
    'Your company was verified. One more access step is still pending.': 'Tu empresa fue verificada. Aún hay un paso de acceso pendiente.',
    'Requires correction': 'Requiere corrección',
    'We could not approve the information': 'No pudimos aprobar la información',
    'Correct information': 'Corregir información',
    'Your application requires correction.': 'Tu solicitud requiere corrección.',
    'Password strength': 'Fortaleza de contraseña',
    'Search mode': 'Modo de búsqueda',
    'AI mode': 'Modo IA',
    'Manufacturers': 'Fabricantes',
    'Worldwide': 'Mundial',
    "women's underwear": 'ropa interior femenina',
    'Frequent searches': 'Búsquedas frecuentes',
    'electronics': 'electrónica',
    'textiles': 'textiles',
    'spare parts': 'repuestos',
    'logistics': 'logística',
    'Featured category': 'Categoría destacada',
    'Verified wholesale products in the Colón Free Zone': 'Productos mayoristas verificados en la Zona Libre de Colón',
    'View all': 'Ver todos',
}


def main() -> int:
    po = polib.pofile(str(PO_PATH))
    filled = 0
    for entry in po:
        if entry.obsolete:
            continue
        msgid = entry.msgid
        if not msgid:
            continue
        if entry.msgstr and not entry.fuzzy:
            continue
        translation = EN_TO_ES.get(msgid)
        if not translation and SPANISH_CHARS.search(msgid):
            translation = msgid
        if translation:
            entry.msgstr = translation
            if 'fuzzy' in entry.flags:
                entry.flags.remove('fuzzy')
            filled += 1
    po.save()
    print(f'Filled {filled} Spanish translations in {PO_PATH}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
