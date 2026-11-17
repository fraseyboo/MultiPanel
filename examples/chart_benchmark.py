"""Chart performance benchmark (charts C5).

Pans and hovers a long line in an off-screen ChartView and prints frame
times::

    python examples/chart_benchmark.py [points ...]     # default 100000

The C5 target is under 16 ms per pan frame for 100k points.
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multipanel._widget_support import set_ui_scale  # noqa: E402
from multipanel.chartview import ChartView, XYChart  # noqa: E402
from multipanel.config import theme  # noqa: E402
from multipanel.router import EventRouter  # noqa: E402
from multipanel.testing import UiHarness  # noqa: E402
from multipanel.units import px  # noqa: E402


def benchmark(points):
    set_ui_scale(1.0)
    with UiHarness(size=(1200, 800)) as ui:
        ui.renderer.theme = theme(dark_mode=False)
        EventRouter.install(ui.interactor)
        x = np.linspace(0.0, 1000.0, points)
        y = np.sin(x / 7.0) + 0.3 * np.random.default_rng(1).normal(
            size=points)
        chart = XYChart()
        line = chart.addLine(x, y, name="signal")
        view = ChartView(ui.renderer, ui.interactor, chart)
        view.setGeometry(*(px(v) for v in (100, 100, 900, 500)))
        window = ui.interactor.GetRenderWindow()
        window.Render()
        window.Render()
        x0, y0, w, h = view.geometry("display")
        cx, cy = x0 + w / 2, y0 + h / 2
        for _ in range(4):                        # zoom in a little
            ui.wheel((cx, cy), steps=1)
            window.Render()

        def timed(action, count):
            times = []
            for i in range(count):
                start = time.perf_counter()
                action(i)
                window.Render()
                times.append(1e3 * (time.perf_counter() - start))
            return np.array(times)

        ui.press((cx + 300, cy))
        pan = timed(lambda i: ui.move((cx + 300 - 15 * i, cy)), 120)
        ui.release()
        hover = timed(lambda i: ui.move((cx + i, cy + 2)), 60)
        drawn = len(line._drawn[0]) if line.isDecimated() else points
        print(f"{points:>9,} points  pan median {np.median(pan):5.1f} ms, "
              f"max {pan.max():5.1f} ms  hover median "
              f"{np.median(hover):5.1f} ms  drawn {drawn:,}")


if __name__ == "__main__":
    for count in [int(v) for v in sys.argv[1:]] or [100_000]:
        benchmark(count)
