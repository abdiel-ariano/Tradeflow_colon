"""
=============================================================================
core/utils/pdf_generator.py — TradeFlow Colón
Generación de facturas PDF (ReportLab) para órdenes.
=============================================================================
"""
from __future__ import annotations

import io
from pathlib import Path

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.models import Order


def generar_factura_pdf(orden_id: int) -> bytes:
    """
    Construye un PDF de factura comercial para la orden indicada.

    Incluye cabecera TradeFlow, número TF-YYYYMM-XXXX, comprador, líneas de
    detalle, totales en USD y pie para uso documental en Zona Libre de Colón.

    Args:
        orden_id: Clave primaria (pk) de la orden en la base de datos.

    Returns:
        Contenido del PDF como bytes (listo para HttpResponse).

    Raises:
        Order.DoesNotExist: Si no existe la orden.
    """
    orden = (
        Order.objects.select_related('buyer', 'ship_address')
        .prefetch_related('items__product__company')
        .get(pk=orden_id)
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Factura {orden.order_number}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="TFTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#0F2A44"),
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    sub_style = ParagraphStyle(
        name="TFSub",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#6B7A88"),
        spaceAfter=12,
    )
    body = ParagraphStyle(
        name="TFBody",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#374151"),
        leading=14,
    )
    small_right = ParagraphStyle(
        name="TFSmallRight",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#6B7A88"),
        alignment=TA_RIGHT,
    )

    story = []
    logo_path = Path(settings.BASE_DIR) / "static" / "img" / "logo.png"
    if logo_path.is_file():
        try:
            img = Image(str(logo_path), width=2.2 * cm, height=2.2 * cm)
            story.append(img)
            story.append(Spacer(1, 0.2 * cm))
        except OSError:
            pass

    story.append(Paragraph("TradeFlow Colón", title_style))
    story.append(Paragraph("Marketplace B2B/B2C — Zona Libre de Colón, Panamá", sub_style))

    empresas = sorted(
        {item.product.company.name for item in orden.items.all()},
    )
    emp_txt = " · ".join(empresas) if empresas else "Varios proveedores ZLC"
    story.append(Paragraph(f"<b>Vendedores / origen mercancía:</b> {emp_txt}", body))
    story.append(Spacer(1, 0.4 * cm))

    meta_data = [
        ["Número de orden:", orden.order_number],
        ["Fecha de emisión:", orden.created_at.strftime("%d/%m/%Y %H:%M")],
        ["Estado:", orden.get_status_display()],
    ]
    meta_tbl = Table(meta_data, colWidths=[4.2 * cm, 11 * cm])
    meta_tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6B7A88")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#0F2A44")),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_tbl)
    story.append(Spacer(1, 0.5 * cm))

    buyer = orden.buyer
    buyer_name = buyer.get_full_name() or buyer.username
    buyer_lines = f"<b>Comprador:</b> {buyer_name}<br/><b>Email:</b> {buyer.email or '—'}"
    if orden.ship_address:
        a = orden.ship_address
        addr = f"{a.line1}"
        if a.line2:
            addr += f", {a.line2}"
        addr += f"<br/>{a.city}, {a.country} {a.postal_code}".strip()
        buyer_lines += f"<br/><b>Envío:</b><br/>{addr}"
    story.append(Paragraph(buyer_lines, body))
    story.append(Spacer(1, 0.6 * cm))

    table_data = [["Producto", "Cant.", "P. unit. (USD)", "Subtotal (USD)"]]
    for item in orden.items.all():
        table_data.append(
            [
                Paragraph(item.product.name[:80], body),
                str(item.qty),
                f"{item.unit_price_snapshot:.2f}",
                f"{item.line_total:.2f}",
            ]
        )

    items_tbl = Table(
        table_data,
        colWidths=[8.5 * cm, 2 * cm, 3.2 * cm, 3.2 * cm],
        repeatRows=1,
    )
    items_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F2A44")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(items_tbl)
    story.append(Spacer(1, 0.5 * cm))

    totals_data = [
        ["Subtotal", f"USD {orden.subtotal:.2f}"],
        ["Envío", f"USD {orden.shipping_cost:.2f}"],
        ["Total", f"USD {orden.total:.2f}"],
    ]
    totals_tbl = Table(totals_data, colWidths=[13.5 * cm, 3.4 * cm])
    totals_tbl.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, 1), 10),
                ("FONTSIZE", (0, 2), (-1, 2), 12),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#0F2A44")),
                ("LINEABOVE", (0, 2), (-1, 2), 1, colors.HexColor("#0F2A44")),
                ("TOPPADDING", (0, 2), (-1, 2), 8),
            ]
        )
    )
    story.append(totals_tbl)
    story.append(Spacer(1, 1 * cm))
    story.append(
        Paragraph(
            "Documento generado electrónicamente para fines comerciales y aduaneros "
            "en el marco de operaciones de la Zona Libre de Colón, Panamá.",
            sub_style,
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Zona Libre de Colón, Panamá", small_right))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
