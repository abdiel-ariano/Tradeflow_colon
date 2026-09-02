"""Guard against Plotly value labels floating outside charts."""
from __future__ import annotations

import pandas as pd
from django.test import SimpleTestCase

from analytics.engine import chart_generator as cg


class TestChartLabelHygiene(SimpleTestCase):
    """Bar/trend charts must not paint outside text that collides with axes."""

    def test_horizontal_bars_have_no_outside_value_labels(self):
        """Ranking bars expose values via hover/axis only."""
        df = pd.DataFrame({
            "producto": [f"Item {i}" for i in range(6)],
            "line_total": [1200, 900, 700, 400, 200, 100],
            "cat": ["A", "A", "B", "B", "C", "C"],
        })
        for fig in (
            cg.grouped_bar(df, "producto", "line_total"),
            cg.bar_top(df, "cat"),
        ):
            self.assertIsNotNone(fig)
            trace = fig.data[0]
            text = getattr(trace, "text", None)
            self.assertTrue(text is None or text == "" or list(text) == [])
            pos = getattr(trace, "textposition", None)
            self.assertNotEqual(pos, "outside")

    def test_trend_bars_have_no_outside_percent_labels(self):
        """Rising/falling bars keep % on the axis/hover, not as outside text."""
        trends = pd.DataFrame({
            "producto": [f"P{i}" for i in range(5)],
            "cambio_pct": [-40.0, -22.5, -11.0, -6.0, -2.0],
        })
        fig = cg.trend_bar(trends, "producto", declining=True)
        self.assertIsNotNone(fig)
        text = getattr(fig.data[0], "text", None)
        self.assertTrue(text is None or text == "" or list(text) == [])
        self.assertNotEqual(getattr(fig.data[0], "textposition", None), "outside")

    def test_dense_heatmap_hides_cell_numbers(self):
        """Wide correlation matrices stay color-only to avoid digit clutter."""
        wide = pd.DataFrame({f"m{i}": range(12) for i in range(8)})
        fig = cg.correlation_heatmap(wide)
        self.assertIsNone(fig.data[0].texttemplate)

    def test_histogram_has_no_mean_median_annotations(self):
        """Reference lines stay silent so card titles are not crowded."""
        df = pd.DataFrame({"ventas": [10, 20, 30, 40, 50, 60, 70]})
        fig = cg.histogram(df, "ventas")
        anns = list(fig.layout.annotations or [])
        texts = " ".join(str(a.text or "") for a in anns)
        self.assertNotIn("Media:", texts)
        self.assertNotIn("Mediana:", texts)
