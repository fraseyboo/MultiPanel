"""Timer ids come from the TimerEvent call data, not GetTimerEventId().

Regression: VTK's native Cocoa interactor leaves GetTimerEventId() at 0 and
passes the firing timer's id only as call data. Timers matched on
GetTimerEventId() never fired on macOS, so tooltips never appeared and
RenderScheduler dropped every request after its first.
"""
from multipanel.core import RenderScheduler
from multipanel.timer import Timer


class CocoaLikeInteractor:
    def __init__(self):
        self.observers = {}
        self.timers = {}
        self.next_tag = 1
        self.next_id = 2

    def AddObserver(self, event, callback, priority=0.0):
        tag = self.next_tag
        self.next_tag += 1
        self.observers[tag] = (event, callback)
        return tag

    def RemoveObserver(self, tag):
        self.observers.pop(tag, None)

    def CreateOneShotTimer(self, ms):
        return self._create(ms)

    def CreateRepeatingTimer(self, ms):
        return self._create(ms)

    def _create(self, ms):
        timer_id = self.next_id
        self.next_id += 1
        self.timers[timer_id] = ms
        return timer_id

    def DestroyTimer(self, timer_id):
        self.timers.pop(timer_id, None)

    def GetTimerEventId(self):
        return 0                       # as vtkCocoaRenderWindowInteractor

    def fire(self, timer_id):
        for event, callback in list(self.observers.values()):
            if event == "TimerEvent":
                callback(self, "TimerEvent", timer_id)

    def GetRenderWindow(self):
        return None


class CountingWindow:
    def __init__(self):
        self.renders = 0

    def Render(self):
        self.renders += 1


def test_timer_fires_from_call_data_id():
    interactor = CocoaLikeInteractor()
    fired = []
    timer = Timer(interactor, 700, single_shot=True)
    timer.timeout.connect(lambda: fired.append(1))
    timer.start()
    other = interactor.CreateOneShotTimer(10)
    interactor.fire(other)              # a different timer: ignored
    assert fired == []
    interactor.fire(timer._vtk_id)
    assert fired == [1]


def test_render_scheduler_flushes_and_accepts_new_requests():
    interactor = CocoaLikeInteractor()
    window = CountingWindow()
    scheduler = RenderScheduler(window, interactor)
    scheduler.request()
    interactor.fire(scheduler._timer_id)
    assert window.renders == 1
    scheduler.request()                 # previously dropped forever
    assert scheduler._timer_id is not None
    interactor.fire(scheduler._timer_id)
    assert window.renders == 2
