"""Small compatibility shims for VTK APIs used across MultiPanel."""

from __future__ import annotations

import vtk


def vtk_version_tuple():
    """Return the runtime VTK version as a comparable integer tuple."""
    version = vtk.vtkVersion()
    return (
        int(version.GetVTKMajorVersion()),
        int(version.GetVTKMinorVersion()),
        int(version.GetVTKBuildVersion()),
    )


VTK_VERSION = vtk_version_tuple()
ACTOR_2D_DEPRECATED_SINCE = (9, 5, 0)


def _use_view_prop_api(renderer):
    """Select the supported 2-D prop API for the runtime renderer."""
    return (VTK_VERSION >= ACTOR_2D_DEPRECATED_SINCE or
            not hasattr(renderer, "AddActor2D"))


def add_actor_2d(renderer, prop):
    """Add a 2-D prop without calling VTK's deprecated API on VTK >= 9.5."""
    if _use_view_prop_api(renderer):
        renderer.AddViewProp(prop)
    else:
        renderer.AddActor2D(prop)


def remove_actor_2d(renderer, prop):
    """Remove a 2-D prop without calling VTK's deprecated API on VTK >= 9.5."""
    if (VTK_VERSION >= ACTOR_2D_DEPRECATED_SINCE or
            not hasattr(renderer, "RemoveActor2D")):
        renderer.RemoveViewProp(prop)
    else:
        renderer.RemoveActor2D(prop)
