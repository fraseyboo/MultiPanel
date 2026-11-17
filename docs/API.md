# Widget API compatibility

MultiPanel provides a Qt-shaped API without importing Qt. The VTK methods are
not deprecated or wrapped away; both styles can be used in the same program.

## Common contract

Every migrated widget derives from `WidgetMixin`. This supplies object names,
parent/child ownership, enabled and visible state, geometry, tooltips, signal
blocking, deterministic close/delete behavior, owned VTK observers, and
coalesced rendering. `SignalBlocker` can be used like `QSignalBlocker`:

```python
from multipanel import SignalBlocker

with SignalBlocker(slider):
    slider.setValue(0.5)
```

Widgets registered with an interactor share a `FocusManager`. This provides a
single focused widget, Tab/Shift-Tab traversal, Enter/Space activation, Escape
cancellation, and pointer capture during drag operations. Editable text widgets
therefore cannot remain in edit mode simultaneously.

Common state is JSON-compatible and can be persisted by a host application:

```python
state = dock.saveState()
# serialize state as JSON, then restore it in a later session
dock.restoreState(state)
```

When a host mutates `renderer.theme`, call
`refresh_renderer_theme(renderer)` (or `widget.refreshTheme()`) to update the
registered widget tree without reconstructing it.

## Logging

The library never prints: every module logs to its own
`logging.getLogger(__name__)` under `multipanel`. Without configuration
only warnings and errors reach the console. To see debug output, set
`MULTIPANEL_LOG=debug` (or `info`, `warning`, `error`) or call
`multipanel.enable_logging("debug", stream=None)`; both add a single
handler to the `multipanel` logger and leave the host's root logger alone.
Hosts with their own logging configuration need do nothing.

## Units

Geometry and (from W2 onward) layout sizes accept both logical pixels and
fractions of the viewport:

```python
from multipanel import frac, px

widget.setGeometry(px(12), frac(0.6), px(260), frac(0.35))
widget.setGeometry(12, 40, 260, 120, units="px")   # bare numbers as pixels
widget.geometry()            # fractions of the viewport (default)
widget.geometry("px")        # logical pixels (display px / ui_scale())
widget.geometry("display")   # display pixels, as GetEventPosition reports
```

Bare numbers passed to `setGeometry` remain viewport fractions. Strings such
as `"8px"` and `"25%"` are also accepted. When geometry is set with explicit
units, `saveState` records them (`[[12, "px"], [0.6, "frac"], ...]`) so a
restored widget keeps pixel sizes fixed and fractional sizes proportional.
Untagged state from earlier releases restores as fractions.
`multipanel.units.strict_mode()` makes new APIs reject bare numbers, for
catching ambiguous call sites in tests.

## Timers

`Timer` mirrors `QTimer` (`start`, `stop`, `isActive`, `setInterval`,
`setSingleShot`, `timeout` signal, `Timer.singleShot(interactor, ms, fn)`)
and uses the interactor's VTK timers. When a `VirtualClock` is installed on
the interactor, timers and `RenderScheduler` renders run only when the clock
is advanced, which makes timing-dependent behaviour testable. Under a running
Qt application (a binding already imported by the host) timers and render
scheduling use `QTimer`, because Qt's `QVTKRenderWindowInteractor` runs all
VTK timers on one shared 10 ms timer that ignores durations.

## Animation

`multipanel.animation.PropertyAnimation` mirrors `QPropertyAnimation`:

```python
from multipanel.animation import PropertyAnimation, animate

fade = PropertyAnimation(popup, "windowOpacity", duration_ms=120,
                         easing="outCubic", start_value=0.0, end_value=1.0)
fade.finished.connect(on_shown)
fade.start()
animate(widget, "height", 40.0)            # fire and forget
```

The property is set through `setX` when the target has it, else as an
attribute; `name` may be a callable setter (pass `interactor=`). Numbers
and tuples interpolate element-wise. Easings: `linear`, `in/out/inOutQuad`,
`in/out/inOutCubic`, `inOutSine`, `outBack`, or any callable. `loop_count=-1`
repeats until `stop()`; `setDirection("backward")`, `pause()`/`resume()`.
Animations run on `Timer` (so a `VirtualClock` drives them in tests) and
request a render each step (`request_render=False` when the setter renders
itself). `set_animations_enabled(False)` or `MULTIPANEL_ANIMATIONS=0` makes
every animation jump to its end value: use it for remote sessions and for
single-frame screenshots without an event loop.

Popups fade in over `Popup.FADE_IN_MS` (90 ms; 0 disables) and expose
`windowOpacity()`/`setWindowOpacity()`.

## Testing helpers

`multipanel.testing.UiHarness` is the `QTest` equivalent. It owns an
off-screen window with a virtual clock and injects real interactor events:
`click`, `double_click`, `press`, `release`, `move`, `drag`, `wheel`, `key`,
`key_clicks` and `process_events(ms)`. Targets are widgets (their centre) or
display-pixel tuples.


### Inspector and screenshot tests

`multipanel.debug.Inspector(interactor)` outlines the widget under the
pointer (its parent more faintly) and shows its class, `objectName`,
geometry, size hints, size policy, style state and z-order; Ctrl+Alt+I
toggles it (`shortcut=` changes the key, `enabled=True` starts it on). It
only observes, so clicks still reach the UI. `dump_tree(interactor,
stream=None)` returns (and optionally writes) the widget tree with
geometry in logical px; `describe(widget)` is the inspector's text.

`examples/gallery.py` exposes `render(theme, scene)`, which renders one
off-screen frame (`scene`: `menu`, `message`, `focus`, `plain`).
`tests/test_gallery_screenshots.py` checks both themes structurally (theme
colours, popups and the focus ring on top) and compares against reference
images in `tests/screenshots`, which are tied to the VTK version in
`versions.json` (other versions skip the comparison). Regenerate them
with `MULTIPANEL_UPDATE_SCREENSHOTS=1 pytest tests/test_gallery_screenshots.py`;
a failing comparison writes `<name>.actual.png` beside the reference.
## Layouts

`multipanel.layouts` provides `VBoxLayout`, `HBoxLayout`, `GridLayout` and
`FormLayout`, and `multipanel.containers.Frame` is a plain host widget (with
an optional rounded background):

```python
from multipanel.containers import Frame
from multipanel.layouts import FormLayout, HBoxLayout, VBoxLayout
from multipanel.units import frac, px

frame = Frame(renderer, interactor, background=True,
              geometry=(frac(0.04), frac(0.45), px(340), px(250)))
form = FormLayout()
form.addRow("Density", density)          # string labels become TextWidgets
buttons = HBoxLayout(spacing=8)
buttons.addStretch()
buttons.addWidget(apply_button)
column = VBoxLayout(margins=(12, 12, 12, 12), spacing=10)
column.addLayout(form)
column.addStretch()
column.addLayout(buttons)
frame.setLayout(column)
```

Sizes are logical pixels. Margins, spacing, `addSpacing` and minimum/maximum
sizes accept numbers (px), `px()`/`frac()` or strings like `"8px"`/`"2%"`;
fractions are re-resolved on every pass. Vertical layouts and grid rows run
top to bottom. A layout relayouts once per frame (just before the render)
after a child's `updateGeometry()` or visibility change, the host's geometry
change, or a window resize; `layout.activate()` lays out immediately.

Widgets negotiate size with `sizeHint()`, `minimumSizeHint()`,
`setMinimumSize`/`setMaximumSize`/`setFixedSize` (and the width/height
variants) and `setSizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)`.
Policies and stretch follow Qt: stretch factors divide the space of the
stretched items by weight, then expanding items take spare space, then any
item that may grow. Hidden widgets take no space unless the policy's
`retainSizeWhenHidden` is set. `TextWidget`, `ValueChangerWidget`,
`SliderWidget`, `ButtonWidget` and `VectorButtonWidget` provide hints and
`GetBounds`/`SetBounds`, so `setGeometry` works on all of them.

### Layouts in panels and docks

`WidgetPanel.setLayout(layout)` fills the area under the panel's header; the
panel grows to the layout's size hint and still collapses, hides and docks
as before. Name-keyed widgets from the properties dictionary can be moved
into a layout with `panel.removeWidget(name)`, which keeps their styling:

```python
buttons = HBoxLayout(spacing=6)
buttons.addWidget(panel.removeWidget("save button"))
buttons.addStretch()
column = VBoxLayout(margins=(4, 2, 4, 4))
column.addLayout(buttons)
column.addWidget(panel.removeWidget("status text"))
panel.setLayout(column)
```

Moved elements stay addressable by name through `panel.widget(name)`.

`DockPane` stacks such panels (and `Frame`s) at the height they report from
`dockHeight()`; legacy panels keep their width-proportional heights.
`DockPane` `width`, `margin` and `spacing`, and `setDockWidth`, accept
`px()`/`frac()` lengths (a pixel-wide dock keeps its width when the window
resizes); bare numbers keep their previous meaning. The dock's wheel scrolling is smooth (`DockPane.SCROLL_MS`, notches
accumulate; instant with animations off); `scrollTo(offset)` and
`setScrollOffset(offset)` take viewport heights. A host that must resize
itself when its layout's hints change implements
`layoutRequestEvent(layout)`, the equivalent of Qt's `LayoutRequest`.

The layout getter is `contentLayout()`, not Qt's `layout()`, because
`DockPane` and `ViewportDisplayPanel` already use `layout()` for their own
relayout. `examples/layout_demo.py` shows a complete panel.

## Text editing

Editable `TextWidget`s behave like `QLineEdit`, on top of the pure-Python
`multipanel.text_buffer.TextBuffer`:

- Shift+arrows/Home/End select; Ctrl or Alt+arrows move by word;
  Ctrl+Backspace/Delete delete by word; Ctrl+A selects all.
- Ctrl+C/X/V use the system clipboard; Ctrl+Z undoes (one step per word of
  typing) and Ctrl+Y or Ctrl+Shift+Z redoes. On macOS VTK reports Cmd as Ctrl.
- A click places the caret where it lands (also when it starts editing),
  dragging selects, a double click selects a word, a triple click selects
  everything. The selection is highlighted; `selectedText()`,
  `hasSelectedText()` and `selectAll()` are available.
- Other Ctrl combinations (e.g. Ctrl+S) are left for shortcuts.
- Text wider than the field scrolls to keep the caret visible (fields
  with `scale_text_to_widget=False`; scaled fields shrink the font instead).
- The caret is drawn as a thin line; `caret_text="I"` restores the old
  inline glyph.

`multipanel.clipboard` picks a backend on first use: a host hook
(`set_clipboard_backend(get_text, set_text)`), Qt's clipboard when a Qt
application runs, the platform tool (`pbcopy`/`pbpaste`, `wl-copy`,
`xclip`/`xsel`, `clip.exe`; no shell, 1 s timeout), else an in-process
buffer. `set_clipboard_backend("internal")` or `MULTIPANEL_CLIPBOARD=internal`
keeps everything in-process (the test suite does this).

### Line edit options

`TextWidget` has the `QLineEdit` options:

```python
field.setMaxLength(8)                    # typing, paste and setText
field.setEchoMode("password")            # normal, password, noEcho,
                                         # passwordEchoOnEdit
field.setInputMask(">AAA-999;_")         # Qt mask syntax, "_" blanks
field.hasAcceptableInput()               # mask filled and validator happy
field.setCompleter(["Air", "Aluminium"]) # or Completer(model, ...)
field.insertText("\u00e9")               # e.g. text from an input method
```

- Password modes show `TextWidget.PASSWORD_CHAR` per character and do not
  copy or cut to the clipboard.
- Input masks (`text_buffer.InputMask`): `A a` letter, `N n` letter or
  digit, `X x` any, `9 0` digit, `D d` 1-9, `#` digit or sign, `H h` hex,
  `B b` binary (upper case required), `>` `<` `!` case conversion, `\\`
  escapes, `;c` sets the blank. Typing skips separators (typing the
  separator jumps past it), Backspace blanks. `self.text` keeps one
  character per mask position; `textValue()` leaves blanks out. Pressing
  Enter with required positions blank reverts, like a rejected validator.
- `multipanel.completer.Completer(items, filter_mode="startsWith" |
  "contains", case_sensitive=False, max_visible=7)`: while editing,
  matches show in a menu under the field without taking focus; Up/Down
  choose, Enter, Tab or a click accept (`activated(text)`), Escape closes
  the list first and editing second. The candidates may be a list or an
  `ItemModel` column, read when the list opens.
- `Popup.popup(..., take_focus=False)` shows a popup that leaves keyboard
  focus alone; Escape then belongs to the focused widget. Focus widgets
  may implement `focusKeyIntercept(key)` to claim Escape, Enter or Tab
  before the `FocusManager` acts on them.

### Multi-line text

`multipanel.textedit.TextEdit` is a plain-text editor (`QPlainTextEdit`):

```python
deck = TextEdit(renderer, interactor, text, monospace=True)
deck.textChanged.connect(on_deck_changed)
log = TextEdit(renderer, interactor, read_only=True)
log.setMaximumBlockCount(500)
log.appendPlainText("Loaded 12 cells")
```

Text wraps at spaces (mid-word only when a word is wider than the field)
and scrolls vertically with the wheel or the scroll bar; it is clipped by
the editor's own `LinkedRenderer` and only visible lines have text
actors. Keys: Shift selects, Ctrl/Alt moves and deletes by word,
Up/Down by visual line keeping the column, PageUp/PageDown by a page,
Home/End to the line, Ctrl+Home/End to the document, Enter inserts a
newline, Ctrl+A/C/X/V/Z/Y. Tab moves focus unless
`setTabChangesFocus(False)` (then it inserts spaces). Mouse: click, drag,
double-click (word), triple-click (line). API: `toPlainText`,
`setPlainText`, `appendPlainText` (a log follows it while scrolled to
the bottom), `insertPlainText`, `clear`, `setReadOnly`,
`setMaximumBlockCount`, `setPlaceholderText`, `setMonospace` (Courier,
for column-aligned input decks), `textCursorPosition`,
`setTextCursorPosition(pos, select)`, `selectedText`, `selectAll`, `copy`,
`cut`, `paste`, `undo`, `redo`, `ensureCursorVisible`, signals
`textChanged`, `cursorPositionChanged`, `selectionChanged`. While focused
and editable, `editing` is true, so typed keys never reach scene
hotkeys; a left press on the scene (no UI under it) takes focus from a
native editor, as clicking a QVTK view does in Qt.
`examples/textedit_demo.py` shows an editor and a live log.

## Styling and focus ring

`multipanel.style.Style` (one per renderer) turns *(role, part, states)* into
a colour from the renderer's theme tokens, so every control reacts to
state the same way. Roles: `button`, `field`, `indicator`, `menu_item`,
`progress`, `focus`, `text`, `muted`; parts: `background`, `border`,
`text`, `mark`, `fill`; states come from `widget.styleState()` (`hover`,
`pressed`, `focus`, `disabled`, `checked`, plus `default`, `active`, `open`
where they apply). Native widgets call `self.color(role, part)`.

```python
from multipanel.style import Style

style = Style.for_renderer(renderer)
style.setOverride("#place_button", "button", "background", (0.8, 0.2, 0.2))
style.setOverride("*", "field", "border", (0.5, 0.5, 0.5), states={"focus"})
```

Overrides match `"*"` or `"#objectName"`; with `states` they apply only
while all of those states hold; later overrides win.

Focus moved by Tab/Shift-Tab draws a 2 px accent ring around the focused
widget (`FocusRing`, one per interactor, created on the first keyboard
focus change). It follows the widget through layout changes, hides with
it, never appears for mouse focus, and is hidden while a text field edits.

### Style state changes

`widget.styleStateChanged(new, old)` fires whenever `styleState()`
changes: the router updates hover, the `FocusManager` focus,
`setEnabled` availability, and native widgets their pressed and checked
states (`updateStyleState()` recomputes and emits; call it after changing
a state of your own). Legacy `VectorButtonWidget`s take part too:

- Rounded-tile buttons take their fill and border from `Style`
  (`button` role): the normal look is unchanged, hover, pressed and
  checked now show. Icon-only buttons do not change on hover.
- Unavailable buttons (`setEnabled(False)` or assigning
  `button.enabled = False`, which now notifies the same way) draw their
  icon at `VectorButtonWidget.DISABLED_OPACITY` (0.4; 1.0 turns it off)
  and ignore hover; buttons already shown in grayscale are left as they
  are.
- Legacy buttons track hover themselves (the router only hit-tests while
  native widgets exist): cheap rectangle tests on mouse moves that never
  consume the event.

`TextWidget` and `SliderWidget` are not ported: for these VTK widgets
`setEnabled` maps to VTK's `SetEnabled`, which hides them.

## Standard controls

`multipanel.standard` provides native controls that work with layouts,
popups, actions, focus and themes: `Label`, `PushButton` (optionally bound
to an `Action`), `CheckBox` (optionally tristate), `RadioButton` with
`ButtonGroup` (radio buttons sharing a parent are exclusive by default),
`ProgressBar` (`setRange(0, 0)` animates a busy bar), `Menu` (actions,
separators, sub-menus, checkable items with marks, keyboard navigation) and
`ComboBox` (its list is a `Menu`), `MenuBar` (click to open, hover to
switch), `StatusBar` (`showMessage(text, timeout_ms)`; shows the status tip
of the widget under the pointer) and `MessageBox` (modal, centred over a
dimmed backdrop; `information`/`warning`/`question`, `finished(button)`;
Enter = default button, Escape = escape button). `examples/gallery.py`
shows them all in light and dark themes (`--message` opens a message box).

```python
from multipanel.standard import CheckBox, ComboBox, Menu

wireframe = CheckBox(renderer, interactor, "Wireframe")
wireframe.toggled.connect(set_wireframe)
material = ComboBox(renderer, interactor)
material.addItems(["Air", "Lead", "Water"])
material.currentTextChanged.connect(set_material)
```

Controls are shown/hidden by containers through `SetVisibility`/
`GetEnabled` (as other widgets) and greyed out with `setEnabled(False)`.

Any widget, native or legacy, can offer a context menu:
`setContextMenuPolicy("custom")` emits `customContextMenuRequested(pos)` on
a right click (not a right drag); `setContextMenuPolicy("actions")` pops up
a `Menu` of the widget's `actions()` (see `addAction`).

## Actions and shortcuts

`multipanel.actions` provides `Action`, `ActionGroup`, `KeySequence` and
`Shortcut`, modelled on Qt:

```python
from multipanel.actions import Action

save = Action("Save scene", interactor=interactor, shortcut="Ctrl+S")
save.triggered.connect(lambda checked: save_scene())
button.setAction(save)      # VectorButtonWidget: click, enabled, tool tip
save.setEnabled(False)      # button greys out, shortcut stops firing
```

The EventRouter dispatches shortcuts after the focused widget has had the
key. While a text field is editing, keys that edit text (characters,
Backspace/Delete, arrows, Home/End, Escape, Ctrl+A/C/V/X/Y/Z) go to the
field. Contexts are `"application"`, `"widget"` and `"widgetWithChildren"`;
two enabled shortcuts on the same key fire neither and emit
`activatedAmbiguously`. Shortcuts are owned by the interactor's map until
`release()` or until their parent widget is closed. Checkable actions in an
exclusive `ActionGroup` behave as radio buttons.

Escape only consumes the key when the focus widget actually had something to
cancel (an edit, a popup); otherwise focus is cleared and the key reaches
the application.

## Scroll areas

`multipanel.scrollarea.ScrollArea` shows one content widget through a
clipped viewport. Build the content on `area.contentRenderer()`:

```python
from multipanel.scrollarea import ScrollArea

area = ScrollArea(renderer, interactor)
content = Frame(area.contentRenderer(), interactor)
rows = VBoxLayout()
for name in materials:
    rows.addWidget(CheckBox(area.contentRenderer(), interactor, name))
content.setLayout(rows)
area.setWidget(content)
column.addWidget(area, stretch=1)
```

The content renderer is a `multipanel.layers.LinkedRenderer`: a
transparent renderer whose viewport is the area (VTK's 2D mappers ignore
clipping planes, so a viewport is the exact way to clip), sharing the
parent renderer's theme and `Style`. With `widgetResizable()` (default)
the content fills the width and at least the height. The wheel scrolls
smoothly (`WHEEL_STEP_PX` per notch over `SCROLL_MS`; instant with
animations off), the `verticalScrollBar()` can be dragged or clicked to
page, `scrollTo(value, animated=True)` and `ensureWidgetVisible(child)`
scroll in code. Widgets inside only receive clicks where they are visible.
`examples/scroll_demo.py` shows one in a panel.

## Splitters

`multipanel.splitter.Splitter(renderer, interactor, orientation)` places
widgets in a row (`"horizontal"`) or column with draggable handles:

```python
split = Splitter(renderer, interactor, "horizontal")
split.addWidget(scene_tree)
split.addWidget(properties)
split.setSizes([220, 380])          # logical px, scaled to fit
split.setStretchFactor(1, 1)        # resizes go to the second widget
split.splitterMoved.connect(lambda position, index: ...)
```

`sizes()`, `setSizes()`, `moveSplitter(position, index)`, `handle(i)`,
`setHandleWidth`, `setChildrenCollapsible`/`setCollapsible(i, b)`,
`insertWidget`, `takeWidget`, `indexOf`, `count`; `saveState()` records
the sizes. Dragging a handle moves its two neighbours; past half a
widget's minimum size it collapses to 0. See [LAYOUTS.md](LAYOUTS.md#splitters).

## Item models and views

`multipanel.models` holds one data model for lists, trees, tables and
combo boxes, after `QAbstractItemModel`; `multipanel.views` shows it:

```python
from multipanel.models import ListModel, TableModel, TreeModel
from multipanel.views import ListView, TableView, TreeView

materials = ListModel(["Air", "Lead"])
materials.append({"display": "Water", "decoration": (0.2, 0.5, 0.9),
                  "checkState": "checked", "toolTip": "H2O", "user": water})
view = ListView(renderer, interactor, model=materials)
view.selectionChanged.connect(on_selection)

tree = TreeView(renderer, interactor,
                model=TreeModel.from_hierarchy(scene_root))
table = TableView(renderer, interactor, model=TableModel(
    rows, headers=("Cell", "Material", "Density")))
combo.setModel(materials)            # ComboBox follows the model too
```

- **Models.** `ModelIndex` locates a cell (`row()`, `column()`,
  `parent()`, `data(role)`, `flags()`). `ItemModel` is the base:
  `rowCount`, `columnCount`, `index`, `parent`, `data`, `setData`,
  `flags`, `headerData`, and signals `dataChanged`, `rowsInserted`,
  `rowsAboutToBeRemoved`, `rowsRemoved`, `modelReset`,
  `headerDataChanged`; subclasses call `beginInsertRows`/`endInsertRows`
  and friends. Roles are strings: `display`, `decoration` (an RGB swatch
  or a `png_icons` name; single-colour icons take the text colour),
  `toolTip`, `checkState` (`unchecked`/`partially`/`checked`), `user`.
  Flags: `selectable`, `enabled`, `editable`, `checkable` (implied by a
  check state).
- `ListModel(items, headers=None)` takes strings, role dicts or objects;
  `append`, `insert`, `insertItems`, `removeRows`, `setItems`, `findRow`.
  `TableModel(rows, headers)` is a list model with columns.
  `TreeModel.from_hierarchy(root, columns=None)` wraps
  `hierarchy.HierarchyNode`s (`label` is the display text, `value` the
  user data); `insertNode`, `appendNode`, `removeNode`, `walk`;
  `columns=[(header, getter)]` adds columns.
- **Selection.** `SelectionModel(model, mode)` keeps whole rows selected
  (`none`, `single`, `multi`, `extended`) with `select(indexes,
  command)` (`clearAndSelect`, `select`, `deselect`, `toggle`),
  `setCurrentIndex`, `selectedRows`, and `selectionChanged` /
  `currentChanged`. Rows are kept by `model.persistentKey(index)`, so
  the built-in models keep selections through inserts, removals and
  collapsed branches; custom models without stable keys clear the
  selection when rows move.
- **Views.** Click selects; in `extended` mode (default) Ctrl toggles,
  Shift selects from the anchor and dragging extends. Up/Down/Home/End/
  PageUp/PageDown move (Shift extends), Space toggles a check box, Enter
  emits `activated`, Ctrl+A selects all. Signals: `pressed`, `clicked`,
  `doubleClicked`, `activated`, `currentChanged`, `selectionChanged`.
  `scrollTo(index)`, `setCurrentIndex(index)`, `indexAt(x, y)`.
  Rows are clipped by the view's own `LinkedRenderer`, scroll smoothly
  with the wheel, and show `toolTip` on hover.
- `TreeView`: click a chevron or double-click a branch; Right/Left open,
  close and move. `expand`, `collapse`, `expandAll`, `collapseAll`,
  `isExpanded`; `expanded`/`collapsed` signals. Nodes with
  `expanded_by_default` start open. Collapsing keeps the selection; the
  current row moves to the collapsed branch. `scrollTo` opens the
  ancestors.
- `TableView`: a header; drag a header edge to resize a column
  (`setColumnWidth`, `resizeColumnToContents`); columns without a width
  share the space and the last one stretches (no horizontal scrolling,
  so long text is cut with an ellipsis). `ListView.setModelColumn`
  picks the column a list shows.
- **Cost.** Only visible rows have text and icon actors; a model change
  marks the view dirty and the rows are synced once before the next
  frame (`doItemsLayout()` syncs now), touching only actors whose content
  changed. Inserting a row outside the view updates no row actors.
  Backgrounds and check boxes are built for blocks of rows and moved by
  the scroll offset, so scrolling a 10k-row list costs ~1.5 ms a frame.
- `ScrollablePanel.setModel` also accepts an `ItemModel` (it shows each
  row's `user` value or text and rebuilds its rows once per event when
  the model changes).

`examples/views_demo.py` shows all three.

## Popups

`multipanel.overlay.Popup` is a topmost `Frame` for menus, dropdown lists
and similar transient UI. Popups draw on the window's popup layer, a
full-window renderer above all others (`multipanel.layers.popup_layer`), so
they show above panels and scroll areas; build their content with
`popup.renderer` (native widgets made on another renderer are moved there
when the popup opens). `at` points are logical px in the renderer the popup
was created with.

```python
from multipanel.overlay import Popup

menu = Popup(renderer, interactor)          # modal=True blocks outside input
menu.setLayout(column_of_native_items)
menu.popup(anchor=button, placement="below")  # or at=(x, y) in logical px
menu.closed.connect(on_closed)
menu.dismiss()
```

Placement flips to the opposite side of the anchor when there is no room and
is clamped inside the viewport. While a popup is open, a press outside every
popup closes them and is consumed (it does not also click what is
underneath), a press inside one closes the popups opened above it, Escape
closes the topmost, and a modal popup blocks pointer input outside itself.
Popups consume input inside their rectangle, so their content should be
native widgets (overriding the `WidgetMixin` handlers).

Tooltips appear after the pointer rests on a button for `tooltip_delay()`
ms (`set_tooltip_delay(ms)`, default 700), switch immediately between
neighbouring buttons, and stay hidden after a press until the pointer leaves.

## Event routing

`EventRouter.install(interactor)` routes UI input for one interactor
(see `multipanel.router` for the full rules):

```python
from multipanel.router import EventRouter

router = EventRouter.install(interactor)
router.isOverUi(x, y)          # display px; is the point over any UI?
router.widgetAt(x, y)          # deepest widget, or None
router.isTextInputActive()     # a text field is editing
router.installEventFilter(fn)  # fn(target, event) -> True consumes
```

Widgets receive events by overriding Qt-named handlers on `WidgetMixin`:
`mousePressEvent`, `mouseReleaseEvent`, `mouseMoveEvent`,
`mouseDoubleClickEvent`, `wheelEvent`, `keyPressEvent`, `keyReleaseEvent`,
`contextMenuEvent`, `enterEvent`, `leaveEvent`. Events start ignored; call
`event.accept()` to consume one. Ignored events bubble to the parent and
then to the 3D scene. Accepted presses grab the mouse until release, and
clicks give focus to widgets whose policy is `StrongFocus` or `ClickFocus`.
Top-level native widgets call `registerWithRouter()`; children are reached
through `children()`. `setCursor(vtk.VTK_CURSOR_HAND)` and `underMouse()`
cover hover. Event objects (`multipanel.events`) provide `pos()` (logical px
local to the receiver), `globalPos()` (display px), `button()`, `buttons()`,
`modifiers()`, `delta()` and `key()`/`text()`.

Widgets that override no handler keep receiving input through their own VTK
observers; the router only counts them for `isOverUi`, routes the wheel to
their `handle_mouse_wheel`, and stops scene hotkeys while they edit text.

### Chart widgets

`multipanel.chartview` puts charts in the UI as widgets:

```python
from multipanel.chartview import ChartPanel, XYChart

chart = XYChart(title="Source spectrum")
chart.axisX().setTitle("Energy (MeV)")
chart.axisY().setLogScale(True)
chart.addStep(edges, probabilities, name="SI1/SP1", fill=True)
chart.addStems([0.662, 1.173, 1.332], [0.85, 1.0, 1.0], name="Lines")
panel = ChartPanel(renderer, interactor, chart, title="Spectrum")
dock.add_panel(panel, tab="sources")      # or leave it floating
```

- `ChartView(renderer, interactor, chart)` is a native widget: it lays
  out, hides (with its panel or dock tab) and clips like the item views
  (its own `LinkedRenderer`). The router delivers the pointer to the
  chart, so the camera never moves under it: wheel zooms, left drag pans,
  right drag zooms to a box, double-click or Home resets.
- `XYChart`: `addLine`, `addScatter`, `addBars(x, y, horizontal=)`, `addStep(edges, values,
  fill=)` (histograms), `addStems` (discrete lines),
  `addErrorBars(x, y, errors=None, x_errors=None, of=series, caps=True)`
  (vertical and/or horizontal bars, each symmetric or `(lower, upper)`,
  with caps of fixed pixel width, in the colour of `of`, not in the
  legend; their errors show in `of`'s tooltips),
  `addErrorScatter(x, y, errors, x_errors)` (points plus their bars),
  `removeSeries`,
  `clear`, `resetView`, `setLegendPosition`, `setLegendVisible`;
  `axisX()`/`axisY()` with `setTitle`, `setRange` (fixed; reset returns
  to it), `setAutoRange`, `setIncludeZero` (automatic range reaches 0),
  `setTickLabels(positions, labels)` (categories, e.g. under bars; the
  axis then fits its data exactly), `clearTickLabels`,
  `setLogScale`, `setGridVisible`. Series update in place with
  `setData`; `setName` renames one. Ranges are rounded to nice numbers
  independently of the chart's size.
- `ChartPanel(..., caption="")` adds a centred bold label above the chart
  (`panel.caption()`); use it rather than a chart title in narrow panels,
  where `vtkChartXY` draws the title over the top axis label.
- **Tooltips.** Hovering shows the item under the pointer: a histogram
  bin anywhere inside it (with `± error` from error bars attached by
  `of=`), a bar or stem along its length (bars named by their category
  label), else the nearest point. `series.setTooltipFormatter(fn)` sets
  the text (`fn(index) -> str`); `view.setTooltipsEnabled(False)` turns
  them off. They hide while dragging or editing. (vtkChartXY alone only
  reports plotted vertices, which miss bins, stems and bars.)
- **Interaction and the context menu.** `view.setInteraction(left="pan",
  right="zoom_box", shift_left="zoom_box", wheel="zoom")` binds each
  button (and `shift_`/`ctrl_` variants) to `"pan"`, `"zoom_box"`,
  `"zoom_axis"`, `"select"`, `"select_box"` or None; `wheel=None` leaves
  the wheel to the scene. A press only reaches VTK once the pointer moves
  past a 3 px slop, so a press without movement is a click: left reports
  items, right opens `view.contextMenu()` (Reset view, Log x/y axis or
  Log colours, Legend, Export PNG/SVG/PDF/CSV). Exports go to
  `view.setExportFolder(path)` (default: the working folder), named after
  the chart title, and emit `exported(path)`;
  `contextMenuAboutToShow(menu)` lets an app add items;
  `setContextMenuEnabled(False)` turns it off.
- **Clicks and highlights.** `series.setClickable()` makes its items
  report a left click (one that moves under 3 px; a drag still pans) as
  `chart.clicked(series, index)`: a bar, a histogram bin or a point; the
  cursor is a hand over them. `chart.itemAt(sx, sy)` gives the item at a
  chart-scene point. `bars.setHighlighted(indices)` draws those bars in
  the accent colour and fades the others (e.g. the selection).
- Axes shorter than 120 px (narrow docks) get three to five nice ticks
  of their own; VTK's pixel-spaced ticks can leave just one.
- **Other chart types.** `Histogram2DChart(values, x_range, y_range,
  colormap="viridis", log=False, value_title="")` is a 2D histogram (heat
  map, `vtkChartHistogram2D`) of a `(ny, nx)` array with a colour legend
  (log scale too), axes fitted to the bins, `binAt(x, y)` and bin
  tooltips. `PieChart(labels, values, title)` (`vtkChartPie`) uses the
  theme palette, a legend and its own themed tooltips (label, value,
  share); `sliceAt`, `setClickable`. Both go in a `ChartView`/
  `ChartPanel` and export (CSV kinds `cell` and `slice`; CSV columns
  `series, kind, x, x_low, x_high, y, y_low, y_high`).
- **Box plots and grids.** `chart.addBoxes(groups, positions=None,
  labels=None, width=0.6, whisker=1.5)` (`BoxSeries`) draws each group's
  Q1–Q3 box, median, capped whiskers (Tukey: furthest values within
  1.5 IQR) and outliers, labels the groups on the x axis and shows the
  statistics on hover (`statistics()`, `box_statistics(values)`; CSV
  kinds `box`, `whisker`, `outlier`). `multipanel.chart_grid.ChartGrid(
  renderer, interactor, columns=2, link=None)` lays several charts out
  in a grid (`addChart(chart, row, column, rowSpan, columnSpan)`), with
  `link="x"`, `"y"` or `"xy"` sharing pans, zooms, box zooms and resets;
  `ChartGridPanel` puts one in a scene panel.
- **Model binding.** `multipanel.chart_models.bind_series(series, model,
  x=0, y=1, selection=None)` keeps a line, scatter, bar or stem series
  equal to two columns of an `ItemModel` (`TableModel` rows): inserted
  rows are read on their own and spliced in, edited cells re-read, removed
  rows spliced out, a reset re-reads everything (values from the `edit`
  role, as a table view edits them). With a `SelectionModel` (e.g. a
  `TableView`'s), selected rows are highlighted and clicking a point or
  bar selects its row (Shift toggles). `series.setHighlighted(indices)`
  marks points (accent markers) or recolours bars; `close()` unbinds.
- **Long series.** Line series over 20,000 points with ascending x are
  drawn decimated: per pixel column the first, lowest, highest and last
  point (so the drawn line covers the same pixels), over the visible range
  and one view width either side, recomputed after a pan leaves that
  margin or the zoom changes. `series.data()`, hit-testing, tooltips,
  editing and exports use every point; `series.isDecimated()` tells.
  Hit-testing is vectorised (and windowed in x on long lines). A hidden
  chart draws nothing and does no work. `examples/chart_benchmark.py`
  measures it: pan and hover cost about 1–2 ms per frame from 100k to 5M
  points (worst frame 4.5 ms at 100k, 24 ms at 5M while re-decimating).
- **Export.** `chart.export(path, size=None, scale=1)` writes by
  extension: `.png`/`.jpg`/`.tif` images, `.svg`/`.pdf`/`.eps`/`.ps`
  vector files (`vtkGL2PSExporter`; text stays text, in the viewer's
  Helvetica), or `.csv` of the visible series (`chart.toCsv()`; columns
  `series, kind, x, x_high, y, y_low, y_high`). The chart is drawn
  off-screen at its view's size (or `size`) times `scale`, on the theme's
  panel colour, and returns to its view with the zoom unchanged.
  `multipanel.chart_export.render_chart(chart, ...)` returns the image as
  `vtkImageData`. `examples/chart_gallery.py` shows every chart type live
  (or, given a folder, writes them in both themes); `tests/test_chart_gallery_screenshots.py` compares them
  with references in `tests/screenshots`.
- Colours come from the theme tokens and an Okabe-Ito palette (light and
  dark variants); text uses the UI font at `ui_scale`.
- **Editing.** `series.setEditable(True, minimum=..., maximum=...,
  move_x=False)` lets the user drag the data: histogram (`StepSeries`) bin
  tops up and down and inner edges sideways (kept in order, at least
  `min_width` apart; `move_outer_edges=True` frees the ends), stems along
  their length (sideways too with `move_x`), line, scatter and bar points.
  Histograms and stems default to `minimum=0`; `x_minimum`/`x_maximum`
  bound sideways moves (e.g. energies above zero). Undo and redo also
  emit `edited`. Hovering a draggable piece
  highlights it (accent colour) and sets the cursor; elsewhere a drag
  still pans. `series.edited(series)` and `chart.edited(series)` fire when
  a drag ends; the chart keeps an undo stack (`undo`, `redo`, `canUndo`,
  `clearHistory`; Ctrl+Z, Ctrl+Y and Ctrl+Shift+Z in a focused chart).
  `axis.toScene(value)`/`fromScene(px)` map between data and chart pixels
  (log axes included); `axis.range()`/`setRange()` are in data units on
  log axes too.
- `ChartPanel(renderer, interactor, chart, title=..., chart_height=...)`
  is a `WidgetPanel` holding a `ChartView` (`panel.chartView()`); it uses
  the theme's panel colours unless given others.
- `DockPane.add_panel` now makes the panel the dock's child, so the
  router reaches widgets inside docked panels.
- `examples/chart_panel_demo.py` shows a docked and a floating chart.

### Chart helpers and the old chart actors

`multipanel.charts` keeps the functional, matplotlib-like helpers
(`figure()`/`show()`, `add_line_chart`, `add_scatter_chart`,
`add_bar_chart`, `add_errorbar_plot`, `imshow`, the axis setters…) on raw
`vtkChartXY` objects. The common ones also accept an `XYChart`,
`ChartView` or `ChartPanel` and use its API, so existing code moves over
by passing the new chart:

```python
from multipanel import charts

charts.add_line_chart(x, y, figure=panel, y_label="Summed")   # a LineSeries
charts.set_x_axis_title(panel, "Energy (keV)")
```

(their default colour then means the theme palette). It imports with the
base dependencies; its colour helpers are those of
`multipanel.colormap_utils`.

**Deprecated:** `add_chart_actor`, `DraggableChartInteractorStyle`,
`HybridInteractorStyle` and `install_chart_mode` (`ChartModeFilter`) moved
to `multipanel.chart_legacy` and warn with `DeprecationWarning`; `charts`
re-exports them until they are removed. They floated a chart actor over
the scene and shared mouse input with the camera through interactor
styles or a router filter; a `ChartView`/`ChartPanel` does all of that as
a widget. `examples/chart_demos.py` still shows them.

## Import surfaces

- `multipanel.controls`: buttons, sliders, text and value/color controls
- `multipanel.containers`: scrolling panels, widget panels and docks
- `multipanel.input`: interactor-level event routing
- `multipanel.specialists`: scene manipulation, slicing and probe widgets
- `multipanel.resources`: icon/font paths with no widget import side effects
- `multipanel.units`: `px`/`frac` lengths and viewport conversions
- `multipanel.timer`: `Timer` and `VirtualClock`
- `multipanel.chartview`: `XYChart`, series, `ChartView`, `ChartPanel`
- `multipanel.display`: `DisplayWatcher` (size/DPI changes between displays), `fit_window_to_screen`
- `multipanel.chart_export`: chart images, vector files and CSV
- `multipanel.chart_models`: series bound to item models, selection sync
- `multipanel.chart_grid`: `ChartGrid`/`ChartGridPanel` (charts with linked axes)
- `multipanel.charts`: functional chart helpers (`chart_legacy`: deprecated actors)
- `multipanel.testing`: `UiHarness` event simulation for tests
- `multipanel.router` / `multipanel.events`: event routing and event objects
- `multipanel.layouts`: box, grid and form layouts
- `multipanel.overlay`: `Popup` and the per-renderer `OverlayLayer`
- `multipanel.actions`: `Action`, `ActionGroup`, `KeySequence`, `Shortcut`
- `multipanel.standard`: labels, buttons, toggles, progress, menus, combo boxes
- `multipanel.text_buffer` / `multipanel.clipboard`: text editing model and clipboard
- `multipanel.widgets`: backward-compatible namespace containing all widgets
- `multipanel.composite` / `multipanel.legacy`: composite versions of the controls that subclass VTK widgets, and the native classes
- `multipanel.backend`: `set_widget_backend("composite" | "legacy")`

### Composite or native controls

`ButtonWidget`, `TextWidget`, `SliderWidget` and `PanelBackgroundWidget`
subclass `vtk*Widget`s. Composite versions with the same constructor and
API are being added to `multipanel.composite` (so far:
`PanelBackgroundWidget`, `ButtonWidget` and `SliderWidget`). `native` is the widget itself on a native class
and `None` on a composite.

```python
import multipanel

multipanel.set_widget_backend("composite")   # before building any UI
from multipanel.containers import PanelBackgroundWidget   # the composite
```

The switch rebinds the names in `controls`, `containers`, `specialists`,
`layouts` and `widgets`, so the library's own containers build composites
too; `multipanel.legacy` always holds the native classes. The
`MULTIPANEL_BACKEND=composite` environment variable does the same at import.
Instances already built keep their class.

A composite answers the VTK calls hosts make (`AddObserver` for
`StateChangedEvent`/`InteractionEvent`, `GetRepresentation()` with the
representation methods in use: values, coordinates, properties, sizes).
Other VTK methods raise `composite.UnsupportedVtkMethod` (an
`AttributeError`, so `hasattr` checks keep working) naming the alternative.

The focused modules own the class implementations. The legacy `widgets`
module re-exports the exact same class objects, so old and new import paths can
be mixed without creating distinct types. The module boundaries and dependency
rules are described in [the architecture guide](ARCHITECTURE.md).

The common control import path requires only NumPy and VTK. Scientific
plotting/reconstruction and source-icon conversion are loaded on demand via
the `scientific` and `icons` package extras respectively.

## Control mappings

| Widget | Qt-style state methods | Signals |
| --- | --- | --- |
| `SliderWidget` | `value`, `setValue`, `minimum`, `maximum`, `setRange`, `singleStep`, `setSingleStep`, `orientation`, `setOrientation` | `valueChanged`, `sliderPressed`, `sliderMoved`, `sliderReleased` |
| `ButtonWidget`, `VectorButtonWidget` | `isChecked`, `setChecked`, `toggle`, `click` | `clicked`, `pressed`, `released`, `toggled` |
| `TextWidget` | `textValue`, `setText`, `clear`, `click`, `isReadOnly`, `setReadOnly`, `validator`, `setValidator` | `clicked`, `doubleClicked`, `textChanged`, `textEdited`, `editingStarted`, `editingFinished`, `returnPressed` |
| `ValueChangerWidget` | `value`, `setValue`, `minimum`, `maximum`, `setRange`, `singleStep`, `setSingleStep`, `prefix`, `setPrefix` | `valueChanged`, `editingFinished` |
| `ScrollablePanel` | `count`, `item`, `currentItem`, `setCurrentItem`, `addItem`, `insertItem`, `takeItem`, `removeItem`, `clear` | `currentItemChanged`, `itemClicked`, `itemDoubleClicked`, `itemActivated`, `itemsChanged` |
| `ColorPaletteWidget` | `currentColor`, `setCurrentColor`, `colors`, `setColors`, `modeValue`, `setMode` | `colorChanged`, `colorSelected` |
| `WidgetPanel` | `title`, `setTitle`, `isCollapsed`, `setCollapsed`, `isClosable`, `setClosable`, `addWidget`, `removeWidget` | `collapsedChanged`, `closed`, `layoutChanged` |
| `DockPane` | `count`, `currentIndex`, `setCurrentIndex`, `currentWidget`, `widget`, `tabText`, `setTabText`, `removeTab`, `dockLocation`, `setDockLocation`, `dockWidth`, `setDockWidth` | `currentChanged`, `tabCloseRequested`, `dockLocationChanged`, `widthChanged` |

`TextWidget.textValue()` is used instead of `text()` because `text` is a
long-standing public data attribute retained for source compatibility.

## Specialist mappings

| Widget | Primary API | Signals |
| --- | --- | --- |
| `ColorBarWidget` | `title`, `setTitle`, `orientation`, `setOrientation`, `labelFormat`, `setLabelFormat`, `lookupTable`, `setLookupTable` | common signals |
| `Cursor3DWidget` | `positionValue`, `setPosition`, `handleSize`, `setHandleSize` | `positionChanged`, `interactionStarted`, `interactionFinished` |
| `LassoWidget` | `path`, `selection`, `clearSelection`, `apply`, `cancel`, `autoReconstruct`, `setAutoReconstruct` | `selectionChanged`, `reconstructionStarted`, `reconstructionFinished`, `failed` |
| `BoxWidget` | `boundsValue`, `setBounds`, `reset` | `interactionStarted`, `boundsChanged`, `interactionFinished`, `reconstructionStarted`, `reconstructionFinished` |
| `SphereProbeWidget` | `center`, `setCenter`, `radius`, `setRadius` | `centerChanged`, `radiusChanged`, `probeFinished` |
| `VolumeSlicer` | `sliceIndex`, `setSliceIndex`, `axisEnabled`, `setAxisEnabled`, `opacityValue`, `setOpacity`, `colorMap`, `setColorMap`, `hasInterpolation`, `setInterpolation` | `sliceChanged`, `axisEnabledChanged` |
| `SplineWidget` | `pointCount`, `points`, `setPoints`, `addPoint`, `insertPoint`, `removePoint`, `clear`, `isClosed`, `setClosed` | `pointsChanged` |
| `MeshProbeWidget` | `dataset`, `setDataset`, `probeMesh`, `probe`, `result` | `probeFinished` |

An axis omitted from `VolumeSlicer.axes_enabled` is not constructed. It can be
disabled later, but enabling an omitted axis requires recreating the slicer.
This keeps the existing VTK actor and interaction behavior unchanged.
