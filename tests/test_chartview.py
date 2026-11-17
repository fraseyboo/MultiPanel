"""ChartView, XYChart, series and ChartPanel (CHARTS_PROPOSAL C0/C1/C4)."""
import numpy as np
import pytest
import vtk

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.chartview import (
    ChartPanel, ChartView, ErrorBarSeries, StemSeries, StepSeries, XYChart,
    palette,
)
from multipanel.config import theme
from multipanel.containers import DockPane
from multipanel.router import EventRouter
from multipanel.testing import UiHarness
from multipanel.units import px

SIZE = (900, 600)
VIEW = (450, 150, 400, 300)              # x, y, w, h logical px


@pytest.fixture
def ui():
    previous = user_scale()
    set_ui_scale(1.0)
    with UiHarness(size=SIZE) as harness:
        harness.renderer.theme = theme(dark_mode=False)
        harness.interactor.SetInteractorStyle(
            vtk.vtkInteractorStyleTrackballCamera())
        source = vtk.vtkCubeSource()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(source.GetOutputPort())
        cube = vtk.vtkActor()
        cube.SetMapper(mapper)
        harness.renderer.AddActor(cube)
        harness.renderer.ResetCamera()
        harness._keep = source
        EventRouter.install(harness.interactor)
        yield harness
        EventRouter.uninstall(harness.interactor)
    set_ui_scale(previous)


def line_chart():
    chart = XYChart(title="Test")
    chart.addLine(np.arange(50.0), np.arange(50.0) ** 0.5, name="sqrt")
    return chart


def view_of(ui, chart=None):
    view = ChartView(ui.renderer, ui.interactor, chart or line_chart())
    view.setGeometry(*(px(v) for v in VIEW))
    ui.render()
    return view


def camera(ui):
    return tuple(round(v, 6) for v in
                 ui.renderer.GetActiveCamera().GetPosition())


def centre(view):
    x, y, w, h = view.geometry("display")
    return (x + w / 2, y + h / 2)


def x_range(view):
    return tuple(round(v, 4) for v in view.chart().axisX().range())


# -- the widget --------------------------------------------------------------------------
def test_chart_draws_in_its_own_clipped_viewport(ui):
    view = view_of(ui)
    x0, y0, x1, y1 = view._content.GetViewport()
    assert (x0 * SIZE[0], y0 * SIZE[1]) == pytest.approx(VIEW[:2])
    assert ((x1 - x0) * SIZE[0], (y1 - y0) * SIZE[1]) == \
        pytest.approx(VIEW[2:])
    scene = view._actor.GetScene()
    assert (scene.GetSceneWidth(), scene.GetSceneHeight()) == \
        pytest.approx(VIEW[2:])


def test_wheel_zooms_and_drag_pans_without_moving_the_camera(ui):
    view = view_of(ui)
    before_camera, start = camera(ui), x_range(view)
    ui.wheel(centre(view), steps=2)
    zoomed = x_range(view)
    assert zoomed[1] - zoomed[0] < start[1] - start[0]
    cx, cy = centre(view)
    ui.drag((cx, cy), (cx + 60, cy), steps=4)
    panned = x_range(view)
    assert panned[0] < zoomed[0]                       # dragged right
    assert panned[1] - panned[0] == pytest.approx(zoomed[1] - zoomed[0])
    assert camera(ui) == before_camera


def test_the_scene_still_moves_outside_the_chart(ui):
    view = view_of(ui)
    before, start = camera(ui), x_range(view)
    ui.drag((100, 100), (200, 160), steps=4)
    assert camera(ui) != before and x_range(view) == start


def test_double_click_and_home_reset_the_view(ui):
    view = view_of(ui)
    start = x_range(view)
    ui.wheel(centre(view), steps=3)
    assert x_range(view) != start
    ui.double_click(centre(view))
    assert x_range(view) == start
    ui.wheel(centre(view), steps=2)
    ui.key("Home")
    assert x_range(view) == start


def test_right_drag_zooms_to_a_box(ui):
    view = view_of(ui)
    start = x_range(view)
    cx, cy = centre(view)
    ui.drag((cx - 80, cy - 60), (cx + 40, cy + 50), button="right", steps=4)
    zoomed = x_range(view)
    assert zoomed[1] - zoomed[0] < (start[1] - start[0]) / 2


def test_fixed_ranges_survive_reset(ui):
    view = view_of(ui)
    view.chart().axisX().setRange(10, 20)
    ui.wheel(centre(view), steps=2)
    view.resetView()
    assert x_range(view) == (10.0, 20.0)
    view.chart().axisX().setAutoRange()
    assert x_range(view)[1] >= 49


def test_hidden_views_draw_nothing_and_take_no_input(ui):
    view = view_of(ui)
    view.SetVisibility(False)
    ui.render()
    assert not view._content.GetDraw()
    before = camera(ui)
    start = x_range(view)
    ui.wheel(centre(view), steps=2)
    assert x_range(view) == start
    assert camera(ui) != before                        # the scene got it


# -- theme ----------------------------------------------------------------------------------
def test_theme_colours_and_palette(ui):
    view = view_of(ui)
    tokens = ui.renderer.theme.tokens
    axis = view.chart().axisX().vtkAxis()
    assert axis.GetLabelProperties().GetColor() == pytest.approx(
        tokens["muted"])
    assert axis.GetTitleProperties().GetFontFamilyAsString() == "File"
    plot = view.chart().series()[0].vtkPlot()

    def colour():
        rgb = [0.0, 0.0, 0.0]
        plot.GetColorF(rgb)
        return rgb

    assert colour() == pytest.approx(palette(False)[0], abs=0.01)
    ui.renderer.theme.update(dark_mode=True)
    view.refreshTheme()
    tokens = ui.renderer.theme.tokens
    assert axis.GetLabelProperties().GetColor() == pytest.approx(
        tokens["muted"])
    assert colour() == pytest.approx(palette(True)[0], abs=0.01)


# -- series ---------------------------------------------------------------------------------
def test_step_series_draws_bins_and_validates():
    step = StepSeries([0, 1, 2, 4], [0.2, 0.5, 0.3])
    columns = step._columns()
    assert list(columns["x"]) == [0, 1, 1, 2, 2, 4]
    assert list(columns["y"]) == [0.2, 0.2, 0.5, 0.5, 0.3, 0.3]
    with pytest.raises(ValueError):
        StepSeries([0, 1, 2], [1, 2, 3])


def test_stems_are_segments_from_zero():
    stems = StemSeries([0.662, 1.173], [0.85, 1.0])
    columns = stems._columns()
    assert list(columns["x"]) == [0.662, 0.662, 1.173, 1.173]
    assert list(columns["y"]) == [0.0, 0.85, 0.0, 1.0]


def test_set_data_updates_in_place_and_refits(ui):
    view = view_of(ui)
    series = view.chart().series()[0]
    table = series._table
    series.setData(np.arange(200.0), np.arange(200.0))
    assert series._table is table and table.GetNumberOfRows() == 200
    assert x_range(view)[1] >= 199
    with pytest.raises(ValueError):
        series.setData([1, 2], [1])


def test_add_and_remove_series(ui):
    view = view_of(ui)
    chart = view.chart()
    bars = chart.addBars([1, 2, 3], [3, 1, 2], name="bars")
    step = chart.addStep([0, 1, 2], [1, 2], name="hist", fill=True)
    assert chart.vtkChart().GetNumberOfPlots() == 4      # line, bars, area, line
    chart.removeSeries(step)
    chart.removeSeries(bars)
    assert chart.vtkChart().GetNumberOfPlots() == 1
    assert [s.name() for s in chart.series()] == ["sqrt"]


# -- panels ---------------------------------------------------------------------------------
def test_chart_panel_docks_and_hides_with_its_tab(ui):
    dock = DockPane(ui.renderer, ui.interactor, side="left", width=0.4)
    dock.add_tab("source", "add_shape")
    dock.add_tab("tools", "GRI")
    panel = ChartPanel(ui.renderer, ui.interactor, line_chart(),
                       title="Spectrum", chart_height=200)
    dock.add_panel(panel, tab="source")
    ui.process_events()
    ui.render()
    view = panel.chartView()
    assert view.isVisible() and view._content.GetDraw()
    assert view.geometry("px")[3] >= 200
    px0, px1, py0, py1 = panel.GetBounds()
    vx, vy, vw, vh = view.geometry("frac")
    assert px0 <= vx and vx + vw <= px1 + 1e-6 and py0 <= vy
    dock.select_tab("tools")
    ui.render()
    assert not view._content.GetDraw()
    dock.select_tab("source")
    ui.render()
    assert view._content.GetDraw()


def test_collapsing_the_panel_hides_the_chart(ui):
    panel = ChartPanel(ui.renderer, ui.interactor, line_chart(),
                       title="Floating")
    ui.process_events()
    ui.render()
    view = panel.chartView()
    assert view._content.GetDraw()
    panel.collapse_panel()
    ui.render()
    assert not view._content.GetDraw()
    panel.expand_panel()
    ui.render()
    assert view._content.GetDraw()


def test_nice_ranges():
    from multipanel.chartview import _nice_range

    assert _nice_range(0, 49) == (0.0, 50.0)
    assert _nice_range(0, 0.0952) == (0.0, 0.1)
    assert _nice_range(-3.2, 7.9) == (-5.0, 10.0)
    assert _nice_range(0.003, 870, log=True) == (0.001, 1000.0)


def test_a_docked_chart_gets_its_events(ui):
    dock = DockPane(ui.renderer, ui.interactor, side="left", width=0.45)
    dock.add_tab("source", "add_shape")
    panel = ChartPanel(ui.renderer, ui.interactor, line_chart(),
                       title="Spectrum", chart_height=200)
    dock.add_panel(panel, tab="source")
    ui.process_events()
    ui.render()
    view = panel.chartView()
    assert panel.parentWidget() is dock
    router = EventRouter.for_interactor(ui.interactor)
    assert router.hitChain(*centre(view))[0] is view
    before, start = camera(ui), x_range(view)
    ui.wheel(centre(view), steps=2)
    assert x_range(view) != start and camera(ui) == before
    dock.remove_panel(panel)
    assert panel.parentWidget() is None


def test_log_axes_fit_in_data_units(ui):
    chart = XYChart()
    chart.addLine([1, 2, 3], [0.003, 0.4, 870.0], name="decades")
    chart.axisY().setLogScale(True)
    view_of(ui, chart)
    assert chart.axisY().range() == pytest.approx((0.001, 1000.0))
    chart.axisY().setRange(0.01, 100)
    assert chart.axisY().range() == pytest.approx((0.01, 100.0))


def test_include_zero_widens_a_narrow_fit(ui):
    chart = XYChart()
    chart.addStems([0.9], [0.95], name="one line")
    view_of(ui, chart)
    low, high = chart.axisX().range()
    assert low > 0.5                                     # hugs the line
    chart.axisX().setIncludeZero()
    assert chart.axisX().range() == pytest.approx((0.0, 1.0))
    chart.axisX().setLogScale(True)                      # ignored on log axes
    assert chart.axisX().range()[0] > 0


def test_error_bars_follow_their_series():
    chart = XYChart()
    step = chart.addStep([0, 1, 2], [1.0, 2.0], name="tally")
    bars = chart.addErrorBars([0.5, 1.5], [1.0, 2.0], [0.1, 0.4], of=step)
    columns = bars._columns()
    # the bars first, then their caps
    assert list(columns["x"][:4]) == [0.5, 0.5, 1.5, 1.5]
    assert list(columns["y"][:4]) == pytest.approx([0.9, 1.1, 1.6, 2.4])
    assert len(columns["x"]) == 4 + 2 * 4
    assert not bars.vtkPlot().GetLegendVisibility()

    def colour(series):
        rgb = [0.0, 0.0, 0.0]
        series.vtkPlot().GetColorF(rgb)
        return rgb

    assert colour(bars) == pytest.approx(colour(step))
    other = chart.addLine([0, 2], [0, 1], name="next")   # palette continues
    assert colour(other) == pytest.approx(palette(False)[1], abs=0.01)
    assert chart.axisY().range()[1] >= 2.4
    asymmetric = ErrorBarSeries([1.0], [2.0], ([0.5], [1.0]))
    assert list(asymmetric._columns()["y"]) == [1.5, 3.0]
    with pytest.raises(ValueError):
        ErrorBarSeries([1.0], [1.0], [-0.1])
    bars.setData([0.5, 1.5], [1.0, 1.0], [0.2, 0.2])
    assert bars.errors()[1] == pytest.approx([0.2, 0.2])


def test_chart_panel_caption(ui):
    plain = ChartPanel(ui.renderer, ui.interactor, line_chart(), title="A")
    assert plain.caption() is None
    panel = ChartPanel(ui.renderer, ui.interactor, line_chart(), title="B",
                       caption="Total 1.0")
    ui.process_events()
    ui.render()
    label, view = panel.caption(), panel.chartView()
    assert label.text() == "Total 1.0"
    lx, ly, _lw, _lh = label.geometry("px")
    vx, vy, _vw, vh = view.geometry("px")
    assert ly > vy + vh - 1                  # above the chart (y up)


def test_bars_show_whole_and_from_zero(ui):
    chart = XYChart()
    chart.addBars([1, 2, 3], [104.0, 108.0, 110.0], name="bars")
    view_of(ui, chart)
    low, high = chart.axisX().range()
    half = chart.vtkChart().GetBarWidthFraction() / 2
    assert low <= 1 - half and high >= 3 + half
    assert chart.axisY().range()[0] == 0.0


def test_horizontal_bars_and_category_labels(ui):
    chart = XYChart()
    bars = chart.addBars([3, 2, 1], [0.6, 0.3, 0.1], name="fractions",
                         horizontal=True)
    chart.axisY().setTickLabels([3, 2, 1], ["O", "C", "H"])
    view_of(ui, chart)
    assert bars.isHorizontal()
    assert bars.vtkPlot().GetOrientation() == vtk.vtkPlotBar.HORIZONTAL
    x_low, x_high = chart.axisX().range()
    y_low, y_high = chart.axisY().range()
    assert x_low == 0.0 and x_high >= 0.6
    half = chart.vtkChart().GetBarWidthFraction() / 2
    assert (y_low, y_high) == pytest.approx((1 - half, 3 + half))  # exact
    assert chart.axisX().vtkAxis().GetTitle() == ""     # not "X Axis"
    axis = chart.axisY().vtkAxis()
    assert axis.GetTickLabels().GetValue(0) == "O"
    assert chart.axisY().tickLabels() == ([3.0, 2.0, 1.0], ["O", "C", "H"])
    chart.axisY().clearTickLabels()
    assert chart.axisY().tickLabels() is None
    with pytest.raises(ValueError):
        chart.axisY().setTickLabels([1, 2], ["a"])


def test_untitled_charts_keep_a_small_top_margin():
    from multipanel.chartview import _DEFAULT_TOKENS

    chart = XYChart()
    chart.applyTheme(_DEFAULT_TOKENS, scale=2.0)
    assert chart.vtkChart().GetHiddenAxisBorder() == 20       # 10 px x 2
    chart.setTitle("Titled")
    assert chart.vtkChart().GetHiddenAxisBorder() == 40


def test_short_axes_get_readable_ticks(ui):
    chart = XYChart()
    chart.addBars([2, 1], [27.0, 8.0], name="v", horizontal=True)
    chart.axisY().setTickLabels([2, 1], ["a", "b"])
    view = ChartView(ui.renderer, ui.interactor, chart)
    view.setGeometry(*(px(v) for v in (300, 100, 120, 200)))
    ui.render()
    ui.render()
    start, end, _low, _high = chart.axisX()._span()
    assert abs(end - start) < chart.axisX().SHORT_AXIS_PX
    axis = chart.axisX().vtkAxis()
    ticks = axis.GetTickPositions()
    values = [ticks.GetValue(i) for i in range(ticks.GetNumberOfTuples())]
    assert values == [0.0, 10.0, 20.0, 30.0]
    assert chart.axisY().tickLabels()[1] == ["a", "b"]    # untouched
    view.setGeometry(*(px(v) for v in (300, 100, 500, 300)))
    ui.render()
    ui.render()
    assert chart.axisX()._short_ticks is None             # VTK's own again


def test_nice_ticks():
    from multipanel.chartview import _nice_ticks

    assert _nice_ticks(0, 30) == [0.0, 20.0]
    assert _nice_ticks(0, 30, count=4) == [0.0, 10.0, 20.0, 30.0]
    assert _nice_ticks(0, 1, count=3) == [0.0, 0.5, 1.0]
    assert _nice_ticks(-3.2, 7.9) == [0.0, 5.0] or \
        _nice_ticks(-3.2, 7.9) == [-0.0, 5.0]
