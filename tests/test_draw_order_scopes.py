"""Draw-order checks compare z layers only within one container's scope."""
import warnings

import pytest

from multipanel._widget_support import register_ui_drawable, ui_stacking_scope


class _Renderer:
    pass


class _Drawable:
    pass


class _Panel:
    pass


class _SortingPanel:
    ui_sorts_draw_order = True


def _register(renderer, z, name, scope_owner):
    drawable = _Drawable()
    with ui_stacking_scope(scope_owner):
        register_ui_drawable(renderer, drawable, z, name)
    return drawable


def test_later_panel_background_does_not_warn_about_other_panel():
    renderer = _Renderer()
    _register(renderer, 45, "first_scrollbar", _Panel())
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _register(renderer, 10, "second_background", _Panel())


def test_late_lower_layer_in_same_panel_warns():
    renderer, panel = _Renderer(), _Panel()
    _register(renderer, 45, "scrollbar", panel)
    with pytest.warns(RuntimeWarning, match="background"):
        _register(renderer, 10, "background", panel)


def test_self_sorting_panel_does_not_warn():
    renderer, panel = _Renderer(), _SortingPanel()
    _register(renderer, 35, "header", panel)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _register(renderer, 20, "row", panel)
