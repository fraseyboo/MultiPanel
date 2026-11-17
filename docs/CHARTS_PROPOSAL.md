# Proposal: VTK charts as first-class widgets

**Status:** accepted; in progress (decisions in §6) · **Scope:** MultiPanel (library) and its first host
application (first users) · **Builds on:** the Qt-parity work (router, layouts,
styles, models, popups; see `QT_PARITY_PROPOSAL.md`).

## 1. Summary

VTK ships a complete 2D charting system
([`vtkChart`](https://vtk.org/doc/nightly/html/classvtkChart.html) and its
family: `vtkChartXY`, `vtkChartPie`, `vtkChartBox`, `vtkChartHistogram2D`,
`vtkChartMatrix`, `vtkChartParallelCoordinates`, plus line, point, bar,
area, stacked, bag, box and 2D-histogram plots, legends, tooltips and range
handles). All of it is present in the VTK 9.5.2 build the host application uses.

Today charts sit beside the UI rather than inside it. They are drawn by
helper functions, placed in hand-managed panels, and switched on by
swapping interactor styles. This proposal makes a chart an ordinary
widget. It is laid out, themed, clipped, hidden, routed and tested like
every other control, and its series can be driven by the item models from
W9. The host application then gets charts where it needs them: source spectra (with
draggable points, the original purpose of the chart dispatch code),
material compositions, tally results and scene statistics.

## 2. What exists today

| Piece | Where | State |
| --- | --- | --- |
| Matplotlib-style helpers: `figure`, `add_line_chart`, `add_scatter_chart`, `add_bar_chart`, `add_filled_area_chart`, `add_errorbar_plot`, `imshow`, `add_box_plot`, `add_pie_chart`, axis titles, limits, legend, gridlines | `multipanel/charts.py` (2,700 lines) | Work, but use fixed colours and fonts (Arial, `SlateGray`/`white` backgrounds, black grid). They ignore the theme, `ui_scale` and dark mode. |
| `add_chart_actor` | `charts.py` | Puts a `vtkContextActor` in a draggable panel. Its resize code depends on globals (`panel_background`, `added_widgets`). It is not a widget: no layouts, no router, no hidden-tab rules. |
| `DraggableChartInteractorStyle` and `HybridInteractorStyle` | `charts.py`, and a copy in the host application's `LIBS/interactor_utils.py` | Switch the whole interactor between "chart" and "camera" by testing the pointer against the chart rectangle. The dragging style moves points (`CLICK_AND_DRAG`). |
| `ChartModeFilter` / `install_chart_mode` | `charts.py` (added in W1) | The same switching as a router event filter. A drag stays with the chart and widgets win. |
| Matplotlib rendered into VTK | `multipanel/mpl_utils.py` | A separate route to publication-style figures as textures. |
| Host prototype | `main.py`, `add_test_chart` (call commented out, l. 654) | An energy-spectrum chart (counts against keV) using the helpers above. |

## 3. Findings from two spikes

1. **Charts clip exactly in a `LinkedRenderer`.** A `vtkContextActor` added
   to a renderer whose viewport is a sub-rectangle sizes its scene to that
   viewport (300×200 here) and draws nothing outside it. So a chart can
   live inside a dock tab, a splitter or a `ScrollArea`, using the same
   clipping as the item views.
2. **Events can go straight to the chart.** The chart items (`vtkChartXY`
   and others) expose `MouseWheelEvent`, `MouseButtonPressEvent`,
   `MouseMoveEvent`, `MouseButtonReleaseEvent`, `MouseDoubleClickEvent`,
   `MouseEnterEvent` and `MouseLeaveEvent` to Python with a
   `vtkContextMouseEvent`. A wheel event delivered this way zoomed the x
   axis (0–50 to 10–40) without touching the interactor style. A
   press/move/release pan returned "handled" but did not move the axis in
   the quick test, so the event fields still need completing (button state
   during the move, last position, scene transform). The scene-level
   dispatch (`vtkContextScene::MouseMoveEvent` and so on) is not wrapped, so
   the widget hit-tests its own items. Usually there is one chart per
   widget, so this is trivial.

Together these remove the need to switch interactor styles: the router
hit-tests the chart widget like any other widget and hands it the events.

## 4. Design

```
 ChartView (WidgetMixin, native)            one per chart area
 ├─ LinkedRenderer (viewport = widget rect) exact clipping, own layer slot
 │   └─ vtkContextActor → vtkContextScene → vtkChart (XY, Pie, Box, ...)
 ├─ router events  ──► chart.Mouse*Event(vtkContextMouseEvent)  (C0)
 ├─ Style tokens   ──► axes, grid, labels, background, palette  (C4)
 └─ series         ◄── numpy arrays or ItemModel columns         (C1, C2)
```

- **`ChartView`** is a native widget, built the way `ListView` and
  `TextEdit` are. It has geometry and size hints, takes part in layouts,
  and is hidden properly (`SetDraw(False)`, no events, no updates). It
  converts router events, which use display pixels, into chart
  coordinates, which are viewport pixels of its `LinkedRenderer`. It holds
  the mouse grab during drags and emits Qt-style signals.
- **Chart classes** (object API, like Qt Charts): `XYChart`, `PieChart`,
  `BoxChart`, `HeatmapChart` (`vtkChartHistogram2D`) and `ChartGrid`
  (`vtkChartMatrix`, subplots). Series: `LineSeries`, `ScatterSeries`,
  `BarSeries`, `AreaSeries`, `StackedSeries`, `ErrorBarSeries`,
  `StepSeries` (histograms) and `RangeHandles`. Axes have titles, ranges,
  log scale, tick formats and autoscale.
- **Existing helpers stay** as thin wrappers over the classes, for scripts
  and notebooks. `add_chart_actor`, `HybridInteractorStyle` and
  `DraggableChartInteractorStyle` are deprecated in favour of `ChartView`.
  `ChartModeFilter` remains for charts placed directly in a scene renderer.

## 5. Workstreams

Sizes: S ≈ a session, M ≈ two or three, L ≈ more.

### C0 — `ChartView` foundation (M)

- A native widget hosting a `vtkContextActor` on its own `LinkedRenderer`.
  It supports the container protocol, `sizeHint`/`minimumSizeHint`,
  visibility (hidden-tab rules) and window resize.
- Event delivery from the router to the chart items: press, move,
  release, double-click, wheel, enter and leave, with the coordinate
  conversion and an implicit grab. Finish the pan fields from spike 2.
- **Acceptance:**
  - A chart in a `DockPane` tab and in a `ScrollArea` clips exactly.
  - The wheel zooms and a drag pans the chart; the 3D camera does not
    move.
  - In a hidden tab the chart draws nothing and receives nothing.
  - The audit (`tools/offscreen_ui.py --audit`) stays clean.

### C1 — Series and axes API (M)

- Implement the chart and series classes from §4, with numpy input.
  `series.setData(x, y)` updates the `vtkTable` arrays in place rather
  than rebuilding plots.
- Axes: title, range, `setLogScale`, tick format and unit suffix,
  autoscale and nice ticks. Legend placement.
- Re-implement the existing helpers on top of the classes, with the same
  signatures.
- **Acceptance:** the helper-based demos in `examples/chart_demos.py`
  render the same through the new classes, and log axes handle
  zero/negative data predictably (masked, not crashing).

### C2 — Model binding (S)

- A series can be bound to columns of a W9 `ItemModel`. `rowsInserted`
  appends points, `dataChanged` updates them in place, and `modelReset`
  rebuilds.
- Chart point selection and a `SelectionModel` stay in sync, so selecting
  rows in a `TableView` highlights the points and the reverse.
- **Acceptance:** appending 1 point to a 10k-point bound series updates
  without a full rebuild, and selection round-trips both ways.

### C3 — Interaction (M)

- Interaction modes in one call:
  `setInteraction(left="pan", wheel="zoom", right="select", shift_left="zoom_box")`.
  It maps onto `vtkChart` actions (`PAN`, `ZOOM`, `ZOOM_AXIS`, `SELECT`,
  `SELECT_RECTANGLE`, `SELECT_POLYGON`, `CLICK_AND_DRAG`).
- Reset view by double-click or Home. Hover tooltips go through the
  library's tooltip overlay (same delay, look and placement as other
  tooltips) rather than `vtkTooltipItem`.
- **Draggable points** (`CLICK_AND_DRAG`) emit `pointMoved` and
  `editFinished` signals, with optional constraints (x fixed, y ≥ 0,
  monotonic x) and undo. **Range handles** (`vtkPlotRangeHandlesItem`)
  emit `rangeChanged`, for energy windows.
- Context menu (W3 `Menu`): reset zoom, toggle log axes, export, copy data.
- **Acceptance:** in harness tests, dragging a point changes its value
  and emits once at release, and a selection rectangle selects the right
  indices.

### C4 — Theme, fonts and scale (S)

- Tokens map onto chart parts:
  - background → `panel`;
  - axes → `border`;
  - labels → `text`/`muted`;
  - grid → a soft border mix;
  - selection → `accent`.
- The bundled UI font is set on every chart text property. Font sizes and
  line widths follow `ui_scale`.
- A categorical series palette that is colour-blind safe and has
  light/dark variants.
- Theme changes repaint every chart (`refresh_renderer_theme`).
- **Acceptance:** screenshot tests of a chart gallery pass in both themes,
  and switching theme at runtime updates open charts.

### C5 — Performance (S–M)

- In-place array updates, renders through `RenderScheduler`, and no work
  for hidden charts.
- Decimation for long series: min/max per pixel column on the visible
  range, recomputed after zoom or pan.
- **Acceptance:** panning a 100k-point line costs under 16 ms per frame
  on the host application's machine, and a hidden chart costs nothing per frame.

### C6 — Export and tests (S)

- Export the chart area as PNG (any scale), SVG/PDF through
  `vtkGL2PSExporter` (check that it works with context actors first; fall
  back to PNG), and CSV of the series.
- `examples/chart_gallery.py` in both themes, plus screenshot tests on the
  same VTK-version-tagged references as the gallery.
- **Acceptance:** exports open and match on-screen content, and the
  gallery screenshot tests are part of the suite.

### C7 — Host application features (M each; choose and order in §6)

| | Feature | Chart pieces |
| --- | --- | --- |
| a | **Source energy spectrum.** Plot SDEF `ERG` distributions (SI/SP: discrete lines, histograms, functions) and edit them by dragging points and bin edges, written back to the source definition with undo. This is what `DraggableChartInteractorStyle` was for. | `XYChart`, `StepSeries`/`BarSeries`, draggable points, log axes |
| b | **Material composition.** Nuclide atom or mass fractions of the selected material; clicking a bar selects that row in the material table. | `BarSeries` or `PieChart`, model binding |
| c | **Tally results.** Imported tallies (e.g. MCTAL) against energy bins with relative-error bars, on log-log axes; several tallies overlaid; a mesh-tally slice as a heatmap linked to a slice plane in the 3D view. | `ErrorBarSeries`, `HeatmapChart`, `ChartGrid` |
| d | **Scene statistics.** Cell volumes, masses and importances as bars; clicking a bar selects the actor. | `BarSeries`, selection sync |

The chart dispatch in the host application's `HybridInteractorStyle` is replaced by
`ChartView`. The removal is ready but uncommitted in the host application's working
tree; see §8.

### C8 — Clean-up (S)

- Split `charts.py`:
  - widgets and series into `multipanel/chartview.py`;
  - functional helpers into `charts.py`;
  - colour utilities into a shared module.
- Deprecate `add_chart_actor`, `HybridInteractorStyle` and
  `DraggableChartInteractorStyle`, with a release of overlap.
- Document charts in `API.md`, and add a section on charts in layouts to
  `LAYOUTS.md`.

## 6. Decisions (agreed)

1. **First feature:** the source energy spectrum (C7a), on demo data until
   it is connected to the scene's SDEF.
2. **API:** chart objects (`XYChart`, series classes) as the core; the
   matplotlib-style helpers stay as wrappers.
3. **No 3D charts** (`vtkChartXYZ`, surface plots): the 3D view does that.
4. **Transport-code output parsers** (MCTAL, MESHTAL, output-file tables) are wanted.
   They belong in the host application and feed the charts as arrays
   or item models; see C9.
5. **Charts behave like scene panels:** a `ChartPanel` is a
   `WidgetPanel` (header, collapse, float, dock into `DockPane` tabs,
   hidden with its tab), not a separate window.

### C9 — Transport-code output parsers (host application; M)

- MCTAL reader: tallies, bins (energy, time, cosine, segment), values
  and relative errors, the statistical checks.
- MESHTAL reader: mesh tallies to arrays (for heatmaps and 3D overlays).
- Output-file tables of interest (e.g. table 126/140 summaries) as needed.
- Tested against small reference files; results feed C7c as arrays or
  `TableModel`s.

## 7. Risks

| Risk | Mitigation |
| --- | --- |
| Panning through direct events needs fields the spike did not fill. | First task of C0. Fall back to delivering through a `vtkContextInteractorStyle` (as `ChartModeFilter` does) if needed. |
| `vtkChart` re-lays out its axes on every paint, which could be slow with many charts visible. | Measure in C5; render charts only when dirty. |
| `vtkGL2PSExporter` support for context actors in OpenGL2 is limited. | Probe early in C6; PNG export always works. |
| Chart text uses VTK's own fonts and DPI. | Set the bundled font file on every text property (C4); test at `ui_scale` 1 and 2. |
| `vtkChartXY` hit-testing treats axes and legend as part of the chart. | Expected: the widget owns the whole chart rectangle. |

## 8. Release plan

| Step | Contents | Host application change |
| --- | --- | --- |
| 1 | C0, C1 (XY only), C4 | A themed, zoomable XY chart in a dock tab (the prototype spectrum). Commit the dispatch removal at this point. |
| 2 | C3, C2, C6 | Interaction, selection, export, gallery tests. |
| 3 | C7a, C5 | Source spectrum editor. |
| 4 | C7b–d, remaining C1 chart types, C8 | Composition, tallies, statistics; clean-up. |

The removal of the old chart dispatch from the host application's
`HybridInteractorStyle` is ready but **uncommitted** in the host application's
working tree. It fits this plan, because charts come back as widgets,
not interactor styles. It can be committed now, or held until step 1
lands.

## 9. Checklist

- [x] C0 `ChartView`: own renderer, layout/visibility protocol, router event delivery, grab
- [x] C1 `XYChart`/series/axes API (line, scatter, bar incl. horizontal, step histogram, stems, error bars; log axes, fixed/auto ranges, category labels, legend position); the common functional helpers accept it
- [x] C1 `PieChart`, `Histogram2DChart` (heat map), x/y error bars, box plots (`BoxSeries`) and `ChartGrid` (linked axes)
- [x] C2 Series bound to `ItemModel` (`chart_models.bind_series`, incremental); selection sync with `SelectionModel` both ways
- [x] C3 Interaction: pan/zoom/box zoom/reset, draggable data with undo, `setInteraction` bindings (incl. axis zoom), themed series-aware tooltips, right-click context menu with export (separate range handles not needed: `zoom_axis`)
- [x] C4 Theme tokens, bundled font, `ui_scale`, palette, live theme switch
- [x] C5 In-place updates, decimation (per-pixel min/max), hidden charts free, benchmark (`examples/chart_benchmark.py`: pan ~1 ms/frame median, worst 4.5 ms at 100k points)
- [x] C6 PNG/SVG/PDF/CSV export (`chart_export`); chart gallery and screenshot tests
- [x] C7a Source energy spectrum (the host application): shows the selected source's (or the next source's) discrete, histogram or continuous energy distribution; drag edits write back with the host application undo
- [x] C7b Material composition (the host application): horizontal bars of element or nuclide weight/atom % for the material picked in the Material Selector (no material table to link to yet)
- [x] C7c Tally results and mesh-tally heatmap (the host application): MCTAL energy spectra with error bars and MESHTAL meshes (XYZ, RZT; whole or by layer) coloured in the 3D view, in a Results tab fed by dropped files
- [x] C7d Scene statistics (the host application): cell volume, mass and density bars in the Validation tab; clicking a bar selects the cell, the selection is highlighted
- [x] C8 Split `charts.py` (`chart_legacy`, shared colour helpers); deprecate the old chart styles and `add_chart_actor`; helpers accept `XYChart`; API and LAYOUTS docs
- [x] C9 Transport-code output parsers (MCTAL, MESHTAL column formats) in the host application
