"""Gallery of the standard controls (labels, buttons, toggles, lists, menus).

Run interactively::

    python examples/gallery.py [--dark]

or write one off-screen frame (with a menu open) to an image::

    python examples/gallery.py --screenshot gallery.png [--dark] [--focus]
"""
import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import vtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multipanel.actions import Action  # noqa: E402
from multipanel.containers import Frame  # noqa: E402
from multipanel.layouts import FormLayout, HBoxLayout, VBoxLayout  # noqa: E402
from multipanel.router import EventRouter  # noqa: E402
from multipanel.standard import (  # noqa: E402
    ButtonGroup,
    CheckBox,
    ComboBox,
    Label,
    Menu,
    MenuBar,
    MessageBox,
    ProgressBar,
    PushButton,
    RadioButton,
    StatusBar,
)
from multipanel.ui_theme import DARK, LIGHT, vtk_tokens  # noqa: E402
from multipanel.units import frac, px  # noqa: E402


def build(renderer, interactor):
    tokens = renderer.theme.tokens
    frame = Frame(renderer, interactor, background=True,
                  panel_color=tokens["panel"],
                  geometry=(frac(0.04), frac(0.30), px(330), px(390)))
    frame.setContentsMargins(12, 12, 12, 12)

    def label(text, **options):
        return Label(renderer, interactor, text, **options)

    title = label("Source settings")
    particle = ComboBox(renderer, interactor)
    particle.addItems(["Photon (p)", "Neutron (n)", "Electron (e)"])
    energy = ComboBox(renderer, interactor)
    energy.addItems(["Discrete", "Histogram", "Watt"])

    form = FormLayout(spacing=6, label_factory=lambda text, host: label(text))
    form.addRow("Particle", particle)
    form.addRow("Energy", energy)

    shapes = ButtonGroup()
    shape_row = HBoxLayout(spacing=10)
    for index, name in enumerate(("Point", "Sphere", "Box")):
        radio = RadioButton(renderer, interactor, name, checked=index == 0)
        shapes.addButton(radio, index)
        shape_row.addWidget(radio)
    shape_row.addStretch()

    options = VBoxLayout(spacing=4)
    options.addWidget(CheckBox(renderer, interactor, "Show source marker",
                               checked=True))
    options.addWidget(CheckBox(renderer, interactor, "Bias towards tallies"))
    partial = CheckBox(renderer, interactor, "Apply to all copies",
                       tristate=True)
    partial.setCheckState(CheckBox.PARTIAL)
    options.addWidget(partial)
    disabled = CheckBox(renderer, interactor, "Disabled option")
    disabled.setEnabled(False)
    options.addWidget(disabled)

    progress = ProgressBar(renderer, interactor, value=64)
    busy = ProgressBar(renderer, interactor, minimum=0, maximum=0,
                       text_visible=False)

    cancel = PushButton(renderer, interactor, "Cancel")
    place = PushButton(renderer, interactor, "Place source", default=True)
    buttons = HBoxLayout(spacing=8)
    buttons.addStretch()
    buttons.addWidget(cancel)
    buttons.addWidget(place)

    column = VBoxLayout(spacing=10)
    column.addWidget(title)
    column.addLayout(form)
    column.addLayout(shape_row)
    column.addLayout(options)
    column.addWidget(label("Reconstruction", muted=True))
    column.addWidget(progress)
    column.addWidget(busy)
    column.addStretch()
    column.addLayout(buttons)
    frame.setLayout(column)

    menu = Menu(renderer, interactor)
    menu.addAction(Action("Copy", interactor=interactor, shortcut="Ctrl+C"))
    menu.addAction(Action("Paste", interactor=interactor, shortcut="Ctrl+V"))
    menu.addSeparator()
    menu.addAction(Action("Show grid", checkable=True, checked=True))
    convert = menu.addMenu("Convert to")
    for name in ("Cell", "Universe", "Lattice"):
        convert.addAction(name)
    unavailable = menu.addAction("Boolean union")
    unavailable.setEnabled(False)

    bar = MenuBar(renderer, interactor)
    bar.setGeometry(frac(0), px(620 - 28), frac(1), px(28))   # top edge
    for title, items in (("File", ("Open", "Save", "Export")),
                         ("Edit", ("Undo", "Copy", "Paste")),
                         ("View", ("Reset camera", "Wireframe")),
                         ("Help", ("About",))):
        submenu = bar.addMenu(title)
        for item in items:
            submenu.addAction(item)
    status = StatusBar(renderer, interactor)
    status.setGeometry(frac(0), frac(0), frac(1), px(22))
    status.showMessage("Ready - 12 actors, 3 materials")
    place.setStatusTip("Place the configured source in the scene")
    return frame, menu, convert


SCENES = ("menu", "message", "focus", "plain")


def render(theme="light", scene="menu", size=(900, 620)):
    """Render one off-screen frame of the gallery; returns ``vtkImageData``.

    ``scene`` is ``"menu"`` (a menu and submenu open), ``"message"`` (a
    message box), ``"focus"`` (a control focused by Tab) or ``"plain"``.
    Used by ``--screenshot`` and the screenshot tests.
    """
    from multipanel.animation import animations_enabled, set_animations_enabled
    from multipanel.core import FocusManager, RenderScheduler

    if scene not in SCENES:
        raise ValueError(f"scene must be one of {SCENES}")
    animated = animations_enabled()
    # One frame, no event loop: show end states, not the first frame of a
    # fade.
    set_animations_enabled(False)
    window = interactor = None
    try:
        renderer, window, interactor = _window(theme, size, offscreen=True)
        frame, menu, convert = build(renderer, interactor)
        frame.contentLayout().activate()
        if scene == "message":
            MessageBox.question(renderer, interactor, "Delete actors?",
                                "Delete the 3 selected actors?\n"
                                "This can be undone with Ctrl+Z.")
        elif scene == "focus":
            manager = FocusManager.for_interactor(interactor)
            for _ in range(3):
                manager.focusNext()
        elif scene == "menu":
            menu.popup(at=(430, 520))
            menu._set_active(menu.items()[4], open_submenu=True)
            convert._set_active(convert.items()[1])
        # No event loop runs here: flush deferred layout passes first.
        RenderScheduler.for_window(window, interactor).flush()
        window.Render()
        grab = vtk.vtkWindowToImageFilter()
        grab.SetInput(window)
        grab.ReadFrontBufferOff()
        grab.Update()
        image = vtk.vtkImageData()
        image.DeepCopy(grab.GetOutput())
        return image
    finally:
        set_animations_enabled(animated)
        if interactor is not None:
            EventRouter.uninstall(interactor)
        if window is not None:
            window.Finalize()


def _window(theme, size, offscreen=False):
    tokens = vtk_tokens(DARK if theme == "dark" else LIGHT)
    renderer = vtk.vtkRenderer()
    renderer.theme = SimpleNamespace(tokens=tokens)
    renderer.SetBackground(*tokens["pane"])
    window = vtk.vtkRenderWindow()
    window.SetSize(*size)
    window.AddRenderer(renderer)
    if offscreen:
        window.SetOffScreenRendering(True)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    EventRouter.install(interactor)
    return renderer, window, interactor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--message", action="store_true",
                        help="screenshot with a message box open")
    parser.add_argument("--focus", action="store_true",
                        help="screenshot with a control focused by Tab")
    args = parser.parse_args()
    theme = "dark" if args.dark else "light"

    if args.screenshot:
        scene = "message" if args.message else \
            "focus" if args.focus else "menu"
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(str(args.screenshot))
        writer.SetInputData(render(theme, scene))
        writer.Write()
        print(f"wrote {args.screenshot}")
        return
    renderer, window, interactor = _window(theme, (900, 620))
    frame, _menu, _convert = build(renderer, interactor)
    frame.contentLayout().activate()
    window.Render()
    interactor.Initialize()
    interactor.Start()


if __name__ == "__main__":
    main()
