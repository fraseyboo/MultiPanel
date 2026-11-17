import numpy as np
import pytest
import vtk

from multipanel.widgets import (
    ButtonWidget,
    DockPane,
    MeshProbeWidget,
    SliderWidget,
    SplineWidget,
    TextWidget,
    ValueChangerWidget,
    VectorButtonWidget,
    VolumeSlicer,
)


@pytest.fixture
def vtk_ui():
    renderer = vtk.vtkRenderer()
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(True)
    window.SetSize(640, 480)
    window.AddRenderer(renderer)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    return renderer, window, interactor


def test_slider_qt_style_range_and_value_api(vtk_ui):
    renderer, _window, interactor = vtk_ui
    slider = SliderWidget(
        renderer, interactor, min_value=0, max_value=10,
        initial_value=5, callback=lambda *_: None)
    values = []
    slider.valueChanged.connect(values.append)

    slider.setRange(-2, 2)
    slider.setValue(1.5)
    slider.setValue(1.5)

    assert slider.minimum() == -2
    assert slider.maximum() == 2
    assert slider.value() == 1.5
    # The range clamped 5 to 2 (signalled, as QAbstractSlider does).
    assert values == [2.0, 1.5]


def test_slider_orientation_tracking_and_state_round_trip(vtk_ui):
    renderer, _window, interactor = vtk_ui
    callbacks = []
    slider = SliderWidget(
        renderer, interactor, min_value=0, max_value=10,
        initial_value=5, callback=lambda *_: callbacks.append("committed"),
        position=(0.2, 0.8), bar_length=0.4,
        use_relative_position=True, orientation="vertical")
    moved = []
    changed = []
    slider.sliderMoved.connect(moved.append)
    slider.valueChanged.connect(changed.append)
    first = slider.rep.GetPoint1Coordinate().GetValue()
    second = slider.rep.GetPoint2Coordinate().GetValue()
    assert first[:2] == pytest.approx((0.2, 0.8))
    assert second[:2] == pytest.approx((0.2, 0.4))

    slider.setTracking(False)
    slider._on_slider_pressed()
    slider.rep.SetValue(7)
    slider._on_slider_moved()
    assert moved == [7.0]
    assert changed == []
    slider._on_slider_released()
    assert changed == [7.0]
    assert callbacks == ["committed"]

    state = slider.saveState()
    slider.setOrientation("horizontal")
    slider.setValue(2)
    slider.setTracking(True)
    slider.restoreState(state)
    assert slider.orientation() == "vertical"
    assert slider.value() == 7
    assert not slider.isTracking()


def test_vector_button_checked_and_click_api(vtk_ui):
    renderer, _window, interactor = vtk_ui
    triangle = np.asarray(((0.1, 0.1), (0.9, 0.5), (0.1, 0.9)))
    button = VectorButtonWidget(
        renderer, interactor, input_data=[triangle, triangle],
        color=(0.5, 0.5, 0.5), interactive=False)
    clicks = []
    events = []
    button.clicked.connect(clicks.append)
    button.pressed.connect(lambda: events.append('pressed'))
    button.released.connect(lambda: events.append('released'))

    button.setChecked(True)
    button.click()

    assert not button.isChecked()
    assert clicks == [False]
    assert events == ['pressed', 'released']


def test_native_button_constructs_and_has_keyboard_focus(vtk_ui):
    renderer, _window, interactor = vtk_ui
    button = ButtonWidget(
        renderer, interactor, icon_name="question-sign", callback=None,
        widget_bounds=(0.1, 0.2, 0.1, 0.2))

    button.setFocus(reason="test")

    assert button.hasFocus()
    assert button.focusPolicy() == "StrongFocus"


def test_text_widget_value_validation_and_signals(vtk_ui):
    renderer, _window, interactor = vtk_ui
    widget = TextWidget(renderer, interactor, text="one", editable=True)
    changed = []
    widget.textChanged.connect(changed.append)
    widget.setValidator(lambda text: text.isalpha())

    widget.setText("two")
    widget.start_editing()
    widget.text = "123"
    widget.finish_editing(commit=True)

    assert widget.textValue() == "two"
    assert changed[0] == "two"


def test_text_widgets_have_exclusive_editing_focus(vtk_ui):
    renderer, _window, interactor = vtk_ui
    first = TextWidget(renderer, interactor, text="first", editable=True)
    second = TextWidget(renderer, interactor, text="second", editable=True)

    assert first.start_editing()
    first.text = "changed"
    assert second.start_editing()

    assert not first.editing
    assert first.textValue() == "changed"
    assert second.editing
    assert second.hasFocus()
    assert second.focusManager().cancelFocused()
    assert not second.editing
    assert second.textValue() == "second"


def test_read_only_clickable_text_remains_focusable(vtk_ui):
    renderer, _window, interactor = vtk_ui
    widget = TextWidget(
        renderer, interactor, text="label", editable=True, clickable=True)

    widget.setReadOnly(True)

    assert widget.isReadOnly()
    assert widget.focusPolicy() == "StrongFocus"
    assert not widget.start_editing()


def test_stable_module_facades_export_existing_widget_classes():
    from multipanel.containers import DockPane as PublicDock
    from multipanel.containers import ViewportDisplayPanel as PublicViewport
    from multipanel.controls import SliderWidget as PublicSlider
    from multipanel.input import ClickManager
    from multipanel.specialists import VolumeSlicer as PublicSlicer
    from multipanel.widgets import ClickManager as LegacyClickManager
    from multipanel.widgets import ViewportDisplayPanel as LegacyViewport

    assert PublicSlider is SliderWidget
    assert PublicSlicer is VolumeSlicer
    assert PublicDock is DockPane
    assert PublicViewport is LegacyViewport
    assert ClickManager is LegacyClickManager
    assert PublicSlider.__module__ == "multipanel.controls"
    assert PublicDock.__module__ == "multipanel.containers"
    assert PublicViewport.__module__ == "multipanel.containers"
    assert ClickManager.__module__ == "multipanel.input"
    assert PublicSlicer.__module__ == "multipanel.specialists"


def test_legacy_widget_namespace_preserves_public_class_identity():
    from multipanel import containers, controls, input, specialists, widgets

    for module in (input, controls, containers, specialists):
        for name in module.__all__:
            assert getattr(widgets, name) is getattr(module, name)


def test_legacy_configuration_setters_update_implementation_modules():
    from multipanel import containers, controls, specialists, widgets

    resolver = object()
    try:
        widgets.set_ui_scale(1.25)
        widgets.set_material_color_resolver(resolver)

        assert controls.ui_scale() == 1.25
        assert containers.ui_scale() == 1.25
        assert specialists.material_color_resolver() is resolver
    finally:
        widgets.set_ui_scale(1.0)
        widgets.set_material_color_resolver(None)


def test_dock_tab_rename_preserves_panel_mapping():
    button = type("TabButton", (), {"callback": None})()
    panel = object()
    dock = DockPane.__new__(DockPane)
    dock.tabs = [{"name": "scene", "button": button}]
    dock.panels = [panel]
    dock._panel_tab = {panel: "scene"}
    dock.active_tab = "scene"

    dock.setTabText(0, "objects")

    assert dock.active_tab == "objects"
    assert dock._panel_tab[panel] == "objects"
    assert dock.widget(0) is panel


def test_value_changer_spinbox_api(vtk_ui):
    renderer, _window, interactor = vtk_ui
    widget = ValueChangerWidget(
        renderer, interactor, initial_value=1, min_value=0,
        max_value=10, callback=lambda **_: None)
    values = []
    widget.valueChanged.connect(values.append)

    widget.setSingleStep(0.5)
    widget.setValue(1.5)
    widget.setRange(0, 1)

    assert widget.singleStep() == 0.5
    assert widget.value() == 1
    assert values == [1.5, 1.0]


def test_spline_point_collection_api(vtk_ui):
    renderer, _window, interactor = vtk_ui
    widget = SplineWidget(
        renderer, interactor,
        points=np.asarray(((0, 0, 0), (1, 0, 0), (1, 1, 0))),
        project_to_plane=False, enabled=False)
    changes = []
    widget.pointsChanged.connect(changes.append)

    widget.addPoint((0, 1, 0))
    removed = widget.removePoint(1)
    widget.setClosed(True)

    assert widget.pointCount() == 3
    assert removed == (1.0, 0.0, 0.0)
    assert widget.isClosed()
    assert len(changes) == 2


def _image_volume(dimensions=(5, 6, 7)):
    image = vtk.vtkImageData()
    image.SetDimensions(*dimensions)
    image.AllocateScalars(vtk.VTK_FLOAT, 1)
    image.GetPointData().GetScalars().Fill(1)
    mapper = vtk.vtkSmartVolumeMapper()
    mapper.SetInputData(image)
    volume = vtk.vtkVolume()
    volume.SetMapper(mapper)
    return volume


def test_volume_slicer_slice_and_display_api(vtk_ui):
    renderer, _window, interactor = vtk_ui
    widget = VolumeSlicer(
        _image_volume(), renderer, interactor,
        axes_enabled=(True, False, False), enabled=False,
        show_intersection=False)
    changes = []
    widget.sliceChanged.connect(lambda axis, index: changes.append((axis, index)))

    widget.setSliceIndex('x', 1)
    widget.setOpacity(0.4)
    widget.setInterpolation(True)

    assert widget.sliceIndex(0) == 1
    assert widget.opacityValue() == 0.4
    assert widget.hasInterpolation()
    assert changes == [(0, 1)]
    widget.close()


def test_mesh_probe_dataset_result_and_reprobe_api(vtk_ui):
    renderer, _window, _interactor = vtk_ui
    volume = _image_volume((3, 3, 3))
    source = vtk.vtkSphereSource()
    source.SetThetaResolution(4)
    source.SetPhiResolution(4)
    source.Update()
    actor = vtk.vtkActor()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(source.GetOutput())
    actor.SetMapper(mapper)

    widget = MeshProbeWidget(volume, actor, renderer, enabled=False)
    finished = []
    widget.probeFinished.connect(finished.append)
    result = widget.probe()

    assert widget.dataset() is volume
    assert result is actor
    assert widget.result().ndim == 1
    assert finished == [actor]
