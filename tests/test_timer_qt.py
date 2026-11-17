"""Timer and RenderScheduler under a running Qt application.

Runs in a subprocess so the QApplication does not leak into other tests.
Skipped when no Qt binding is installed.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"

SCRIPT = textwrap.dedent("""
    import os, sys, time
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, sys.argv[1])
    from PyQt5.QtWidgets import QApplication
    import vtk
    from multipanel.core import RenderScheduler
    from multipanel.timer import Timer, qt_core

    app = QApplication([])
    assert qt_core() is not None
    window = vtk.vtkRenderWindow(); window.SetOffScreenRendering(True)
    interactor = vtk.vtkGenericRenderWindowInteractor()
    interactor.SetRenderWindow(window)

    def pump(ms):
        end = time.monotonic() + ms / 1000.0
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.002)

    fired = []
    start = time.monotonic()
    Timer.singleShot(interactor, 150, lambda: fired.append(("slow", time.monotonic() - start)))
    Timer.singleShot(interactor, 40, lambda: fired.append(("fast", time.monotonic() - start)))
    stopped = Timer(interactor, 60, single_shot=True)
    stopped.timeout.connect(lambda: fired.append(("stopped", 0)))
    stopped.start(); stopped.stop()
    pump(300)
    names = [name for name, _ in fired]
    assert names == ["fast", "slow"], fired
    assert fired[1][1] >= 0.14, fired         # the duration is honoured

    ticks = []
    repeating = Timer(interactor, 30)
    repeating.timeout.connect(lambda: ticks.append(1))
    repeating.start(); pump(170); repeating.stop()
    assert 3 <= len(ticks) <= 7, ticks

    renders = []
    window.AddObserver("StartEvent", lambda *_: renders.append(1))
    scheduler = RenderScheduler(window, interactor)
    scheduler.request(); scheduler.request()
    pump(50)
    assert len(renders) == 1, renders
    scheduler.request(); pump(50)
    assert len(renders) == 2, renders
    print("OK")
""")


def test_qt_backend_honours_durations_and_coalesces_renders():
    pytest.importorskip("PyQt5.QtWidgets")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([sys.executable, "-c", SCRIPT, str(SRC)],
                            capture_output=True, text=True, timeout=120,
                            env=env)
    assert result.returncode == 0 and "OK" in result.stdout, (
        result.stdout[-2000:] + result.stderr[-2000:])
