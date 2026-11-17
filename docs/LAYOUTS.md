# The layout model

How MultiPanel sizes and places widgets: coordinates, size negotiation,
nesting, clipped containers and when layout passes run. The API is in
[API.md](API.md#layouts); this page explains how the pieces fit.

## Coordinates

Everything is measured from the **lower-left** corner of a renderer's
viewport, with y pointing **up**, as in VTK. Three units are in use:

```
 window (display px)                       viewport of the renderer
 +--------------------------------------+   +------------------------+
 |                                      |   |      +------+          |
 |        +------------------------+    |   |      |widget|  h       |
 |        | viewport               |    |   |      +------+          |
 |        |   origin (ox, oy) -->  *    |   |  (x, y)  w             |
 |        +------------------------+    |   *------------------------+
 +--------------------------------------+   (0, 0)
 (0, 0)
```

| Unit | Meaning | Where it appears |
| --- | --- | --- |
| `frac` | fraction of the viewport (0–1) | bare numbers in `setGeometry`, `GetBounds` |
| `px` | logical pixels: display px / `ui_scale()` | layouts, size hints, `geometry("px")` |
| display px | window pixels, origin at the window's lower left | events (`globalPos()`), `geometry("display")` |

Layouts work in logical px, so a doubled `ui_scale()` (a HiDPI screen)
doubles every display size and leaves layout code untouched. `frac`
lengths are re-resolved on every pass, so a widget given `frac(0.3)` keeps
30% of the viewport as the window resizes.

## Display density (high-DPI windows)

On a Retina display VTK's Cocoa window reports its size in device pixels
and its DPI as 144 (72 on a standard display). The library scales by that
density:

- `ui_scale()` (display px per logical px) = the size preference ×
  `device_scale()` (DPI / 72). `px()` lengths, icon and row sizes,
  padding and line widths use it, so they keep their physical size.
- Font **point** sizes use `font_scale()` (the preference alone): VTK
  turns points into pixels at the window's DPI.
- Fractions (`frac()`, dock widths given as fractions) grow with the
  window's pixels already and take the preference alone
  (`user_scale()`).

Code that turns a pixel height into a font size, or a font size into
pixels, must divide or multiply by `device_scale()`.
`multipanel.display.DisplayWatcher` (installed by `EventRouter.install`)
keeps the density current and sends a resize when a window moves to
another display without one (VTK often sends none), so layouts re-run.
`fit_window_to_screen()` keeps a requested size within the screen (macOS
shrinks larger windows without VTK noticing).

## Narrow windows

Dock content never gets narrower than `DockPane.MIN_CONTENT_PX` (220
logical px). When a window narrows so far that the docks would leave the
scene less than `DockPane.MIN_SCENE_PX` (200 logical px), docks collapse,
newest first (a tabbed dock to its tab bar); they re-open when the window
widens again, unless the user changed them in between.

## Who places whom

A **host** widget owns one layout; the layout places the host's
children inside the host's rectangle minus its margins. Layouts nest:

```
Frame (host)                          setLayout(column)
└─ VBoxLayout column                  margins 12, spacing 10
   ├─ Label "Source settings"
   ├─ FormLayout form                 label column | field column
   │  ├─ "Particle"  ComboBox
   │  └─ "Energy"    ComboBox
   ├─ HBoxLayout shape_row            [Point] [Sphere] [Box] <stretch>
   ├─ <stretch>
   └─ HBoxLayout buttons              <stretch> [Cancel] [Place source]
```

Adding a widget to a layout makes it a child of the layout's host
(`parentWidget()`), so the router, hiding and `dump_tree()` follow the
same tree. Hosts are `Frame`, `WidgetPanel` (below its header), `DockPane`
(which stacks panels), `ScrollArea` (one content widget) and `Splitter`.

## Size negotiation

Each item reports, along each axis, a **minimum**, a **hint**, a
**maximum**, a **size policy** and a **stretch** factor:

```
 0        minimum          hint                       maximum
 |-----------|---------------|-----------------------------|
             <-- may shrink --  -- may grow / expand ------->
             (policy SHRINK)    (policy GROW, EXPAND)
```

`sizeHint()` and `minimumSizeHint()` come from the widget (text width,
row count...). `setMinimumSize`/`setMaximumSize`/`setFixedSize` override
them; `setSizePolicy` picks which directions are allowed, as in Qt:

| Policy | shrink below hint | grow above hint | wants spare space |
| --- | --- | --- | --- |
| `Fixed` | no | no | no |
| `Minimum` | no | yes | no |
| `Maximum` | yes | no | no |
| `Preferred` | yes | yes | no |
| `Expanding` | yes | yes | **yes** |
| `MinimumExpanding` | no | yes | **yes** |
| `Ignored` | hint ignored | yes | no |

A box layout shares its length (`layouts.distribute`) like this:

1. Every item starts at its hint, clamped to its minimum and maximum.
2. **Spare space**: items with a stretch factor share the *total* space
   of the stretched items by weight (an item whose hint already exceeds
   its share keeps its hint); what remains goes equally to expanding
   items, or, when there are none, to any item that may grow. Maximums
   cap; the excess is passed on.
3. **Too little space**: the deficit is taken from shrinkable items in
   proportion to how far each is above its minimum. If minimums still do
   not fit, the items overflow (the host should grow, see below).

The cross axis is simpler: each item gets the full breadth up to its
maximum, positioned by its alignment (`"start"`, `"center"`, `"end"`).

```
 HBoxLayout, spacing 6, two Fixed buttons around a stretch:
   300 px:  [Cancel 70] 6 [stretch ..... 98] 6 [Place source 120]
   200 px:  [Cancel 70] 6 [] 6 [Place source 120]   stretch at 0; the fixed
                                                   buttons overflow by 2 px
```

A layout's own hint is the sum of its items' hints plus spacing and
margins along its direction, and the largest breadth across it, so hosts
can size themselves to their content: a `WidgetPanel` grows to its
layout's hint, and `DockPane` stacks panels at their `dockHeight()`.

## Hidden widgets

`hide()` removes a widget from its layout and closes the gap, unless its
policy has `retainSizeWhenHidden`. Being hidden *along with* a host (a
collapsed panel, an inactive dock tab) is different: the widget keeps its
place, so the layout does not reflow when the host comes back. Form
labels follow their field: hiding the field hides its label and row.

## Clipped containers

VTK's 2D mappers ignore clipping planes, so containers that show part of
their content draw it on their own renderer (a `LinkedRenderer`) whose
viewport is the visible rectangle:

```
 window
 +-----------------------------------------------+   popup layer (top)
 | panel renderer (layer n)                       |   menus, combo lists,
 |  +------------------+                          |   message boxes,
 |  | ScrollArea or    |<- LinkedRenderer,        |   the Inspector
 |  | item view        |   viewport = this rect,  |
 |  |  rows clipped    |   same layer, drawn after|
 |  +------------------+                          |
 +-----------------------------------------------+
```

- `ScrollArea`: build the content on `area.contentRenderer()`; the
  content is laid out at full height and moved by the scroll offset.
- `ListView`/`TreeView`/`TableView`: rows are drawn directly on the
  view's renderer; only visible rows have actors.
- Popups live on one full-window renderer above every layer, so they
  stay on top of clipped containers.

A widget inside a clipped container only receives clicks where it is
visible.

## Splitters

A `Splitter` is a host that places widgets in a row or column with
handles between them:

```
 horizontal:  [ widget 0 ][|][ widget 1 ][|][ widget 2 ]      sizes() = [w0, w1, w2]
                          handle 1      handle 2               (logical px)
```

Dragging handle *i* moves widgets *i-1* and *i* only. A widget dragged
below half its minimum collapses to 0 (if collapsible); between half and
the minimum it stops at the minimum. Resizing the splitter shares the
change by stretch factor, or in proportion to the current sizes when no
factor is set. `setSizes` before the first layout is kept and scaled in
proportion once the splitter has a size.

## Charts

A `ChartView` is an ordinary laid-out widget: it takes its rectangle from
its layout and draws the chart on its own `LinkedRenderer` whose viewport
is that rectangle, so a chart is clipped exactly by docks, scroll areas
and splitters, and hidden (not drawn, no input) with its tab or a
collapsed panel.

```
 VBoxLayout
 ├─ Label (caption)          sizeHint: one text line
 ├─ ChartView   stretch=1    Expanding/Expanding, minimum 160×120 px
 └─ Label (status)
```

- Give it a minimum height (`view.setMinimumHeight(px(220))`; `ChartPanel`'s
  `chart_height`): it is Expanding, so it otherwise shares space with
  other stretch items and can become too small to read.
- The chart scene is sized to the view in pixels; fonts and line widths
  follow `ui_scale`. Axes shorter than 120 px get their own few ticks.
- Put captions in a `Label` above the view (`ChartPanel(caption=)`)
  rather than a chart title in narrow panels: `vtkChartXY` draws a title
  a fixed distance above the plot, over the top axis label.
- Input over the view goes to the chart (pan, zoom, edit, click); the
  camera only moves outside it.

## When layout runs

Changes mark a layout **dirty** rather than laying out at once:

```
 child.updateGeometry() ─┐
 child hidden / shown ───┤
 host geometry change ───┼──> invalidate() ──> RenderScheduler.request()
 window resize ──────────┘                          │
                                                    v
                          before the next frame: activate() once
```

So a burst of changes (adding twenty rows, a theme switch) costs one
pass. Within a pass each widget's hints are measured once and cached
until the pass ends (`layouts.layout_pass()`; `DockPane.layout` runs all
its panels in one). Nothing is cached *between* passes, so a legacy
control whose text changed without `updateGeometry()` is measured afresh
next time. `layout.activate()` lays out immediately, for tests and screenshots
that do not run an event loop (`RenderScheduler.flush()` does the same
for everything pending).

## Debugging layouts

```python
from multipanel.debug import Inspector, dump_tree

Inspector(interactor)          # Ctrl+Alt+I: outline + hints under the pointer
print(dump_tree(interactor))   # the widget tree with geometry in px
```

```
Frame 'frame' (29.4, 22.4, 921.2, 515.2)
  Splitter 'splitter' (41.4, 63.4, 897.2, 462.2)
    Frame 'frame' (41.4, 63.4, 218.3, 462.2)
      Label 'label' (41.4, 506.6, 218.3, 19)
      ListView 'listview' (41.4, 63.4, 218.3, 437.2)
        ScrollBar 'listview/bar' (248.7, 64.4, 10, 435.2)
    ...
```

The inspector shows each widget's geometry, `sizeHint`, minimum, size
policy, style state and z-order; when a widget is the wrong size, compare
its hint and policy with its neighbours'.
