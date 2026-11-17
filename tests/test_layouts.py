import pytest

from multipanel._widget_support import set_ui_scale, ui_scale, user_scale
from multipanel.core import SizePolicy, WidgetMixin
from multipanel.layouts import (
    FormLayout,
    GridLayout,
    HBoxLayout,
    VBoxLayout,
    distribute,
    parse_alignment,
)
from multipanel.units import frac, px

P = SizePolicy


@pytest.fixture(autouse=True)
def unit_scale():
    previous = user_scale()
    set_ui_scale(1.0)
    yield
    set_ui_scale(previous)


class Viewport:
    """Mutable viewport size shared by a host and its children."""

    def __init__(self, width=800, height=600):
        self.size = (width, height)


class Fake(WidgetMixin):
    def __init__(self, viewport, hint=(50, 20), minimum=(10, 10),
                 policy=None, name="fake"):
        self.viewport = viewport
        self._hint = hint
        self._min = minimum
        self.initWidget(name)
        if policy is not None:
            self.setSizePolicy(*policy)

    def viewportSource(self):
        return self.viewport.size

    def sizeHint(self):
        return self._hint

    def minimumSizeHint(self):
        return self._min


def host(viewport, width, height, x=0, y=0):
    widget = Fake(viewport, name="host")
    widget.setGeometry(px(x), px(y), px(width), px(height))
    return widget


def rect(widget):
    return tuple(round(value, 6) for value in widget.geometry("px"))


# -- distribution --------------------------------------------------------------

def test_distribute_prefers_stretch_then_expanding_then_growable():
    preferred = (0, 50, 1e9, P.Preferred, 0)
    expanding = (0, 50, 1e9, P.Expanding, 0)
    stretched = (0, 50, 1e9, P.Preferred, 2)
    assert distribute([preferred, preferred], 200) == [100, 100]
    assert distribute([preferred, expanding], 200) == [50, 150]
    assert distribute([expanding, stretched], 200) == [50, 150]


def test_distribute_respects_maximum_and_redistributes():
    capped = (0, 50, 60, P.Expanding, 0)
    free = (0, 50, 1e9, P.Expanding, 0)
    assert distribute([capped, free], 200) == [60, 140]


def test_distribute_shrinks_proportionally_to_minimum():
    a = (10, 50, 1e9, P.Preferred, 0)
    b = (30, 50, 1e9, P.Preferred, 0)
    fixed = (40, 40, 40, P.Fixed, 0)
    sizes = distribute([a, b, fixed], 100)
    assert sizes[2] == 40
    assert sizes[0] + sizes[1] == pytest.approx(60)
    assert (50 - sizes[0]) / (50 - sizes[1]) == pytest.approx(40 / 20)


def test_parse_alignment():
    assert parse_alignment(None) == (None, None)
    assert parse_alignment("left|top") == ("start", "end")
    assert parse_alignment("center") == ("center", "center")
    with pytest.raises(ValueError):
        parse_alignment("middle")


# -- box layouts -----------------------------------------------------------------------

def test_hbox_fixed_stretch_fixed_keeps_button_widths(viewport=None):
    for width in (640, 1920):
        vp = Viewport(width, 600)
        frame = host(vp, width, 40)
        row = HBoxLayout(spacing=6)
        left = Fake(vp, (80, 24), policy=(P.Fixed, P.Fixed))
        right = Fake(vp, (80, 24), policy=(P.Fixed, P.Fixed))
        row.addWidget(left)
        row.addStretch()
        row.addWidget(right)
        frame.setLayout(row)

        assert rect(left)[0] == 0 and rect(left)[2] == 80
        assert rect(right)[2] == 80
        assert rect(right)[0] + 80 == pytest.approx(width)
        assert rect(left)[1] == pytest.approx(8)      # centred: (40-24)/2


def test_vbox_runs_top_to_bottom_with_margins_and_spacing():
    vp = Viewport()
    frame = host(vp, 200, 300, x=10, y=20)
    column = VBoxLayout(margins=(8, 8, 8, 8), spacing=4)
    first = Fake(vp, (50, 30), policy=(P.Preferred, P.Fixed))
    second = Fake(vp, (50, 40), policy=(P.Preferred, P.Fixed))
    column.addWidget(first)
    column.addWidget(second)
    frame.setLayout(column)

    top = 20 + 300 - 8
    assert rect(first) == (18, top - 30, 184, 30)
    assert rect(second) == (18, top - 30 - 4 - 40, 184, 40)


def test_stretch_factors_share_spare_space():
    vp = Viewport()
    frame = host(vp, 306, 20)
    row = HBoxLayout(spacing=6)
    a, b = Fake(vp, (0, 20)), Fake(vp, (0, 20))
    row.addWidget(a, stretch=1)
    row.addWidget(b, stretch=2)
    frame.setLayout(row)
    assert rect(a)[2] == pytest.approx(100)
    assert rect(b)[2] == pytest.approx(200)


def test_hidden_widget_closes_gap_unless_size_retained():
    vp = Viewport()
    frame = host(vp, 100, 200)
    column = VBoxLayout(spacing=10)
    items = [Fake(vp, (50, 20), policy=(P.Preferred, P.Fixed)) for _ in range(3)]
    for item in items:
        column.addWidget(item)
    column.addStretch()
    frame.setLayout(column)
    assert rect(items[2])[1] == pytest.approx(200 - 20 - 10 - 20 - 10 - 20)

    items[1].hide()
    assert rect(items[2])[1] == pytest.approx(200 - 20 - 10 - 20)

    policy = items[1].sizePolicy()
    policy.retainSizeWhenHidden = True
    items[1].setSizePolicy(policy)
    assert rect(items[2])[1] == pytest.approx(200 - 20 - 10 - 20 - 10 - 20)


def test_alignment_inside_cell():
    vp = Viewport()
    frame = host(vp, 200, 100)
    column = VBoxLayout()
    item = Fake(vp, (40, 20), policy=(P.Preferred, P.Preferred))
    column.addWidget(item, alignment="right|top")
    frame.setLayout(column)
    assert rect(item) == (160, 80, 40, 20)


def test_nested_layouts_and_layout_hints():
    vp = Viewport()
    frame = host(vp, 300, 200)
    outer = VBoxLayout(spacing=0)
    inner = HBoxLayout(spacing=10)
    a = Fake(vp, (40, 20), policy=(P.Fixed, P.Fixed))
    b = Fake(vp, (60, 30), policy=(P.Fixed, P.Fixed))
    inner.addWidget(a)
    inner.addWidget(b)
    outer.addLayout(inner)
    outer.addStretch()
    frame.setLayout(outer)

    assert inner.sizeHint() == (110, 30)
    assert rect(a)[0] == 0 and rect(b)[0] == 50
    assert a.parentWidget() is frame and b.parentWidget() is frame


def test_minimum_size_mixes_pixels_and_viewport_fractions():
    for height in (600, 400):
        vp = Viewport(800, height)
        frame = host(vp, 100, 50)
        column = VBoxLayout()
        item = Fake(vp, (10, 10), policy=(P.Preferred, P.Preferred))
        item.setMinimumSize(px(160), frac(0.3))
        column.addWidget(item)
        frame.setLayout(column)
        assert item.minimumSize() == (160, pytest.approx(0.3 * height))
        assert column.minimumSize() == (160, pytest.approx(0.3 * height))


def test_fixed_size_overrides_policy():
    vp = Viewport()
    frame = host(vp, 400, 100)
    row = HBoxLayout()
    item = Fake(vp, (10, 10), policy=(P.Expanding, P.Expanding))
    item.setFixedSize(120, "30px")
    row.addWidget(item)
    frame.setLayout(row)
    assert rect(item)[2:] == (120, 30)


def test_ui_scale_changes_display_but_not_logical_size():
    vp = Viewport()
    frame = host(vp, 200, 40)
    row = HBoxLayout()
    item = Fake(vp, (50, 20), policy=(P.Fixed, P.Fixed))
    row.addWidget(item)
    frame.setLayout(row)
    display_1 = item.geometry("display")[2:]

    set_ui_scale(1.5)
    frame.setGeometry(px(0), px(0), px(200), px(40))
    row.activate()
    assert item.geometry("px")[2:] == pytest.approx((50, 20))
    assert item.geometry("display")[2:] == pytest.approx(
        (display_1[0] * 1.5, display_1[1] * 1.5))


def test_layout_frac_margins_follow_viewport():
    vp = Viewport(800, 600)
    frame = host(vp, 400, 100)
    row = HBoxLayout(margins=(frac(0.01), 0, 0, 0))
    item = Fake(vp, (10, 10))
    row.addWidget(item)
    frame.setLayout(row)
    assert rect(item)[0] == pytest.approx(8)
    vp.size = (1600, 600)
    frame.setGeometry(px(0), px(0), px(400), px(100))
    row.activate()
    assert rect(item)[0] == pytest.approx(16)


# -- grid and form ----------------------------------------------------------------

def test_grid_rows_top_down_spans_and_column_stretch():
    vp = Viewport()
    frame = host(vp, 310, 70)
    grid = GridLayout(spacing=10)
    a = Fake(vp, (50, 30), policy=(P.Preferred, P.Fixed))
    b = Fake(vp, (50, 30), policy=(P.Preferred, P.Fixed))
    wide = Fake(vp, (50, 30), policy=(P.Preferred, P.Fixed))
    grid.addWidget(a, 0, 0)
    grid.addWidget(b, 0, 1)
    grid.addWidget(wide, 1, 0, 1, 2)
    grid.setColumnStretch(1, 2)
    frame.setLayout(grid)

    assert grid.rowCount() == 2 and grid.columnCount() == 2
    assert rect(a)[1] == pytest.approx(40)        # row 0 at the top
    assert rect(wide)[1] == pytest.approx(0)
    assert rect(wide)[2] == pytest.approx(310)
    # Spare 200 px goes to the stretched column only.
    assert rect(a)[2] == pytest.approx(50)
    assert rect(b)[2] == pytest.approx(250)


def test_form_layout_aligns_field_column():
    vp = Viewport()
    frame = host(vp, 400, 100)
    form = FormLayout(spacing=8)
    labels = [Fake(vp, (w, 20), policy=(P.Preferred, P.Fixed)) for w in (40, 120)]
    fields = [Fake(vp, (100, 24), policy=(P.Expanding, P.Fixed)) for _ in labels]
    for label, field in zip(labels, fields):
        form.addRow(label, field)
    frame.setLayout(form)

    assert rect(fields[0])[0] == rect(fields[1])[0] == pytest.approx(128)
    assert rect(fields[0])[2] == pytest.approx(400 - 128)
    assert rect(labels[0])[0] == 0 and rect(labels[0])[2] == 40   # left aligned
    assert form.labelForRow(1) is labels[1]


def test_string_labels_are_created_when_installed():
    vp = Viewport()
    frame = host(vp, 300, 60)
    created = []

    def factory(text, owner):
        widget = Fake(vp, (len(text) * 10, 20), policy=(P.Preferred, P.Fixed),
                      name=text)
        created.append((text, owner))
        return widget

    form = FormLayout(label_factory=factory)
    field = Fake(vp, (100, 24), policy=(P.Expanding, P.Fixed))
    form.addRow("Density", field)
    assert created == []
    frame.setLayout(form)
    assert created == [("Density", frame)]
    assert form.labelForRow(0).objectName() == "Density"
    assert rect(field)[0] == pytest.approx(70 + 6)


def test_moving_a_widget_between_layouts():
    vp = Viewport()
    first, second = VBoxLayout(), VBoxLayout()
    item = Fake(vp)
    first.addWidget(item)
    second.addWidget(item)
    assert first.count() == 0 and second.count() == 1


def test_grid_column_stretch_grows_fixed_items_cells():
    vp = Viewport()
    frame = host(vp, 300, 40)
    grid = GridLayout(spacing=0)
    buttons = [Fake(vp, (30, 30), policy=(P.Fixed, P.Fixed)) for _ in range(3)]
    for column, button in enumerate(buttons):
        grid.addWidget(button, 0, column, alignment="center")
        grid.setColumnStretch(column, 1)
    frame.setLayout(grid)
    # Each column is 100 px wide; the fixed buttons sit centred in them.
    assert [rect(b)[0] for b in buttons] == pytest.approx([35, 135, 235])
    assert all(rect(b)[2] == 30 for b in buttons)
