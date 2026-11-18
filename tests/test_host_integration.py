"""Regressions found while porting a host application (COMPTON) to MultiPanel.

Each test covers a path that raised or misbehaved in 0.1.0.
"""
import gc

import numpy as np
import pytest
import vtk


@pytest.fixture
def scene():
    ren = vtk.vtkRenderer()
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(800, 600)
    window.AddRenderer(ren)
    iren = vtk.vtkRenderWindowInteractor()
    iren.SetRenderWindow(window)
    iren.Initialize()
    return ren, window, iren


def _volume(size=16):
    image = vtk.vtkImageData()
    image.SetDimensions(size, size, size)
    image.SetSpacing(0.1, 0.1, 0.1)
    image.AllocateScalars(vtk.VTK_FLOAT, 1)
    values = np.indices((size, size, size)).sum(axis=0).astype(np.float32)
    from vtkmodules.util.numpy_support import numpy_to_vtk
    image.GetPointData().SetScalars(numpy_to_vtk(values.ravel(order="F"), deep=True))
    mapper = vtk.vtkSmartVolumeMapper()
    mapper.SetInputData(image)
    volume = vtk.vtkVolume()
    volume.SetMapper(mapper)
    return volume


# -- create_text_widget ------------------------------------------------------------
def test_create_text_widget_registers_a_text_widget(scene):
    from multipanel.specialists import create_text_widget

    ren, _window, iren = scene
    widget = create_text_widget(ren, iren, text="status", object_name="probe_text",
                                enabled=False)
    assert isinstance(widget, vtk.vtkTextWidget)
    assert ren.widgets["probe_text"] is widget
    assert widget.GetTextActor().GetInput() == "status"
    assert not widget.GetEnabled()


def test_sphere_probe_widget_builds_its_status_text(scene):
    # SphereProbeWidget's constructor called the (commented-out)
    # create_text_widget and raised NameError.
    from multipanel.specialists import SphereProbeWidget

    ren, _window, iren = scene
    volume = _volume()
    ren.AddVolume(volume)
    probe = SphereProbeWidget(volume, ren, iren, sphere_radius=0.3, resolution=20,
                              enabled=False, sphere_center=(0.8, 0.8, 0.8))
    assert isinstance(probe.text_widget, vtk.vtkTextWidget)
