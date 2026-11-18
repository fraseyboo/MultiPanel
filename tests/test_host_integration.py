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


# -- vtk_utils.add_volume / load_gltf ------------------------------------------
def test_add_volume_builds_a_named_volume():
    pytest.importorskip("sklearn")
    from multipanel import vtk_utils

    values = np.random.default_rng(0).random((6, 5, 4))
    volume = vtk_utils.add_volume(values, spacing=(1, 2, 3), origin=(1, 1, 1),
                                  c_range=(0, 0.5), name='widgets/test_volume', enabled=False)
    assert isinstance(volume, vtk.vtkVolume)
    assert volume.GetObjectName() == 'widgets/test_volume'
    assert not volume.GetVisibility()
    image = volume.GetMapper().GetInput()
    assert image.GetDimensions() == (6, 5, 4)
    assert image.GetSpacing() == (1, 2, 3)
    colors = volume.GetProperty().GetRGBTransferFunction()
    assert colors.GetRange() == pytest.approx((0, 0.5))


def test_add_volume_clips_a_copy_to_the_range():
    pytest.importorskip("sklearn")
    from multipanel import vtk_utils
    from vtkmodules.util.numpy_support import vtk_to_numpy

    values = np.linspace(-1, 2, 27).reshape(3, 3, 3)
    original = values.copy()
    volume = vtk_utils.add_volume(values, c_range=(0, 1), clip_to_range=True)
    scalars = vtk_to_numpy(volume.GetMapper().GetInput().GetPointData().GetScalars())
    assert scalars.min() == 0 and scalars.max() == 1
    np.testing.assert_array_equal(values, original)      # the caller's array is untouched


def test_add_volume_rejects_unknown_modes():
    pytest.importorskip("sklearn")
    from multipanel import vtk_utils

    with pytest.raises(ValueError):
        vtk_utils.add_volume(np.ones((2, 2, 2)), render_mode='raytraced')
    with pytest.raises(ValueError):
        vtk_utils.add_volume(np.ones((2, 2, 2)), blend_mode='screen')


@pytest.mark.parametrize("widget", ["LassoWidget", "BoxWidget"])
def test_selection_widgets_build_reconstructed_volumes(widget):
    # Box/Lasso reconstructions called vtk_utils.add_volume, which was missing.
    pytest.importorskip("sklearn")
    from multipanel import specialists

    create = getattr(specialists, widget).create_new_volume
    spacings, volume = create(None, (0, 1, 0, 2, 0, 3), np.ones((4, 4, 4)), name='widgets/region')
    assert isinstance(volume, vtk.vtkVolume) and volume.GetObjectName() == 'widgets/region'
    assert spacings == pytest.approx(np.array([1, 2, 3]) / 4, rel=1e-4)


def test_load_gltf_reader_returns_one_actor(tmp_path):
    pytest.importorskip("sklearn")
    from multipanel import vtk_utils

    source = vtk.vtkCubeSource()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(source.GetOutputPort())
    cube = vtk.vtkActor()
    cube.SetMapper(mapper)
    ren = vtk.vtkRenderer()
    ren.AddActor(cube)
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.AddRenderer(ren)
    path = str(tmp_path / "cube.gltf")
    exporter = vtk.vtkGLTFExporter()
    exporter.SetRenderWindow(window)
    exporter.SetFileName(path)
    exporter.InlineDataOn()
    exporter.Write()

    actor = vtk_utils.load_gltf(path, name='marker', import_method='vtkGLTFReader')
    assert isinstance(actor, vtk.vtkActor) and actor.GetObjectName() == 'marker'
    actor.GetMapper().Update()
    assert actor.GetMapper().GetInput().GetNumberOfPoints() > 0
    with pytest.raises(ValueError):
        vtk_utils.load_gltf(path, import_method='vtkGLTFImporter')    # needs a render window


# -- collapsed layout panels keep their header-only bounds --------------------
def _collapsed_layout_panel(ren, iren, collapsed=True):
    from multipanel.containers import WidgetPanel
    from multipanel.layouts import VBoxLayout
    from multipanel.standard import Label

    panel = WidgetPanel(ren, iren, {}, panel_title='Collapsed', keep_aspect_ratio=False,
                        panel_position=(0.7, 0.9), panel_width=0.2, collapsed=collapsed)
    column = VBoxLayout()
    for index in range(6):
        column.addWidget(Label(ren, iren, f'row {index}'))
    panel.setLayout(column)
    return panel


def test_collapsed_layout_panel_keeps_header_bounds_on_relayout(scene):
    # update_layout (run on window resizes, and for panels in inactive dock
    # tabs) grew a collapsed layout panel to its full layout height, drawing
    # its title and collapse button over the next docked panel.
    ren, window, iren = scene
    expanded = _collapsed_layout_panel(ren, iren, collapsed=False)
    collapsed = _collapsed_layout_panel(ren, iren, collapsed=True)
    window.Render()
    for panel in (expanded, collapsed):
        panel.update_layout(render=False)
    height = lambda panel: panel.GetBounds()[3] - panel.GetBounds()[2]
    assert height(collapsed) < 0.5 * height(expanded)
    title = collapsed.added_widgets['panel_title'].GetBounds()
    top = collapsed.GetBounds()[3]
    assert top - title[3] < height(collapsed)          # title stays in the header band


def test_collapsed_layout_panel_survives_a_resize_in_a_dock(scene):
    from multipanel.containers import DockPane, WidgetPanel

    ren, window, iren = scene
    dock = DockPane(ren, iren, side='right', width=0.2)
    panel = _collapsed_layout_panel(ren, iren)
    below = WidgetPanel(ren, iren, {}, panel_title='Below', keep_aspect_ratio=False)
    dock.add_panel(panel)
    dock.add_panel(below)
    window.Render()
    window.SetSize(1000, 700)
    iren.InvokeEvent('ConfigureEvent')
    window.Render()
    assert below.GetBounds()[3] <= panel.GetBounds()[2] + 1e-6


# -- interactor styles survive garbage collection -------------------------------
def _style_interactor(style_class, style_args):
    ren = vtk.vtkRenderer()
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.AddRenderer(ren)
    iren = vtk.vtkRenderWindowInteractor()
    iren.SetRenderWindow(window)
    iren.Initialize()
    # As create_renderer does: no Python reference to the style is kept.
    iren.SetInteractorStyle(style_class(*style_args(iren, ren, window)))
    return iren


def _assert_style_survives_gc(iren, capfd):
    gc.collect()
    gc.collect()
    style = iren.GetInteractorStyle()
    assert hasattr(style, "verbose")      # VTK 9.7 wiped the Python attributes
    capfd.readouterr()
    iren.SetEventPosition(20, 20)
    iren.InvokeEvent("MouseMoveEvent")
    iren.InvokeEvent("LeftButtonPressEvent")
    iren.InvokeEvent("LeftButtonReleaseEvent")
    assert "Traceback" not in capfd.readouterr().err   # handlers still run
    return style


def test_interactor_utils_style_survives_gc(capfd):
    from multipanel import interactor_utils

    iren = _style_interactor(interactor_utils.MyInteractorStyle,
                             lambda iren, ren, window: (iren, ren.GetActiveCamera(), window, ren))
    style = _assert_style_survives_gc(iren, capfd)
    assert style in interactor_utils._LIVE_INTERACTOR_STYLES
    style.release()
    assert style not in interactor_utils._LIVE_INTERACTOR_STYLES


def test_vtk_utils_style_survives_gc(capfd):
    pytest.importorskip("sklearn")
    from multipanel import vtk_utils

    iren = _style_interactor(vtk_utils.MyInteractorStyle,
                             lambda iren, ren, window: (iren, ren.GetActiveCamera(), ren))
    _assert_style_survives_gc(iren, capfd)


# -- SVG icon conversion: holes by nesting, not winding -------------------------
def _square(x0, y0, size, clockwise=False):
    corners = [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)]
    if clockwise:
        corners = corners[::-1]
    return "M " + " L ".join(f"{x},{y}" for x, y in corners) + " Z"


def _filled_area(tmp_path, *subpaths, extra_path=None, fill_rule=None):
    pytest.importorskip("triangle")
    pytest.importorskip("svgpathtools")
    from multipanel.icon_converter import convert_svg_to_triangles

    rule = f";fill-rule:{fill_rule}" if fill_rule else ""
    paths = f'<path style="fill:#c160ff{rule}" d="{" ".join(subpaths)}"/>'
    if extra_path:
        paths += f'<path style="fill:#000000" d="{extra_path}"/>'
    svg = tmp_path / "icon.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                   f'{paths}</svg>')
    shapes = convert_svg_to_triangles(str(svg), plot=False, normalize=False)
    purple = [s for s in shapes if tuple(np.round(s[2][:3], 2)) == (0.76, 0.38, 1.0)]
    total = 0.0
    for verts, tris, _color in purple:
        u = verts[tris[:, 1]] - verts[tris[:, 0]]
        w = verts[tris[:, 2]] - verts[tris[:, 0]]
        total += 0.5 * np.abs(u[:, 0] * w[:, 1] - u[:, 1] * w[:, 0]).sum()
    return total


@pytest.mark.parametrize("clockwise", [False, True])
def test_svg_separate_shapes_are_filled_whatever_their_winding(tmp_path, clockwise):
    # Two separate shapes in one path, both drawn clockwise, were both taken
    # for holes and the path was dropped (COMPTON's compton.svg lost its
    # purple regions).
    area = _filled_area(tmp_path, _square(5, 5, 30, clockwise), _square(50, 50, 40, clockwise),
                        extra_path=_square(0, 0, 100))
    assert area == pytest.approx(30 * 30 + 40 * 40, rel=1e-3)


RING, HOLE = 60 * 60, 20 * 20


@pytest.mark.parametrize("fill_rule", [None, "nonzero", "evenodd"])
@pytest.mark.parametrize("outer_cw", [False, True])
def test_svg_opposite_winding_inner_ring_is_a_hole(tmp_path, fill_rule, outer_cw):
    area = _filled_area(tmp_path, _square(0, 0, 60, outer_cw), _square(20, 20, 20, not outer_cw),
                        fill_rule=fill_rule)
    assert area == pytest.approx(RING - HOLE, rel=1e-3)


@pytest.mark.parametrize("fill_rule,expected", [(None, RING), ("nonzero", RING),
                                                ("evenodd", RING - HOLE)])
@pytest.mark.parametrize("clockwise", [False, True])
def test_svg_same_winding_inner_ring_follows_the_fill_rule(tmp_path, fill_rule, expected, clockwise):
    # SVG's default (nonzero) fills an inner boundary drawn the same way as
    # its outer one; evenodd cuts it out.
    area = _filled_area(tmp_path, _square(0, 0, 60, clockwise), _square(20, 20, 20, clockwise),
                        fill_rule=fill_rule)
    assert area == pytest.approx(expected, rel=1e-3)


def test_svg_island_inside_a_hole_is_filled(tmp_path):
    area = _filled_area(tmp_path, _square(0, 0, 90), _square(20, 20, 50, clockwise=True),
                        _square(35, 35, 20))
    assert area == pytest.approx(90 * 90 - 50 * 50 + 20 * 20, rel=1e-3)


def test_svg_island_inside_an_evenodd_hole_is_filled(tmp_path):
    area = _filled_area(tmp_path, _square(0, 0, 90), _square(20, 20, 50), _square(35, 35, 20),
                        fill_rule="evenodd")
    assert area == pytest.approx(90 * 90 - 50 * 50 + 20 * 20, rel=1e-3)
