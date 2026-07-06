"""
=============================================================================
TradeFlow Colón — Generador PDF (ReportLab)
=============================================================================
Este módulo genera documentos PDF para el marketplace B2B/B2C de la Zona
Libre de Colón (ZLC), Panamá: facturas comerciales, listas de empaque
(alineadas a prácticas documentales ante la ANA / DUA) y cotizaciones
formales (RFQ).

Contexto legal — Panamá ZLC:
  · Ley 76 de 2002 y normativa conexa sobre el régimen de Zona Libre.
  · Operaciones en ZLC: tratamiento fiscal distinto; la documentación debe
    reflejar condiciones de ITBMS según el caso (muchas ventas ZLC/B2B
    documentan exención o no sujeción — ver notas en cada PDF).
  · ANA (Aduanas Nacional): facturas y packing lists sirven de soporte a
    declaraciones DUA; los textos legales del pie no sustituyen asesoría
    contable ni aduanera.

Cada función devuelve ``bytes`` listos para ``HttpResponse`` o almacenamiento.
=============================================================================
"""

from __future__ import annotations

import io
from decimal import Decimal
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.utils.tf_brand_assets import logo_icon_color_path

# --- Paleta TradeFlow (identidad visual) ------------------------------------
TF_NAVY = HexColor("#0F2A44")
TF_ORANGE = HexColor("#F26522")
TF_LIGHT = HexColor("#F2F3F5")
TF_BORDER = HexColor("#D1D5DB")
TF_MUTED = HexColor("#6B7A88")

_PAGE_FRAME_W = A4[0] - 4 * cm


def _get_styles():
    """
    Estilos de párrafo personalizados con nombres únicos para el documento.
    No usa ``textTransform`` (no soportado por ReportLab ParagraphStyle).
    """
    base = getSampleStyleSheet()
    sty = base

    sty.add(
        ParagraphStyle(
            name="DocTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=TF_NAVY,
            spaceAfter=4,
            alignment=TA_CENTER,
        )
    )
    sty.add(
        ParagraphStyle(
            name="DocSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=TF_MUTED,
            spaceAfter=10,
            alignment=TA_CENTER,
        )
    )
    sty.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=TF_ORANGE,
            spaceBefore=8,
            spaceAfter=6,
            alignment=TA_LEFT,
        )
    )
    sty.add(
        ParagraphStyle(
            name="BodySmall",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=HexColor("#374151"),
            alignment=TA_LEFT,
        )
    )
    sty.add(
        ParagraphStyle(
            name="LabelGray",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=TF_MUTED,
            alignment=TA_LEFT,
        )
    )
    sty.add(
        ParagraphStyle(
            name="TotalLabel",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=TF_NAVY,
            alignment=TA_RIGHT,
        )
    )
    sty.add(
        ParagraphStyle(
            name="TotalValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=TF_NAVY,
            alignment=TA_RIGHT,
        )
    )
    sty.add(
        ParagraphStyle(
            name="Legal",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            leading=10,
            textColor=TF_MUTED,
            alignment=TA_LEFT,
        )
    )
    sty.add(
        ParagraphStyle(
            name="TableHeaderWhite",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.white,
            alignment=TA_CENTER,
        )
    )
    sty.add(
        ParagraphStyle(
            name="TableHeaderWhiteLeft",
            parent=sty["TableHeaderWhite"],
            alignment=TA_LEFT,
        )
    )
    sty.add(
        ParagraphStyle(
            name="TableCellProduct",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=HexColor("#374151"),
            alignment=TA_LEFT,
        )
    )
    return sty


def _table_header_cell(styles, text: str, align_center: bool = True) -> Paragraph:
    """Celda de cabecera navy con texto blanco legible (Paragraph, no string plano)."""
    key = "TableHeaderWhite" if align_center else "TableHeaderWhiteLeft"
    return Paragraph(text, styles[key])


def _format_dt(dt) -> str:
    if dt is None:
        return "—"
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime("%d/%m/%Y %H:%M")


def _usd(amount: Decimal) -> str:
    q = amount.quantize(Decimal("0.01"))
    return f"{q:.2f}"


def _usd_cell(amount: Decimal) -> str:
    return f"USD {_usd(amount)}"


def _meta_row_table(rows, styles) -> Table:
    """
    Tabla meta de dos columnas con labels cortos y valores en Paragraph (sin solapes).

    Args:
        rows: lista de tuplas (label_sin_dos_puntos, valor_html_escaped_o_texto).
    """
    data = []
    for label, value in rows:
        label_para = Paragraph(
            f"<font color='#6B7A88'><b>{escape(label)}</b></font>",
            styles["LabelGray"],
        )
        if isinstance(value, Paragraph):
            value_para = value
        else:
            value_para = Paragraph(str(value), styles["BodySmall"])
        data.append([label_para, value_para])

    meta_tbl = Table(data, colWidths=[6.2 * cm, 10.8 * cm])
    meta_tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return meta_tbl


def _table_style_navy_header() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), TF_NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("LINEBELOW", (0, 0), (-1, 0), 2, TF_ORANGE),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TF_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, TF_BORDER),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
            ("TOPPADDING", (0, 1), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
    )


def _orange_rule():
    return HRFlowable(
        width=_PAGE_FRAME_W,
        thickness=1.5,
        color=TF_ORANGE,
        spaceAfter=8,
        spaceBefore=3 * mm,
    )


def _story_brand_logo(styles) -> list:
    """
    Cabecera con logo oficial (icono TF azul/naranja).
    Si falta el archivo en static/img, usa título textual de respaldo.
    """
    path = logo_icon_color_path()
    if path.is_file():
        logo = RLImage(str(path), width=4.2 * cm, height=2.8 * cm, kind="proportional")
        logo.hAlign = "CENTER"
        return [logo, Spacer(1, 0.2 * cm)]
    return [Paragraph("TradeFlow Colón", styles["DocTitle"])]


def _story_doc_footer_legal(styles) -> list:
    return [
        Spacer(1, 0.4 * cm),
        _orange_rule(),
        Paragraph(
            "Law 76 (Colón Free Zone) and applicable regulations. On ITBMS: "
            "in ZLC operations taxation depends on the taxable event and "
            "the type of operation; this document is commercial and should "
            "be coordinated with tax counsel. Supporting document for "
            "ANA / DUA filings; does not replace official guides or "
            "rulings from the customs authority.",
            styles["Legal"],
        ),
    ]


def generar_factura_pdf(orden) -> bytes:
    """
    Factura comercial en USD para una instancia de ``Order``.

    Usa ``orden.items.all()`` con datos snapshot del pedido (empresa del
    producto, cantidades y precios). Meta y cabeceras de tabla evitan solapes
    (labels cortos + Paragraph en ambas columnas).
    """
    styles = _get_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title=f"Invoice {orden.order_number}",
    )

    story: list = []
    story.extend(_story_brand_logo(styles))
    story.append(
        Paragraph(
            "Commercial invoice — Colón Free Zone, Republic of Panama",
            styles["DocSubtitle"],
        )
    )
    story.append(_orange_rule())

    buyer = orden.buyer
    buyer_name = escape(buyer.get_full_name() or buyer.username or "")
    buyer_email = escape(buyer.email or "—")

    empresas = sorted(
        {item.product.company.name for item in orden.items.all()},
        key=str.lower,
    )
    expedidor_txt = escape(" · ".join(empresas)) if empresas else "—"

    story.append(
        _meta_row_table(
            [
                ("Number", escape(str(orden.order_number))),
                ("Issue date", escape(_format_dt(orden.created_at))),
                ("Order type", escape(str(orden.get_order_type_display()))),
                ("Buyer", buyer_name),
                ("Email", buyer_email),
                ("ZLC shipper(s)", expedidor_txt),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 0.25 * cm))

    if orden.ship_address_id:
        a = orden.ship_address
        addr_html = escape(f"{a.line1}")
        if a.line2:
            addr_html += escape(f", {a.line2}")
        addr_html += escape(f"<br/>{a.city}, {a.country} {a.postal_code or ''}".strip())
        story.append(Paragraph(f"<b>Shipping address</b><br/>{addr_html}", styles["BodySmall"]))
        story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("Line items", styles["SectionTitle"]))

    table_data = [
        [
            _table_header_cell(styles, "Product / ZLC supplier", align_center=False),
            _table_header_cell(styles, "Qty."),
            _table_header_cell(styles, "Unit price<br/>USD"),
            _table_header_cell(styles, "Line total<br/>USD"),
        ]
    ]
    for item in orden.items.all():
        cname = item.product.company.name
        cell_txt = (
            f"<b>{escape(item.product.name)}</b><br/>"
            f"<font color='#6B7A88' size='8'>{escape(cname)}</font>"
        )
        table_data.append(
            [
                Paragraph(cell_txt, styles["TableCellProduct"]),
                str(item.qty),
                _usd_cell(item.unit_price_snapshot),
                _usd_cell(item.line_total),
            ]
        )

    items_tbl = Table(
        table_data,
        colWidths=[7.6 * cm, 2.3 * cm, 3.5 * cm, 3.6 * cm],
        repeatRows=1,
    )
    ts = _table_style_navy_header()
    ts.add("ALIGN", (1, 0), (-1, -1), "CENTER")
    ts.add("ALIGN", (2, 1), (-1, -1), "RIGHT")
    items_tbl.setStyle(ts)
    story.append(items_tbl)
    story.append(Spacer(1, 0.45 * cm))

    totals = Table(
        [
            [Paragraph("Subtotal", styles["TotalLabel"]), Paragraph(_usd_cell(orden.subtotal), styles["TotalValue"])],
            [
                Paragraph("Shipping", styles["TotalLabel"]),
                Paragraph(_usd_cell(orden.shipping_cost), styles["TotalValue"]),
            ],
            [
                Paragraph("<b>Total</b>", styles["TotalLabel"]),
                Paragraph(f"<b>{_usd_cell(orden.total)}</b>", styles["TotalValue"]),
            ],
        ],
        colWidths=[12 * cm, 5 * cm],
    )
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, 2), (1, 2), 1.2, TF_NAVY),
                ("LINEBELOW", (0, 2), (1, 2), 2, TF_ORANGE),
                ("TOPPADDING", (0, 2), (1, 2), 6),
                ("BOTTOMPADDING", (0, 2), (1, 2), 6),
            ]
        )
    )
    story.append(totals)

    story.extend(_story_doc_footer_legal(styles))

    doc.build(story)
    out = buffer.getvalue()
    buffer.close()
    return out


def generar_packing_list_pdf(orden) -> bytes:
    """
    Lista de empaque — formato útil como anexo para inspección y DUA (ANA).

    Incluye descripción de mercancía, cantidades y referencia de orden,
    coherente con las mismas líneas que la factura.
    """
    styles = _get_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title=f"Packing List {orden.order_number}",
    )

    story: list = []
    story.extend(_story_brand_logo(styles))
    story.append(Paragraph("Packing list", styles["DocTitle"]))
    story.append(
        Paragraph(
            "Packing document — reference for customs authority (ANA) and DUA — ZLC",
            styles["DocSubtitle"],
        )
    )
    story.append(_orange_rule())

    buyer = orden.buyer
    buyer_name = escape(buyer.get_full_name() or buyer.username or "")

    empresas = sorted(
        {item.product.company.name for item in orden.items.all()},
        key=str.lower,
    )

    expedidor_txt = escape(" · ".join(empresas)) if empresas else "—"
    story.append(
        _meta_row_table(
            [
                ("Order reference", escape(str(orden.order_number))),
                ("Date", escape(_format_dt(orden.created_at))),
                ("Type", escape(str(orden.get_order_type_display()))),
                ("ZLC shipper(s)", expedidor_txt),
                ("Consignee", buyer_name),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    if orden.ship_address_id:
        a = orden.ship_address
        addr_html = escape(f"{a.line1}, {a.line2 or ''}<br/>{a.city}, {a.country} {a.postal_code or ''}")
        story.append(
            Paragraph(f"<b>Delivery location / consignee (detail)</b><br/>{addr_html}", styles["BodySmall"])
        )
        story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Detailed merchandise", styles["SectionTitle"]))

    pl_data = [
        [
            _table_header_cell(styles, "#"),
            _table_header_cell(styles, "Code"),
            _table_header_cell(styles, "Description", align_center=False),
            _table_header_cell(styles, "ZLC supplier", align_center=False),
            _table_header_cell(styles, "Qty."),
            _table_header_cell(styles, "UOM"),
            _table_header_cell(styles, "Net weight<br/>(kg)"),
            _table_header_cell(styles, "Gross weight<br/>(kg)"),
        ]
    ]
    total_qty = 0
    for n, item in enumerate(orden.items.all(), start=1):
        total_qty += item.qty
        sku = item.product.sku or "—"
        pl_data.append(
            [
                str(n),
                Paragraph(escape(sku), styles["TableCellProduct"]),
                Paragraph(escape(item.product.name), styles["TableCellProduct"]),
                Paragraph(escape(item.product.company.name), styles["TableCellProduct"]),
                str(item.qty),
                "pcs.",
                "—",
                "—",
            ]
        )

    pl_tbl = Table(
        pl_data,
        colWidths=[0.8 * cm, 2.2 * cm, 4.5 * cm, 3.5 * cm, 1.2 * cm, 0.9 * cm, 1.4 * cm, 1.5 * cm],
        repeatRows=1,
    )
    ts = _table_style_navy_header()
    ts.add("ALIGN", (0, 0), (0, -1), "CENTER")
    ts.add("ALIGN", (4, 1), (5, -1), "CENTER")
    ts.add("ALIGN", (6, 0), (-1, -1), "CENTER")
    pl_tbl.setStyle(ts)
    story.append(pl_tbl)

    story.append(Spacer(1, 0.35 * cm))
    story.append(
        Paragraph(
            f"<b>Total declared pieces (units):</b> {total_qty}. "
            f"Net/gross weights must be completed according to the physical shipment and "
            f"match the DUA declaration filed with ANA.",
            styles["LabelGray"],
        )
    )
    story.extend(_story_doc_footer_legal(styles))

    doc.build(story)
    out = buffer.getvalue()
    buffer.close()
    return out


def generar_cotizacion_pdf(cotizacion) -> bytes:
    """
    PDF formal de cotización (RFQ) con ítems, precios ofertados y notas.
    """
    styles = _get_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title=f"Quote {cotizacion.numero}",
    )

    story: list = []
    story.extend(_story_brand_logo(styles))
    story.append(Paragraph("Formal quote (RFQ)", styles["DocTitle"]))
    story.append(
        Paragraph(
            "TradeFlow Colón — price proposal under ZLC framework; validity per stated period",
            styles["DocSubtitle"],
        )
    )
    story.append(_orange_rule())

    empresa = cotizacion.empresa
    buyer = cotizacion.buyer
    buyer_name = escape(buyer.get_full_name() or buyer.username or "")
    ruc = escape(empresa.ruc or "—")

    header_rows = [
        ["Number:", escape(str(cotizacion.numero))],
        ["Date:", _format_dt(cotizacion.created_at)],
        ["Offering company:", escape(empresa.name)],
        ["RUC / registration:", ruc],
        ["Buyer:", buyer_name],
        ["Offer validity:", f"{cotizacion.validez_dias} days"],
    ]
    ht = Table(header_rows, colWidths=[4.5 * cm, 12.5 * cm])
    ht.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), TF_MUTED),
                ("TEXTCOLOR", (1, 0), (1, -1), TF_NAVY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(ht)
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("Quoted lines", styles["SectionTitle"]))

    rows = [
        [
            _table_header_cell(styles, "Product", align_center=False),
            _table_header_cell(styles, "Qty.<br/>requested"),
            _table_header_cell(styles, "Offered price<br/>(unit USD)"),
            _table_header_cell(styles, "Line notes", align_center=False),
        ]
    ]

    subtotal = Decimal("0")
    has_amounts = False
    for it in cotizacion.items.all():
        precio_txt: str
        if it.precio_ofertado is not None:
            precio_txt = _usd_cell(it.precio_ofertado)
            subtotal += it.precio_ofertado * it.cantidad_solicitada
            has_amounts = True
        else:
            precio_txt = "Pending"
        notas_cell = escape(it.notas) if it.notas else "—"
        rows.append(
            [
                Paragraph(escape(it.product.name), styles["BodySmall"]),
                str(it.cantidad_solicitada),
                precio_txt,
                Paragraph(notas_cell, styles["BodySmall"]),
            ]
        )

    ct = Table(rows, colWidths=[5.8 * cm, 2.2 * cm, 3.5 * cm, 5.5 * cm], repeatRows=1)
    ts = _table_style_navy_header()
    ts.add("ALIGN", (1, 0), (2, -1), "CENTER")
    ct.setStyle(ts)
    story.append(ct)

    if has_amounts:
        story.append(Spacer(1, 0.35 * cm))
        tot = Table(
            [
                [
                    Paragraph("Estimated subtotal (USD)", styles["TotalLabel"]),
                    Paragraph(_usd_cell(subtotal), styles["TotalValue"]),
                ],
            ],
            colWidths=[12 * cm, 5 * cm],
        )
        tot.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (1, 0), "RIGHT"),
                    ("LINEABOVE", (0, 0), (1, 0), 1, TF_NAVY),
                ]
            )
        )
        story.append(tot)

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Buyer notes", styles["SectionTitle"]))
    nb = cotizacion.notas_buyer.strip() if cotizacion.notas_buyer else "—"
    story.append(Paragraph(escape(nb), styles["BodySmall"]))

    story.append(Paragraph("Seller notes", styles["SectionTitle"]))
    ns = cotizacion.notas_seller.strip() if cotizacion.notas_seller else "—"
    story.append(Paragraph(escape(ns), styles["BodySmall"]))

    story.extend(_story_doc_footer_legal(styles))

    doc.build(story)
    out = buffer.getvalue()
    buffer.close()
    return out
