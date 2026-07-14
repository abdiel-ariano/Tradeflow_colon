from __future__ import annotations
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from . import labels as L

# ── Paleta de marca Tradeflow Colón (variada, sin monopolio azul ni naranja) ─
# Navy = autoridad en UI; en charts repartimos teal / ámbar / malva / verde /
# azul / naranja para que cada serie se distinga a simple vista.
C1 = "#F26522"   # naranja
C2 = "#0F2A44"   # navy
C3 = "#E8A33D"   # ámbar
C4 = "#2E5B8A"   # azul mid
C5 = "#3FA796"   # teal
C6 = "#A0506B"   # malva
C7 = "#5B7DB1"   # azul suave
C8 = "#7BAF5A"   # verde
C9 = "#0057A8"   # primary blue

# Alterna cálido/frío: evita rachas de azules o naranjas seguidos.
PALETTE = [C5, C3, C6, C8, C4, C1, C7, C2, C9]
PRIMARY_RGB = "63,167,150"    # teal — rellenos de área / bandas base
ACCENT_RGB = "242,101,34"     # naranja — proyección / umbral

# Barras de ranking: cada categoría un color distinto (no mono-azul).
BAR_COLORS = [C5, C3, C6, C8, C4, C1, C7, C9]
BAR_HL = C5
BAR_BASE = C7

# Secuencial cálido→teal; divergente teal↔ámbar (identidad sin ahogar en azul).
SCALE_SEQ = [[0.0, "#E6F5F2"], [0.35, C5], [0.7, C3], [1.0, C1]]
SCALE_DIV = [[0.0, C5], [0.25, "#A8D9D0"], [0.5, "#F2F3F5"],
             [0.75, "#F5D4A8"], [1.0, C3]]


def _bar_colors(n: int, *, highlight_last: bool = True) -> list[str]:
    """n colores distintos para barras; el último (top) usa un tono no repetido."""
    if n <= 0:
        return []
    if n == 1:
        return [BAR_HL]
    body = [BAR_COLORS[i % len(BAR_COLORS)] for i in range(n - 1)]
    used = set(body)
    top = next((c for c in BAR_COLORS if c not in used), BAR_HL)
    if highlight_last:
        return body + [top]
    return [BAR_COLORS[i % len(BAR_COLORS)] for i in range(n)]

BG        = "rgba(0,0,0,0)"   # transparente: combina con la tarjeta del dashboard
GRID_COL  = "#E9EDF2"
AXIS_COL  = "#D1D5DB"
TEXT_COL  = "#0F2A44"         # navy
SUBTEXT   = "#6B7A88"         # tf-muted
FONT      = "Montserrat, system-ui, -apple-system, sans-serif"

# Neutrales para modo oscuro (se aplican con apply_theme; los colores de marca
# de las series no cambian, solo texto/cuadrícula/ejes para que combinen).
DARK_TEXT = "#E8ECF2"
DARK_SUB  = "#9DB0C2"
DARK_GRID = "rgba(255,255,255,0.09)"
DARK_AXIS = "rgba(255,255,255,0.20)"


def _base_layout(title: str = "", height: int = 420, *, bottom: int = 56) -> dict:
    return dict(
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(size=16, color=TEXT_COL, family=FONT),
            x=0.01, xanchor="left", y=0.98, yanchor="top",
        ),
        font=dict(family=FONT, color=TEXT_COL, size=13),
        colorway=PALETTE,
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        height=height,
        # Márgenes amplios: evita que títulos de eje / ticks rotados se monten
        # sobre barras o series (caso frecuente en dashboard 2-col).
        margin=dict(t=72, b=bottom, l=64, r=28),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, color=SUBTEXT),
        ),
        hoverlabel=dict(
            bgcolor="white",
            bordercolor=GRID_COL,
            font=dict(family=FONT, size=13, color=TEXT_COL),
        ),
        # Deja aire entre etiquetas de datos "outside" y el borde del plot.
        uniformtext=dict(minsize=10, mode="hide"),
    )


def _style_axes(fig, x_title: str = "", y_title: str = "", tickangle: int = 0):
    # Con ticks angulados, el título de X compite por el mismo espacio: lo omitimos
    # (las categorías ya se leen en los ticks) y pedimos más margen inferior.
    x_title_final = "" if tickangle else x_title
    fig.update_xaxes(
        title_text=x_title_final,
        title_font=dict(size=12, color=SUBTEXT),
        title_standoff=18,
        tickfont=dict(size=11, color=SUBTEXT),
        gridcolor=GRID_COL,
        linecolor=AXIS_COL,
        tickangle=tickangle,
        showgrid=False,
        zeroline=False,
        ticks="outside", ticklen=4, tickcolor=AXIS_COL,
        automargin=True,
        separatethousands=True,
    )
    fig.update_yaxes(
        title_text=y_title,
        title_font=dict(size=12, color=SUBTEXT),
        title_standoff=14,
        tickfont=dict(size=11, color=SUBTEXT),
        gridcolor=GRID_COL,
        linecolor="rgba(0,0,0,0)",
        showgrid=True,
        zeroline=False,
        griddash="dot",
        automargin=True,
        separatethousands=True,
    )
    if tickangle:
        cur_b = 56
        try:
            cur_b = int(fig.layout.margin.b or 56)
        except Exception:
            pass
        fig.update_layout(margin=dict(b=max(cur_b, 96)))
    return fig


def apply_theme(fig, dark: bool = False):
    """Re-skin neutrals (texto/cuadrícula/ejes) para modo claro u oscuro.
    Los colores de marca de las series no se tocan. El fondo queda transparente
    en ambos modos (la tarjeta del dashboard aporta el color)."""
    if fig is None:
        return fig
    text = DARK_TEXT if dark else TEXT_COL
    sub  = DARK_SUB if dark else SUBTEXT
    grid = DARK_GRID if dark else GRID_COL
    axis = DARK_AXIS if dark else AXIS_COL

    fig.update_layout(font=dict(color=text))
    if fig.layout.title is not None and fig.layout.title.font is not None:
        fig.layout.title.font.color = text
    if fig.layout.legend is not None and fig.layout.legend.font is not None:
        fig.layout.legend.font.color = sub

    fig.update_xaxes(gridcolor=grid, linecolor=axis, tickcolor=axis,
                     tickfont_color=sub, title_font_color=sub)
    fig.update_yaxes(gridcolor=grid, tickcolor=axis,
                     tickfont_color=sub, title_font_color=sub)

    # Anotaciones neutras (p. ej. total al centro del donut) siguen el tema;
    # las de color de marca (media/mediana) se respetan.
    for ann in fig.layout.annotations:
        if ann.font is None or ann.font.color in (None, TEXT_COL, DARK_TEXT):
            ann.font.color = text

    # Indicadores (gauge): título neutro
    try:
        fig.update_traces(selector=dict(type="indicator"), title_font_color=text)
    except Exception:
        pass
    return fig


def _is_categorical(s: pd.Series, max_unique: int = 50) -> bool:
    """Robust categorical detection across dtypes (object, arrow str, category,
    bool). Numeric and datetime columns are never categorical here."""
    if pd.api.types.is_bool_dtype(s):
        return True
    if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
        return False
    try:
        return s.nunique(dropna=True) <= max_unique
    except Exception:
        return False


def histogram(df: pd.DataFrame, col: str):
    if col not in df.columns or df[col].dropna().empty:
        return None
    mean_val = df[col].mean()
    median_val = df[col].median()

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=df[col],
        nbinsx=30,
        name=L.pretty(col),
        marker=dict(
            color=C5,
            opacity=0.85,
            line=dict(color="white", width=0.8),
        ),
        hovertemplate=f"<b>{L.pretty(col)}:</b> %{{x}}<br><b>Frecuencia:</b> %{{y}}<extra></extra>",
    ))
    fig.add_vline(x=mean_val, line=dict(color=C4, dash="dash", width=2),
                  annotation=dict(text=f"Media: {mean_val:.2f}", font_color=C4, bgcolor="rgba(255,255,255,0.85)"))
    fig.add_vline(x=median_val, line=dict(color=C3, dash="dot", width=2),
                  annotation=dict(text=f"Mediana: {median_val:.2f}", font_color=C3, bgcolor="rgba(255,255,255,0.85)", yshift=-20))

    fig.update_layout(**_base_layout(f"Distribución — {L.pretty(col)}"))
    _style_axes(fig, x_title=L.pretty(col), y_title="Frecuencia")
    return fig


def bar_top(df: pd.DataFrame, col: str, top_n: int = 15):
    if col not in df.columns or df[col].dropna().empty:
        return None
    counts = df[col].value_counts().head(top_n).reset_index()
    counts.columns = [col, "frecuencia"]
    counts = counts.sort_values("frecuencia", ascending=True)
    if counts.empty:
        return None

    n = len(counts)
    # Horizontal ascendente → el mayor queda arriba; colores distintos por barra.
    colors = _bar_colors(n, highlight_last=True)
    xmax = float(counts["frecuencia"].max() or 1)

    fig = go.Figure(go.Bar(
        x=counts["frecuencia"],
        y=counts[col].astype(str),
        orientation="h",
        marker=dict(color=colors, line=dict(color="white", width=0.5), cornerradius=5),
        text=counts["frecuencia"],
        textposition="outside",
        textfont=dict(size=12, color=SUBTEXT),
        cliponaxis=False,
        hovertemplate=f"<b>%{{y}}</b><br>Frecuencia: <b>%{{x}}</b><extra></extra>",
    ))
    fig.update_layout(**_base_layout(f"Top {n} — {L.pretty(col)}", height=max(360, n * 34), bottom=40))
    # Sin título de eje: el card ya dice qué se mide; evita solapes con ticks.
    _style_axes(fig, x_title="", y_title="")
    fig.update_xaxes(range=[0, xmax * 1.22], automargin=True)
    fig.update_yaxes(
        tickfont=dict(size=11, color=TEXT_COL),
        automargin=True,
        title_text="",
        ticklabelposition="outside",
        ticksuffix=" ",
    )
    # Margen izquierdo amplio: las categorías viven a la IZQUIERDA de las barras
    # (l bajo las montaba encima del trazo).
    fig.update_layout(margin=dict(r=80, l=168))
    return fig


def pie_chart(df: pd.DataFrame, col: str, top_n: int = 8,
              value_col: str | None = None, agg: str = "sum"):
    if col not in df.columns or df[col].dropna().empty:
        return None
    # Ponderar por una métrica (p. ej. suma de ventas por categoría/producto) si
    # se pide; si no, contar filas (proporción por frecuencia).
    if value_col and value_col in df.columns and pd.api.types.is_numeric_dtype(df[value_col]):
        series = df.groupby(col)[value_col].agg(agg).sort_values(ascending=False)
        unit, title = value_col, f"Proporción de {L.pretty(value_col)} — {L.pretty(col)}"
        hover = f"<b>%{{label}}</b><br>{L.pretty(value_col)}: <b>%{{value:,.0f}}</b> (%{{percent}})<extra></extra>"
    else:
        series = df[col].value_counts()
        unit, title = "registros", f"Proporción — {L.pretty(col)}"
        hover = "<b>%{label}</b><br>%{value} registros (%{percent})<extra></extra>"

    counts = series.head(top_n)
    other = series.iloc[top_n:].sum()
    if other > 0:
        counts["Otros"] = other

    total = int(counts.sum())
    fig = go.Figure(go.Pie(
        labels=counts.index.astype(str),
        values=counts.values,
        hole=0.58,
        sort=False,
        marker=dict(
            colors=PALETTE[:len(counts)],
            line=dict(color="white", width=2),
        ),
        textinfo="percent",
        textfont=dict(size=12, color=TEXT_COL),
        insidetextorientation="horizontal",
        hovertemplate=hover,
    ))
    fig.update_layout(
        **_base_layout(title, bottom=40),
        showlegend=True,
    )
    fig.update_layout(legend=dict(
        orientation="v", x=1.02, y=0.5,
        font=dict(size=12, color=SUBTEXT),
    ))
    # Centro limpio: un solo número; el % vive en el anillo / leyenda.
    center_html = f"<b>{total:,}</b>" if len(counts) > 1 else f"<b>{total:,}</b><br><span style='font-size:11px;color:{SUBTEXT}'>{counts.index[0]}</span>"
    fig.add_annotation(
        text=center_html,
        x=0.5, y=0.5, xanchor="center", yanchor="middle", showarrow=False,
        font=dict(size=20, family=FONT, color=TEXT_COL),
    )
    return fig


def scatter(df: pd.DataFrame, x: str, y: str, color_col: str | None = None):
    sample = df.sample(min(2000, len(df)), random_state=42) if len(df) > 2000 else df
    # Renombrar a etiquetas legibles ANTES de graficar: así hasta la ecuación de
    # la línea de tendencia OLS sale con nombres bonitos (px no remapea eso con labels).
    cols = [c for c in (x, y, color_col) if c]
    ren = {c: L.pretty(c) for c in cols}
    sample = sample[cols].rename(columns=ren)
    px_x, px_y = ren[x], ren[y]
    px_color = ren.get(color_col) if color_col else None

    fig = px.scatter(
        sample, x=px_x, y=px_y,
        color=px_color,
        color_discrete_sequence=PALETTE,
        trendline="ols",
        trendline_color_override=C4,
        opacity=0.75,
    )
    fig.update_traces(
        marker=dict(size=8, line=dict(color="white", width=0.6)),
        selector=dict(mode="markers"),
    )
    fig.update_layout(**_base_layout(f"{px_y} vs {px_x}"))
    _style_axes(fig, x_title=px_x, y_title=px_y)
    return fig


def line_chart(df: pd.DataFrame, x: str, y: str | list[str]):
    if x not in df.columns:
        return None
    ys = [c for c in ([y] if isinstance(y, str) else y) if c in df.columns]
    if not ys:
        return None
    # Serie de tiempo limpia: agrega por período (suma por valor de x). Sin esto,
    # con varias filas en la misma fecha la línea sube y baja en vertical.
    try:
        data = df.groupby(x, dropna=True)[ys].sum(numeric_only=True).reset_index().sort_values(x)
    except Exception:
        data = df.sort_values(x)
    if data.empty:
        return None
    many = len(data) > 60   # con muchos puntos, ocultar marcadores y no usar spline

    fig = go.Figure()
    for i, col in enumerate(ys):
        color = PALETTE[i % len(PALETTE)]
        fig.add_trace(go.Scatter(
            x=data[x],
            y=data[col],
            mode="lines" if many else "lines+markers",
            name=L.pretty(col),
            line=dict(color=color, width=2.5, shape="linear" if many else "spline"),
            marker=dict(size=5, color=color, line=dict(color="white", width=1)),
            fill="tozeroy" if len(ys) == 1 else "none",
            fillgradient=(dict(type="vertical",
                               colorscale=[[0, f"rgba({PRIMARY_RGB},0)"],
                                           [1, f"rgba({PRIMARY_RGB},0.45)"]])
                          if len(ys) == 1 else None),
            hovertemplate=f"<b>{L.pretty(col)}:</b> %{{y}}<br>%{{x}}<extra></extra>",
        ))
    title = (f"Evolución — {L.pretty(ys[0])}" if len(ys) == 1
             else "Evolución — " + ", ".join(L.pretty(c) for c in ys))
    fig.update_layout(**_base_layout(title))
    _style_axes(fig, x_title=L.pretty(x), y_title=L.pretty(ys[0]) if len(ys) == 1 else "Valor")
    return fig


def box_plot(df: pd.DataFrame, col: str, group_col: str | None = None):
    fig = go.Figure()
    groups = df[group_col].unique() if group_col else [None]

    for i, grp in enumerate(groups[:12]):
        subset = df[df[group_col] == grp][col] if group_col else df[col]
        color = PALETTE[i % len(PALETTE)]
        etiqueta = str(grp) if grp is not None else L.pretty(col)
        fig.add_trace(go.Box(
            y=subset,
            name=etiqueta,
            marker=dict(color=color, size=4, opacity=0.5),
            line=dict(color=color, width=2),
            fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.15)",
            boxmean="sd",
            boxpoints="outliers",
            hovertemplate=f"<b>%{{y}}</b><extra>{etiqueta}</extra>",
        ))

    title = f"{L.pretty(col)}" + (f" por {L.pretty(group_col)}" if group_col else "")
    fig.update_layout(**_base_layout(f"Box plot — {title}"))
    _style_axes(fig, y_title=L.pretty(col))
    return fig


def correlation_heatmap(df: pd.DataFrame):
    numeric = df.select_dtypes(include="number")
    corr = numeric.corr().round(2)
    ticks = [L.pretty(c) for c in corr.columns]

    fig = go.Figure(go.Heatmap(
        z=corr.values,
        x=ticks,
        y=ticks,
        colorscale=SCALE_DIV,
        zmin=-1, zmax=1,
        xgap=2, ygap=2,
        text=corr.values,
        texttemplate="%{text}",
        textfont=dict(size=11, family=FONT),
        hoverongaps=False,
        colorbar=dict(outlinewidth=0, tickfont=dict(size=10, color=SUBTEXT),
                      thickness=12, len=0.8),
        hovertemplate="<b>%{x}</b> × <b>%{y}</b><br>Correlación: <b>%{z}</b><extra></extra>",
    ))
    n = len(corr.columns)
    fig.update_layout(
        **_base_layout("Mapa de correlación", height=max(400, n * 55 + 100)),
    )
    fig.update_xaxes(tickangle=-30, tickfont=dict(size=11), automargin=True)
    fig.update_yaxes(tickfont=dict(size=11), automargin=True)
    fig.update_layout(margin=dict(b=88, l=88))
    return fig


def grouped_bar(df: pd.DataFrame, group_col: str, value_col: str, agg: str = "sum",
                top_n: int = 20):
    if group_col not in df.columns or value_col not in df.columns:
        return None
    grouped = (
        df.groupby(group_col)[value_col]
        .agg(agg)
        .reset_index()
        .sort_values(value_col, ascending=True)  # horizontal: mayor arriba
        .tail(int(top_n) if top_n else 20)
    )
    if grouped.empty:
        return None
    n = len(grouped)
    # Horizontal evita ticks rotados solapados con el título del eje.
    colors = _bar_colors(n, highlight_last=True)
    labels = grouped[group_col].astype(str).map(
        lambda s: (s[:28] + "…") if len(s) > 30 else s
    )
    xmax = float(grouped[value_col].max() or 1)
    fig = go.Figure(go.Bar(
        x=grouped[value_col],
        y=labels,
        orientation="h",
        marker=dict(color=colors, line=dict(color="white", width=0.6), cornerradius=6),
        text=[f"{v:,.0f}" for v in grouped[value_col]],
        textposition="outside",
        textfont=dict(size=11, color=SUBTEXT),
        cliponaxis=False,
        hovertemplate=(
            f"<b>%{{y}}</b><br>{L.pretty(value_col)}: <b>%{{x:,.0f}}</b><extra></extra>"
        ),
    ))
    fig.update_layout(**_base_layout(
        f"{L.agg_label(agg)} de {L.pretty(value_col)} por {L.pretty(group_col)}",
        height=max(360, n * 36),
        bottom=40,
    ))
    # Títulos de eje omitidos: el encabezado del card ya informa métrica/categoría
    # (evita "Día"/"Ventas" montado sobre valores numéricos).
    _style_axes(fig, x_title="", y_title="")
    fig.update_xaxes(range=[0, xmax * 1.22], automargin=True, title_text="")
    fig.update_yaxes(
        tickfont=dict(size=11, color=TEXT_COL),
        automargin=True,
        title_text="",
        ticklabelposition="outside",
        ticksuffix=" ",
    )
    fig.update_layout(margin=dict(r=80, l=168))
    return fig


def multi_histogram(df: pd.DataFrame, cols: list[str]):
    cols = cols[:6]
    n = len(cols)
    n_cols = min(n, 3)
    n_rows = (n + n_cols - 1) // n_cols

    fig = make_subplots(
        rows=n_rows, cols=n_cols,
        subplot_titles=[f"<b>{L.pretty(c)}</b>" for c in cols],
        vertical_spacing=0.14,
        horizontal_spacing=0.08,
    )
    for i, col in enumerate(cols):
        r, c = divmod(i, n_cols)
        color = PALETTE[i % len(PALETTE)]
        mean_v = df[col].mean()
        fig.add_trace(
            go.Histogram(
                x=df[col], nbinsx=25,
                name=L.pretty(col),
                marker=dict(color=color, opacity=0.82, line=dict(color="white", width=0.5)),
                showlegend=False,
                hovertemplate=f"<b>{L.pretty(col)}:</b> %{{x}}<br>Frecuencia: %{{y}}<extra></extra>",
            ),
            row=r + 1, col=c + 1,
        )
        fig.add_vline(
            x=mean_v, line=dict(color="rgba(0,0,0,0.4)", dash="dash", width=1.5),
            row=r + 1, col=c + 1,
        )

    fig.update_layout(
        **_base_layout("Distribuciones numéricas", height=280 * n_rows),
        showlegend=False,
    )
    fig.update_annotations(font=dict(size=13, color=TEXT_COL))
    fig.update_xaxes(gridcolor=GRID_COL, showgrid=False, zeroline=False, tickfont=dict(size=10))
    fig.update_yaxes(gridcolor=GRID_COL, showgrid=True, zeroline=False, tickfont=dict(size=10))
    return fig


def area_chart(df: pd.DataFrame, x: str, y: str):
    sorted_df = df.sort_values(x)
    fig = go.Figure(go.Scatter(
        x=sorted_df[x], y=sorted_df[y],
        mode="lines",
        fill="tozeroy",
        line=dict(color=C5, width=3, shape="spline"),
        fillgradient=dict(type="vertical",
                          colorscale=[[0, f"rgba({PRIMARY_RGB},0)"],
                                      [1, f"rgba({PRIMARY_RGB},0.42)"]]),
        hovertemplate=f"<b>{L.pretty(y)}:</b> %{{y}}<br>%{{x}}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(f"Área — {L.pretty(y)}"))
    _style_axes(fig, x_title=L.pretty(x), y_title=L.pretty(y))
    return fig


def _hierarchy_data(df, path_cols, value_col, agg, top_n):
    """Build aggregated data for treemap/sunburst. Returns (data, value_name)."""
    path = [c for c in path_cols if c in df.columns]
    if not path:
        return None, None
    if (value_col and value_col in df.columns
            and pd.api.types.is_numeric_dtype(df[value_col])):
        data = df.groupby(path, dropna=True)[value_col].agg(agg).reset_index()
        vname = value_col
    else:
        data = df.groupby(path, dropna=True).size().reset_index(name="conteo")
        vname = "conteo"
    for c in path:
        data[c] = data[c].astype(str)
    data = data[data[vname] > 0].sort_values(vname, ascending=False).head(top_n)
    return (data, vname) if not data.empty else (None, None)


def treemap(df: pd.DataFrame, path_cols: list[str], value_col: str | None = None,
            agg: str = "sum", top_n: int = 200):
    data, vname = _hierarchy_data(df, path_cols, value_col, agg, top_n)
    if data is None:
        return None
    path = [c for c in path_cols if c in df.columns]
    top = path[0]   # el nivel superior da el color: un tono por categoría
    fig = px.treemap(
        data, path=[px.Constant("Total")] + path, values=vname,
        color=top,
        color_discrete_sequence=PALETTE,
        labels={c: L.pretty(c) for c in [*path, vname] if c},
    )
    fig.update_traces(
        marker=dict(line=dict(color="white", width=2), pad=dict(t=28, l=4, r=4, b=4)),
        tiling=dict(pad=4),
        textfont=dict(size=12, family=FONT, color=TEXT_COL),
        textposition="middle center",
        hovertemplate="<b>%{label}</b><br>" + L.pretty(vname) + ": %{value}<extra></extra>",
    )
    fig.update_layout(**_base_layout("Composición — " + " / ".join(L.pretty(p) for p in path)),
                      showlegend=False)
    # Evita el pathbar/root "Total" robando espacio y empujando labels a solaparse.
    fig.update_traces(root_color="rgba(15,42,68,0.06)")
    return fig


def sunburst(df: pd.DataFrame, path_cols: list[str], value_col: str | None = None,
             agg: str = "sum", top_n: int = 200):
    data, vname = _hierarchy_data(df, path_cols, value_col, agg, top_n)
    if data is None:
        return None
    path = [c for c in path_cols if c in df.columns]
    top = path[0]   # color por categoría del nivel superior
    fig = px.sunburst(
        data, path=path, values=vname,
        color=top,
        color_discrete_sequence=PALETTE,
        labels={c: L.pretty(c) for c in [*path, vname] if c},
    )
    fig.update_traces(
        marker=dict(line=dict(color="white", width=1.5)),
        hovertemplate="<b>%{label}</b><br>" + L.pretty(vname) + ": %{value}<extra></extra>",
    )
    fig.update_layout(**_base_layout("Jerarquía — " + " / ".join(L.pretty(p) for p in path)),
                      showlegend=False)
    return fig


def funnel(df: pd.DataFrame, stage_col: str, value_col: str | None = None,
           agg: str = "sum"):
    if stage_col not in df.columns:
        return None
    if (value_col and value_col in df.columns
            and pd.api.types.is_numeric_dtype(df[value_col])):
        data = df.groupby(stage_col, dropna=True)[value_col].agg(agg).reset_index()
        vcol = value_col
    else:
        data = df[stage_col].value_counts(dropna=True).reset_index()
        data.columns = [stage_col, "conteo"]
        vcol = "conteo"
    data = data.sort_values(vcol, ascending=False).head(15)
    if data.empty:
        return None
    fig = go.Figure(go.Funnel(
        y=data[stage_col].astype(str),
        x=data[vcol],
        textinfo="value+percent initial",
        textfont=dict(size=12),
        marker=dict(color=PALETTE[:len(data)], line=dict(color="white", width=1)),
        connector=dict(line=dict(color=GRID_COL, width=1)),
        hovertemplate="<b>%{y}</b><br>" + L.pretty(vcol) + ": %{x}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(f"Embudo — {L.pretty(stage_col)}"))
    return fig


def gauge(value: float, title: str = "", max_value: float | None = None,
          ref: float | None = None):
    if value is None:
        return None
    if max_value is None or max_value <= 0:
        max_value = abs(value) * 1.5 if value else 1.0
    mode = "gauge+number" + ("+delta" if ref is not None else "")
    fig = go.Figure(go.Indicator(
        mode=mode,
        value=value,
        number={"font": {"color": C5, "size": 40}},
        delta=({"reference": ref} if ref is not None else None),
        title={"text": f"<b>{title}</b>", "font": {"size": 16, "color": TEXT_COL}},
        gauge={
            "axis": {"range": [0, max_value], "tickcolor": SUBTEXT, "tickwidth": 1},
            "bar": {"color": C5, "thickness": 0.78},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, max_value * 0.5], "color": "rgba(63,167,150,0.12)"},
                {"range": [max_value * 0.5, max_value * 0.8], "color": "rgba(232,163,61,0.18)"},
                {"range": [max_value * 0.8, max_value], "color": "rgba(242,101,34,0.22)"},
            ],
            "threshold": {"line": {"color": C6, "width": 3}, "value": value},
        },
    ))
    fig.update_layout(**_base_layout(title or "Indicador", height=320))
    return fig


def auto_charts(df: pd.DataFrame) -> list[tuple[str, object]]:
    charts = []
    num_cols = list(df.select_dtypes(include="number").columns)
    cat_cols = [c for c in df.columns if _is_categorical(df[c], max_unique=50)]
    date_cols = list(df.select_dtypes(include=["datetime", "datetimetz"]).columns)

    # Detect date-like string columns (works for object AND arrow str dtypes)
    text_like = [
        c for c in df.columns
        if not pd.api.types.is_numeric_dtype(df[c])
        and not pd.api.types.is_datetime64_any_dtype(df[c])
        and c not in date_cols
    ]
    for col in text_like:
        try:
            if df[col].nunique() <= 50:   # puede lanzar con valores no-hashables
                continue
            converted = pd.to_datetime(df[col], errors="coerce", format="mixed")
            if converted.notna().sum() / max(len(df), 1) > 0.7:
                df = df.copy()
                df[col] = converted
                date_cols.append(col)
                if col in cat_cols:
                    cat_cols.remove(col)
        except Exception:
            continue

    def add(title, fn):
        """Agrega una gráfica; si su construcción falla, se omite (no tumba el resto)."""
        try:
            fig = fn()
            if fig is not None:
                charts.append((title, fig))
        except Exception:
            pass

    # Time series first — highest priority if dates exist
    if date_cols and num_cols:
        for num_col in num_cols[:2]:
            add(f"Serie de tiempo — {L.pretty(num_col)}", lambda c=num_col: line_chart(df, date_cols[0], c))

    # Numeric distributions
    if len(num_cols) >= 2:
        add("Distribuciones numéricas", lambda: multi_histogram(df, num_cols[:6]))
    elif len(num_cols) == 1:
        add(f"Distribución — {L.pretty(num_cols[0])}", lambda: histogram(df, num_cols[0]))

    # Categorical bars + pie
    for col in cat_cols[:3]:
        add(f"Top valores — {L.pretty(col)}", lambda c=col: bar_top(df, c))
        try:
            small = df[col].nunique() <= 10
        except Exception:
            small = False
        if small:
            add(f"Proporción — {L.pretty(col)}", lambda c=col: pie_chart(df, c))

    # Grouped bar: best cat × best num
    if cat_cols and num_cols:
        add(f"{L.pretty(num_cols[0])} por {L.pretty(cat_cols[0])}",
            lambda: grouped_bar(df, cat_cols[0], num_cols[0]))

    # Treemap: composición jerárquica (2 categóricas, opcional métrica)
    if len(cat_cols) >= 2:
        add("Composición jerárquica",
            lambda: treemap(df, cat_cols[:2], num_cols[0] if num_cols else None))

    # Scatter for first two numeric cols
    if len(num_cols) >= 2:
        color = cat_cols[0] if cat_cols and _is_categorical(df[cat_cols[0]], 10) else None
        add(f"Dispersión — {L.pretty(num_cols[1])} vs {L.pretty(num_cols[0])}",
            lambda: scatter(df, num_cols[0], num_cols[1], color))

    # Correlation heatmap
    if len(num_cols) >= 2:
        add("Correlación entre variables", lambda: correlation_heatmap(df))

    # Box plots
    if cat_cols and num_cols:
        grp = cat_cols[0] if _is_categorical(df[cat_cols[0]], 12) else None
        add(f"Box plot — {L.pretty(num_cols[0])}" + (f" por {L.pretty(grp)}" if grp else ""),
            lambda: box_plot(df, num_cols[0], grp))

    return charts


# ── Proyecciones a futuro ───────────────────────────────────────────────────
UP_GREEN = "#3FA796"   # alza
DOWN_RED = "#D1495B"   # caída


def forecast_chart(fc: dict, title: str = "Proyección", y_title: str = "valor"):
    """Histórico (línea sólida) + proyección (línea punteada) + banda de
    incertidumbre sombreada. `fc` es el dict de forecasting.linear_forecast."""
    if not fc:
        return None
    hist, fut = fc["history"], fc["forecast"]
    low, high = fc["low"], fc["high"]

    fig = go.Figure()
    # Banda de predicción (contorno relleno)
    fig.add_trace(go.Scatter(
        x=list(high.index) + list(low.index[::-1]),
        y=list(high.values) + list(low.values[::-1]),
        fill="toself", fillcolor=f"rgba({PRIMARY_RGB},0.10)",
        line=dict(width=0), hoverinfo="skip", showlegend=True, name="Rango probable",
    ))
    # Histórico
    fig.add_trace(go.Scatter(
        x=list(hist.index), y=list(hist.values), mode="lines+markers", name="Histórico",
        line=dict(color=C5, width=2.6, shape="spline"),
        marker=dict(size=5, color=C5, line=dict(color="white", width=1)),
        hovertemplate="%{x|%b %Y}<br><b>%{y:,.0f}</b><extra>Histórico</extra>",
    ))
    # Proyección — acento naranja (contraste vs histórico teal)
    fig.add_trace(go.Scatter(
        x=[hist.index[-1]] + list(fut.index), y=[hist.values[-1]] + list(fut.values),
        mode="lines+markers", name="Proyección",
        line=dict(color=C1, width=2.2, dash="dash"),
        marker=dict(size=5, color=C1, symbol="diamond", line=dict(color="white", width=1)),
        hovertemplate="%{x|%b %Y}<br><b>%{y:,.0f}</b><extra>Proyección</extra>",
    ))
    fig.update_layout(**_base_layout(title, bottom=64))
    # El título del card / fig ya nombra la métrica; un y-title ("Unidades",
    # "Ventas") se solapa con la serie en layouts estrechos del shell seller.
    _style_axes(fig, x_title="", y_title="")
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True, separatethousands=True)
    fig.update_layout(margin=dict(l=56, r=28, t=72, b=64))
    fig.add_vline(x=hist.index[-1], line=dict(color=SUBTEXT, width=1, dash="dot"))
    return fig


def trend_bar(trends: pd.DataFrame, item_col: str, n: int = 10, declining: bool = True):
    """Barras horizontales de los ítems que más suben o bajan (% de cambio),
    en verde/rojo según la dirección. `trends` viene de forecasting.item_trends."""
    if trends is None or trends.empty or item_col not in trends.columns:
        return None
    # declining → más negativos primero; rising → más positivos primero
    df = trends.sort_values("cambio_pct", ascending=declining)
    df = df[df["cambio_pct"] < 0] if declining else df[df["cambio_pct"] > 0]
    if df.empty:
        return None
    # head(n) toma los N más fuertes; invertir deja el más fuerte arriba (Plotly
    # dibuja la 1ª fila abajo en barras horizontales).
    df = df.head(n).iloc[::-1]
    color = DOWN_RED if declining else UP_GREEN
    fig = go.Figure(go.Bar(
        x=df["cambio_pct"], y=df[item_col].astype(str), orientation="h",
        marker=dict(color=color, line=dict(color="white", width=0.5), cornerradius=5),
        text=[f"{v:+.0f}%" for v in df["cambio_pct"]],
        textposition="outside", textfont=dict(size=12, color=SUBTEXT),
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Cambio: <b>%{x:+.1f}%</b><extra></extra>",
    ))
    titulo = ("Productos con ventas a la baja" if declining
              else "Productos con ventas al alza")
    fig.update_layout(**_base_layout(titulo, height=max(360, len(df) * 32), bottom=40))
    _style_axes(fig, x_title="", y_title="")
    fig.update_yaxes(tickfont=dict(size=11), automargin=True)
    span = float(df["cambio_pct"].abs().max() or 1)
    fig.update_xaxes(range=[-span * 1.35, span * 1.35] if declining else [0, span * 1.35], automargin=True)
    fig.update_layout(margin=dict(r=80, l=168))
    fig.add_vline(x=0, line=dict(color=AXIS_COL, width=1))
    return fig
