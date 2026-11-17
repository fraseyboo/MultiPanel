import types

import numpy as np
import pytest

from multipanel import radiation

MOVED_FROM_SPECIALISTS = (
    "calculate_compton_angle",
    "create_radiation_marker",
    "refresh_compton_widgets",
    "refresh_reconstruction_callback",
    "set_auto_reconstruction_callback",
    "set_reconstruction_selection_callback",
    "spectrum_button_callback",
)


def test_legacy_import_paths_return_the_same_objects():
    from multipanel import specialists, widgets

    for name in MOVED_FROM_SPECIALISTS:
        assert getattr(specialists, name) is getattr(radiation, name)
        assert getattr(widgets, name) is getattr(radiation, name)


def test_vtk_utils_reexports_geant4_tracks():
    # vtk_utils needs the "scientific" extra (scikit-learn, matplotlib).
    pytest.importorskip("sklearn")
    from multipanel import vtk_utils

    assert vtk_utils.add_GEANT4_tracks is radiation.add_GEANT4_tracks


def test_compton_angle_matches_kinematics():
    # Backscatter of a 511 keV photon depositing 2/3 of its energy:
    # cos(theta) = 1 - 511 * (1/E2 - 1/Etot) with E2 the scattered energy.
    e_total, e_scattered = 511.0, 511.0 / 3.0
    expected = np.arccos(1 - 511.0 * (1 / e_scattered - 1 / e_total))
    assert radiation.calculate_compton_angle(e_scattered, e_total) == \
        pytest.approx(expected)
    assert radiation.calculate_compton_angle(e_total, e_total) == \
        pytest.approx(0.0)


def test_missing_reconstruction_backend_raises_actionable_error():
    radiation.set_reconstruction_backend(None)
    with pytest.raises(RuntimeError, match="set_reconstruction_backend"):
        radiation.reconstruction_backend()


def test_registered_backend_is_used_by_specialists():
    from multipanel import specialists

    backend = types.SimpleNamespace(name="host")
    radiation.set_reconstruction_backend(backend)
    try:
        assert specialists.reconstruction_backend() is backend
    finally:
        radiation.set_reconstruction_backend(None)


class _StateWidget:
    def __init__(self, state):
        self.renderer = types.SimpleNamespace(
            invert_selection=False, Modified=lambda: None)
        self._state = state

    def GetRepresentation(self):
        return types.SimpleNamespace(GetState=lambda: self._state)


def test_reconstruction_toggle_callbacks_set_renderer_flags():
    widget = _StateWidget(1)
    radiation.set_auto_reconstruction_callback(widget, None)
    assert widget.renderer.auto_reconstruct is True
    radiation.set_reconstruction_selection_callback(widget, None)
    assert widget.renderer.invert_selection is True

    widget._state = 2
    radiation.set_reconstruction_selection_callback(widget, None)
    assert widget.renderer.invert_selection is None
