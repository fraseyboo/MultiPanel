"""A multi-line editor beside a read-only log that a timer keeps filling.

Run interactively::

    python examples/textedit_demo.py [--dark]

or write one off-screen frame to an image::

    python examples/textedit_demo.py --screenshot textedit.png [--dark]
"""
import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import vtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multipanel.containers import Frame  # noqa: E402
from multipanel.layouts import HBoxLayout, VBoxLayout  # noqa: E402
from multipanel.router import EventRouter  # noqa: E402
from multipanel.splitter import Splitter  # noqa: E402
from multipanel.standard import Label, PushButton  # noqa: E402
from multipanel.textedit import TextEdit  # noqa: E402
from multipanel.timer import Timer  # noqa: E402
from multipanel.ui_theme import DARK, LIGHT, vtk_tokens  # noqa: E402
from multipanel.units import frac, px  # noqa: E402

DECK = """c Lead shield around a photon point source
1  1 -11.35  -2 1  imp:p=1   $ shield
2  0          -1   imp:p=1   $ inner void
3  0           2   imp:p=0   $ outside

1  so  10
2  so  15

mode p
sdef pos=0 0 0 erg=0.662
m1  82000 1"""


def build(renderer, interactor):
    panel = Frame(renderer, interactor, background=True,
                  geometry=(frac(0.03), frac(0.04), frac(0.94), frac(0.92)))
    panel.setContentsMargins(12, 12, 12, 12)
    editor = TextEdit(renderer, interactor, DECK, monospace=True)
    editor.setPlaceholderText("Notes...")
    log = TextEdit(renderer, interactor, read_only=True)
    log.setMaximumBlockCount(200)

    def column(title, widget, *extra):
        holder = Frame(renderer, interactor)
        holder.setMinimumSize(px(160), px(120))
        rows = VBoxLayout(spacing=6)
        rows.addWidget(Label(renderer, interactor, title, bold=True))
        rows.addWidget(widget, stretch=1)
        for item in extra:
            rows.addLayout(item)
        holder.setLayout(rows)
        return holder

    buttons = HBoxLayout(spacing=8)
    clear = PushButton(renderer, interactor, "Clear log")
    clear.clicked.connect(lambda *_: log.clear())
    buttons.addStretch()
    buttons.addWidget(clear)
    split = Splitter(renderer, interactor, "horizontal")
    split.setHandleWidth(12)
    split.addWidget(column("Input deck", editor))
    split.addWidget(column("Run log", log, buttons))
    outer = VBoxLayout()
    outer.addWidget(split, stretch=1)
    panel.setLayout(outer)
    return panel, editor, log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--dark", action="store_true")
    args = parser.parse_args()
    if args.screenshot:
        from multipanel.animation import set_animations_enabled

        set_animations_enabled(False)
    tokens = vtk_tokens(DARK if args.dark else LIGHT)
    renderer = vtk.vtkRenderer()
    renderer.theme = SimpleNamespace(tokens=tokens)
    renderer.SetBackground(*tokens["pane"])
    window = vtk.vtkRenderWindow()
    window.SetSize(900, 480)
    window.AddRenderer(renderer)
    if args.screenshot:
        window.SetOffScreenRendering(True)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    EventRouter.install(interactor)
    panel, editor, log = build(renderer, interactor)
    panel.contentLayout().activate()
    count = [0]

    def tick():
        count[0] += 1
        log.appendPlainText(f"[{count[0]:04d}] history {count[0] * 1000} "
                            f"particles, {count[0] % 5} lost")

    if args.screenshot:
        for _ in range(40):
            tick()
        editor.setFocus(reason="mouse")
        editor.setTextCursorPosition(DECK.index("-11.35"))
        editor.setTextCursorPosition(DECK.index("-11.35") + 6, select=True)
        window.Render()
        grab = vtk.vtkWindowToImageFilter()
        grab.SetInput(window)
        grab.ReadFrontBufferOff()
        grab.Update()
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(str(args.screenshot))
        writer.SetInputConnection(grab.GetOutputPort())
        writer.Write()
        print(f"wrote {args.screenshot}")
        return
    timer = Timer(interactor, 500)
    timer.timeout.connect(tick)
    timer.start()
    window.Render()
    interactor.Initialize()
    interactor.Start()


if __name__ == "__main__":
    main()
