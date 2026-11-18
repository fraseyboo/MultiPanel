# Changelog

All notable changes to MultiPanel will be documented here.

## Unreleased

## 0.1.0 (2026-11-18)

First public release, as MultiPanel (formerly VTK-2D-UI).

- Requires VTK 9.4 or newer (was 9.3): VTK 9.3's Python bindings cannot
  pass non-ASCII key codes (`é`, `µ`), so hosts such as Qt could not
  forward that typing. CI tests VTK 9.4, 9.5 and the latest release, on
  Python 3.10 to 3.13, on Linux and macOS.
- The scene background uses VTK's own dithered gradient
  (`SetDitherGradient`) instead of a pre-dithered texture; the texture
  remains as `apply_scene_theme(..., dither="texture")`, and
  `MULTIPANEL_BACKGROUND_DITHER=vtk|texture|off` overrides the default.
- `multipanel.__version__`; a `publish` workflow releases a version tag
  to PyPI.
- Removed the unused `icons/old` folder.
- **Renamed from VTK-2D-UI to MultiPanel** (package `multipanel`,
  distribution `multipanel`), so the project is not mistaken for an
  official VTK project. `import vtk_2d_ui` still works through a
  deprecated alias that returns the `multipanel` modules. Environment
  variables are now `MULTIPANEL_*` (`MULTIPANEL_LOG`, `MULTIPANEL_BACKEND`,
  `MULTIPANEL_CLIPBOARD`, `MULTIPANEL_ANIMATIONS`, `MULTIPANEL_UI_THEME`,
  `MULTIPANEL_UI_ACCENT`, `MULTIPANEL_UI_SCALE`,
  `MULTIPANEL_RENDER_PROFILER`).
- Licensed under the BSD 3-Clause License; the third-party fonts are
  listed in `THIRD_PARTY_NOTICES.md` with their license texts.
- New chevron icons drawn for MultiPanel (`tools/make_chevrons.py`: one
  rounded stroke in four directions), replacing chevrons from Material
  Design Icons. The unused `trash-can-outline` and
  `unfold-less-horizontal` icons (also from that set) were removed.
- Host-specific behaviour is now configured by the host:
  `config.set_settings_scope(org, app)` names the Qt preference store
  (default "MultiPanel"), and `set_scene_actor_predicate` /
  `set_actor_material_resolver` choose the actors the viewport display
  modes restyle and their materials.
- `specialists.add_logo` takes the logo image (a path or an icon name); the
  package ships no logos.
- New `examples/quickstart.py`.
- Editable `TextWidget`s whose text is wider than the field shorten it
  with an ellipsis when not editing (`elide_to_bounds` now defaults to
  `editable`), and hovering a shortened field shows its full text as a
  tooltip; while editing the field still scrolls to the caret.
- Text input from characters (W6): `TextWidget` inserts what
  `CharEvent` delivers (Shift, Alt/Option and dead-key compositions) and
  consumes it while editing, so the interactor style's hotkeys (w, e, q,
  3, ...) never see typing, with or without an EventRouter; key presses
  only drive editing keys and shortcuts. The key-code blanking hack is
  gone. VTK carries one Latin-1 character per event; hosts deliver other
  text with `insertText`.
- Chart interaction (charts C3): `ChartView.setInteraction()` binds
  buttons, modifier variants and the wheel to chart actions; presses wait
  for a 3 px slop so clicks and drags are told apart; a right click opens
  a context menu (reset, log axes or log colours, legend, export to
  PNG/SVG/PDF/CSV with `setExportFolder`, `exported`,
  `contextMenuAboutToShow`).
- Box plots: `XYChart.addBoxes` / `BoxSeries` (quartile box, median,
  Tukey whiskers with caps, outliers, group labels, statistics tooltips,
  CSV rows), `box_statistics`.
- `multipanel.chart_grid.ChartGrid` / `ChartGridPanel`: charts in a grid
  with linked x and/or y axes. ChartView emits `viewChanged` after a box
  zoom too.
- Gallery: box plot and linked-axes cards (thirteen in all).
- Error bars in x and y with capped ends (`ErrorBarSeries(x_errors=,
  caps=)`, `XYChart.addErrorScatter`), as the old `ErrorBar` drew; errors
  appear in the tooltips of the series they belong to.
- `Histogram2DChart` (2D histogram / heat map with a colour legend, log
  colour scale, bin tooltips) and `PieChart` (themed slices, legend,
  tooltips, clicks), both usable in `ChartView`/`ChartPanel` and export.
- CSV export gains an `x_low` column (x error bars, 2D histogram cells).
- The chart gallery shows the new types (eleven cards) and the chart
  screenshot tests cover them.
- `examples/chart_gallery.py` without a folder opens an interactive
  gallery: every chart type in a 4 x 2 grid of cards (lines, histogram
  with error bars and lines, log axis, bars, composition, an editable
  spectrum, clickable bars, a table bound to a chart); T switches theme.
- Chart model binding (charts C2): `chart_models.bind_series` keeps a
  series in step with two columns of an item model incrementally (an
  appended row reads one row) and syncs selection both ways with a
  `SelectionModel`; every series has `setHighlighted` (accent markers;
  bars recolour).
- Fix: the missing-icon fallback replaced every "vtk" in the path
  (`input.replace("vtk", "svg")`), so `…/multipanel/…` or any folder with
  "vtk" in its name broke it. `resources.icon_sources(path)` lists the
  candidates changing only the format folder and extension
  (`vtk_icons/x.vtk` → `svg_icons/x.svg`, `png_icons/x.png`), then the
  icon's own folder, then the package's; `resources.icon_folder(fmt)`.
- Narrow windows:
  - `DockPane` content keeps at least `MIN_CONTENT_PX` (220 logical px)
    instead of shrinking with its window fraction.
  - When the docks would leave the scene under `MIN_SCENE_PX` (200
    logical px), the newest dock collapses first (to its tab bar if it
    has tabs), and re-opens once there is room; collapsing or expanding
    by hand is respected until the next width change. Also on start-up.
  - `ViewportDisplayPanel` shrinks its buttons to the visible scene
    instead of spilling over the docks; buttons stay square in portrait
    windows (they shrank by the aspect ratio); the camera orientation
    widget stays where the layout puts it (VTK moved its renderer back
    to the window corner, over the right pane, on every render).
  - Fix: `TypeError` from the camera widget's `SetSize` in narrow
    windows (a float size once the padding scaled with the display).
  - `DockPane.setCollapsed` keeps a tab-less pane's collapse button in
    step.
- High-DPI and multi-display windows (`multipanel.display`):
  - `ui_scale()` now includes the display density (window DPI / 72: 2 on
    a Retina display), so logical-px sizes keep their physical size as
    text (sized by VTK from the DPI) does; `font_scale()` gives the
    preference alone for font point sizes, `user_scale()` for fractions.
    Fixed point-as-pixel mix-ups (panel header band, list and title text
    sizes, dock fraction widths, the viewport display panel).
  - `DisplayWatcher` (installed by `EventRouter.install`) keeps the
    density current and sends the resize events VTK's Cocoa window often
    omits when it moves between displays, so layouts re-run.
  - `fit_window_to_screen` (used by `vtk_utils.create_renderer`): macOS
    shrank a window taller than its screen without VTK noticing, cutting
    off the top of the UI.
  - Dock tab bars shrink their tabs to fit a short window instead of
    overlapping them.
  - Test fixtures save the preference with `user_scale()`.
- Chart performance (charts C5): long line series are decimated per
  pixel column (first/min/max/last) on the visible range and recomputed
  after pans and zooms; hit-testing, tooltips and editing are vectorised
  (hover on 100k points: 151 ms to 0.1 ms per move); `Axis.toScene`/
  `fromScene` take arrays; `examples/chart_benchmark.py`.
- `charts.py` split (charts C8): the chart-actor helpers
  (`add_chart_actor`, `DraggableChartInteractorStyle`,
  `HybridInteractorStyle`, `install_chart_mode`) moved to
  `multipanel.chart_legacy` and are deprecated (`DeprecationWarning`;
  still importable from `charts`). The functional helpers accept an
  `XYChart`/`ChartView`/`ChartPanel`; `charts` imports with the base
  dependencies (no `vtk_utils`/scikit-learn) and shares its colour helpers
  with `colormap_utils`.
- Chart tooltips are series-aware: a histogram bin anywhere inside it
  (with its error), stems and bars along their length, else the nearest
  point; `setTooltipFormatter`, `ChartView.setTooltipsEnabled`. Before,
  only the plotted vertices answered, so bins and stems showed nothing.
- Fix: filled histograms fit their y axis from zero (the fill was cut).
- Highlighted bars fade the others towards the panel colour, so the
  highlight shows where the accent and series colours are alike.
- Fix: short axes (under 120 px, e.g. in narrow docks) could show a
  single tick; they now get three to five nice ticks.
- Clickable chart items: `series.setClickable()`, `chart.clicked(series,
  index)`, `chart.itemAt()`; a hand cursor over them. Bars highlight with
  `setHighlighted(indices)` (accent colour, per-bar lookup table).
- Untitled charts keep a 10 px margin above the plot instead of VTK's
  20 px title space (both scale with `ui_scale`).
- `addBars(..., horizontal=True)` and `Axis.setTickLabels(positions,
  labels)` for category charts (a labelled axis fits its data exactly).
- Fix: unset axis titles showed VTK's "X Axis"/"Y Axis"; legend headroom
  is only added when the legend is shown.
- Chart export (charts C6): `XYChart.export(path, size=, scale=)` to PNG,
  JPEG, TIFF, SVG, PDF, EPS/PS or CSV (`multipanel.chart_export`), drawn
  off-screen and returned to its view unchanged; `toCsv()`.
- `examples/chart_gallery.py` and chart screenshot tests against
  references (VTK 9.5.2) in both themes.
- Fix: bar charts cut their first and last bars in half (the x range
  fitted the bar centres) and could start above zero.
- `ChartPanel(..., caption=)`: a label above the chart (`panel.caption()`).
- `ErrorBarSeries` / `XYChart.addErrorBars(x, y, errors, of=)`: vertical
  error bars (VTK 9.5 plots have none), following another series' colour.
- `Series.setEditable(..., x_minimum=, x_maximum=)` bounds sideways
  drags of points, stems and histogram edges.
- Editing drags keep the grab offset (scene px), so grabbing a stem midway
  or moving it sideways no longer snaps its top to the pointer.
- `Axis.setIncludeZero()` makes the automatic range reach zero;
  `Series.setName()` renames a series.
- Chart editing (charts proposal C3): editable series drag in a
  `ChartView` (histogram bin tops and edges with ordering and minimum-gap
  constraints, stems, line/scatter/bar points), with hover highlight,
  cursors, `edited` signals on release and an undo/redo stack (Ctrl+Z,
  Ctrl+Y). `Axis.toScene`/`fromScene` map data to chart pixels.
- Fix: log-scale axes were fitted and fixed in log10 units by mistake;
  ranges are now given in data units (`SetUnscaledRange`).
- Add `multipanel.chartview` (charts proposal C0/C1/C4): `ChartView`, a
  native widget showing an `XYChart` on its own clipped renderer with
  pointer input delivered by the router (wheel zoom, drag pan, box zoom,
  reset); `XYChart` with line, scatter, bar, step-histogram and stem
  series, axes (titles, fixed/auto ranges with size-independent nice
  rounding, log scale, grid) and legend placement; theme colours, UI font
  and a colour-blind-safe palette; `ChartPanel` puts a chart in a scene
  panel that floats or docks.
- `DockPane.add_panel` parents the panel to the dock (and `remove_panel`
  unparents it), so router hit chains, theme refresh and `dump_tree`
  descend into docked panels.
- `charts.ChartModeFilter` / `install_chart_mode` (W1): chart-versus-camera
  switching as an EventRouter filter instead of an interactor style.
  `examples/chart_demos.py` uses it; `HybridInteractorStyle` stays for
  existing code.
- `vtk_utils` lists Matplotlib backends with `backend_registry` (no
  deprecation warning on Matplotlib 3.9+).
- The library no longer prints (W0 hygiene): about 300 `print` calls are
  module-logger calls (`logger.warning` for warnings and errors, else
  `logger.debug`) and about 280 commented-out `print` lines are gone. A
  test keeps library code print-free (`__main__` blocks excepted).
  `multipanel.enable_logging(level)` and `MULTIPANEL_LOG=debug` show debug
  output. The host application's startup console output drops from 11 lines to
  its own 4.
- `WidgetMixin.styleStateChanged(new, old)` and `updateStyleState()`
  (W7), emitted on hover (router), focus (FocusManager), `setEnabled` and
  native widgets' own state changes.
- `VectorButtonWidget` states from `Style`: rounded tiles show hover,
  pressed and checked; unavailable buttons draw their icon at
  `DISABLED_OPACITY` (0.4) unless already grayscale; assigning
  `button.enabled` now emits `enabledChanged`/`styleStateChanged` and
  repaints. Legacy buttons track hover themselves. In the host application the
  Transform panel's axis locks now look unavailable when nothing is
  selected.
- Add `multipanel.textedit.TextEdit` (W6): multi-line plain text with word
  wrapping, smooth vertical scrolling, exact clipping, line-wise caret
  movement, mouse selection, clipboard and undo, a read-only log mode
  (`appendPlainText` follows the end, `setMaximumBlockCount`), a
  placeholder and an optional monospace font. Only visible lines have
  actors.
- A left press on the scene takes keyboard focus from a native text
  editor (legacy `TextWidget`s keep ending their own editing).
- Text measurement caches distinguish monospace text.
- TextBuffer property test: random edit sequences undo back to the start.
- `TextWidget` line edit options (W6): `setMaxLength`, `setEchoMode`
  (password, noEcho, passwordEchoOnEdit; no copying masked text),
  `setInputMask` with `hasAcceptableInput` (a Qt-syntax
  `text_buffer.InputMask`; `TextBuffer(mask=...)` edits masked text with
  undo), `setCompleter` (`multipanel.completer.Completer`; a list under the
  field that keeps focus in it) and `insertText` for input-method text.
- `Popup.popup(take_focus=False)`; Escape only closes popups that took
  focus. `FocusManager` asks the focus widget's `focusKeyIntercept(key)`
  before handling Escape, Enter and Tab.
- Layout passes cache size hints for the duration of one pass
  (`layouts.layout_pass()`), so each widget is measured once per pass
  instead of about ten times; nothing is cached across passes, so widgets
  that change their hints without `updateGeometry()` are still re-measured.
  `DockPane.layout` runs as one pass: in the host application a dock layout pass
  drops from 14-23 ms to 5-9 ms on the heavier tabs, with pixel-identical
  results.
- `DockPane` wheel scrolling is smooth (`SCROLL_MS`; notches accumulate;
  instant, as before, with animations off), with `scrollOffset`,
  `setScrollOffset` and `scrollTo(offset, animated=True)`. Dragging the
  scroll bar, switching tabs and `restoreState` stop a running scroll.
- Add `multipanel.splitter.Splitter` (W2): widgets in a row or column with
  draggable handles; `setSizes` (also before the first layout), stretch
  factors, collapsing, `moveSplitter`, `splitterMoved`, state round trip.
- Add `multipanel.debug` (W10): `Inspector` (Ctrl+Alt+I outlines the widget
  under the pointer with its geometry, hints, policy and style state),
  `dump_tree()` and `describe()`.
- `examples/gallery.py` gains `render(theme, scene)`; screenshot tests
  check both themes and compare with VTK-version-tagged references in
  `tests/screenshots`.
- Add `docs/LAYOUTS.md`, the layout model with diagrams.
- `examples/views_demo.py` puts its views in a splitter.
- Add `multipanel.models` (W9): `ModelIndex`, `ItemModel`, `ListModel`,
  `TableModel`, `TreeModel.from_hierarchy` and `SelectionModel` (single,
  multi, extended; rows kept by persistent key through inserts and
  removals).
- Add `multipanel.views`: `ListView`, `TreeView` and `TableView` with
  Ctrl/Shift selection, keyboard navigation, check boxes, swatch and icon
  decorations, row tooltips, expandable branches, a resizable header,
  exact clipping and smooth wheel scrolling. Only visible rows have
  actors, and model changes update only the actors that changed.
- `ComboBox.setModel(model, column)` shows and follows an item model;
  `ScrollablePanel.setModel` accepts an `ItemModel`.
- `Style` has an `item` role (row selection, hover, header and branch
  colours).
- Add `multipanel.scrollarea`: `ScrollArea` (a clipped viewport onto one
  content widget; smooth wheel scrolling, `scrollTo`,
  `ensureWidgetVisible`, `widgetResizable`) and a native `ScrollBar`
  (drag the thumb, click the track to page). The content is drawn by the
  area's own renderer (`multipanel.layers.LinkedRenderer`) whose viewport is
  the area, so it is clipped exactly; widgets only receive clicks where
  they are visible.
- Popups (menus, combo box lists, message boxes) now draw on one
  full-window popup layer above every other renderer
  (`multipanel.layers.popup_layer`), so they also show above scroll areas.
  Native content made on another renderer is moved onto it when shown.
  `OverlayLayer.for_renderer` returns the window's shared stack.
- Default buttons and check marks use the theme's `accent_text` colour
  (white on the accent in dark mode instead of the panel colour).
- Add `multipanel.animation`: `PropertyAnimation` (setter method,
  attribute or callable; numbers and tuples; easing curves; loops,
  direction, pause/resume; `valueChanged`/`finished`/`stateChanged`),
  `animate()`, and a global switch `set_animations_enabled(False)` /
  `MULTIPANEL_ANIMATIONS=0` that makes animations jump to their end.
- Popups and menus fade in (`Popup.FADE_IN_MS`, `setWindowOpacity`);
  the `ProgressBar` busy chunk eases back and forth on an animation and
  requests no renders while hidden.
- Menu shortcut text is raised (and faded) with its menu.
- Editing text wider than its field scrolls horizontally to keep the caret
  in view (as `QLineEdit`): the view moves only as far as needed, slides
  back as text is deleted, and dragging a selection past an edge scrolls.
  Applies to fields with `scale_text_to_widget=False`.
- Add `multipanel.style`: `Style.for_renderer(renderer).color(role, part,
  states)` resolves colours from theme tokens by role and state, with
  `setOverride("#objectName" | "*", role, part, color, states=...)`;
  `WidgetMixin.styleState()`. The standard controls draw through it.
- Keyboard focus ring: Tab/Shift-Tab focus outlines the focused widget
  (native or legacy) with a 2 px accent ring; never shown for mouse focus
  or while a field is editing.
- `TextWidget` draws its caret as a thin line (no longer an inline "I"
  that shifted the text); pass `caret_text="I"` for the old behaviour.
  Hiding a field while it edits commits the edit; `close()` removes the
  caret and selection actors. A field focused by Tab keeps that focus
  reason when editing starts.
- `TextWidget` editing on the new `TextBuffer`: selection (Shift, mouse
  drag, double/triple click) with a highlight, word movement and deletion,
  clipboard (`multipanel.clipboard`), undo/redo, and click-to-caret.
- Add `MenuBar`, `StatusBar` (status tips on hover via the router's new
  `hoverChanged` signal) and `MessageBox` (modal, dimmed backdrop via
  `Popup.setScrim`); `Label(bold=True)`.
- Add `multipanel.standard`: native `Label`, `PushButton`, `CheckBox`,
  `RadioButton`/`ButtonGroup`, `ProgressBar`, `Menu`/`MenuItem` and
  `ComboBox`, themed from the renderer's tokens; `examples/gallery.py`.
- Context menus for any widget: `setContextMenuPolicy("custom"|"actions")`,
  `customContextMenuRequested`, `addAction`/`actions`.
- `Frame`/`Popup` backgrounds use the theme's panel and border tokens.
- Add `multipanel.actions`: `Action` (text, tool/status tips, enabled,
  checkable, shortcut; `triggered`/`toggled`/`changed`), `ActionGroup`
  (exclusive), `KeySequence` and `Shortcut` (application/widget contexts,
  ambiguity detection), dispatched by the EventRouter after the focus
  widget. Text-editing keys stay with an editing field.
- `VectorButtonWidget.setAction` binds a button to an action.
- `FocusManager` only consumes Escape when something was cancelled, so a
  clicked button no longer swallows the application's Escape.
- Fix timers and render scheduling on VTK's native macOS (Cocoa)
  interactor: it leaves `GetTimerEventId()` at 0 and passes the firing
  timer's id only as `TimerEvent` call data. `Timer` never fired (no
  tooltips) and `RenderScheduler` dropped every request after its first.
  Both now read the id from call data via `core.timer_observer`.
- Add `multipanel.overlay`: `Popup` (anchored or point placement with
  flipping and clamping, `aboutToShow`/`aboutToHide`/`closed`, modal
  option) and `OverlayLayer` (outside-click dismissal that does not click
  through, nested popups, Escape, modal input blocking, raise to front).
- Tooltips wait `tooltip_delay()` ms (default 700, `set_tooltip_delay`)
  before showing, switch immediately between neighbours, and hide on press.
- `Timer` and `RenderScheduler` use `QTimer` under a running Qt application:
  Qt's VTK interactor shares one 10 ms timer for all VTK timers, ignoring
  durations and mixing up timer ids.
- `Frame` hides children by switching their actors only, so hidden frames
  keep their layout size hints (popups measured themselves as empty).
- Fix tooltips only appearing after a click: `HoverTextOverlay` showed and
  hid its text on mouse move but never requested a render, and hover moves
  do not render by themselves.
- `GridLayout`: an explicitly stretched column or row grows even when its
  items are fixed-size (they are aligned within it), as in Qt.
- `WidgetPanel` owns the on-screen state of its layout's widgets: one is
  drawn and interactive only while the panel is shown and expanded and the
  widget is not hidden, so `show()` on a widget in a hidden tab no longer
  draws it. `set_element_shown` works for layout-managed elements.
- `FormLayout` labels follow their field: hiding a field hides its label
  and frees the row.
- `ColorPaletteWidget` gains `GetBounds` and size hints;
  `ValueChangerWidget` minimum width is 80 px.
- `TextWidget`: non-draggable editable/clickable text claims presses
  anywhere in its cell (`claim_cell_clicks`, default on unless
  `grabbable`). With fixed-size fonts VTK's border box shrank to the text
  and its edge tolerance turned most clicks into a locked edge drag, so
  fields rarely entered editing. Clicking elsewhere commits editing.
  `ScrollablePanel` rows opt out (they can overlap the scrollbar).
- `WidgetPanel.widget(name)` also finds elements moved into the panel's
  layout with `removeWidget`. `ScrollablePanel` gains layout size hints.
- Fix buttons in hidden panels and inactive dock tabs being clickable.
  `VectorButtonWidget` used one `enabled` flag for both "shown" (set by
  containers) and "available" (set by hosts); a host marking a hidden
  button available made it interactive while invisible, and showing a panel
  re-enabled buttons the host had disabled. Shown state now lives in
  `GetEnabled`/`GetVisibility`/`isVisible`; `enabled`/`isEnabled`/
  `setEnabled` mean availability; clicks need both.
- Hidden `VectorPanelBackground`s hide their context actor, so VTK skips
  them instead of calling an empty `Paint` every frame (the host application:
  4.3 to 2.8 ms per frame), and ignore drag/resize input while hidden.
- Add `WidgetMixin.isHidden()` (explicitly hidden); layouts use it so
  widgets hidden along with their panel or tab keep their space.
- `WidgetPanel.setLayout`: a layout fills the area under the header and the
  panel grows to its hint; collapse, hide and docking include the layout's
  widgets. `Frame` and layout panels report `dockHeight()` to `DockPane`.
- `DockPane` `width`/`margin`/`spacing`/`setDockWidth` accept `px`/`frac`
  lengths (pixel widths survive window resizes; saved with `widthSpec`).
  Bare numbers and legacy panel stacking are unchanged.
- `Layout.activate` defers to a host's `layoutRequestEvent(layout)`; a host
  geometry change that leaves the content rectangle unchanged no longer
  relayouts.
- `WidgetMixin.setVisible` hides VTK widgets without `SetVisibility` (such
  as `SliderWidget`) by disabling them; it previously only set a flag.
- Add layouts (`VBoxLayout`, `HBoxLayout`, `GridLayout`, `FormLayout`),
  `SizePolicy`, size hints and min/max/fixed sizes on `WidgetMixin`, and a
  `Frame` host widget. Layouts accept `px`/`frac` lengths and relayout once
  per frame on hint, visibility, host-geometry or window-size changes.
- `TextWidget`, `ValueChangerWidget`, `SliderWidget` and `ButtonWidget`
  gain `GetBounds`/`SetBounds` (and size hints), so `setGeometry` works on
  them; `ButtonWidget.setGeometry` previously mixed fractions and pixels.
- `WidgetMixin.viewportSource()` resolves to `renderer.ui_overlay` when
  present, so fraction/pixel conversion and hit-testing match where the UI
  is drawn.
- `SliderWidget.update_size` sizes the native parts in VTK's actual units
  (fractions of the window extent); it previously drew very thick tracks.
- Remove the unused caret-blink code from `TextWidget` (`on_timer`,
  `cursor_visible`, `timer_id`); the caret is shown whenever a field edits.
- `FocusManager`: Enter/Space no longer activate a widget that was focused
  by a mouse click (keyboard and programmatic focus still activate), and
  Tab/Escape/Enter/Space are left alone while another text field is
  editing (including hosts that only set `interactor.text_edit_mode`).
  Previously Enter re-clicked the last clicked button and never reached
  the field being edited.
- `EventRouter` skips per-event hit-testing and hover tracking while no
  native widgets or filters exist, making it effectively free for hosts
  that only use legacy widgets.
- Fix click-to-edit on `TextWidget` when the UI is drawn on an overlay
  renderer (`renderer.ui_overlay`): the click pick ran against the scene
  renderer, so editing never started.
- Add `EventRouter` (opt-in via `EventRouter.install`) and Qt-style event
  handlers on `WidgetMixin`: z-ordered hit-testing, bubbling, implicit
  mouse grab, hover enter/leave, cursor shapes, double-click, context menu,
  event filters, and `isOverUi`/`widgetAt`/`isTextInputActive` queries.
  Legacy widgets keep their own observers; the router routes the wheel to
  their `handle_mouse_wheel` and consumes KeyPress/Char while any text
  field edits, so scene hotkeys no longer fire while typing.
- Move demo functions out of the library: chart demos (`test_plots`,
  `test_chart_actor`, …) to `examples/chart_demos.py`, the 3D panel demo to
  `examples/panel_3d_demo.py` and the specialists demo to
  `examples/specialists_demo.py`. They are no longer importable from
  `charts`, `panel_utils` or `specialists`.
- Move radiation and Compton-reconstruction helpers to
  `multipanel.radiation`; `specialists`, `widgets` and `vtk_utils` re-export
  them until 1.0. Reconstruction now uses a backend registered with
  `radiation.set_reconstruction_backend()` instead of an unimported
  `reconstruction_utils` name, which previously raised `NameError`.
- `ClickManager` no longer prints every click by default (`verbose=False`).
- Add `px()`/`frac()` lengths: `setGeometry`, `move` and `resize` accept
  pixel or viewport-fraction values, `geometry()` reports `frac`, `px` or
  `display` units, and `saveState` records units for explicit geometry.
- Add `Timer` (QTimer equivalent) and `VirtualClock`; `RenderScheduler`
  flushes through the virtual clock when one is installed.
- Add `multipanel.testing.UiHarness` for headless click/drag/wheel/key tests.
- Add a consistent Qt-style control, container, and specialist widget API.
- Add synchronous signals, signal blocking, focus traversal, exclusive text
  editing, pointer capture, and deterministic observer ownership.
- Add JSON-compatible widget state save/restore hooks and runtime theme refresh.
- Add slider orientation and tracking behavior, panel selection signals, dock
  state, and reconstruction lifecycle signals.
- Move widget implementations into stable `input`, `controls`, `containers`,
  and `specialists` modules while retaining identity-compatible exports from
  `multipanel.widgets`.
- Remove obsolete duplicate widget implementations and import-time path
  mutation left over from the original monolithic module.
- Add automated Linux/macOS tests and package build validation.
- Reduce the default runtime dependency set to NumPy and VTK; load scientific
  plotting/reconstruction and SVG/PNG conversion through documented extras.
- Move resource paths into an import-light module and add actionable errors
  for unavailable optional features.
