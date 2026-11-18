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


# -- VectorButtonWidget.GetCurrentRenderer ------------------------------------
def test_vector_button_reports_its_renderer(scene):
    # Panel button callbacks (spectrum, plot, plot slices, plot sphere
    # probe, export) call widget.GetCurrentRenderer(), as vtkButtonWidget has.
    from multipanel._widget_support import disc_icon_polydata
    from multipanel.controls import VectorButtonWidget

    ren, _window, iren = scene
    button = VectorButtonWidget(ren, iren, input_data=disc_icon_polydata(),
                                callback=lambda *_: None)
    assert button.GetCurrentRenderer() is ren


def test_export_button_callback_reaches_the_window(scene, monkeypatch):
    from multipanel import specialists
    from multipanel._widget_support import disc_icon_polydata
    from multipanel.controls import VectorButtonWidget

    ren, window, iren = scene
    exported = []
    monkeypatch.setattr(specialists, "write_gltf", exported.append)
    button = VectorButtonWidget(ren, iren, input_data=disc_icon_polydata(),
                                callback=specialists.export_button_callback)
    specialists.export_button_callback(button, None)
    assert exported == [window]


# -- plot callbacks: helpers in specialists itself ----------------------------
def _button(ren, iren, callback=None):
    from multipanel._widget_support import disc_icon_polydata
    from multipanel.controls import VectorButtonWidget
    return VectorButtonWidget(ren, iren, input_data=disc_icon_polydata(),
                              callback=callback or (lambda *_: None))


def test_plot_sphere_probe_callback_finds_the_probe_mesh(scene, monkeypatch):
    # It called widget_utils.return_actor, a module MultiPanel lacks.
    import types
    from multipanel import specialists
    from vtkmodules.util.numpy_support import numpy_to_vtk

    ren, _window, iren = scene
    sphere = vtk.vtkSphereSource()
    sphere.Update()
    mesh = sphere.GetOutput()
    mesh.GetPointData().SetScalars(numpy_to_vtk(np.arange(mesh.GetNumberOfPoints(), dtype=float)))
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(mesh)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.SetObjectName('widgets/sphere_widget_mesh')
    ren.AddActor(actor)
    plotted = []
    monkeypatch.setattr(specialists, "_mpl_utils", lambda: types.SimpleNamespace(
        plot_spherical_slice=lambda coords, values: plotted.append((coords.shape, values.shape))))

    specialists.plot_sphere_probe_callback(_button(ren, iren), None)
    assert plotted == [((mesh.GetNumberOfPoints(), 3), (mesh.GetNumberOfPoints(),))]


def test_plot_slices_callback_without_slicers_is_a_no_op(scene):
    # It called widget_utils.return_widget and raised NameError at once.
    from multipanel import specialists

    ren, _window, iren = scene
    specialists.plot_slices_callback(_button(ren, iren), None, verbose=False)
