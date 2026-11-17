# Proposal: desktop-toolkit usability (Qt parity, phase 2)

Status: **accepted** (decisions recorded in §17) · Owner: MultiPanel maintainers · Supersedes nothing;
follows on from [the completed implementation plan](IMPLEMENTATION_PLAN.md).

## 1. Summary

The first phase gave every widget a Qt-shaped *object* API: names,
parent/child ownership, signals, focus, mouse grabs, render coalescing,
state persistence and theme refresh. What it did not add are the
*toolkit services* that make Qt productive to build with:

1. a single event router that owns hit-testing and propagation,
2. a layout system driven by size hints,
3. a popup/overlay layer,
4. actions and keyboard shortcuts,
5. the standard widget catalogue (check box, combo box, menu, …),
6. native-feeling text editing,
7. state-based styling with visible focus,
8. timers and animation,
9. a shared item model,
10. test and debugging tooling.

This document proposes each of these as an independent workstream. It gives
the current state (with code references), the target API, the migration
path, the acceptance tests and a task checklist. The workstreams are ordered
so that each one only depends on earlier ones.

### Guiding rules (unchanged from phase 1)

- **Additive.** Existing VTK methods, constructor signatures and
  `multipanel.widgets` imports keep working. New behaviour is opt-in until a
  host has migrated, then becomes the default in a minor release.
- **No Qt import.** Qt names are borrowed; Qt is never required. Optional Qt
  integration (clipboard, cursor shapes) is loaded lazily, like the
  `scientific` extra.
- **Host-agnostic.** Anything the host application currently does on the library's
  behalf (see §3.1) should move into the library so other hosts get it.
- **Every behaviour lands with a headless test** using the event simulation
  helpers from §4.

## 2. Dependency graph

```text
W0 Foundations (testing helpers, Timer, units, hygiene)
 ├── W1 Event router ───────────┬── W3 Overlay layer ──┬── W5 Widget catalogue
 │                              │                      │      (needs W2, W3, W4)
 │                              ├── W4 Actions/shortcuts
 │                              ├── W6 Text editing
 │                              └── W7 State styling + focus ring
 └── W2 Layout system ──────────────────────────────────┘
W8 Animation (needs W0 Timer)     W9 Item model (needs W5 for views)
W10 Inspector + docs (any time after W1/W2)
```

W1 and W2 can run in parallel. Everything that users would *see* as
"Qt-like" (W5) waits for both.

## 3. Current state: what the work starts from

### 3.1 Event routing is split between the library and the host

- [`input.ClickManager`](../src/multipanel/input.py) sends each click to the
  first panel whose bounds contain it, has no z-order and hard-codes
  `verbose = True`. The host application does not use it: `GUI/UI.py` has it commented
  out.
- The host application's `HybridInteractorStyle` (`LIBS/interactor_utils.py`) does the
  real routing. It calls `pointer_is_over_ui_panel(...)` so clicks on UI are
  not treated as empty-scene clicks, offers wheel events to
  `renderer.UI_panels` in a hand-sorted order, and skips scene hotkeys while
  `interactor.text_edit_mode` is set.
- Containers forward wheel events to children themselves
  (`handle_mouse_wheel` in `ScrollablePanel`, `WidgetPanel` and `DockPane`),
  each with its own "deepest child first" loop.
- Leaf widgets add their own observers to the interactor (for example
  `DockPane` resize handles, `TextWidget` key presses), so the order they
  run in depends on observer priority and registration order.
- `TextWidget.on_key_press` keeps a `blocked_keys` list (a–z, 0–9) and
  clears the key code so `vtkInteractorStyle.OnChar` hotkeys (`e`/`q` exit,
  `w` wireframe, `3` stereo, …) do not fire while typing. This is a
  workaround for the missing "consume the event" rule.
- `FocusManager` already handles Tab, Shift-Tab, Escape, Enter and Space at
  priority 200 and sets the abort flag when it handles one of them. W1
  extends this approach to every event.

### 3.2 Layout is done by hand per container

- `WidgetPanel.update_layout` ([containers.py](../src/multipanel/containers.py),
  around line 2705) checks each child's VTK class (`vtkButtonWidget`,
  `vtkSliderWidget`, `vtkTextWidget`, `ValueChangerWidget`, …) and rescales
  its stored position by the panel's change in size. Unrecognised types raise
  `NotImplementedError`.
- `DockPane.layout` stacks panels vertically using `_effective_height`, with
  `margin` and `spacing` in normalized viewport units (`.008`).
- Measurements mix normalized viewport coordinates with pixel conversions
  (`/ window_height`, `_available_width_px`, `ui_scale()`), so resizing the
  window stretches some controls and not others.
- `WidgetMixin.geometry()` returns whatever the widget's `GetBounds()`
  reports, so its units differ between widget types.

### 3.3 The widget catalogue

Present: `SliderWidget`, `ButtonWidget`/`VectorButtonWidget` (checkable),
`TextWidget`, `ValueChangerWidget` (spin box), `ColorPaletteWidget`,
`ScrollablePanel`/`ScrollableTextPanel` (list), `WidgetPanel` (group box),
`DockPane` (tabbed dock), `HoverTextOverlay` (tooltip), plus scene
specialists.

Missing: label, check box, radio button and button group, combo box, menu
and context menu, progress bar, message box/modal dialog, tree and table
views, splitter, status bar.

### 3.4 Text editing

`TextWidget` supports a caret, Backspace, Delete, Left/Right, Home/End and
printable characters taken from `GetKeyCode()`. It has no selection,
clipboard, click-to-place caret, word movement, undo/redo or horizontal
scrolling, and keyboard modifiers are ignored.

### 3.5 Tests

There are 31 tests in `tests/`. They use an off-screen `vtkRenderWindow`
fixture and call widget methods directly. Nothing simulates interactor
events, so input behaviour is barely covered.

## 4. W0 — Foundations

**Goal:** the shared pieces that every other workstream needs. Size: **S–M**.

### 4.1 `multipanel.testing` (QTest equivalent)

```python
from multipanel.testing import UiHarness

ui = UiHarness(size=(800, 600))          # off-screen renderer/window/interactor
button = VectorButtonWidget(ui.renderer, ui.interactor, ...)
ui.click(button)                          # press+release at widget centre
ui.click_at(120, 40, button="right")      # display pixels
ui.drag(slider.handle_pos(), (300, 40))
ui.wheel(panel, steps=-3)
ui.key_clicks("hello")                    # KeyPress + Char + KeyRelease per char
ui.key("a", ctrl=True)
ui.process_events()                       # flush RenderScheduler + timers
```

- It drives events with `SetEventInformation` and `InvokeEvent`, so
  observers and abort flags behave as they do in a real application.
- `ui.process_events()` fires pending `Timer`s deterministically, using a
  virtual clock, without starting the real VTK event loop.

### 4.2 `Timer`

```python
t = Timer(interactor, interval_ms=500, single_shot=False)
t.timeout.connect(blink)
t.start(); t.stop(); t.isActive()
Timer.singleShot(interactor, 250, callback)
```

Built on `CreateRepeatingTimer`/`CreateOneShotTimer` and the existing
`TimerEvent` observer in `RenderScheduler`. The test harness swaps in a
virtual clock. W3 (tooltip delay), W6 (caret blink, double-click timing) and
W8 (animation) all use it.

### 4.3 Units: pixels and screen fractions

**Decision:** the API accepts both pixel values and fractions of the screen
(the viewport). Neither replaces the other. Fractions are the right choice
for things that should scale with the window, such as a dock that is 25%
wide. Pixels are the right choice for things that should not, such as
padding, icon size and row height.

New module `multipanel.units`:

```python
from multipanel.units import px, frac

px(8)          # 8 logical pixels (display px / ui_scale())
frac(0.25)     # 25% of the viewport along the axis it is used on
"8px", "25%"   # string forms, parsed with units.parse_length()
```

- **`Length` values.** `px(...)` and `frac(...)` create `Length` values.
  These are resolved against the current viewport and `ui_scale()` **at
  layout time**, not when they are created. A `frac` therefore keeps tracking
  window resizes and a `px` stays fixed.
- **Axis.** A `frac` resolves against the viewport width for x, width and
  horizontal margins, and against the viewport height for y, height and
  vertical margins. Layout spacing resolves along the layout's direction.
- **Bare numbers.** Each API has a documented default unit, used when a
  plain number is passed:
  - Existing constructor parameters keep their current meaning. For
    example, `DockPane(margin=.008)` still means a fraction, so no current
    call changes behaviour.
  - New size-related APIs (`setMinimumSize`, `sizeHint`, layout `spacing`
    and `margins`) default to pixels.
  - `units="px" | "frac"` can be passed to override the default for a
    single call.
- **Mixing.** Units can be mixed in one call, for example
  `setMinimumSize(px(160), frac(0.3))` or
  `DockPane(width=frac(0.22), min_width=px(220))`.
- **Conversion helpers.** `to_display(length, axis)`,
  `to_frac(length, axis)` and `to_px(length, axis)` replace the scattered
  `/ window_height` and `_available_width_px` conversions.
- **Geometry.** `WidgetMixin.geometry(units="frac")` is the default and
  matches the normalized bounds most widgets report today.
  `geometry(units="px")` returns logical pixels. `setGeometry` and
  `move`/`resize` accept `Length` values or a `units=` keyword.
- **State.** `saveState` stores geometry with its unit
  (`{"x": [0.1, "frac"], ...}`), so a restored layout keeps whether it
  scales with the window. State saved before this change, without units, is
  read as fractions.

### 4.4 Hygiene

- [ ] Set `ClickManager.verbose` to `False` by default, and deprecate the
      class once W1 lands.
- [ ] Move `test_*()`, `main()` and `generate_test_data()` out of
      `charts.py`, `specialists.py` and `panel_utils.py` into `examples/`.
- [ ] Move the radiation and reconstruction helpers out of `specialists.py`
      into their own module, `multipanel/radiation.py`. That covers
      `calculate_compton_angle`, `create_radiation_marker`,
      `add_GEANT4_tracks` (from `vtk_utils.py`), `spectrum_button_callback`,
      `refresh_compton_widgets`, `refresh_reconstruction_callback`,
      `set_auto_reconstruction_callback` and
      `set_reconstruction_selection_callback`, plus whatever they need
      privately.
      - `specialists` and `widgets` keep re-exporting them, which preserves
        identity, until 1.0.
      - The new module imports its scientific dependencies lazily, through
        the existing `scientific` extra.
      - `LassoWidget`, `BoxWidget` and `SphereProbeWidget` stay in
        `specialists`. They are general scene tools, and their
        reconstruction behaviour calls into `radiation` through a hook.
- [x] Replace the commented-out `print` debugging in `controls.py` and
      `containers.py` with the structured logger from phase 1.

**Acceptance:** `UiHarness` exists. A test clicks a `VectorButtonWidget` and
sees `clicked` emitted. `Timer` has single-shot and repeating tests on the
virtual clock.

## 5. W1 — Event router

**Goal:** one object per interactor decides which widget receives every
pointer, wheel and key event, and stops the 3D interactor style from seeing
events the UI handled. Size: **L**. This is the workstream with the highest
risk and the biggest payoff.

**Decision:** all UI routing moves into this library. Afterwards, a host's
interactor style only deals with scene interaction (picking, camera, gizmos,
charts). It asks the router whether an event belongs to the UI and never
looks at UI panels itself.

### 5.1 Design

```python
router = EventRouter.for_interactor(interactor)   # created lazily, like FocusManager
```

- **Observers.** At priority 300 (above `FocusManager`'s 200 and the
  interactor style), the router observes `MouseMove`,
  `{Left,Middle,Right}Button{Press,Release}`, `MouseWheel{Forward,Backward}`,
  `KeyPress`, `KeyRelease`, `Char`, `Enter`, `Leave`, `Configure`.
- **Hit-testing.** Top-level widgets register with the router (the
  constructor does this automatically once `registerFocus` is called).
  Hit-testing walks the widget tree **topmost first**, using the
  `ui_z_order` band, then reverse child order. It calls a new
  `WidgetMixin.hitTest(x_px, y_px) -> bool`, whose default checks
  `geometry(units="px")`.
- **Event objects:**

  ```python
  class MouseEvent:   pos, global_pos, button, buttons, modifiers, accepted
  class WheelEvent:   pos, delta (steps), modifiers, accepted
  class KeyEvent:     key, text, modifiers, is_auto_repeat, accepted
  class HoverEvent:   pos, old_pos
  # accept() / ignore()
  ```

- **Virtual handlers** on `WidgetMixin`, named as in Qt:
  `mousePressEvent`, `mouseReleaseEvent`, `mouseMoveEvent`,
  `mouseDoubleClickEvent`, `wheelEvent`, `keyPressEvent`,
  `keyReleaseEvent`, `enterEvent`, `leaveEvent`, `contextMenuEvent`. Each
  default calls `event.ignore()`.
- **Propagation.** The event goes to the deepest widget hit. If it is
  ignored, it bubbles up to the parent, then the parent's parent, and so on.
  If a widget accepts it, the router sets the VTK command's abort flag and
  the interactor style never sees it.
- **Mouse grab.** After an accepted press, all move and release events go to
  that widget until release (implicit grab). The existing
  `FocusManager.grabMouse` becomes an explicit grab on top of this.
- **Keys** go to the focused widget, then bubble to its parents, then to
  shortcuts (W4). While a text widget is editing, `Char` events are always
  consumed, which makes `blocked_keys` unnecessary.
- **Hover.** The router keeps track of the widget under the pointer, sends
  enter and leave events, and sets `underMouse()`. W7 styling uses this.
- **Double-click** is detected in the router: a press within the platform
  interval (default 400 ms, configurable) and within 4 logical pixels of the
  previous one.
- **Cursor shape.** `WidgetMixin.setCursor(shape)` is applied on hover. This
  replaces the per-widget `_set_cursor` code.
- **Event filters.** `widget.installEventFilter(obj)` and
  `router.installEventFilter(obj)`, where `obj.eventFilter(target, event)`
  returns `True` to consume. Hosts use this to keep special cases such as
  chart-versus-camera mode.
- **Host queries** that replace the host application's helpers:
  `router.widgetAt(x, y)`, `router.isOverUi(x, y)`,
  `router.isTextInputActive()`.

### 5.2 Legacy widgets (as implemented)

Existing widgets receive input through their own interactor observers
(`VectorButtonWidget`, the native `vtk*Widget` subclasses, `TextWidget`,
dock resize handles). Delivering pointer events to them as well would
double-handle input, and aborting presses would starve those observers. The
router therefore treats any widget that overrides none of the `WidgetMixin`
event handlers as **legacy**:

- Press, move and release are never delivered to legacy widgets or consumed
  on their behalf. The scene still sees them, and the host asks
  `router.isOverUi()` before treating a press as a scene click.
- Legacy widgets count for `isOverUi`/`widgetAt`/`hitChain`. Top-level
  legacy containers are discovered from `renderer.UI_panels` and hit-tested
  with their `is_within_bounds` (window-normalized), exactly as the host did.
- The wheel goes to legacy containers' `handle_mouse_wheel` in the host's
  former order (later-registered first, containers with nested panels
  before plain panels), and is consumed when one scrolls.
- While any text field is editing (library `TextWidget`, or a host widget
  that sets `interactor.text_edit_mode`), KeyPress and Char are consumed at
  priority 50, after text widgets (100) and before the style (0).

A widget becomes native, with exclusive delivery, as soon as it overrides a
handler, so widgets can be ported one at a time with no adapter class.

### 5.3 Migration in the host application

1. Install the router and keep `HybridInteractorStyle` as it is. Replace
   `pointer_is_over_ui_panel` with `router.isOverUi` and `text_edit_mode`
   with `router.isTextInputActive()`.
2. Remove the host application's wheel dispatch and the hand-sorted `renderer.UI_panels`
   ordering. The router's registry replaces `UI_panels` for routing.
   `UI_panels` can remain as the host application's own lookup table by name.
3. Express chart-versus-camera switching as an event filter.
4. Remove the `dispatch_*` UI branches from `HybridInteractorStyle`. Once
   this is done, the style's mouse handlers only run for events the router
   did not consume.
5. Delete the host-side helpers that the router replaced
   (`pointer_is_over_ui_panel`, the wheel dispatch function and the
   `text_edit_mode` flag). The removal is tracked in the host application's PR for the
   matching submodule bump.

### 5.4 Acceptance tests

- [ ] Two overlapping panels: the click goes to the higher `ui_z_order`.
- [ ] A click on a non-interactive label inside a panel bubbles to the
      panel. A click on empty scene reaches the interactor style.
- [ ] Wheel over a nested scrollable list inside a scrollable dock scrolls
      the list until it reaches its limit. Pass-through is configurable.
- [ ] Typing `e`, `w` or `q` into a focused `TextWidget` inserts the
      characters and does not trigger the interactor style's hotkeys.
- [ ] Dragging a slider outside its bounds keeps delivering moves to it.
- [ ] Enter and leave events are delivered once each when crossing a
      widget edge.

## 6. W2 — Layout system

**Goal:** containers lay out children from size hints instead of
special-casing VTK classes. Sizes can be given in pixels or as screen
fractions (§4.3), and the result stays predictable when the window is
resized. Size: **L**.

### 6.1 Size negotiation on `WidgetMixin`

Internally, the layout engine works in logical pixels. Every `Length` is
resolved to pixels at the start of a layout pass, so pixel and fraction
constraints can be combined. For example, a panel can take
`frac(0.3)` of the height but never less than `px(160)`.

```python
widget.sizeHint() -> (w, h)              # logical px, computed from content
widget.minimumSizeHint() -> (w, h)
widget.setMinimumSize(w, h); setMaximumSize(w, h); setFixedSize(w, h)
#   each argument is a Length or a bare number (px by default):
#   setMinimumSize(px(160), frac(0.3)); setFixedSize("48px", "48px")
widget.sizePolicy() -> SizePolicy(horizontal, vertical)
#   Fixed | Minimum | Maximum | Preferred | Expanding | Ignored
widget.updateGeometry()                  # marks the parent layout dirty
```

Each existing control gets a real `sizeHint`:

| Widget | Width | Height |
| --- | --- | --- |
| `VectorButtonWidget` | icon + padding (+ text width) | icon + padding |
| `TextWidget` | measured text or `minimumCharacters` | `text_line_height` + padding |
| `SliderWidget` | 120 px preferred, Expanding | track + handle |
| `ValueChangerWidget` | field + two steppers | line height |
| `ScrollablePanel` | Expanding | `visibleRows × element_height` |
| `WidgetPanel` | layout hint + margins | header + layout hint |

### 6.2 Layout classes

```python
from multipanel.layouts import VBoxLayout, HBoxLayout, GridLayout, FormLayout

form = FormLayout()
form.addRow("Density", density_spin)
form.addRow("Material", material_combo)

row = HBoxLayout(spacing=6)                  # bare number = px
row.addWidget(apply_btn); row.addStretch(1); row.addWidget(close_btn)

v = VBoxLayout(margins=(8, 8, 8, 8))
v.addLayout(form); v.addWidget(slider, stretch=1); v.addLayout(row)
v.addSpacing(frac(0.02))                     # gap that scales with the window
panel.setLayout(v)
```

- The algorithm follows Qt's box layout: sum the minimum sizes, share the
  spare space by stretch factor, then by policy (Expanding before
  Preferred), and clamp to maximum sizes. Grid layouts do this per row and
  column. Form layouts are a two-column grid with label alignment.
- **Invalidation.** `updateGeometry()` marks the layout dirty. Layouts run
  once per frame, from a `RenderScheduler` pre-render hook, so a series of
  changes produces one layout pass.
- **Top-level placement.** Top-level panels and docks use the window as
  their parent area and position themselves with `Length`s:
  `panel.setGeometry(frac(0.02), frac(0.6), px(260), frac(0.35))`.
  Anchors (`setAnchor("top-right", offset=(px(12), px(12)))`) cover the
  common cases without arithmetic.
- **Getter name.** Implemented as `contentLayout()`: `DockPane` and
  `ViewportDisplayPanel` already define `layout()` to run their own relayout.
- **Setting geometry.** A layout calls `child.setGeometry(..., units="px")`.
  Each widget converts that to its native representation (VTK bounds,
  `SetPosition`/`SetSize`, slider endpoints). All per-type special cases
  live in that widget's `setGeometry` override, not in the container.
- **Hidden widgets** take no space by default
  (`setRetainSizeWhenHidden(True)` to opt out).
- **Containers.** `WidgetPanel.setLayout` replaces the name-keyed
  `addWidget(name, widget)` positioning; the old path stays for panels with
  no layout set. `DockPane` keeps its vertical stack but measures panels via
  `sizeHint`. Its `margin`, `spacing`, `width`, `min_width` and `max_width`
  accept `Length`s, and bare numbers keep their current meaning as
  fractions.
- **Scroll areas.** A `ScrollArea(widget)` uses the existing `ScrollBox` to
  scroll content taller than its viewport. `DockPane`'s own scrolling
  becomes an instance of it.
- **Splitter.** `Splitter(orientation)` with draggable handles, generalised
  from the `DockPane` width handle.

### 6.3 Migration

1. Add the API, plus `sizeHint` for leaf controls. No behaviour changes.
2. Port `DockPane` first, since it is the simplest stack, then
   `ViewportDisplayPanel`.
3. Port the host application's `WidgetPanel`s one at a time to `setLayout`. The legacy
   `update_layout` code stays until no host uses it, then it is deprecated.

### 6.4 Acceptance tests

- [ ] An `HBoxLayout` with a fixed button, a stretch and a fixed button keeps
      both buttons at their hint widths at 640 and 1920 px wide.
- [ ] A `FormLayout` lines up the field column across rows with labels of
      different lengths.
- [ ] Changing a child's text and then calling `updateGeometry` relayouts on
      the next render, and repeated changes cause only one layout pass.
- [ ] Hiding a row in a `VBoxLayout` closes the gap.
- [ ] Doubling `ui_scale()` doubles display sizes and leaves logical sizes
      unchanged.
- [ ] A child with `setMinimumSize(px(160), frac(0.3))` is 30% of the height
      in a tall window and 160 px in a short one.
- [ ] A dock created with the legacy `margin=.008` lays out identically
      before and after the port.

## 7. W3 — Overlay and popup layer

**Goal:** a place to draw transient UI above everything else, which every
menu, dropdown, tooltip and dialog needs. Size: **M**.

- `OverlayLayer.for_renderer(renderer)` reserves the top `ui_z_order` band
  and owns a stack of popups.
- A `Popup(WidgetMixin)` base provides:
  - `popup(anchor_widget, placement="below")` or `popup(pos_px)`, with
    automatic flipping and clamping to the viewport;
  - closing on an outside click (consumed by default, as in Qt), on Escape,
    and when its anchor is hidden;
  - a `aboutToShow` / `aboutToHide` / `closed` signal set;
  - submenus as child popups, where closing a parent closes its children.
- **Modal mode.** While a modal popup is open, the router (W1) sends all
  input to it and its children, and a dimmed scrim may be drawn over the
  rest of the UI. `exec()` cannot block a VTK event loop, so it returns
  immediately and the `finished(result)` signal reports the result.
- **Tooltips.** `HoverTextOverlay` is rebuilt as a `Popup`. It shows after a
  hover delay (W0 `Timer`, 700 ms by default) and reads
  `WidgetMixin.toolTip()`. This makes the existing `setToolTip` work on
  every widget.

**Acceptance:** a popup near the right edge flips to stay on screen. An
outside click closes it without clicking through. A tooltip appears after
the delay and hides on leave. A modal popup blocks clicks to a button
underneath.

## 8. W4 — Actions and shortcuts

**Goal:** a command is defined once and every button, menu item and
shortcut that triggers it stays in sync. Size: **M**.

```python
save = Action("Save scene", icon="save", shortcut="Ctrl+S",
              checkable=False, status_tip="Save the current scene")
save.triggered.connect(save_scene)
save.setEnabled(False)            # every bound control greys out

ToolButton(action=save)           # W5
menu.addAction(save)              # W5
```

- `Action` has `text`, `icon`, `toolTip`, `statusTip`, `isEnabled`,
  `isVisible`, `isCheckable`, `isChecked`, `shortcut` and `data`, with the
  signals `triggered(checked)`, `toggled(checked)` and `changed`.
- `ActionGroup` makes checkable actions exclusive.
- `VectorButtonWidget.setAction(action)` binds an existing button to an
  action.
- `KeySequence.parse("Ctrl+Shift+S")` normalises modifier names. `Ctrl`
  means Cmd on macOS unless `"Meta+"` is written explicitly, as in Qt.
- `Shortcut(sequence, context=...)` where the context is
  `"application"`, `"window"`, `"widget"` or `"widgetWithChildren"`.
  The router (W1) checks shortcuts after the focused widget has ignored the
  key, so Ctrl+C in a text field copies the text and Ctrl+C elsewhere
  reaches the host application's "copy actors" shortcut.
- Ambiguous shortcuts emit `activatedAmbiguously` instead of running both.

**Host application migration:** the `if ctrl and key == ...` chain in
`HybridInteractorStyle.on_key_press` becomes a set of `Action`s. They can
then also appear in a context menu.

**Acceptance:** an enabled-state change shows up on a bound button. A
focused text field takes precedence over a window-level Ctrl+C. Two
checkable actions in a group are mutually exclusive.

## 9. W5 — Widget catalogue

**Goal:** the standard controls people expect, all built on W1–W4 and all
following the phase-1 contract (signals, `saveState`, `refreshTheme`,
focus). Size: **L** overall; each widget is **S–M**.

| Widget | Key API | Signals | Depends on |
| --- | --- | --- | --- |
| `Label` | `text`, `setText`, `setAlignment`, `setWordWrap`, `setBuddy` | `linkActivated` | W2 |
| `CheckBox` | `isChecked`, `setChecked`, `checkState`, `setTristate` | `toggled`, `stateChanged` | W1, W2 |
| `RadioButton` + `ButtonGroup` | `addButton(btn, id)`, `checkedId`, `setExclusive` | `idToggled`, `buttonClicked` | W1 |
| `ToolButton` | `setAction`, `setPopupMenu`, icon-only/with-text modes | `clicked`, `triggered` | W4 |
| `ComboBox` | `addItem(text, data)`, `currentIndex`, `currentText`, `currentData`, `setEditable`, `findText`, `setModel` | `currentIndexChanged`, `activated`, `textActivated` | W3, W9 (optional) |
| `Menu` / context menu | `addAction`, `addMenu`, `addSeparator`, `popup(pos)`, keyboard navigation, mnemonics | `triggered(action)`, `aboutToShow` | W3, W4 |
| `MenuBar` | top strip of `Menu`s, hover-to-switch once open | — | `Menu` |
| `ProgressBar` | `setRange`, `setValue`, `setFormat("%p%")`, busy mode when `max == 0` | `valueChanged` | W2, W8 for busy mode |
| `MessageBox` | `information/warning/question(parent, title, text, buttons)`, returning a pending result | `finished(button)` | W3 modal |
| `StatusBar` | `showMessage(text, timeout_ms)`; shows the `statusTip` of hovered widgets | `messageChanged` | W1 hover, W0 Timer |
| `Splitter` | see W2 | `splitterMoved` | W2 |

Rules for every new widget:

- It is a composite `WidgetMixin`: a vector background plus
  `vtkTextActor`/`vtkActor2D` children, drawn through
  `register_ui_drawable`. It does not subclass a `vtk*Widget`, which avoids
  the bounds inconsistencies listed in §3.2.
- It has `sizeHint`, `hitTest` and native event handlers from day one, and
  no legacy adapter.
- It is added to `docs/API.md`, has a contract test file and appears in
  `examples/gallery.py`.

### 9.1 Composite replacements for the native-VTK controls

**Decision:** provide versions of the existing controls that do not subclass
VTK widgets, and keep the native-subclass versions permanently for
compatibility.

`ButtonWidget` (`vtkButtonWidget`), `TextWidget` (`vtkTextWidget`),
`SliderWidget` (`vtkSliderWidget`) and `PanelBackgroundWidget`
(`vtkBorderWidget`) get composite implementations. These follow the same
rules as the new widgets above.

| Phase | `multipanel.controls` / `containers` export | `multipanel.legacy` | `multipanel.widgets` (compat namespace) |
| --- | --- | --- | --- |
| 0.x | native classes, unchanged | the same native class objects | native classes |
| 0.x opt-in | composites from `multipanel.composite` | — | — |
| 1.0 onward | **composite** classes | native classes, maintained | native classes, so old imports behave identically |

- **Same public API.** A composite and its legacy class share the same
  constructor and phase-1 API (`setValue`, `valueChanged`, `saveState`, …).
  A shared contract test suite is run against both, so moving a host over
  is mostly a change of import.
- **VTK methods.** Composites provide the VTK-style methods hosts call today
  (`SetEnabled`, `GetRepresentation().GetState()`, `AddObserver` for
  `StateChangedEvent`/`InteractionEvent`). They are thin shims over the new
  API that also emit the VTK event. Calls that can't be supported raise
  `NotImplementedError` with a pointer to the replacement API.
- **The `.native` attribute.** It always returns `None` on composites and
  `self` on legacy classes, so a host can branch on it if it needs to.
- **Legacy classes still improve.** They receive W1 routing (as
  pass-through targets), W2 `sizeHint`s and W7 state colours where their VTK
  representation allows it. They are not frozen; they are just not where new
  features are developed first.
- **Choosing per renderer.** `multipanel.set_widget_backend("composite" |
  "legacy")` changes what the `controls` and `containers` names resolve to
  for code that imports them after the call. The host application can then switch in one
  place and fall back if something regresses.

**Context menus:** the router sends a `contextMenuEvent` on right-button
release when the pointer has moved less than the drag threshold. Widgets
opt in with `setContextMenuPolicy("custom")` and the
`customContextMenuRequested(pos)` signal.

## 10. W6 — Text editing

**Goal:** `TextWidget` behaves like a `QLineEdit`, and a new `TextEdit`
handles multi-line text. Size: **M** for the line edit, **L** for
multi-line.

### 10.1 Model

Pull the editing logic out of `TextWidget` into a pure-Python
`TextBuffer`: text, caret, anchor (selection = caret…anchor), an undo stack
that coalesces consecutive typing, and word boundaries. It has no VTK
dependency, so it can have thorough unit tests.

### 10.2 Behaviour

- [ ] Selection: Shift+arrows/Home/End, mouse drag, double-click selects a
      word, triple-click selects all, Ctrl/Cmd+A.
- [ ] Word movement: Ctrl+arrow (Alt+arrow on macOS); Ctrl+Backspace and
      Ctrl+Delete delete a word.
- [ ] Clipboard: Ctrl/Cmd+C, X and V, through `multipanel.clipboard`. The
      backend is chosen once, on first use:
      1. a host-supplied `set_clipboard_backend(get_text, set_text)`;
      2. `QGuiApplication.clipboard()` if a `QApplication` instance exists
         (imported lazily);
      3. the platform's command-line tool: `pbcopy`/`pbpaste` on macOS,
         `wl-copy`/`wl-paste` on Wayland, `xclip` or `xsel` on X11, and
         `clip.exe` with PowerShell `Get-Clipboard` on Windows. These run
         with a 1 s timeout and no shell, passing text over stdin/stdout;
      4. an in-process buffer, which still allows copy and paste within the
         application.

      The choice is logged once at debug level. The command-line fallback
      can be turned off with `set_clipboard_backend("internal")` or the
      `MULTIPANEL_CLIPBOARD=internal` environment variable.
- [x] Undo/redo with Ctrl/Cmd+Z and Ctrl+Shift+Z/Ctrl+Y.
- [ ] Clicking places the caret at the nearest character boundary, measured
      with `vtkTextRenderer` bounding boxes of prefixes (cached per string).
- [ ] Horizontal scrolling keeps the caret visible when the text is wider
      than the field. `_elided` remains the display used when not editing.
- [ ] A selection highlight drawn as a rectangle behind the text, using the
      theme's highlight colour.
- [ ] `setMaxLength`, `setEchoMode("password")`, `setInputMask`, and a
      `setCompleter(list)` hook that uses a W3 popup.
- [ ] Text arrives from the `Char` event rather than `GetKeyCode()` on
      `KeyPress`, and `TextWidget` is the only consumer of `Char` while it
      is editing (W1). A host hook can inject composed or non-Latin text
      (for example from a Qt `QVTKRenderWindowInteractor` input-method
      event).
- [ ] Remove `blocked_keys`.

### 10.3 Multi-line `TextEdit`

Builds on `TextBuffer` with line wrapping and vertical scrolling through
`ScrollArea`. Up/Down move by line and PageUp/PageDown by page. Read-only
mode replaces `ScrollableTextPanel` for log output.

**Acceptance:** a `TextBuffer` property test (random edit sequences, then
undo all, gives back the original text). Harness tests cover selecting with
the mouse and copying, pasting over a selection, and typing past the field
width.

## 11. W7 — State-based styling and focus visibility

**Goal:** every widget gets hover, pressed, focus, disabled and checked
appearances from the theme, instead of computing its own colours.
Size: **M**.

- `WidgetMixin.styleState()` returns a set of
  `{"hover", "pressed", "focus", "disabled", "checked", "selected"}`, kept
  up to date by the router and the widget's own state changes. A
  `styleStateChanged` signal is emitted when it changes.
- A `Style` object maps `(role, state) → tokens` (background, border, text,
  icon tint, radius), built from the existing `ui_theme.vtk_tokens`. Widgets
  ask for tokens by role (`"button"`, `"field"`, `"menu-item"`, …) and are
  never given raw colours.
- **Focus ring.** The focused widget gets a 2 px accent outline that
  follows its rounded-rectangle shape. It is shown only after keyboard
  navigation (`focus-visible` semantics), so mouse users don't see rings.
- **Disabled** means reduced opacity plus no hover response, applied the
  same way everywhere.
- Hosts can override styles per object name, for example
  `style.override("#run_button", "button", accent="danger")`. This is
  deliberately not a full stylesheet parser.

**Acceptance:** with the harness, hovering a button changes its background
token, and pressing Tab after a mouse click shows the focus ring on the
next focusable widget. A theme change updates every state.

## 12. W8 — Animation

**Goal:** transitions that look smooth without adding timer code to each
widget. Size: **S**.

```python
anim = PropertyAnimation(panel, "contentHeight", duration_ms=150,
                         easing="outCubic")
anim.setEndValue(target); anim.start()
anim.finished.connect(...)
```

- Built on the W0 `Timer`. Each tick calls a setter and `requestRender()`.
- Uses: panel collapse/expand, `ScrollArea` smooth wheel scrolling, popup
  fade-in, the `ProgressBar` busy mode, and the caret blink, which currently
  uses its own `flashing_caret` path.
- A global `set_animations_enabled(False)` for remote sessions and tests.

## 13. W9 — Item model and views

**Goal:** one data model shared by list, combo box, tree and table views.
Size: **L**.

- `ItemModel`: `rowCount(parent)`, `columnCount(parent)`,
  `data(index, role)`, `setData`, `flags`, `index`, `parent`; signals
  `dataChanged`, `rowsInserted`, `rowsRemoved`, `modelReset`. Roles are
  `display`, `decoration` (icon name), `toolTip`, `checkState`, `user`.
- `ListModel(items)` and `TreeModel.from_hierarchy(HierarchyNode)`, using
  the existing `hierarchy.py`.
- `ScrollablePanel.setModel(list)` keeps its current behaviour; passing an
  `ItemModel` subscribes to fine-grained updates instead of rebuilding
  every row.
- `ListView`, `TreeView` (expand/collapse, built from the current
  `_toggle_tree_node` logic) and `TableView` (header and column resize,
  using W2's splitter). Each has a `SelectionModel` (single, multi,
  extended) supporting Shift- and Ctrl-click.
- Views draw only the visible rows, as `ScrollablePanel._sync_shown_rows`
  already does.

**Acceptance:** inserting one row into a 10k-row model updates one row's
actors. Tree expand and collapse keep the selection. Shift-click selects
a contiguous range.

## 14. W10 — Inspector and documentation

Size: **S**; can be done at any point after W1/W2.

- `multipanel.debug.Inspector(interactor)` is toggled with Ctrl+Alt+I. It
  outlines widget geometry, shows `objectName`, size hint and style state
  under the pointer, and `dump_tree()` prints the widget hierarchy.
- `examples/gallery.py` shows every widget in light and dark themes and is
  also used for screenshot tests.
- `docs/API.md` gets a section for each new module, and `docs/LAYOUTS.md`
  covers the layout model with diagrams.

## 15. Release plan

| Release | Contents | Breaking? |
| --- | --- | --- |
| 0.2 | W0 (incl. `units`, `radiation.py` split), W1 (router opt-in via `EventRouter.install(interactor)`); the host application's routing moved into the library | No |
| 0.3 | W2 layouts, `DockPane` ported; W7 styling; `multipanel.legacy` namespace created | No |
| 0.4 | W3 overlay, W4 actions, W5 first batch (Label, CheckBox, Radio, ComboBox, Menu, ProgressBar); composite `ButtonWidget` opt-in | No |
| 0.5 | W6 text editing + clipboard, W8 animation, W5 second batch (MessageBox, StatusBar, MenuBar); composite `TextWidget`, `SliderWidget` opt-in | No |
| 0.6 | W9 model/views, W10; the host application runs on the composite backend | No |
| 1.0 | Router and layouts on by default; focused modules export composites (legacy classes stay in `multipanel.legacy` and `multipanel.widgets`); `ClickManager`, `WidgetPanel.update_layout` type dispatch and `blocked_keys` removed; `specialists` stops re-exporting radiation helpers | **Yes** (announced in the 0.x changelogs) |

At each release, the host application's submodule pointer is bumped, and the host application
migrates the corresponding call sites in the same PR.

## 16. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| The router's abort flag stops events reaching native `vtk*Widget`s (sliders, the camera orientation widget, box widgets) that rely on their own observers. | Native widgets register as *pass-through* targets. The router identifies the target but does not abort, and the native widget's observer stays responsible for it. These widgets are covered in the W1 tests. |
| The host application's `HybridInteractorStyle` chart/camera switching conflicts with the router. | It is expressed as an event filter (§5.3). The router stays opt-in until the host application's tests pass with it enabled. |
| Layout passes add per-frame cost. | Layouts run only when dirty and once per frame. The `render_profiler` timings are measured before and after on the host application's largest dock. |
| Text measurement for click-to-place caret is slow. | Prefix widths are cached per (string, font, size) and only computed while editing. |
| `exec()` cannot block a VTK event loop. | A result signal is documented as the only modal API. `exec()` is not offered. |
| Maintaining both legacy and composite classes doubles the surface area. | One contract test suite runs against both. Legacy classes get fixes and pass-through compatibility, but new features land in composites first. |
| Fractions and pixels get mixed up silently. | Bare numbers have one documented default per API, `Length` has a `repr` showing its unit, and `units.strict_mode()` (used in tests) rejects bare numbers in new APIs. |
| The scope is large. | Each workstream ships on its own, and W5 widgets ship individually. |

## 17. Decisions

Agreed 2026-11-14:

| # | Topic | Decision | Where it applies |
| --- | --- | --- | --- |
| 1 | Units | The API accepts both pixels and screen fractions, through `px()`/`frac()` `Length` values, string forms and a per-API default unit for bare numbers. Existing parameters keep their current meaning. | §4.3, §6 |
| 2 | Routing | All UI routing moves into this library. Host interactor styles keep only scene interaction. | §5 |
| 3 | Native VTK bases | Composite (non-subclassing) implementations are provided. Native-subclass versions are kept permanently in `multipanel.legacy` and the `widgets` compat namespace. | §9.1, §15 |
| 4 | Clipboard | The command-line fallback (`pbcopy`, `wl-copy`, `xclip`, …) is acceptable when Qt is absent, with an opt-out. | §10.2 |
| 5 | Domain helpers | The radiation and reconstruction helpers move to their own module, `multipanel/radiation.py`. | §4.4 |

Still open (needed before the noted workstream starts):

- **W1:** default double-click interval, and whether it is read from the OS
  where VTK exposes it.
- ~~**W7:** whether the focus ring is shown after a mouse click when the
  clicked widget is a text field.~~ Settled: never after a mouse click, and
  not while a field is editing (the caret shows focus); a field reached by
  Tab gets the ring back when editing ends.

## 18. Tracking checklist

Tick items as PRs merge. Each line should be roughly one PR.

**W0 Foundations**
- [x] `multipanel.testing.UiHarness` (click, drag, wheel, key, key_clicks, process_events)
- [x] `Timer` + virtual clock
- [x] `multipanel.units`: `px`/`frac` `Length`s, string parsing, conversion helpers
- [x] `geometry(units=...)`, `setGeometry` accepting `Length`s, unit-tagged `saveState`
- [x] Move radiation/reconstruction helpers to `multipanel/radiation.py` with re-exports
- [x] Hygiene: `ClickManager.verbose` off by default
- [x] Hygiene: move demos to `examples/`
- [x] Hygiene: replace print/commented-out debugging with the structured logger (`multipanel.enable_logging`, `MULTIPANEL_LOG`)

**W1 Event router**
- [x] `EventRouter` + event classes + virtual handlers on `WidgetMixin`
- [x] Hit-testing by z-order, bubbling, implicit grab, abort-flag consumption
- [x] Hover enter/leave, double-click, context menu, cursor shapes
- [x] Event filters + host queries (`isOverUi`, `isTextInputActive`, `widgetAt`)
- [x] Legacy handling without an adapter (§5.2): `UI_panels` discovery, legacy wheel routing, text-input guard
- [ ] Port `ScrollablePanel`, `WidgetPanel`, `DockPane` from `handle_mouse_wheel` to native `wheelEvent`: deferred. Overriding a handler makes a class native, which switches the router to hit-testing every pointer event in the host application and changes delivery to the legacy children inside these panels; the router already offers the wheel to `handle_mouse_wheel` in the right order. Revisit with the W5 composites.
- [x] Native `vtk*Widget`s pass through untouched (legacy rule, §5.2)
- [x] The host application: router installed; `pointer_is_over_ui_panel`, `text_edit_mode` checks and wheel dispatch delegate to it
- [x] The host application: remove UI branches from `HybridInteractorStyle.dispatch_*`; chart mode as event filter (`charts.install_chart_mode`; the host application's never-enabled chart dispatch removed. Its `pointer_is_over_ui_panel`/wheel/text-edit helpers already defer to the router and keep their fallbacks only for a host-side router opt-out)

**W2 Layouts**
- [x] `sizeHint`/`minimumSizeHint`/`sizePolicy`/min-max-fixed size on `WidgetMixin`
- [x] `sizeHint` + `GetBounds`/`SetBounds` for leaf controls (text, value changer, slider, buttons, colour palette, list)
- [x] `VBoxLayout`, `HBoxLayout`, stretch/spacing/margins/alignment
- [x] `GridLayout`, `FormLayout`
- [x] Dirty-flag invalidation via `RenderScheduler`; `Frame` host widget
- [x] `ScrollArea` (exact clipping via a per-area `LinkedRenderer`; popups moved to a top popup layer)
- [x] `Splitter`
- [ ] `DockPane` scrolling as a `ScrollArea`: not possible while the dock
  holds legacy panels, whose VTK widgets are bound to the renderer they
  were built on (a `ScrollArea` needs its content built on its own
  renderer). Done instead: smooth dock wheel scrolling, and per-pass hint
  caching that makes each dock pass 2-3x cheaper. Revisit with native panels.
- [x] `DockPane`: length-aware width/margin/spacing; stacks layout panels by `dockHeight()` (legacy stacking unchanged)
- [x] `WidgetPanel.setLayout` (+ `removeWidget` to move existing elements into a layout), `layoutRequestEvent` hook
- [ ] `ViewportDisplayPanel`
- [x] The host application: every classic-UI WidgetPanel on layouts (Macrobody, Source, Transform, Info, Actor Appearance, Modifier, Save & Export, Settings)

**W3 Overlay**
- [x] `OverlayLayer` + `Popup` placement/flip/dismiss, nested popups, draw-on-top
- [x] Modal input grab
- [x] Scrim behind modal popups (`Popup.setScrim`)
- [x] Tooltip hover delay, neighbour switching, hide-on-press (kept on `HoverTextOverlay`)
- [ ] Tooltips for any widget via `toolTip()` (needs native hover on legacy controls)

**W4 Actions**
- [x] `Action`, `ActionGroup`, `KeySequence`
- [x] `Shortcut` with contexts, routed after focus widget; text-editing keys stay with editing fields
- [x] `VectorButtonWidget.setAction`
- [x] The host application: key-press chain → Actions (`install_scene_actions`)

**W5 Widgets**
- [x] `Label`
- [x] `CheckBox` (tristate)
- [x] `RadioButton` + `ButtonGroup`
- [x] `PushButton` (+ `VectorButtonWidget.setAction` covers tool buttons)
- [x] `ComboBox`
- [x] `Menu` + context menu policy
- [x] `MenuBar`
- [x] `ProgressBar`
- [x] `MessageBox`
- [x] `StatusBar`
- [x] `examples/gallery.py`
- [x] `multipanel.legacy` namespace + shared contract suite run against legacy and composite (`tests/test_composite_backend.py`; grows with each composite)
- [x] Composite `ButtonWidget` (icon per state on a textured quad; VTK-style `AddObserver`/`GetRepresentation().GetState()` shims. The native one now emits `pressed`/`released` on mouse clicks, and its `toggle()`/`SetPosition` bounds were fixed)
- [ ] Composite `TextWidget`
- [x] Composite `SliderWidget` (VTK 9.5's slider geometry, picking and jump-on-release reproduced in `SliderRepresentation`, pixel-identical; native and composite share `_SliderAPI`; the host application's 16 sliders and list scrollbars run on it)
- [x] Composite `PanelBackgroundWidget` (`multipanel.composite`, on the `VectorPanelBackground` painter)
- [~] `set_widget_backend()` switch (`multipanel.backend`, or `MULTIPANEL_BACKEND=composite`); the host application runs on composites once all four exist

**W6 Text**
- [x] `TextBuffer` (caret/anchor/undo/word boundaries) + property tests
- [x] Selection, word navigation, select-all
- [x] `multipanel.clipboard`: host hook → Qt → CLI tools → in-process, with opt-out
- [x] Undo/redo
- [x] Click-to-caret, drag/double/triple-click selection, selection highlight
- [x] Horizontal scrolling of text wider than the field (fixed-size fonts; drag past an edge scrolls)
- [x] Draw the caret as a line instead of an inline glyph (`caret_text="I"` keeps the old glyph)
- [x] Max length, password echo, input mask, completer (+ `insertText` hook for input-method text)
- [x] Clicks anywhere in a field start editing (`claim_cell_clicks`; list rows still use VTK's hit box)
- [x] `Char`-event input (text from `CharEvent`, consumed by the editing field, so style hotkeys never fire with or without the router; `insertText` for text beyond Latin-1); the host application's `blocked_keys` removed
- [x] Multi-line `TextEdit` (own clipped renderer rather than a `ScrollArea`, so only visible lines have actors; read-only log mode; monospace option)

**W7 Styling**
- [x] `styleState()` + `Style` token resolution, `#objectName`/`*` overrides
- [x] Focus-visible ring (Tab/Shift-Tab only; hidden while editing; works for legacy widgets)
- [x] Port standard controls to role tokens
- [x] `styleStateChanged` signal
- [~] Port legacy controls (`controls.py`) to `Style`: `VectorButtonWidget` done (hover/pressed/checked tiles, disabled opacity, own hover tracking). `TextWidget`/`SliderWidget` not: their `setEnabled` hides them (VTK `SetEnabled`), so there is no visible disabled state to style without changing behaviour.

**W8 Animation**
- [x] `PropertyAnimation` + easing; global disable (`set_animations_enabled`, `MULTIPANEL_ANIMATIONS=0`)
- [x] `ProgressBar` busy mode and popup/menu fade-in on animations
- [ ] Collapse/expand: deferred; the legacy panels rebuild rows and reflow the whole dock on collapse, so a per-frame height animation would relayout the dock every frame (the old manipulator-lag pattern). Revisit with native panels.
- [x] Smooth wheel scrolling in `ScrollArea`
- (no caret blink: removed at the user's request)

**W9 Models**
- [x] `ItemModel`, `ListModel`, `TreeModel.from_hierarchy` (plus `TableModel`)
- [x] `SelectionModel`
- [x] `ListView`, `TreeView`, `TableView` (header resize is built in; the
  W2 splitter is not needed for it)
- [x] `ScrollablePanel`/`ComboBox` accept `ItemModel` (the panel rebuilds
  its rows once per event; per-row updates come with `ListView`)

**W10 Tooling**
- [x] `Inspector` (`multipanel.debug`; plus `dump_tree`, `describe`)
- [x] Screenshot tests from the gallery (structural checks + VTK-version-tagged references)
- [x] `docs/LAYOUTS.md`, API.md sections
