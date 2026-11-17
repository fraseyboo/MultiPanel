"""Interactor-level routing utilities."""

from ._widget_support import *
import logging

logger = logging.getLogger(__name__)

class ClickManager(WidgetMixin):
    """
    Manages click events on a VTK interactor to capture mouse click positions and
    redirect them to the appropriate handlers by looking at the bounds of the UI panels.
    Attributes:
        interactor (vtkRenderWindowInteractor): The VTK interactor to manage click events.
        panels (list): A list of UI panels to check for click bounds.
    Methods:
        __init__(self, interactor, panels):
            Initializes the ClickManager with the given interactor and panels.
        on_left_button_down(self, caller, event):
            Handles left button down events, capturing the click position and
            redirecting to the appropriate panel if the click is within its bounds.
        on_left_button_up(self, caller, event):
            Handles left button up events, capturing the click position and
            redirecting to the appropriate panel if the click is within its bounds.
        on_mouse_move(self, caller, event):
            Handles mouse move events, capturing the current mouse position and
            redirecting to the appropriate panel if the mouse is within its bounds.
        on_right_button_down(self, caller, event):
            Handles right button down events, capturing the click position and
            redirecting to the appropriate panel if the click is within its bounds.
        on_right_button_up(self, caller, event):
            Handles right button up events, capturing the click position and
            redirecting to the appropriate panel if the click is within its bounds.
        on_middle_button_down(self, caller, event):
            Handles middle button down events, capturing the click position and
            redirecting to the appropriate panel if the click is within its bounds.
        on_middle_button_up(self, caller, event):
            Handles middle button up events, capturing the click position and
            redirecting to the appropriate panel if the click is within its bounds.
    """
    def __init__(self, interactor, panels, verbose=False):
        """Initialize the instance."""
        self.interactor = interactor
        self.panels = panels
        self.verbose = bool(verbose)
        self.initWidget('click_manager')
        self.ownObserver(
            interactor, "LeftButtonPressEvent", self.on_left_button_down)
        self.ownObserver(
            interactor, "LeftButtonReleaseEvent", self.on_left_button_up)
        self.ownObserver(interactor, "MouseMoveEvent", self.on_mouse_move)
        self.ownObserver(
            interactor, "RightButtonPressEvent", self.on_right_button_down)
        self.ownObserver(
            interactor, "RightButtonReleaseEvent", self.on_right_button_up)
        self.ownObserver(
            interactor, "MiddleButtonPressEvent", self.on_middle_button_down)
        self.ownObserver(
            interactor, "MiddleButtonReleaseEvent", self.on_middle_button_up)

    def on_left_button_down(self, caller, event):
        """Handle left button down."""
        x, y = self.interactor.GetEventPosition()
        window_size = self.interactor.GetRenderWindow().GetSize()
        x = x/window_size[0]
        y = y/window_size[1]
        for panel_name, panel in self.panels.items():
            if panel.is_within_bounds(x, y):
                if self.verbose:
                    logger.debug(f"Left button down on panel: {panel_name}")
                panel.handle_left_button_down(x, y)
                return
        if self.verbose:
            logger.debug("Left button down outside panels")

    def on_left_button_up(self, caller, event):
        """Handle left button up."""
        x, y = self.interactor.GetEventPosition()
        window_size = self.interactor.GetRenderWindow().GetSize()
        x = x/window_size[0]
        y = y/window_size[1]
        for panel_name, panel in self.panels.items():
            if panel.is_within_bounds(x, y):
                if self.verbose:
                    logger.debug(f"Left button up on panel: {panel_name}")
                panel.handle_left_button_up(x, y)
                return
        if self.verbose:
            logger.debug("Left button up outside panels")

    def on_mouse_move(self, caller, event):
        """Handle mouse move."""
        x, y = self.interactor.GetEventPosition()
        window_size = self.interactor.GetRenderWindow().GetSize()
        x = x/window_size[0]
        y = y/window_size[1]
        for panel_name, panel in self.panels.items():
            if panel.is_within_bounds(x, y):
                if self.verbose:
                    logger.debug(f"Mouse move on panel: {panel_name}")
                panel.handle_mouse_move(x, y)
                return
        if self.verbose:
            logger.debug("Mouse move outside panels")

    def on_right_button_down(self, caller, event):
        """Handle right button down."""
        x, y = self.interactor.GetEventPosition()
        window_size = self.interactor.GetRenderWindow().GetSize()
        x = x/window_size[0]
        y = y/window_size[1]
        for panel_name, panel in self.panels.items():
            if panel.is_within_bounds(x, y):
                if self.verbose:
                    logger.debug(f"Right button down on panel: {panel_name}")
                panel.handle_right_button_down(x, y)
                return
        if self.verbose:
            logger.debug("Right button down outside panels")

    def on_right_button_up(self, caller, event):
        """Handle right button up."""
        x, y = self.interactor.GetEventPosition()
        window_size = self.interactor.GetRenderWindow().GetSize()
        x = x/window_size[0]
        y = y/window_size[1]
        for panel_name, panel in self.panels.items():
            if panel.is_within_bounds(x, y):
                if self.verbose:
                    logger.debug(f"Right button up on panel: {panel_name}")
                panel.handle_right_button_up(x, y)
                return
        if self.verbose:
            logger.debug("Right button up outside panels")

    def on_middle_button_down(self, caller, event):
        """Handle middle button down."""
        x, y = self.interactor.GetEventPosition()
        window_size = self.interactor.GetRenderWindow().GetSize()
        x = x/window_size[0]
        y = y/window_size[1]
        for panel_name, panel in self.panels.items():
            if panel.is_within_bounds(x, y):
                if self.verbose:
                    logger.debug(f"Middle button down on panel: {panel_name}")
                panel.handle_middle_button_down(x, y)
                return
        if self.verbose:
            logger.debug("Middle button down outside panels")

    def on_middle_button_up(self, caller, event):
        """Handle middle button up."""
        x, y = self.interactor.GetEventPosition()
        window_size = self.interactor.GetRenderWindow().GetSize()
        x = x/window_size[0]
        y = y/window_size[1]
        for panel_name, panel in self.panels.items():
            if panel.is_within_bounds(x, y):
                if self.verbose:
                    logger.debug(f"Middle button up on panel: {panel_name}")
                panel.handle_middle_button_up(x, y)
                return
        if self.verbose:
            logger.debug("Middle button up outside panels")




__all__ = ["ClickManager"]
