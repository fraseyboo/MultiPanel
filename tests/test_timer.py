import vtk

from multipanel.core import RenderScheduler
from multipanel.timer import Timer, VirtualClock


def make_interactor():
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(True)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    return window, interactor


def test_virtual_clock_runs_callbacks_in_due_order():
    clock = VirtualClock()
    calls = []
    clock.call_later(30, lambda: calls.append("b"))
    clock.call_later(10, lambda: calls.append("a"))
    cancelled = clock.call_later(20, lambda: calls.append("x"))
    clock.cancel(cancelled)

    assert clock.advance(15) == 1
    assert calls == ["a"]
    assert clock.advance(15) == 1
    assert calls == ["a", "b"]
    assert clock.now() == 30
    assert clock.pending() == 0


def test_single_shot_timer_fires_once_after_interval():
    _window, interactor = make_interactor()
    clock = VirtualClock.install(interactor)
    fired = []
    timer = Timer.singleShot(interactor, 250, lambda: fired.append(clock.now()))

    clock.advance(249)
    assert fired == []
    clock.advance(1)
    assert fired == [250]
    clock.advance(1000)
    assert fired == [250]
    assert not timer.isActive()
    VirtualClock.uninstall(interactor)


def test_repeating_timer_restart_and_stop():
    _window, interactor = make_interactor()
    clock = VirtualClock.install(interactor)
    ticks = []
    timer = Timer(interactor, interval_ms=100)
    timer.timeout.connect(lambda: ticks.append(clock.now()))
    timer.start()

    clock.advance(350)
    assert ticks == [100, 200, 300]

    timer.start(50)          # restart with a new interval
    clock.advance(120)
    assert ticks[3:] == [400, 450]

    timer.stop()
    clock.advance(500)
    assert len(ticks) == 5
    assert not timer.isActive()
    VirtualClock.uninstall(interactor)


def test_zero_interval_repeating_timer_does_not_spin():
    _window, interactor = make_interactor()
    clock = VirtualClock.install(interactor)
    timer = Timer(interactor, interval_ms=0)
    ticks = []
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    clock.advance(10)
    assert len(ticks) == 10
    timer.stop()
    VirtualClock.uninstall(interactor)


def test_render_scheduler_flushes_through_virtual_clock():
    window, interactor = make_interactor()
    clock = VirtualClock.install(interactor)
    renders = []
    window.AddObserver("StartEvent", lambda *_: renders.append(1))
    scheduler = RenderScheduler(window, interactor)

    scheduler.request()
    scheduler.request()
    assert renders == []
    clock.advance(0)
    assert len(renders) == 1

    scheduler.request()      # a new request after flushing schedules again
    clock.advance(0)
    assert len(renders) == 2
    VirtualClock.uninstall(interactor)
