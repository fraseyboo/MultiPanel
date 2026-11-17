"""Deprecated chart-actor helpers (moved out of :mod:`multipanel.charts`).

``add_chart_actor`` put a ``vtkChartXY`` in a ``vtkContextActor`` over the
scene, and ``DraggableChartInteractorStyle``, ``HybridInteractorStyle``
and ``install_chart_mode`` shared mouse input between it and the camera.
:class:`multipanel.chartview.ChartView` and
:func:`multipanel.chartview.ChartPanel` replace them: a chart is a widget
with its own clipped renderer, its input delivered by the event router,
in panels, docks and layouts, themed, editable and exportable.

Each entry point warns with ``DeprecationWarning``; they will be removed
in a later release.
"""
import logging
import warnings

import numpy as np
import vtk

logger = logging.getLogger(__name__)


def _deprecated(name, instead):
    warnings.warn(f"multipanel {name} is deprecated; use {instead} "
                  f"(multipanel.chartview)", DeprecationWarning, stacklevel=3)


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def _widgets():
    from . import widgets
    return widgets


def add_chart_actor(
    axes=None,
    renderer=None,
    interactor=None,
    position=(0, 0),
    size=(640, 480),
    title="VTK Chart",
    background_color="white",
    background_opacity=0.9,
    window_size=None,
    grabbable=False
):
    """
    Adds a VTK chart actor to a renderer or interactor with customizable properties.
    Parameters:
        axes (vtk.vtkChartXY, optional): The VTK chart object to be used.
            If None, a new vtkChartXY is created.
        renderer (vtk.vtkRenderer, optional): The VTK renderer to which the chart actor
            will be added.
        interactor (vtk.vtkRenderWindowInteractor, optional): The interactor for
            handling user interactions.
        position (tuple, optional): The position of the chart in normalized coordinates
            (0 to 1) or pixels. Default is (0, 0).
        size (tuple, optional): The size of the chart in pixels or normalized
            coordinates (0 to 1). Default is (640, 480).
        title (str, optional): The title of the chart. Default is 'VTK Chart'.
        background_color (str, optional): The background color of the chart panel.
            Default is 'SlateGray'.
        background_opacity (float, optional): The opacity of the chart panel background.
            Default is 0.9.
        window_size (tuple, optional): The size of the render window, used for
            fractional sizing. Default is None.
    Returns:
        vtk.vtkContextActor: The created chart actor.
    Raises:
        ValueError: If fractional sizing is assumed but no method to determine window
            size is provided.
    Notes:
        - If `size` or `position` values are fractional (less than 1), the method
        attempt to determine the window size using the provided `interactor`,
        `renderer`, or
            `window_size`.
        - The chart actor is draggable and resizable.
        - If a `renderer` is provided, a panel background is added with bounds and
        interaction events are set up to
            update the chart's position and size dynamically.
    """
    _deprecated("add_chart_actor()", "ChartPanel or ChartView")

    if axes is None:
        axes = vtk.vtkChartXY()

    axes.SetAutoSize(False)

    if size[0] < 1 or size[1] < 1:
        if interactor is not None:
            window_size = interactor.GetRenderWindow().GetSize()

        elif renderer is not None:
            window_size = renderer.GetRenderWindow().GetSize()
        elif window_size is not None:
            pass
        else:
            raise ValueError("Assuming fractional sizing but window size not provided")

        size = np.asarray([size[0] * window_size[0], size[1] * window_size[1]])
        position = np.asarray(
            [position[0] * window_size[0], position[1] * window_size[1]]
        )

    axes.SetSize(vtk.vtkRectf(position[0], position[1], size[0], size[1]))
    axes.SetTitle(title)
    axes.GetTitleProperties().SetFontSize(20)
    axes.GetTitleProperties().SetFontFamilyToArial()
    axes.GetTitleProperties().SetBold(False)

    chartActor = vtk.vtkContextActor()
    chartScene = vtk.vtkContextScene()
    chartScene.AddItem(axes)
    chartActor.SetScene(chartScene)

    chartActor.SetUseBounds(True)
    chartActor.SetDragable(True)

    chartActor.SetObjectName(f"ChartActor-{title}")


    link = chartScene.GetAnnotationLink()


    def update_panel_elements(obj, event):
        """
        Updates the size and position of panel elements based on the panel's anchor
        positions, dimensions, and the window size. This is similar to the code in
        the widgets module.

        Parameters:
            obj: The panel background object that triggered the update.
            event: The event that triggered the update. Can be used to identify what
                caused the update (e.g., window resize, interaction event).
        Functionality:
            - Retrieves the anchor positions, panel height, and panel width from the
              panel background's representation.
            - Calculates the screen position and size of the panel based on the
              window size and a buffer value.
            - Iterates through the panel elements and updates their size and position
              accordingly:
                - If the element is a `vtk.vtkPlot`, its size is updated using
                  `vtk.vtkRectf`.
                - If the element is a `vtk.vtkContextActor`, the size of its scene's
                  first item is updated using `vtk.vtkRectf`.
                - If the element type is unknown, it logs the type of the element.
        Notes:
            - This function assumes the presence of global variables such as
              `panel_background`, `interactor`, and `added_widgets`.
            - The `buffer` attribute of `panel_background` is used to adjust the
              panel's dimensions.
            - The function is designed to work with VTK (Visualization Toolkit)
              objects and may not be applicable outside of this context.
        """

        # if isinstance(obj, vtk.vtkBorderWidget):
        anchor_positions = (
            panel_background.GetRepresentation().GetPositionCoordinate().GetValue()
        )
        panel_height = (
            panel_background.GetRepresentation().GetPosition2Coordinate().GetValue()[1]
        )
        panel_width = (
            panel_background.GetRepresentation().GetPosition2Coordinate().GetValue()[0]
        )

        window_size = interactor.GetRenderWindow().GetSize()

        panel_elements = added_widgets.values()

        buffer = panel_background.buffer

        anchor_positions = np.asarray(
            [anchor_positions[0] + buffer, anchor_positions[1] + buffer]
        )
        panel_width = panel_width - 2 * buffer
        panel_height = panel_height - 2 * buffer

        screen_position = np.asarray(
            [anchor_positions[0] * window_size[0], anchor_positions[1] * window_size[1]]
        )
        screen_panel_size = np.asarray(
            [panel_width * window_size[0], panel_height * window_size[1]]
        )

        for panel_element in panel_elements:
            if isinstance(panel_element, vtk.vtkPlot):
                panel_element.SetSize(
                    vtk.vtkRectf(
                        screen_position[0],
                        screen_position[1],
                        screen_panel_size[0],
                        screen_panel_size[1],
                    )
                )
            elif isinstance(panel_element, vtk.vtkContextActor):
                panel_element.GetScene().GetItem(0).SetSize(
                    vtk.vtkRectf(
                        screen_position[0],
                        screen_position[1],
                        screen_panel_size[0],
                        screen_panel_size[1],
                    )
                )
            else:
                logger.debug("%s %s", "Unknown type", type(panel_element))

    if renderer is not None:
        window_size = renderer.GetRenderWindow().GetSize()

        panel_bounds = np.asarray(
            [
                position[0] / window_size[0],
                (position[0] + size[0]) / window_size[0],
                position[1] / window_size[1],
                (position[1] + size[1]) / window_size[1],
            ]
        )

        panel_background = _widgets().PanelBackgroundWidget(
            renderer=renderer,
            interactor=interactor,
            panel_bounds=panel_bounds,
            panel_color=background_color,
            radius=0.1,
            opacity=background_opacity,
            grabbable=grabbable,
        )

        panel_background.AddObserver("InteractionEvent", update_panel_elements)

        render_window = interactor.GetRenderWindow()
        render_window.AddObserver("WindowResizeEvent", update_panel_elements)

        added_widgets = {}

        added_widgets[chartActor.GetObjectName()] = chartActor

    return chartActor


    


# import vtk

# A draggable chart interactor that lets you drag points in a vtkChartXY
class DraggableChartInteractorStyle(vtk.vtkContextInteractorStyle):
    def __init__(self, chart):
        """Initialize the instance."""
        _deprecated("DraggableChartInteractorStyle", "editable series in a ChartView")
        super().__init__()
        self.chart = chart
        self.selected_point_idx = -1
        self.selected_series = None
        self.mode = "camera"
        self.pressed = False
        self.verbose = False
        

    def OnMouseMove(self, obj=None, event=None):
        """Execute the on mouse move operation."""
        if self.mode != "chart":
            return 0
        elif self.mode == "chart":
            if self.pressed:
                super().OnMouseMove()
                self.GetInteractor().GetRenderWindow().Render()
            else:
                if self.verbose:
                    logger.debug("Mouse move without press - no action")
                return 0


    def OnLeftButtonDown(self, obj=None, event=None):
        """Execute the on left button down operation."""
        if self.mode != "chart":
            return 0
        elif self.mode == "chart":
            self.pressed = True
            super().OnLeftButtonDown()
        self.GetInteractor().GetRenderWindow().Render()

    def OnLeftButtonUp(self, obj=None, event=None):
        """Execute the on left button up operation."""
        if self.mode != "chart":
            return 0
        elif self.mode == "chart":
            self.pressed = False
            super().OnLeftButtonUp()
        self.GetInteractor().GetRenderWindow().Render()

    def OnRightButtonDown(self):
        """Execute the on right button down operation."""
        if self.mode != "chart":
            return 0
        elif self.mode == "chart":
            self.pressed = True
            super().OnRightButtonDown()
        self.GetInteractor().GetRenderWindow().Render()

    def OnRightButtonUp(self):
        """Execute the on right button up operation."""
        if self.mode != "chart":
            return 0
        elif self.mode == "chart":
            self.pressed = False
            super().OnRightButtonUp()
        self.GetInteractor().GetRenderWindow().Render()

    def OnMiddleButtonDown(self):
        """Execute the on middle button down operation."""
        if self.mode != "chart":
            return 0
        elif self.mode == "chart":
            self.pressed = True
            super().OnMiddleButtonDown()
        self.GetInteractor().GetRenderWindow().Render()

    def OnMiddleButtonUp(self):
        """Execute the on middle button up operation."""
        if self.mode != "chart":
            return 0
        elif self.mode == "chart":
            self.pressed = False
            super().OnMiddleButtonUp()
        self.GetInteractor().GetRenderWindow().Render()

    


class ChartModeFilter:
    """Router event filter: pointer input over a chart goes to the chart.

    The replacement for :class:`HybridInteractorStyle`'s ``dispatch_*``
    methods (``QT_PARITY_PROPOSAL`` §5.3): keep any camera style on the
    interactor and install this filter on the
    :class:`~multipanel.router.EventRouter`::

        drag = DraggableChartInteractorStyle(chart_actor.GetScene().GetItem(0))
        drag.SetInteractor(interactor)
        drag.SetScene(chart_actor.GetScene())
        install_chart_mode(interactor, chart_actor, drag)

    Presses, moves, releases and the wheel over the chart's plot area go to
    ``chart_style`` and are consumed, so the camera does not also move. A
    press that starts on the chart keeps the chart until its release.
    Everywhere else the events pass through to widgets and the camera;
    UI widgets under the pointer always win.
    """

    _PRESS = {"left": "OnLeftButtonDown", "right": "OnRightButtonDown",
              "middle": "OnMiddleButtonDown"}
    _RELEASE = {"left": "OnLeftButtonUp", "right": "OnRightButtonUp",
                "middle": "OnMiddleButtonUp"}

    def __init__(self, chart_view, chart_style):
        self.chart_view = chart_view
        self.chart_style = chart_style
        self.chart_style.mode = "camera"
        self.chart_style.pressed = False
        self._dragging = None            # button held since a chart press

    def _chart(self):
        scene = self.chart_view.GetScene()
        for index in range(scene.GetNumberOfItems()):
            item = scene.GetItem(index)
            if isinstance(item, vtk.vtkChartXY):
                return item
        return None

    def isOverChart(self, x, y):
        chart = self._chart()
        if chart is None:
            return False
        (x0, y0), (x1, y1) = chart.GetPoint1(), chart.GetPoint2()
        return x0 <= x <= x1 and y0 <= y <= y1

    def _call(self, name):
        handler = getattr(self.chart_style, name, None)
        if callable(handler):
            handler()

    def eventFilter(self, target, event):
        from .events import MouseEvent, WheelEvent

        x, y = event.globalPos() if hasattr(event, "globalPos") else (0, 0)
        kind = event.type()
        if self._dragging is not None:
            if kind == MouseEvent.MOVE:
                self._call("OnMouseMove")
                return True
            if kind == MouseEvent.RELEASE and event.button() == self._dragging:
                self._dragging = None
                self._call(self._RELEASE.get(event.button(), ""))
                self.chart_style.pressed = False
                return True
        if target is not None:
            self.chart_style.mode = "camera"
            return False                   # a UI widget is under the pointer
        over = self.isOverChart(x, y)
        self.chart_style.mode = "chart" if over else "camera"
        if not over:
            self.chart_style.pressed = False
            return False
        if isinstance(event, WheelEvent):
            self._call("OnMouseWheelForward" if event.delta() > 0
                       else "OnMouseWheelBackward")
            return True
        if kind in (MouseEvent.PRESS, MouseEvent.DOUBLE_CLICK):
            name = self._PRESS.get(event.button())
            if name is None:
                return False
            self._dragging = event.button()
            self._call(name)
            return True
        if kind == MouseEvent.MOVE:
            self._call("OnMouseMove")
            return True
        if kind == MouseEvent.RELEASE:
            self._call(self._RELEASE.get(event.button(), ""))
            return True
        return False


def install_chart_mode(interactor, chart_view, chart_style):
    """Install a :class:`ChartModeFilter` on ``interactor``'s router."""
    _deprecated("install_chart_mode()", "ChartView, whose input the router delivers")
    from .router import EventRouter

    chart_filter = ChartModeFilter(chart_view, chart_style)
    EventRouter.install(interactor).installEventFilter(chart_filter)
    return chart_filter


# Hybrid interactor style: Camera in 3D, draggable inside chart
class HybridInteractorStyle(vtk.vtkInteractorStyleTrackballCamera):
    """Camera style that hands pointer input over a chart to the chart.

    Kept for existing code; new code should keep any camera style and use
    :func:`install_chart_mode`, which does the same through the
    EventRouter, so UI widgets and the chart cooperate.
    """

    def __init__(self, chart_view, chart_style):
        """Initialize the instance."""
        _deprecated("HybridInteractorStyle", "ChartView")
        super().__init__()
        self.chart_view = chart_view
        self.chart_style = chart_style

        self.picker = vtk.vtkPropPicker()
        self.chart_style.mode = "camera"
        self.verbose = False

        # Hook mouse events we want to switch
        self.AddObserver("MouseMoveEvent", self.dispatch_move)
        self.AddObserver("LeftButtonPressEvent", self.dispatch_left_down)
        self.AddObserver("LeftButtonReleaseEvent", self.dispatch_left_up)
        self.AddObserver("RightButtonPressEvent", self.dispatch_right_down)
        self.AddObserver("RightButtonReleaseEvent", self.dispatch_right_up)
        self.AddObserver("MiddleButtonPressEvent", self.dispatch_middle_down)
        self.AddObserver("MiddleButtonReleaseEvent", self.dispatch_middle_up)
        self.AddObserver("MouseWheelForwardEvent", self.dispatch_mouse_wheel_forward)
        self.AddObserver("MouseWheelBackwardEvent", self.dispatch_mouse_wheel_backward)

    def over_chart(self):


        """Execute the over chart operation."""
        x, y = self.GetInteractor().GetEventPosition()

        # window_size = self.GetInteractor().GetRenderWindow().GetSize()

        total_items = self.chart_view.GetScene().GetNumberOfItems()
        for i in range(total_items):
            item = self.chart_view.GetScene().GetItem(i)
            if isinstance(item, vtk.vtkChartXY):
                axes = item
                break

        point_1 = axes.GetPoint1()  # bottom-left
        point_2 = axes.GetPoint2()  # top-right

        chart_bounds = (point_1[0], point_2[0], point_1[1], point_2[1])  # (xmin, xmax, ymin, ymax) in pixel coords

        if chart_bounds[0] <= x <= chart_bounds[1] and chart_bounds[2] <= y <= chart_bounds[3]:
            return "chart"
        else:
            return "camera"

    
    def dispatch_move(self, obj, evt):

        """Execute the dispatch move operation."""
        interaction_mode = self.over_chart()
        self.chart_style.mode = interaction_mode

        if self.chart_style.mode == "camera":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.FAIL}Moving over camera, pressed={self.chart_style.pressed}{bcolors.ENDC}")
            self.chart_style.pressed = False
            super().OnMouseMove()
            return 0

        elif self.chart_style.mode == "chart":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.OKGREEN}Moving over chart, pressed={self.chart_style.pressed}{bcolors.ENDC}")
            self.chart_style.OnMouseMove()

    def dispatch_left_down(self, obj, evt):
        """Execute the dispatch left down operation."""
        self.chart_style.mode = self.over_chart()

        if self.chart_style.mode == "camera":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.FAIL}Left button down not over chart{bcolors.ENDC}")
            self.chart_style.pressed = False
            super().OnLeftButtonDown()
        elif self.chart_style.mode == "chart":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.OKGREEN}Left button down over chart{bcolors.ENDC}")
            self.chart_style.OnLeftButtonDown()
 

    def dispatch_left_up(self, obj, evt):
        """Execute the dispatch left up operation."""
        self.chart_style.mode = self.over_chart()
        
        if self.chart_style.mode == "camera":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.FAIL}Left button up not over chart{bcolors.ENDC}")
            self.chart_style.pressed = False
            super().OnLeftButtonUp()
            return 0
        elif self.chart_style.mode == "chart":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.OKGREEN}Left button up over chart{bcolors.ENDC}")
            self.chart_style.pressed = False
            self.chart_style.OnLeftButtonUp()


    def dispatch_right_down(self, obj, evt):
        """Execute the dispatch right down operation."""
        self.chart_style.mode = self.over_chart()

        if self.chart_style.mode == "camera":
            self.chart_style.pressed = False
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.FAIL}Right button down not over chart{bcolors.ENDC}")
            super().OnRightButtonDown()

        elif self.chart_style.mode == "chart":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.OKGREEN}Right button down over chart{bcolors.ENDC}")
            self.chart_style.OnRightButtonDown()

    
    def dispatch_right_up(self, obj, evt):
        """Execute the dispatch right up operation."""
        self.chart_style.mode = self.over_chart()

        if self.chart_style.mode == "chart":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.OKGREEN}Right button up over chart{bcolors.ENDC}")
            self.chart_style.OnRightButtonUp()
        elif self.chart_style.mode == "camera":
            self.chart_style.pressed = False
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.FAIL}Right button up not over chart{bcolors.ENDC}")
            super().OnRightButtonUp()

    def dispatch_middle_down(self, obj, evt):
        """Execute the dispatch middle down operation."""
        self.chart_style.mode = self.over_chart()

        if self.chart_style.mode == "camera":
            self.chart_style.pressed = False
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.FAIL}Middle button down not over chart{bcolors.ENDC}")
            super().OnMiddleButtonDown()
        elif self.chart_style.mode == "chart":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.OKGREEN}Middle button down over chart{bcolors.ENDC}")
            self.chart_style.OnMiddleButtonDown()

    def dispatch_middle_up(self, obj, evt):
        """Execute the dispatch middle up operation."""
        self.chart_style.mode = self.over_chart()

        if self.chart_style.mode == "camera":
            self.chart_style.pressed = False
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.FAIL}Middle button up not over chart{bcolors.ENDC}")
            super().OnMiddleButtonUp()
        elif self.chart_style.mode == "chart":
            self.chart_style.pressed = False
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.OKGREEN}Middle button up over chart{bcolors.ENDC}")
            self.chart_style.OnMiddleButtonUp()

    def dispatch_mouse_wheel_forward(self, obj, evt):
        """Execute the dispatch mouse wheel forward operation."""
        self.chart_style.mode = self.over_chart()

        if self.chart_style.mode == "camera":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.FAIL}Mouse wheel forward not over chart{bcolors.ENDC}")
            self.chart_style.pressed = False
            super().OnMouseWheelForward()
        elif self.chart_style.mode == "chart":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.OKGREEN}Mouse wheel forward over chart{bcolors.ENDC}")
            self.chart_style.OnMouseWheelForward()
            self.GetInteractor().GetRenderWindow().Render()

    def dispatch_mouse_wheel_backward(self, obj, evt):
        """Execute the dispatch mouse wheel backward operation."""
        self.chart_style.mode = self.over_chart()

        if self.chart_style.mode == "camera":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.FAIL}Mouse wheel backward not over chart{bcolors.ENDC}")
            self.chart_style.pressed = False
            super().OnMouseWheelBackward()
        elif self.chart_style.mode == "chart":
            if self.chart_style.verbose:
                logger.debug(f"{bcolors.OKGREEN}Mouse wheel backward over chart{bcolors.ENDC}")
            self.chart_style.OnMouseWheelBackward()

            # update the render window
            self.GetInteractor().GetRenderWindow().Render()

    
