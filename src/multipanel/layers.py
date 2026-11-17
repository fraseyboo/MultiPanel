"""Extra renderers the UI draws on: clipped scroll viewports and popups.

VTK 9's 2D mappers ignore clipping planes, so the only exact way to clip 2D
props to a rectangle is a renderer whose viewport is that rectangle. A
:class:`LinkedRenderer` is such a renderer; it shares the theme (and the
:class:`~multipanel.style.Style`) of the renderer it was made for.

Renderers on one layer draw in the order they were added, so a clipped
viewport added after a panel's renderer draws over everything on that
layer, including popups. Popups therefore live on their own full-window
renderer above every other layer (:func:`popup_layer`), the way Qt shows
menus and dialogs in top-level windows.
"""
from __future__ import annotations

import weakref

import vtk

__all__ = ["LinkedRenderer", "popup_layer", "ui_root"]


class LinkedRenderer(vtk.vtkRenderer):
    """A transparent UI renderer that follows another renderer's theme."""

    def link(self, source):
        self._ui_source_ref = weakref.ref(source)
        self._theme_override = None
        self.InteractiveOff()
        self.SetPreserveColorBuffer(True)
        self.SetPreserveDepthBuffer(True)
        return self

    def SetLayer(self, layer):
        # vtkRenderer.SetLayer turns colour preservation off on layer 0,
        # which would clear the viewport over the panel behind it.
        super().SetLayer(layer)
        self.SetPreserveColorBuffer(True)
        self.SetPreserveDepthBuffer(True)

    def uiSource(self):
        reference = getattr(self, "_ui_source_ref", None)
        return None if reference is None else reference()

    @property
    def theme(self):
        if getattr(self, "_theme_override", None) is not None:
            return self._theme_override
        return getattr(self.uiSource(), "theme", None)

    @theme.setter
    def theme(self, value):
        self._theme_override = value


def ui_root(renderer):
    """The application renderer a linked renderer ultimately belongs to."""
    seen = 0
    while isinstance(renderer, LinkedRenderer) and seen < 32:
        source = renderer.uiSource()
        if source is None:
            break
        renderer, seen = source, seen + 1
    return renderer


def _top_layer(window, exclude=None):
    top = 0
    renderers = window.GetRenderers()
    renderers.InitTraversal()
    for _ in range(renderers.GetNumberOfItems()):
        renderer = renderers.GetNextItem()
        if renderer is not None and renderer is not exclude:
            top = max(top, renderer.GetLayer())
    return top


def popup_layer(renderer):
    """The full-window renderer popups draw on (created on first use).

    Kept above every other layer, also when the host adds layers later.
    Returns ``renderer`` itself while it is not in a render window yet.
    """
    from ._widget_support import ui_layer

    root = ui_layer(ui_root(renderer))
    window = root.GetRenderWindow()
    if window is None:
        return root
    layer = getattr(window, "_multipanel_popup_layer", None)
    if layer is None or layer.GetRenderWindow() is not window:
        layer = LinkedRenderer().link(root)
        layer.SetViewport(0.0, 0.0, 1.0, 1.0)
        window.AddRenderer(layer)
        window._multipanel_popup_layer = layer
    top = _top_layer(window, exclude=layer) + 1
    if layer.GetLayer() != top:
        if window.GetNumberOfLayers() <= top:
            window.SetNumberOfLayers(top + 1)
        layer.SetLayer(top)
    return layer
