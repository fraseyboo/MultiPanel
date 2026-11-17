"""Functional chart helpers on raw VTK charts (matplotlib-like).

``figure()``/``show()`` and ``add_line_chart``, ``add_bar_chart``,
``set_x_axis_title`` … build ``vtkChartXY`` plots in a ``vtkContextView``
or a chart actor. For charts inside the UI use
:mod:`multipanel.chartview` (``XYChart``, ``ChartView``, ``ChartPanel``):
themed, laid out, routed, editable and exportable. The common helpers
(``add_line_chart``, ``add_scatter_chart``, ``add_bar_chart``, the axis
title/limit setters, ``set_title``, ``add_legend``, ``add_gridlines``)
also accept one of those and use its API, so existing code can move to
it; their default colour then means the theme palette.

The chart-actor and interactor-style helpers (``add_chart_actor``,
``DraggableChartInteractorStyle``, ``HybridInteractorStyle``,
``install_chart_mode``) moved to :mod:`multipanel.chart_legacy` and are
deprecated; they are still importable from here for now.
"""
import logging

import numpy as np
import vtk
from vtkmodules.util import numpy_support

from .colormap_utils import (  # noqa: F401  (re-exported)
    color_to_RGB, color_to_RGB_255, color_to_RGBA, color_to_RGBA_255,
    make_LUT,
)

logger = logging.getLogger(__name__)


VTK_HAS_SETCOLORF = (
    vtk.vtkVersion.GetVTKMajorVersion() >= 9
    and vtk.vtkVersion.GetVTKMinorVersion() >= 2
)


def _xy_chart(*targets):
    """The :class:`~multipanel.chartview.XYChart` among ``targets`` (an
    XYChart, ChartView or ChartPanel), or None for raw VTK charts."""
    from .chartview import ChartView, XYChart

    for target in targets:
        if isinstance(target, XYChart):
            return target
        if isinstance(target, ChartView):
            return target.chart()
        view = getattr(target, "chartView", None)
        if callable(view):
            return view().chart()
    return None


def _xy_data(x, y):
    if y is None:
        y, x = x, np.arange(len(x))
    return np.asarray(x, float), np.asarray(y, float)


def _series_colour(colour, default):
    """None (the theme palette) for the helper's default colour."""
    if colour is None or (isinstance(colour, str) and colour == default):
        return None
    return tuple(float(c) for c in color_to_RGB(colour))


def _convert_np_data_to_table(x, y=None, x_label=None, y_label=None, verbose=False):
    """
    Converts input data into a vtkTable format for visualization or further processing.

    Parameters:
        x (numpy.ndarray, vtk.vtkTable, vtk.vtkDataArray): The x-axis data or input data
            to be converted.
            If `y` is None, `x` is assumed to be the y-axis data, and x-axis values are
            generated as `np.arange(len(y))`.
        y (numpy.ndarray, vtk.vtkDataArray, optional): The y-axis data. If not provided,
            `x` is treated as the y-axis data.
        x_label (str, optional): Label for the x-axis column in the table.
            Defaults to 'X Values'.
        y_label (str, optional): Label for the y-axis column(s) in the table
            Defaults to 'Y Values'.
        verbose (bool, optional): If True, prints detailed information about the
            generated table.Defaults to False.
    Returns:
        vtk.vtkTable: A vtkTable object containing the converted data.
    Raises:
        ValueError: If the input data format is invalid or if the numpy array type is
        not float.
    Notes:
        - The function supports input data in the form of numpy arrays, vtkTable,
            or vtkDataArray.
        - If `y` is a 2D array, multiple y-columns are created in the table, each
            labeled as `y_label_0`, `y_label_1`, etc.
        - The function ensures that the x-axis and y-axis data are compatible in terms
            of dimensions.
    Example:
        >>> x = np.array([1.0, 2.0, 3.0])
        >>> y = np.array([4.0, 5.0, 6.0])
        >>> table = _convert_np_data_to_table(
        ...     x, y, x_label="Time", y_label="Value", verbose=True
        ... )
    """

    assert isinstance(x, np.ndarray), "x must be a numpy array"

    if y is None:
        logger.debug("(x,y) pair not provided, assuming input is y, using np.arange(len(y))")

        if isinstance(x, vtk.vtkTable):
            y = x
            x = np.arange(y.GetNumberOfTuples())

        elif isinstance(x, np.ndarray):
            y = np.asarray(x)
            x = np.arange(y.shape[0]).astype(np.float64)
        elif isinstance(x, (vtk.vtkDataArray)):
            y = x
            x = np.arange(y.GetNumberOfTuples()).astype(np.float64)

        else:
            raise ValueError(
                "Invalid input format. vtkTable, vtkDataArray (int, float, double)"
            )

    if x_label is None:
        x_label = "X Values"
    if y_label is None:
        y_label = "Y Values"

    table = vtk.vtkTable()

    if x.dtype == np.float64:
        arrX = vtk.vtkDoubleArray()
    elif x.dtype == np.float32:
        arrX = vtk.vtkFloatArray()
    else:
        raise ValueError("Invalid Numpy array type. Expected float, got: ", x.dtype)
    arrX.SetName(x_label)
    table.AddColumn(arrX)

    num_points = x.shape[0]

    if isinstance(y, tuple):
        y = np.vstack(y)

    if y.dtype not in [np.float64, np.float32]:
        y = y.astype(np.float64)

    if np.ndim(y) == 1:
        multiple_y = False
        if y.dtype == np.float64:
            arr = vtk.vtkDoubleArray()
        elif y.dtype == np.float32:
            arr = vtk.vtkFloatArray()
        arr = vtk.vtkFloatArray()
        arr.SetName(y_label)
        table.AddColumn(arr)

    elif np.ndim(y) == 2:
        multiple_y = True
        for i in range(y.shape[0]):
            if y.dtype == np.float64:
                arr = vtk.vtkDoubleArray()
            elif y.dtype == np.float32:
                arr = vtk.vtkFloatArray()
            arr.SetName(f"{y_label}_{i}")
            table.AddColumn(arr)

    table.SetNumberOfRows(num_points)
    for i in range(num_points):
        table.SetValue(i, 0, x[i])
        if multiple_y:
            for j in range(y.shape[0]):
                table.SetValue(i, j + 1, y[j, i])
        else:
            table.SetValue(i, 1, y[i])

    if verbose:
        total_columns = table.GetNumberOfColumns()
        total_rows = table.GetNumberOfRows()
        logger.debug(f"Stacked table has {total_columns} columns and {total_rows} rows")
        logger.debug("%s %s %s", "Stacked table", table, sorted(dir(table)))

    return table


def _convert_vtk_data_to_table(x_array, y_array=None, x_label=None, y_label=None):
    """Convert vtk data to table."""
    if x_label is None:
        x_label = "X values"
    if y_label is None:
        y_label = "Y values"

    table = vtk.vtkTable()
    if x_array.GetName() is None:
        x_array.SetName(x_label)
    table.AddColumn(x_array)

    if y_array is not None:
        if isinstance(y_array, tuple):
            for i in range(len(y_array)):
                if y_array[i].GetName() is None:
                    y_array[i].SetName(f"{y_label}_{i}")
                table.AddColumn(y_array[i])
        else:
            if y_array.GetName() is None:
                y_array.SetName(y_label)
            table.AddColumn(y_array)

    return table


def _determine_marker_style(marker_style):
    """
    Determines the VTK marker style based on the input marker style.
    This function maps a given marker style (either as an integer or a string)
    to its corresponding VTK marker style. If the input is already an integer,
    it is returned directly. For string inputs, a predefined mapping is used
    to convert the string to the appropriate VTK marker style. The mapping is
    case-insensitive, and default behavior is to return the VTK circle marker
    style if the input is not recognized.
    Args:
        marker_style (int or str): The marker style to be converted. It can be
            an integer representing a VTK marker style or a string representing
            a common marker style name.
    Returns:
        int: The corresponding VTK marker style. Defaults to `vtk.vtkPlotPoints.CIRCLE`
            if the input is not recognized.
    Raises:
        AttributeError: If `marker_style` is a string and the `vtk` module or
            its attributes are not properly defined.
    """

    if isinstance(marker_style, int):
        # If the marker_style is already an int, return it directly
        return marker_style

    # Define a mapping from string marker styles to VTK marker styles
    marker_style_map = {
        "circle": vtk.vtkPlotPoints.CIRCLE,
        "o": vtk.vtkPlotPoints.CIRCLE,
        "cross": vtk.vtkPlotPoints.CROSS,
        "x": vtk.vtkPlotPoints.CROSS,
        "diamond": vtk.vtkPlotPoints.DIAMOND,
        "d": vtk.vtkPlotPoints.DIAMOND,
        "plus": vtk.vtkPlotPoints.PLUS,
        "+": vtk.vtkPlotPoints.PLUS,
        "square": vtk.vtkPlotPoints.SQUARE,
        "s": vtk.vtkPlotPoints.SQUARE,
        "none": vtk.vtkPlotPoints.NONE,
        "": vtk.vtkPlotPoints.NONE,
    }

    return marker_style_map.get(marker_style.lower(), vtk.vtkPlotPoints.CIRCLE)


def _determine_line_style(line_style):
    """
    Determines the VTK line style corresponding to the given input.
    This function maps a given line style (either as an integer or a string)
    to its corresponding VTK line style constant. It supports various string
    representations of line styles, including common matplotlib equivalents.
    Args:
        line_style (int or str): The line style to be converted. It can be an
            integer representing a VTK line style constant or a string
            representing a line style (e.g., 'solid', '--', 'dotted').
    Returns:
        int: The corresponding VTK line style constant. If the input is not
        recognized, it defaults to `vtk.vtkPen.SOLID_LINE`.
    Supported Line Styles:
        - 'solid', '-', 'solid_line': Solid line.
        - 'dash', '--', 'dashed', 'dashed_line': Dashed line.
        - 'dot', ':', 'dotted', 'dotted_line': Dotted line.
        - 'dashdot', '-.': Dash-dot line.
        - 'dashdotdot': Dash-dot-dot line.
        - 'none', '': No line.
    Note:
        The function performs case-insensitive matching for string inputs.
    """

    if isinstance(line_style, int):
        # If the line_style is already an int, return it directly
        return line_style

    # Define a mapping from string line styles to VTK line styles,
    # including matplotlib equivalents
    line_style_map = {
        "solid": vtk.vtkPen.SOLID_LINE,
        "-": vtk.vtkPen.SOLID_LINE,
        "solid_line": vtk.vtkPen.SOLID_LINE,
        "dash": vtk.vtkPen.DASH_LINE,
        "dashed": vtk.vtkPen.DASH_LINE,
        "--": vtk.vtkPen.DASH_LINE,
        "dashed_line": vtk.vtkPen.DASH_LINE,
        "dot": vtk.vtkPen.DOT_LINE,
        "dotted": vtk.vtkPen.DOT_LINE,
        ":": vtk.vtkPen.DOT_LINE,
        "dotted_line": vtk.vtkPen.DOT_LINE,
        "dashdot": vtk.vtkPen.DASH_DOT_LINE,
        "-.": vtk.vtkPen.DASH_DOT_LINE,
        "dashdotdot": vtk.vtkPen.DASH_DOT_DOT_LINE,
        "none": vtk.vtkPen.NO_PEN,
        "": vtk.vtkPen.NO_PEN,
    }

    # Convert the input line_style to lowercase for case-insensitive matching

    return line_style_map.get(line_style.lower(), vtk.vtkPen.SOLID_LINE)


class ErrorBar:
    """
    A class to represent error bars for visualizing uncertainties in data.
    Attributes:
        positions (list or numpy.ndarray): The positions of the error bars.
        error_x (list or numpy.ndarray, optional): The x-axis error values.
            Can be a 1D array for symmetric errors or a 2D array for asymmetric errors.
            Defaults to None.
        error_y (list or numpy.ndarray, optional): The y-axis error values.
            Can be a 1D array for symmetric errors or a 2D array for asymmetric errors.
            Defaults to None.
        color (str, optional): The color of the error bars. Defaults to "black".
        error_width (float, optional): The width of the error bar symbols.
            Defaults to 0.02.
        symbol_thickness (float, optional): The thickness of the error bar symbols.
            Defaults to 0.1.
        fixed_size (bool, optional): Whether the error bar symbols have a fixed size.
            Defaults to False.
        polydata (vtk.vtkPolyData): The polydata representation of the error bars.
        axes (object, optional): The axes associated with the error bars.
        Defaults to None.
    Methods:
        Initialize(vtkSelf):
            Initializes the error bar object. Returns True.
        SetAxes(axes):
            Sets the axes for the error bars.
        build_I_symbol():
            Builds the polydata representation of the error bar symbols.
        convert_xy_to_screen(x, y):
            Converts data coordinates to screen coordinates.
        scale_polydata(polydata):
            Scales the polydata points to screen coordinates.
        Paint(vtkSelf, context2D):
            Paints the error bars on the given 2D context.
        __repr__():
            Returns a string representation of the ErrorBar object.
    """

    def __init__(
        self,
        positions,
        error_x=None,
        error_y=None,
        color="black",
        error_width=0.02,
        symbol_thickness=0.1,
        fixed_size=False,
        opacity=1.0
    ):
        """Initialize the instance."""
        self.positions = positions
        self.color = color_to_RGBA_255(color)[:3]
        self.error_y = error_y
        self.error_x = error_x
        self.error_width = error_width
        self.symbol_thickness = symbol_thickness
        self.fixed_size = fixed_size
        self.opacity = opacity
        self.points = vtk.vtkPoints()
        self.polydata = self.build_symbols()

        self.axes = None

    def Initialize(self, vtkSelf):
        """Execute the initialize operation."""
        return True

    def SetAxes(self, axes):
        """Execute the set axes operation."""
        self.axes = axes

    def confine_point_to_bounds(self, point, x_limits, y_limits):

        """Execute the confine point to bounds operation."""
        if x_limits is not None:
            if point[0] > x_limits[1]:
                point[0] = x_limits[1]
            if point[0] < x_limits[0]:
                point[0] = x_limits[0]
        if y_limits is not None:
            if point[1] > y_limits[1]:
                point[1] = y_limits[1]
            if point[1] < y_limits[0]:
                point[1] = y_limits[0]

        return point
    

    def add_cells_in_bounds(self, np_line_points, x_limits=None, y_limits=None):

        
        """Add cells in bounds."""
        cell_length = 0
        valid_cells = []

        cells = [
            [0, 1],
            [2, 3],
            [4, 5],
        ]

        in_bounds = np.zeros((np_line_points.shape[0], 2))

        for p, point in enumerate(np_line_points):
            # in_bounds[p, :] = np.asarray([True, True])
            if x_limits is not None:
                if point[0] < x_limits[0]:
                    in_bounds[p, 0] = -1
                elif point[0] > x_limits[1]:
                    in_bounds[p, 0] = 1
            if y_limits is not None:
                if point[1] < y_limits[0]:
                    in_bounds[p, 1] = -1
                elif point[1] > y_limits[1]:
                    in_bounds[p, 1] = 1

        for cell in cells:
            if np.all(in_bounds[cell[0]] == 0):
                if np.all(in_bounds[cell[1]] == 0): # both points are in bounds
                    new_cell = [cell_length, cell_length + 1]
                    self.points.InsertNextPoint(np_line_points[cell[0]][0], np_line_points[cell[0]][1], np_line_points[cell[0]][2])
                    self.points.InsertNextPoint(np_line_points[cell[1]][0], np_line_points[cell[1]][1], np_line_points[cell[1]][2])
                    valid_cells.append(new_cell)
                    cell_length += 2
                else: # only first point is in bounds
                    new_cell = [cell_length, cell_length + 1]
                    self.points.InsertNextPoint(np_line_points[cell[0]][0], np_line_points[cell[0]][1], np_line_points[cell[0]][2])
                    out_of_bounds_point = np.asarray([np_line_points[cell[1]][0], np_line_points[cell[1]][1], np_line_points[cell[1]][2]])
                    self.points.InsertNextPoint(*self.confine_point_to_bounds(out_of_bounds_point, x_limits, y_limits))
                    valid_cells.append(new_cell)
                    cell_length += 2

            elif np.all(in_bounds[cell[1]] == 0): # only second point is in bounds
                new_cell = [cell_length, cell_length + 1]
                out_of_bounds_point = np.asarray([np_line_points[cell[0]][0], np_line_points[cell[0]][1], np_line_points[cell[0]][2]])
                self.points.InsertNextPoint(*self.confine_point_to_bounds(out_of_bounds_point, x_limits, y_limits))
                self.points.InsertNextPoint(np_line_points[cell[1]][0], np_line_points[cell[1]][1], np_line_points[cell[1]][2])
                valid_cells.append(new_cell)
                cell_length += 2

            elif np.any(in_bounds[cell[0]] != in_bounds[cell[1]]): # the special case where both points are out of bounds but on opposite sides
                if (in_bounds[cell[0]][0] == 0 and in_bounds[cell[1]][0] == 0) or (in_bounds[cell[0]][1] == 0 and in_bounds[cell[1]][1] == 0): # one of the dimensions must be in bounds  
                    new_cell = [cell_length, cell_length + 1]
                    out_of_bounds_point_1 = np.asarray([np_line_points[cell[0]][0], np_line_points[cell[0]][1], np_line_points[cell[0]][2]])
                    out_of_bounds_point_2 = np.asarray([np_line_points[cell[1]][0], np_line_points[cell[1]][1], np_line_points[cell[1]][2]])
                    self.points.InsertNextPoint(*self.confine_point_to_bounds(out_of_bounds_point_1, x_limits, y_limits))
                    self.points.InsertNextPoint(*self.confine_point_to_bounds(out_of_bounds_point_2, x_limits, y_limits))
                    valid_cells.append(new_cell)
                    cell_length += 2

        return valid_cells


    def build_symbols(self, x_limits=None, y_limits=None):
        """Build symbols."""
        pd = vtk.vtkPolyData()

        colors = vtk.vtkUnsignedCharArray()
        colors.SetNumberOfComponents(4)

        self.points = vtk.vtkPoints()

        if self.fixed_size:
            half_width = self.error_width / 2.0
            half_thickness = self.symbol_thickness / 2.0

            np_points = np.asarray(
                [
                    [-half_width, (self.error_height + half_thickness), 0.0],
                    [half_width, (self.error_height + half_thickness), 0.0],
                    [half_width, (self.error_height - half_thickness), 0.0],
                    [half_thickness, (self.error_height - half_thickness), 0.0],
                    [half_thickness, (-self.error_height + half_thickness), 0.0],
                    [half_width, (-self.error_height + half_thickness), 0.0],
                    [half_width, (-self.error_height - half_thickness), 0.0],
                    [-half_width, (-self.error_height - half_thickness), 0.0],
                    [-half_width, (-self.error_height + half_thickness), 0.0],
                    [-half_thickness, (-self.error_height + half_thickness), 0.0],
                    [-half_thickness, (self.error_height - half_thickness), 0.0],
                    [-half_width, (self.error_height - half_thickness), 0.0],
                ]
            )

            cell_length = np_points.shape[0]

            positions = np.asarray(self.positions)
            positions = np.hstack(
                (positions, np.zeros(positions.shape[0])[:, np.newaxis])
            )

            np_points = np.tile(np_points, (positions.shape[0], 1, 1))
            np_points = np_points + positions[:, np.newaxis, :]

            polygons = vtk.vtkCellArray()
            pts = vtk.vtkPoints()
            offset = 0

            for symbol in np_points:
                for point in symbol:
                    pts.InsertNextPoint(point[0], point[1], point[2])

                cells = [
                    [0, 1, 2, 0],
                    [0, 2, 11, 0],
                    [3, 4, 9, 3],
                    [3, 9, 10, 3],
                    [5, 6, 8, 5],
                    [6, 7, 8, 6],
                ]

                cells = np.asarray(cells) + offset
                offset += cell_length

                for cell in cells:
                    polygons.InsertNextCell(len(cell) - 1)
                    for point in cell[:-1]:
                        polygons.InsertCellPoint(point)
                    colors.InsertNextTypedTuple(color_to_RGBA_255(self.color, opacity=self.opacity))

            pd.SetPoints(pts)
            pd.SetPolys(polygons)
            pd.GetCellData().SetScalars(colors)

        else:

            half_width = self.error_width / 2.0

            positions = np.asarray(self.positions)

            positions = np.hstack(
                (positions, np.zeros(positions.shape[0])[:, np.newaxis])
            )

            offset = 0
            lines = vtk.vtkCellArray()

            if self.error_x is not None:
                for e, error_position in enumerate(positions):
                    if np.ndim(self.error_x) == 1:
                        pos_error_height = self.error_x[e]
                        neg_error_height = self.error_x[e]
                    else:
                        pos_error_height = self.error_x[e, 0]
                        neg_error_height = self.error_x[e, 1]

                    np_line_points = np.asarray(
                        [
                            [-neg_error_height, half_width, 0.0],
                            [-neg_error_height, -half_width, 0.0],
                            [pos_error_height, half_width, 0.0],
                            [pos_error_height, -half_width, 0.0],
                            [-neg_error_height, 0.0, 0.0],
                            [pos_error_height, 0.0, 0.0],
                        ]
                    )

                    np_line_points = np_line_points + error_position

                    valid_cells = self.add_cells_in_bounds(np_line_points, x_limits=x_limits, y_limits=y_limits)

                    cells = np.asarray(valid_cells) + offset

                    offset += cells.size

                    for cell in cells:
                        lines.InsertNextCell(2)
                        for point in cell:
                            lines.InsertCellPoint(point)
                        colors.InsertNextTypedTuple(color_to_RGBA_255(self.color, self.opacity))

            if self.error_y is not None:
                for e, error_position in enumerate(positions):
                    if np.ndim(self.error_y) == 1:
                        pos_error_height = self.error_y[e]
                        neg_error_height = self.error_y[e]
                    else:
                        pos_error_height = self.error_y[e, 0]
                        neg_error_height = self.error_y[e, 1]

                    np_line_points = np.asarray(
                        [
                            [-half_width, pos_error_height, 0.0],
                            [half_width, pos_error_height, 0.0],
                            [-half_width, -neg_error_height, 0.0],
                            [half_width, -neg_error_height, 0.0],
                            [0, pos_error_height, 0.0],
                            [0, -neg_error_height, 0.0],
                        ]
                    )

                    np_line_points = np_line_points + error_position

                    valid_cells = self.add_cells_in_bounds(np_line_points, x_limits=x_limits, y_limits=y_limits)

                    cells = np.asarray(valid_cells) + offset
                    offset += cells.size

                    for cell in cells:
                        lines.InsertNextCell(2)
                        for point in cell:
                            lines.InsertCellPoint(point)
                        colors.InsertNextTypedTuple(color_to_RGBA_255(self.color, self.opacity))

            pd.SetPoints(self.points)
            pd.SetLines(lines)
            pd.GetCellData().SetScalars(colors)

        return pd


    def convert_xy_to_screen(self, x, y):
        """Convert xy to screen."""
        pixel_offset = self.pixel_offset
        xy_offset = self.xy_offset
        scale = self.scale

        px = ((x - xy_offset[0]) * scale[0]) + pixel_offset[0]
        py = ((y - xy_offset[1]) * scale[1]) + pixel_offset[1]

        return px, py


    def scale_polydata(self, polydata):
        """Execute the scale polydata operation."""
        points = polydata.GetPoints()
        new_points = vtk.vtkPoints()

        for i in range(points.GetNumberOfPoints()):
            point = points.GetPoint(i)
            point2D = self.convert_xy_to_screen(point[0], point[1])
            new_points.InsertNextPoint(point2D[0], point2D[1], 0.0)

        polydata.SetPoints(new_points)

        return polydata


    def Paint(self, vtkSelf, context2D):
        """Execute the paint operation."""
        parent = vtkSelf.GetParent()

        xaxis = parent.GetAxis(1)
        yaxis = parent.GetAxis(0)

        xp1 = xaxis.GetPoint1()
        xp2 = xaxis.GetPoint2()

        xmin = xaxis.GetMinimum()
        xmax = xaxis.GetMaximum()

        yp1 = yaxis.GetPoint1()
        yp2 = yaxis.GetPoint2()

        ymin = yaxis.GetMinimum()
        ymax = yaxis.GetMaximum()

        

        self.pixel_offset = [xp1[0], yp1[1]]
        self.xy_offset = [xmin, ymin]
        self.scale = [
            (xp2[0] - xp1[0]) / (xmax - xmin),
            (yp2[1] - yp1[1]) / (ymax - ymin),
        ]


        pen = context2D.GetPen()
        brush = context2D.GetBrush()

        pen.SetWidth(self.symbol_thickness)
        pen.SetOpacity(int(self.opacity * 255))
        pen.SetColor(self.color)

        brush.SetColor(self.color)
        brush.SetOpacity(int(self.opacity * 255))

        new_polydata = self.build_symbols(x_limits=(xmin, xmax), y_limits=(ymin, ymax))
        scaled_polydata = self.scale_polydata(new_polydata)

        context2D.DrawPolyData(
            0.0,
            0.0,
            scaled_polydata,
            self.polydata.GetCellData().GetScalars(),
            vtk.VTK_SCALAR_MODE_USE_CELL_DATA,
        )

        return True

    def __repr__(self):
        """Return the developer-facing representation."""
        return f"ErrorBar(centre={self.centre}, color={self.color},\
        error_height={self.error_height}, error_width={self.error_width}\
        symbol_thickness={self.symbol_thickness},\n {self.axes})"


def set_x_axis_limits(input_plot, min_val, max_val, forced=True):
    """
    Sets the limits of the X-axis for a given plot object.
    This function adjusts the range, minimum, and maximum values of the X-axis
    for various types of VTK plot objects. It ensures that the X-axis is properly
    configured with the specified limits.
    Args:
        input_plot: The plot object whose X-axis limits need to be set.
            Supported types include:
            - vtk.vtkOpenGLContextActor
            - vtk.vtkContextActor
            - vtk.vtkChartXY
            - vtk.vtkContextScene
        min_val (float): The minimum value for the X-axis.
        max_val (float): The maximum value for the X-axis.
        forced (bool): If True, enforces the limits on zooming rigidly.
    Raises:
        ValueError: If the input plot does not have an X-axis
            or is of an unsupported type.
    Notes:
        - The function modifies the X-axis range and limits directly on the input plot.
        - The `Modified` method is called on the axis to ensure the changes take effect.
    """
    # A multipanel XYChart (or ChartView/ChartPanel): its own API.
    chart = _xy_chart(input_plot)
    if chart is not None:
        return chart.axisX().setRange(min_val, max_val)

    if isinstance(
        input_plot, (vtk.vtkContextActor, vtk.vtkOpenGLContextActor, vtk.vtkContextView)
    ):
        input_plot = input_plot.GetScene().GetItem(0)
    elif isinstance(input_plot, vtk.vtkChartXY):
        pass
    elif isinstance(input_plot, vtk.vtkContextScene):
        input_plot = input_plot.GetItem(0)

    if hasattr(input_plot, "GetAxis"):
        axis = input_plot.GetAxis(1)
    elif hasattr(input_plot, "GetXAxis"):
        axis = input_plot.GetXAxis()
    else:
        logger.debug("%s", input_plot)
        raise ValueError("Input plot does not have an X axis")

    axis.SetRange(min_val, max_val)
    axis.SetMinimum(min_val)
    axis.SetMaximum(max_val)
    if forced:
        axis.SetMinimumLimit(min_val)
        axis.SetMaximumLimit(max_val)

    axis.Modified()


def set_y_axis_limits(input_plot, min_val, max_val, forced=True):
    """
    Sets the Y-axis limits for a given input plot.
    This function adjusts the range, minimum, and maximum values of the Y-axis
    for a specified input plot object. It supports various types of VTK plot
    objects, including vtkOpenGLContextActor, vtkContextActor, vtkChartXY,
    and vtkContextScene.
    Parameters:
        input_plot (vtk.vtkObject): The input plot object whose Y-axis limits
            need to be set. This can be an instance of vtkOpenGLContextActor,
            vtkContextActor, vtkChartXY, or vtkContextScene.
        min_val (float): The minimum value for the Y-axis.
        max_val (float): The maximum value for the Y-axis.
        forced (bool): If True, enforces the limits on zooming rigidly.
    Raises:
        ValueError: If the input plot does not have a Y-axis.
    Notes:
        - The function modifies the Y-axis range and limits directly on the
          provided plot object.
        - The input plot is internally resolved to its appropriate axis object
          based on its type.
    """
    # A multipanel XYChart (or ChartView/ChartPanel): its own API.
    chart = _xy_chart(input_plot)
    if chart is not None:
        return chart.axisY().setRange(min_val, max_val)

    if isinstance(
        input_plot, (vtk.vtkContextActor, vtk.vtkOpenGLContextActor, vtk.vtkContextView)
    ):
        input_plot = input_plot.GetScene().GetItem(0)
    elif isinstance(input_plot, vtk.vtkChartXY):
        pass
    elif isinstance(input_plot, vtk.vtkContextScene):
        input_plot = input_plot.GetItem(0)

    if hasattr(input_plot, "GetAxis"):
        axis = input_plot.GetAxis(0)
    elif hasattr(input_plot, "GetYAxis"):
        axis = input_plot.GetYAxis()
    else:
        raise ValueError("Input plot does not have an Y axis")

    axis.SetRange(min_val, max_val)
    axis.SetMinimum(min_val)
    axis.SetMaximum(max_val)
    if forced:
        axis.SetMinimumLimit(min_val)
        axis.SetMaximumLimit(max_val)

    axis.Modified()


def add_legend(
    input_plot,
    opacity=0.9,
    font_size=20,
    text_color="black",
    background_color=(1, 1, 1),
    bold=False,
    italic=False,
    inline=True,
):
    """
    Adds a customizable legend to a VTK plot.
    Parameters:
        input_plot (vtk.vtkOpenGLContextActor | vtk.vtkContextActor | vtk.vtkChartXY |
          vtk.vtkContextScene):
            The input VTK plot or scene to which the legend will be added.
        opacity (float, optional):
            The opacity of the legend background, ranging from 0.0 (completely
            transparent) to 1.0 (completely opaque).
            Default is 0.9.
        font_size (int, optional):
            The font size of the legend labels. Default is 20.
        text_color (str, optional):
            The color of the legend text, specified as a string (e.g., 'black', 'red').
            Default is 'black'.
        background_color (tuple, optional):
            The background color of the legend, specified as an RGB tuple with values
            ranging from 0 to 1.
            Default is (1, 1, 1) (white).
        bold (bool, optional):
            Whether the legend text should be bold. Default is False.
        italic (bool, optional):
            Whether the legend text should be italicized. Default is False.
        inline (bool, optional):
            Whether the legend should be displayed inline. Default is True.
    Returns:
        None
    Notes:
        - The function modifies the input plot to enable and customize the legend.
        - The `convert_color_to_RGB` and `convert_color_to_RGBA` helper functions are
        assumed to convert color specifications to the appropriate format for VTK.
    """
    # A multipanel XYChart (or ChartView/ChartPanel): its own API.
    chart = _xy_chart(input_plot)
    if chart is not None:
        return chart.setLegendVisible(True)

    if isinstance(input_plot, (vtk.vtkContextActor, vtk.vtkOpenGLContextActor)):
        input_plot = input_plot.GetScene().GetItem(0)
    elif isinstance(input_plot, vtk.vtkChartXY):
        pass
    elif isinstance(input_plot, vtk.vtkContextScene):
        input_plot = input_plot.GetItem(0)

    alpha = int(opacity * 255)

    input_plot.SetShowLegend(True)

    legend = input_plot.GetLegend()

    legend.SetOpacity(opacity)
    legend.SetInteractive(True)
    legend.SetDragEnabled(True)
    legend.SetLabelSize(font_size)
    legend.SetInline(inline)

    label_properties = legend.GetLabelProperties()

    label_properties.SetColor(*color_to_RGB(text_color))
    label_properties.SetFontFamilyToArial()
    label_properties.SetBold(bold)
    label_properties.SetItalic(italic)

    background_brush = legend.GetBrush()
    if VTK_HAS_SETCOLORF:
        background_brush.SetColorF(*color_to_RGB(background_color))
    else:
        background_brush.SetColor(*color_to_RGBA_255(background_color))
    background_brush.SetOpacity(alpha)


def add_gridlines(input_plot, color="black", opacity=1.0, line_width=2.0):
    """
    Adds gridlines to a VTK plot with customizable color, opacity, and line width.
    Parameters:
        input_plot (vtk.vtkObject): The VTK plot object to which gridlines will be
            added.
            Supported types include vtkOpenGLContextActor, vtkContextActor, vtkChartXY,
            and vtkContextScene.
        color (str): The color of the gridlines, specified as a string
            (default: 'black').
        opacity (float): The opacity of the gridlines, ranging from 0.0
            (fully transparent) to 1.0 (fully opaque) (default: 1.0).
        line_width (float): The width of the gridlines (default: 2.0).
    Notes:
        - The function determines the type of the input plot and applies gridline
            settings accordingly.
        - The function checks for VTK version compatibility to use appropriate methods
          for setting gridline colors and properties.
        - The `convert_color_to_RGB` function is assumed to convert the color string to
          an RGB tuple.
    Raises:
        AttributeError: If the input_plot does not have the expected methods for setting
            gridline properties.
    """
    # A multipanel XYChart (or ChartView/ChartPanel): its own API.
    chart = _xy_chart(input_plot)
    if chart is not None:
        chart.axisX().setGridVisible(True)
        return chart.axisY().setGridVisible(True)

    if isinstance(input_plot, (vtk.vtkContextActor, vtk.vtkOpenGLContextActor)):
        input_plot = input_plot.GetScene().GetItem(0)
    elif isinstance(input_plot, vtk.vtkChartXY):
        pass
    elif isinstance(input_plot, vtk.vtkContextScene):
        input_plot = input_plot.GetItem(0)

    alpha = int(opacity * 255)

    VTK_HAS_SETCOLORF = (
        vtk.vtkVersion.GetVTKMajorVersion() >= 9
        and vtk.vtkVersion.GetVTKMinorVersion() >= 2
    )

    if hasattr(input_plot, "GetAxis"):
        for i in range(3):
            axis = input_plot.GetAxis(i)
            if VTK_HAS_SETCOLORF:
                axis.GetGridPen().SetColorF(*color_to_RGB(color))
                axis.GetGridPen().SetOpacity(alpha)
                axis.GetGridPen().SetWidth(line_width)
            else:
                axis.GetGridPen().SetColor(*color_to_RGB(color))
                axis.GetGridPen().SetOpacity(alpha)
                axis.GetGridPen().SetWidth(line_width)

    elif hasattr(input_plot, "GetXAxis"):
        if VTK_HAS_SETCOLORF:
            input_plot.GetXAxis().GetGridPen().SetColorF(*color_to_RGB(color))
            input_plot.GetYAxis().GetGridPen().SetColorF(*color_to_RGB(color))
            input_plot.GetXAxis().GetGridPen().SetOpacity(alpha)
            input_plot.GetYAxis().GetGridPen().SetWidth(line_width)
        else:
            input_plot.GetXAxis().GetGridPen().SetColor(*color_to_RGB(color))
            input_plot.GetYAxis().GetGridPen().SetColor(*color_to_RGB(color))
            input_plot.GetXAxis().GetGridPen().SetOpacity(alpha)
            input_plot.GetYAxis().GetGridPen().SetWidth(line_width)


def set_x_axis_title(
    input_plot, title, font_size=20, color="black", bold=False, italic=False
):
    """
    Sets the title of the X-axis for a given VTK plot object.

    Parameters:

        input_plot (vtk.vtkOpenGLContextActor | vtk.vtkContextActor | vtk.vtkChartXY |
        vtk.vtkContextScene):
            The VTK plot object whose X-axis title needs to be set. The function handles
            different types of VTK objects and extracts the appropriate chart or scene
            item.
        title (str):
            The title text to set for the X-axis.
        font_size (int, optional):
            The font size of the X-axis title. Default is 20.
        color (str, optional):
            The color of the X-axis title in string format (e.g., 'black', 'red').
            Default is 'black'.
        bold (bool, optional):
            Whether the X-axis title should be bold. Default is False.
        italic (bool, optional):
            Whether the X-axis title should be italicized. Default is False.
    Raises:
        AttributeError:
            If the input_plot does not have the required methods to access the X-axis.
    Notes:
        - The function assumes that the input_plot is compatible with VTK and ha
          methods to access the X-axis.
        - The `convert_color_to_RGB` function is used to convert the color string to an
            RGB format compatible with VTK.
    """
    # A multipanel XYChart (or ChartView/ChartPanel): its own API.
    chart = _xy_chart(input_plot)
    if chart is not None:
        return chart.axisX().setTitle(title)

    if isinstance(input_plot, (vtk.vtkContextActor, vtk.vtkOpenGLContextActor)):
        input_plot = input_plot.GetScene().GetItem(0)
    elif isinstance(input_plot, vtk.vtkChartXY):
        pass
    elif isinstance(input_plot, vtk.vtkContextScene):
        input_plot = input_plot.GetItem(0)

    if hasattr(input_plot, "GetAxis"):
        axis = input_plot.GetAxis(1)
    elif hasattr(input_plot, "GetXAxis"):
        axis = input_plot.GetXAxis()

    axis.SetTitle(title)
    title_properties = axis.GetTitleProperties()
    title_properties.SetFontSize(font_size)
    title_properties.SetFontFamilyToArial()
    title_properties.SetBold(bold)
    title_properties.SetItalic(italic)
    title_properties.SetColor(color_to_RGB(color))
    axis.Modified()


def set_y_axis_title(
    input_plot, title, font_size=20, color="black", bold=False, italic=False
):
    """
    Sets the title of the Y-axis for a given VTK plot object.

    Parameters:

        input_plot (vtk.vtkOpenGLContextActor | vtk.vtkContextActor | vtk.vtkChartXY |
        vtk.vtkContextScene):
            The VTK plot object whose Y-axis title needs to be set.
            The function supports multiple types of VTK objects.
        title (str):
            The title text to set for the Y-axis.
        font_size (int, optional):
            The font size of the title text. Defaults to 20.
        color (str, optional):
            The color of the title text in string format (e.g., 'black', 'red').
            Defaults to 'black'.
        bold (bool, optional):
            Whether the title text should be bold. Defaults to False.
        italic (bool, optional):
            Whether the title text should be italicized. Defaults to False.
    Raises:
        AttributeError:
            If the input_plot does not have a Y-axis or the required methods to set the
            title.
    Notes:
        - The function automatically determines the type of the input_plot and retrieves
            the appropriate axis object.
        - The color is converted to RGB format using the `convert_color_to_RGB`
            function.
        - The axis is marked as modified after updating the title and its properties.
    """
    # A multipanel XYChart (or ChartView/ChartPanel): its own API.
    chart = _xy_chart(input_plot)
    if chart is not None:
        return chart.axisY().setTitle(title)

    if isinstance(input_plot, (vtk.vtkContextActor, vtk.vtkOpenGLContextActor)):
        input_plot = input_plot.GetScene().GetItem(0)
    elif isinstance(input_plot, vtk.vtkChartXY):
        pass
    elif isinstance(input_plot, vtk.vtkContextScene):
        input_plot = input_plot.GetItem(0)

    if hasattr(input_plot, "GetAxis"):
        axis = input_plot.GetAxis(0)
    elif hasattr(input_plot, "GetYAxis"):
        axis = input_plot.GetYAxis()

    axis.SetTitle(title)
    title_properties = axis.GetTitleProperties()
    title_properties.SetFontSize(font_size)
    title_properties.SetFontFamilyToArial()
    title_properties.SetBold(bold)
    title_properties.SetItalic(italic)
    title_properties.SetColor(color_to_RGB(color))
    axis.Modified()


def set_title(input_plot, title, font_size=20, color="black", bold=False, italic=False):
    """
    Sets the title of a given plot with specified properties.
    Args:
        input_plot: The plot object to which the title will be applied.
        title (str): The text of the title to set.
        font_size (int, optional): The font size of the title. Defaults to 20.
        color (str, optional): The color of the title text. Defaults to 'black'.
        bold (bool, optional): Whether the title text should be bold. Defaults to False.
        italic (bool, optional): Whether the title text should be italicized.
            Defaults to False.
    Returns:
        None
    """
    # A multipanel XYChart (or ChartView/ChartPanel): its own API.
    chart = _xy_chart(input_plot)
    if chart is not None:
        return chart.setTitle(title)

    input_plot.SetTitle(title)

    title_properties = input_plot.GetTitleProperties()
    title_properties.SetFontSize(font_size)
    title_properties.SetFontFamilyToArial()
    title_properties.SetBold(bold)
    title_properties.SetItalic(italic)
    title_properties.SetColor(color_to_RGB(color))


def add_scatter_chart(
    x,
    y=None,
    axes=None,
    figure=None,
    color="blue",
    gridlines_color=None,
    opacity=1.0,
    marker_style="circle",
    marker_size=20,
    y_label="Scatter Points",
    x_label="X Values",
):
    """
    Adds a scatter chart to a given figure or axes.
    Parameters:
        x (array-like): The x-coordinates of the scatter points.
        y (array-like, optional): The y-coordinates of the scatter points.
            If None, defaults to a range of indices.
        axes (vtk.vtkChartXY, optional): The axes to which the scatter chart will be
            added. If None, a new axes object will be created if a figure is provided.
        figure (vtk.vtkContextView, optional): The figure to which the scatter chart
            will be added. If provided, the axes will be retrieved or created within the
            figure.
        color (str, optional): The color of the scatter points. Defaults to 'blue'.
        gridlines_color (str, optional): The color of the gridlines.
            If None, gridlines are not added. Defaults to None.
        opacity (float, optional): The opacity of the scatter points, ranging from 0.0
            (completely transparent) to 1.0 (completely opaque). Defaults to 1.0.
        marker_style (str, optional): The style of the scatter point markers.
            Defaults to 'circle'.
        marker_size (int, optional): The size of the scatter point markers.
            Defaults to 20.
        y_label (str, optional): The label for the y-axis. Defaults to 'Scatter Points'.
        x_label (str, optional): The label for the x-axis. Defaults to 'X Values'.
    Returns:
        vtk.vtkPlot: The scatter plot object added to the axes.
    Notes:
        - If both `axes` and `figure` are None, the function will not create a new
            figure or axes.
        - The function assumes that the `vtk` module and helper functions like
        `_convert_np_data_to_table`,
            `_determine_marker_style`, `convert_color_to_RGBA`, and `add_gridlines`
            are available in the scope.
    """
    # A multipanel XYChart (or ChartView/ChartPanel): its own API.
    chart = _xy_chart(axes, figure)
    if chart is not None:
        x, y = _xy_data(x, y)
        return chart.addScatter(x, y, name=y_label or "",
                                color=_series_colour(color, "steel_blue"))

    if figure is not None:
        total_items = figure.GetScene().GetNumberOfItems()
        for i in range(total_items):
            item = figure.GetScene().GetItem(i)
            if isinstance(item, vtk.vtkChartXY):
                axes = item
                break
        if axes is None:
            logger.warning("Could not find XY axes, creating new one")
            axes = vtk.vtkChartXY()
            figure.GetScene().AddItem(axes)

    if isinstance(x, np.ndarray):
        stacked_table = _convert_np_data_to_table(
            x, y, x_label=x_label, y_label=y_label
        )
    else:
        stacked_table = _convert_vtk_data_to_table(
            x, y, x_label=x_label, y_label=y_label
        )

    scatter_points = axes.AddPlot(vtk.vtkChart.POINTS)
    scatter_points.SetInputData(stacked_table, 0, 1)
    scatter_points.SetScalarVisibility(True)
    scatter_points.SetMarkerSize(marker_size)
    scatter_points.SetMarkerStyle(_determine_marker_style(marker_style))
    scatter_points.SetColor(*color_to_RGBA_255(color, opacity=opacity))

    if gridlines_color is not None:
        add_gridlines(scatter_points, gridlines_color)

    return scatter_points


def add_bar_chart(
    x,
    y=None,
    axes=None,
    figure=None,
    x_label=None,
    y_label=None,
    bar_color="dark_orange",
    gridlines_color=None,
    opacity=1.0,
):
    """
    Adds a bar chart to the specified figure or axes.
    Parameters:
        x (array-like): The data for the x-axis.
        y (array-like, optional): The data for the y-axis. If None, x is assumed to
            contain both x and y data.
        axes (vtk.vtkChartXY, optional): The axes to which the bar chart will be added.
            If None, a new chart is created.
        figure (vtk.vtkContextView, optional): The figure to which the bar chart will
            be added. If provided, axes are retrieved or created from the figure.
        x_label (str, optional): Label for the x-axis (also needed to handle the
            internal conversion to vtkTable).
        y_label (str, optional): Label for the y-axis (also needed to handle the
            internal conversion to vtkTable).
        bar_color (str, optional): Color of the bars. Default is "dark_orange".
        gridlines_color (str, optional): Color of the gridlines. If None, gridlines are
            not added.
        opacity (float, optional): Opacity of the bars. Default is 1.0.
    Returns:
        vtk.vtkPlot: The created bar chart plot.
    """
    # A multipanel XYChart (or ChartView/ChartPanel): its own API.
    chart = _xy_chart(axes, figure)
    if chart is not None:
        x, y = _xy_data(x, y)
        return chart.addBars(x, y, name=y_label or "",
                             color=_series_colour(bar_color, "steel_blue"))

    if figure is not None:
        total_items = figure.GetScene().GetNumberOfItems()
        for i in range(total_items):
            item = figure.GetScene().GetItem(i)
            if isinstance(item, vtk.vtkChartXY):
                axes = item
                break
        if axes is None:
            logger.warning("Could not find XY axes, creating new one")
            axes = vtk.vtkChartXY()
            figure.GetScene().AddItem(axes)

    if isinstance(x, np.ndarray):
        stacked_table = _convert_np_data_to_table(
            x, y, x_label=x_label, y_label=y_label
        )
    else:
        stacked_table = _convert_vtk_data_to_table(
            x, y, x_label=x_label, y_label=y_label
        )

    bar_chart = axes.AddPlot(vtk.vtkChart.BAR)
    bar_chart.SetInputData(stacked_table, 0, 1)
    bar_chart.SetColor(*color_to_RGBA_255(bar_color))
    bar_chart.SetOpacity(opacity)
    bar_chart.SetWidth(0.5)

    if gridlines_color is not None:
        add_gridlines(bar_chart, gridlines_color)

    return bar_chart


def add_line_chart(
    x,
    y=None,
    axes=None,
    figure=None,
    x_label=None,
    y_label=None,
    opacity=1.0,
    line_width=3,
    color="steel_blue",
    gridlines_color=None,
    line_style="solid",
):
    """
    Adds a line chart to a specified figure or axes.

    Parameters:
        x (array-like): The data for the x-axis.
        y (array-like, optional): The data for the y-axis. If None, only x-axis data is
            used.
        axes (vtk.vtkChartXY, optional): The axes to which the line chart will be added.
            If None, a new axes object is created.
        figure (vtk.vtkContextView, optional): The figure to which the line chart will
            be added. If provided, the axes will be retrieved or created from the figure
        x_label (str, optional): Label for the x-axis.
        y_label (str, optional): Label for the y-axis.
        opacity (float, optional): Opacity of the line chart, ranging from 0.0
            (completely transparent) to 1.0 (completely opaque). Default is 1.0.
        line_width (int, optional): Width of the line in the chart. Default is 3.
        color (str, optional): Color of the line in the chart. Default is "steel_blue".
        gridlines_color (str, optional): Color of the gridlines. If None, gridlines
            are not modified.
        line_style (str, optional): Style of the line, e.g., 'solid', 'dashed', etc.
            Default is 'solid'.
    Returns:
        vtk.vtkPlot: The created line chart object.
    """
    # A multipanel XYChart (or ChartView/ChartPanel): its own API.
    chart = _xy_chart(axes, figure)
    if chart is not None:
        x, y = _xy_data(x, y)
        return chart.addLine(x, y, name=y_label or "",
                             color=_series_colour(color, "steel_blue"),
                             width=line_width)

    if figure is not None:
        total_items = figure.GetScene().GetNumberOfItems()
        for i in range(total_items):
            item = figure.GetScene().GetItem(i)
            if isinstance(item, vtk.vtkChartXY):
                axes = item
                break
        if axes is None:
            logger.warning("Could not find XY axes, creating new one")
            axes = vtk.vtkChartXY()
            figure.GetScene().AddItem(axes)

    if isinstance(x, np.ndarray):
        stacked_table = _convert_np_data_to_table(
            x, y, x_label=x_label, y_label=y_label
        )
    else:
        stacked_table = _convert_vtk_data_to_table(
            x, y, x_label=x_label, y_label=y_label
        )

    line_chart = axes.AddPlot(vtk.vtkChart.LINE)
    line_chart.SetInputData(stacked_table, 0, 1)
    line_chart.SetColor(*color_to_RGBA_255(color))
    line_chart.SetWidth(line_width)
    line_chart.GetPen().SetLineType(_determine_line_style(line_style))
    line_chart.SetOpacity(opacity)

    if gridlines_color is not None:
        add_gridlines(line_chart, gridlines_color)

    return line_chart


def add_filled_area_chart(
    x,
    y_lower,
    y_upper,
    axes=None,
    figure=None,
    x_label=None,
    y_label=None,
    color="steel_blue",
    gridlines_color=None,
    opacity=0.5,
):
    """
    Adds a filled area chart to a VTK chart.
    Parameters:
        x (list or numpy.ndarray): The x-axis data points.
        y_lower (list or numpy.ndarray): The lower boundary of the filled area.
        y_upper (list or numpy.ndarray): The upper boundary of the filled area.
        axes (vtk.vtkChartXY, optional): The VTK chart axes to which the filled area
                                        chart will be added.
                                        If None, a new chart will be created.
        figure (vtk.vtkContextView, optional): The VTK figure to which the chart will be
                                                added.
                                                If provided, the axes will be retrieve
                                                or created from the figure.
        x_label (str, optional): Label for the x-axis. Defaults to None.
        y_label (str, optional): Label for the y-axis. Defaults to None.
        color (str, optional): Color of the filled area. Defaults to "steel_blue".
        gridlines_color (str, optional): Color of the gridlines. If None, gridlines are
                                        not added. Defaults to None.
        opacity (float, optional): Opacity of the filled area, ranging from 0
                                    (completely transparent) to 1 (completely opaque).
                                    Defaults to 0.5.
    Returns:
        vtk.vtkPlotArea: The created filled area chart.
    Notes:
        - The function uses VTK's `vtkChartXY` and `vtkPlotArea` to create the filled
        area chart.
        - The color and opacity are applied to the chart's brush.
        - If the VTK version is 9.2 or higher, `SetColorF` is used for setting the color
        with floating-point values.
        - Gridlines can be added if `gridlines_color` is specified.
    """

    if figure is not None:
        total_items = figure.GetScene().GetNumberOfItems()
        for i in range(total_items):
            item = figure.GetScene().GetItem(i)
            if isinstance(item, vtk.vtkChartXY):
                axes = item
                break
        if axes is None:
            logger.warning("Could not find XY axes, creating new one")
            axes = vtk.vtkChartXY()
            figure.GetScene().AddItem(axes)

    if isinstance(x, np.ndarray):
        stacked_table = _convert_np_data_to_table(
            x, (y_lower, y_upper), x_label=x_label, y_label=y_label
        )

    else:
        stacked_table = _convert_vtk_data_to_table(
            x, (y_lower, y_upper), x_label=x_label, y_label=y_label
        )

    filled_area_chart = axes.AddPlot(vtk.vtkChart.AREA)
    filled_area_chart.SetInputData(stacked_table)
    filled_area_chart.SetInputArray(0, stacked_table.GetColumnName(0))
    filled_area_chart.SetInputArray(1, stacked_table.GetColumnName(1))
    filled_area_chart.SetInputArray(2, stacked_table.GetColumnName(2))
    fill_color = color_to_RGBA_255(color, opacity)

    filled_area_chart.SetColor(*fill_color)

    if gridlines_color is not None:
        add_gridlines(filled_area_chart, gridlines_color)

    return filled_area_chart


def add_errorbar_plot(
    x, y, figure=None, axes=None, y_errors=None, x_errors=None,
    error_width=0.2, line_thickness=4, line_color="blue", opacity=0.5
):
    """
    Adds an error bar plot to a given VTK figure.
    Parameters:
        x (array-like or vtk.vtkDataArray): The x-coordinates of the data points.
            Can be a NumPy array or a VTK data array.
        y (array-like or vtk.vtkDataArray): The y-coordinates of the data points.
            Can be a NumPy array or a VTK data array.
        figure (vtk.vtkChartXY): The VTK figure to which the error bar plot will be
            added.
        y_errors (array-like, optional): The y-axis error values. If provided, must be
            broadcastable to the shape of `x`. Defaults to None.
        x_errors (array-like, optional): The x-axis error values. If provided, must be
            broadcastable to the shape of `y`. Defaults to None.
        error_width (float, optional): The width of the error bars. Defaults to 0.2.
        line_thickness (float, optional): The thickness of the error bar lines.
            Defaults to 4.
    Notes:
        - This function converts VTK data arrays to NumPy arrays if necessary.
        - If the error arrays have a single value, they will be repeated to match the
            size of the data points.
        - The error bar plot is added as a `vtkPythonItem` to the first `vtkChartXY`
            found in the figure's scene.
    Returns:
        None
    """
    if isinstance(x, np.ndarray):
        x = x.flatten()
    if isinstance(y, np.ndarray):
        y = y.flatten()

    if isinstance(x, vtk.vtkDataArray):
        x = numpy_support.vtk_to_numpy(x)
    if isinstance(y, vtk.vtkDataArray):
        y = numpy_support.vtk_to_numpy(y)


    if x_errors is not None:
        x_errors = np.array(x_errors)
        if np.ndim(x_errors) == 0:
            x_errors = np.repeat(x_errors, x.shape[0])
    if y_errors is not None:
        y_errors = np.array(y_errors)
        if np.ndim(y_errors) == 0:
            y_errors = np.repeat(y_errors, y.shape[0])

    positions = np.vstack((x, y)).T

    errorbar_item = vtk.vtkPythonItem()

    errorbar = ErrorBar(
        positions,
        error_x=x_errors,
        error_y=y_errors,
        error_width=error_width,
        symbol_thickness=line_thickness,
        color=line_color,
        fixed_size=False,
        opacity=opacity
    )

    errorbar_item.SetPythonObject(errorbar)
    errorbar_item.SetOpacity(opacity)
    errorbar_item.SetVisible(True)


    scene = axes.GetScene()

    total_items = scene.GetNumberOfItems()


    if figure is not None:
        total_items = figure.GetScene().GetNumberOfItems()
        for i in range(total_items):
            item = figure.GetScene().GetItem(i)
            if isinstance(item, vtk.vtkChartXY):
                axes = item
                break
        if axes is None:
            logger.warning("Could not find XY axes, creating new one")
            axes = vtk.vtkChartXY()
            figure.GetScene().AddItem(axes)

    if axes is not None:
        axes.AddItem(errorbar_item)
        
        # errorbar_item.
    else:
        raise RuntimeError("Could not find a ChartXY in the provided figure.")


def imshow(
    data,
    axes=None,
    figure=None,
    title_color=(0, 0, 0),
    label_color=(0, 0, 0),
    x_label=None,
    y_label=None,
    extent=None,
    colormap="viridis",
):
    """
    Displays a 2D histogram chart.
    Parameters:
        data (numpy.ndarray): The 2D data to be displayed in the histogram.
        axes (vtk.vtkChartHistogram2D, optional): The chart axes to be used. If None,
                                                a new vtkChartHistogram2D is created.
        figure (vtk.vtkContextView, optional): The figure or context view to which the
            chart will be added. If provided,
            the chart is added to the scene of the figure.
        title_color (tuple, optional): RGB color tuple for the chart title.
            Default is (0, 0, 0) (black).
        label_color (tuple, optional): RGB color tuple for the axis labels.
            Default is (0, 0, 0) (black).
        x_label (str, optional): Title for the X-axis. If None, no title is set.
        y_label (str, optional): Title for the Y-axis. If None, no title is set.
    Behavior:
        - Configures the chart's title, axis titles, and label properties
            (font size and color).
        - Generates a 2D dataset with random values between -100 and 100.
        - Sets the dataset as input to the chart.
        - Configures a color transfer function for the chart to map data values to
            colors.
        - Adds the chart to the provided figure's scene.
    Notes:
        - The function assumes that the `convert_color_to_RGB` utility is available for
            converting color tuples.
        - The function uses NumPy for generating random data and VTK for visualization.
    """

    if figure is not None:
        axes = figure.GetScene().GetItem(0)
        if axes is None:
            axes = vtk.vtkChartHistogram2D()
    figure.GetScene().AddItem(axes)

    # axes.SetTitle(title)
    axes.GetTitleProperties().SetFontSize(36)
    axes.GetTitleProperties().SetColor(color_to_RGB(title_color))
    axes.GetTitleProperties().SetBold(False)

    axes.GetAxis(0).GetTitleProperties().SetFontSize(24)
    axes.GetAxis(0).GetTitleProperties().SetColor(color_to_RGB(title_color))
    axes.GetAxis(0).GetLabelProperties().SetColor(color_to_RGB(label_color))
    axes.GetAxis(0).GetLabelProperties().SetFontSize(18)
    axes.GetAxis(0).GetLabelProperties().BoldOff()
    if x_label is not None:
        axes.GetAxis(0).SetTitle(x_label)

    axes.GetAxis(1).GetTitleProperties().SetFontSize(24)
    axes.GetAxis(1).GetTitleProperties().SetColor(color_to_RGB(title_color))
    axes.GetAxis(1).GetLabelProperties().SetColor(color_to_RGB(label_color))
    axes.GetAxis(1).GetLabelProperties().SetFontSize(18)
    axes.GetAxis(1).GetLabelProperties().BoldOff()
    if y_label is not None:
        axes.GetAxis(1).SetTitle(y_label)

    # axes.GetAxis(2).GetTitleProperties().SetFontSize(24)
    # axes.GetAxis(2).GetTitleProperties().SetColor(color_to_RGB(title_color))
    # axes.GetAxis(2).GetLabelProperties().SetColor(color_to_RGB(label_color))
    # axes.GetAxis(2).GetLabelProperties().SetFontSize(18)
    # axes.GetAxis(2).GetLabelProperties().BoldOff()
    # axes.GetAxis(2).SetTitle("Z Axis")

    # third_axis = axes.GetAxis(2)



    figure.GetScene().AddItem(axes)

    if isinstance(data, np.ndarray):
        x_size = data.shape[0]
        y_size = data.shape[1]

        vtk_data = vtk.vtkImageData()
        vtk_data.SetDimensions(x_size, y_size, 1)
        vtk_data.AllocateScalars(vtk.VTK_DOUBLE, 1)

        if extent is not None:
            # vtk_data.SetExtent(extent[0], extent[1], extent[2], extent[3], 0, 0)
            origin = extent[0], extent[2], 0
            vtk_data.SetOrigin(origin)
            spacing = (
                (extent[1] - extent[0]) / x_size,
                (extent[3] - extent[2]) / y_size,
                1,
            )
            vtk_data.SetSpacing(spacing)

        for y in range(y_size):
            for x in range(x_size):
                vtk_data.SetScalarComponentFromDouble(x, y, 0, 0, float(data[y, x]))

    elif isinstance(data, vtk.vtkImageData):
        vtk_data = data
    else:
        raise TypeError("Data must be a numpy array or vtkImageData")

    axes.SetInputData(vtk_data)

    LUT = make_LUT(colormap=colormap, total_colors=256)

    axes.SetTransferFunction(LUT)


def add_box_plot(values, axes=None, figure=None):
    """
    Adds a box plot to the specified axes .
    This function creates a box plot chart and populates it with
    predefined data. If a figure is provided, the box plot is added to the
    figure's scene. If axes are not provided, they are created automatically.
    Parameters:
        axes (vtk.vtkChartBox, optional): The axes to which the box plot will
            be added. If None, axes will be created or retrieved from the figure.
        figure (vtk.vtkContextView, optional): The figure to which the box plot
            will be added. If provided, the axes will be retrieved or created
            within the figure's scene.
    Returns:
        vtk.vtkChartBox: The axes containing the box plot.
    Notes:
        - The function assumes that VTK is properly installed and imported.
    """

    if figure is not None:
        axes = figure.GetScene().GetItem(0)
        if axes is None:
            axes = vtk.vtkChartBox()
        figure.GetScene().AddItem(axes)

    # Creates a vtkPlotBox input table.
    num_param = 5
    input_box_plot_table = vtk.vtkTable()

    for i in range(num_param):
        run = f"Run {i:d}"
        arr_index = vtk.vtkIntArray()
        arr_index.SetName(run)
        input_box_plot_table.AddColumn(arr_index)

    input_box_plot_table.SetNumberOfRows(len(values))

    for j in range(len(values)):
        for i in range(5):
            input_box_plot_table.SetValue(j, i, values[j][i])

    quartiles = vtk.vtkComputeQuartiles()
    quartiles.SetInputData(vtk.vtkStatisticsAlgorithm.INPUT_DATA, input_box_plot_table)
    quartiles.Update()

    out_table = quartiles.GetOutput()
    lookup = vtk.vtkLookupTable()
    lookup.SetNumberOfColors(num_param)
    lookup.SetTableRange(0, num_param - 1)

    lookup.Build()

    axes.GetPlot(0).SetInputData(out_table)
    axes.SetColumnVisibilityAll(True)

    # Set the labels.
    labels = vtk.vtkStringArray()
    labels.SetNumberOfValues(num_param)
    for i in range(num_param):
        run = f"Run {i:d}"
        labels.SetValue(i, run)
    axes.GetPlot(0).SetLabels(labels)

    return axes


def add_pie_chart(figure, values, labels, axes=None, title="Pie Chart"):
    """
    Adds a pie chart to a given VTK figure.
    Parameters:
        figure (vtk.vtkContextView): The VTK figure to which the pie chart will be
            added.
        axes (vtk.vtkChartPie, optional): The pie chart axes. If None, a new vtkChartPie
            instance will be created. Defaults to None.
        title (str, optional): The title of the pie chart. Defaults to 'Pie Chart'.
        values (list of int, optional): A list of integer values representing the data
            for the pie chart. Defaults to None.
        labels (list of str, optional): A list of string labels corresponding to the pie
            chart values. Defaults to None.
    Returns:
        vtk.vtkPlotPie: The created pie chart plot.
    Notes:
        - The function assumes that the `figure` parameter is a valid VTK context view.
        - The `values` and `labels` lists must have the same length.
        - The pie chart uses a warm color scheme by default.
        - the axes parameter is not vtkChartXY, it is vtkChartPie which is a subclass of
            vtkChart.
    """

    if figure is not None:
        axes = figure.GetScene().GetItem(0)
        if axes is None:
            axes = vtk.vtkChartPie()
        figure.GetScene().AddItem(axes)

    # stacked_table = _convert_np_data_to_table(x, y, x_label=x_label, y_label=y_label)
    figure.GetScene().AddItem(axes)

    # pie_chart = vtk.vtkPlotPie()
    pie_chart = axes.AddPlot(0)

    logger.debug("%s %s %s", "Pie chart", pie_chart, sorted(dir(pie_chart)))

    arrData = vtk.vtkIntArray()
    labelArray = vtk.vtkStringArray()

    arrData.SetName("pie chart data")

    for i in range(len(values)):
        arrData.InsertNextValue(values[i])
        labelArray.InsertNextValue(labels[i])

    new_table = vtk.vtkTable()

    new_table.AddColumn(arrData)


    colorSeries = vtk.vtkColorSeries()
    colorSeries.SetColorScheme(vtk.vtkColorSeries.WARM)

    axes.SetShowLegend(True)
    axes.SetTitle(title)
    axes.GetTitleProperties().SetFontSize(20)
    axes.GetTitleProperties().SetFontFamilyToArial()
    axes.GetTitleProperties().SetBold(True)
    axes.GetTitleProperties().SetItalic(False)
    axes.SetTopBorder(100)


    pie_chart.SetInputData(new_table)
    pie_chart.SetColorSeries(colorSeries)
    pie_chart.SetInputArray(0, "pie chart data")
    pie_chart.SetLabels(labelArray)
    # pie.SetColor(*convert_color_to_RGBA(pie_color))
    # pie.SetOpacity(opacity)

    return pie_chart


def add_xyz_suface_plot(figure, axes=None):

    """Add xyz suface plot."""
    if figure is not None:
        total_items = figure.GetScene().GetNumberOfItems()
        for i in range(total_items):
            item = figure.GetScene().GetItem(i)
            if isinstance(item, vtk.vtkChartXYZ):
                axes = item
                break
        if axes is None:
            logger.warning("Could not find XYZ axes, creating new one")
            axes = vtk.vtkChartXYZ()
            figure.GetScene().AddItem(axes)

    # stacked_table = _convert_np_data_to_table(x, y, x_label=x_label, y_label=y_label)

    axes.SetGeometry(vtk.vtkRectf(10.0, 10.0, 630, 470))

    plot = vtk.vtkPlotSurface()

    view = vtk.vtkContextView()

    view.GetScene().AddItem(axes)

    # Create a surface
    table = vtk.vtkTable()
    numPoints = 70
    inc = 9.424778 / (numPoints - 1)
    for i in range(numPoints):
        arr = vtk.vtkFloatArray()
        table.AddColumn(arr)

    table.SetNumberOfRows(numPoints)
    for i in range(numPoints):
        x = i * inc
        for j in range(numPoints):
            y = j * inc
            table.SetValue(i, j, np.sin(np.sqrt(x * x + y * y)))

    # Set up the surface plot we wish to visualize and add it to the chart
    plot.SetXRange(0, 10.0)
    plot.SetYRange(0, 10.0)
    plot.SetInputData(table)
    # plot.GetPen().SetColorF(colors.GetColor3d("Tomato"))
    axes.AddPlot(plot)

    return axes


def add_dendrogram(figure, tree=None):
    """
    Adds a dendrogram to the specified figure.

    Parameters:
        figure (vtk.vtkContextView): The VTK figure to which the dendrogram will be
            added.
        tree (vtk.vtkTree): The tree structure to be visualized as a dendrogram.
        axes (vtk.vtkChartXY, optional): The axes to which the dendrogram will be added.
            If None, a new axes object will be created.
        title (str, optional): The title of the dendrogram. Defaults to "Dendrogram".
        color (str, optional): The color of the dendrogram. Defaults to "steel_blue".

    Returns:
        None
    """
    # Create a mutable directed graph
    graph = vtk.vtkMutableDirectedGraph()
    root = graph.AddVertex()
    internal_one = graph.AddChild(root)
    internal_two = graph.AddChild(internal_one)
    a = graph.AddChild(internal_two)
    b = graph.AddChild(internal_two)
    c = graph.AddChild(internal_one)

    # Add edge weights
    weights = vtk.vtkDoubleArray()
    weights.SetNumberOfTuples(5)
    weights.SetValue(graph.GetEdgeId(root, internal_one), 1.0)
    weights.SetValue(graph.GetEdgeId(internal_one, internal_two), 2.0)
    weights.SetValue(graph.GetEdgeId(internal_two, a), 1.0)
    weights.SetValue(graph.GetEdgeId(internal_two, b), 1.0)
    weights.SetValue(graph.GetEdgeId(internal_one, c), 3.0)
    weights.SetName("weight")
    graph.GetEdgeData().AddArray(weights)

    # Add node names
    names = vtk.vtkStringArray()
    names.SetNumberOfTuples(6)
    names.SetValue(a, "a")
    names.SetValue(b, "b")
    names.SetValue(c, "c")
    names.SetName("node name")
    graph.GetVertexData().AddArray(names)

    # Add node weights
    node_weights = vtk.vtkDoubleArray()
    node_weights.SetNumberOfTuples(6)
    node_weights.SetValue(root, 0.0)
    node_weights.SetValue(internal_one, 1.0)
    node_weights.SetValue(internal_two, 3.0)
    node_weights.SetValue(a, 4.0)
    node_weights.SetValue(b, 4.0)
    node_weights.SetValue(c, 4.0)
    node_weights.SetName("node weight")
    graph.GetVertexData().AddArray(node_weights)

    # Convert the graph to a tree
    tree = vtk.vtkTree()
    tree.ShallowCopy(graph)

    # Create a dendrogram item
    dendrogram = vtk.vtkDendrogramItem()
    dendrogram.SetTree(tree)
    dendrogram.SetPosition(10, 10)

    # Add the dendrogram to a context transform for interactivity
    transform = vtk.vtkContextTransform()
    transform.SetInteractive(False)
    transform.AddItem(dendrogram)
    transform.Scale(1, 1)

    # Add the transform to the figure's scene
    figure.GetScene().AddItem(transform)


 


def add_label(figure=None, axes=None, label=None, horizontal_alignment='left', vertical_alignment='bottom'):

    """Add label."""
    block = vtk.vtkBlockItem()
    props = block.GetLabelProperties()

    props.SetFontSize(100)
    props.SetBold(True)
    props.SetItalic(False)
    # props.SetColor(0.0, 0.0, 0.0)
    props.SetJustificationToCentered()
    props.SetVerticalJustificationToCentered()
    block.SetLabel(label)
    block.SetAutoComputeDimensions(True)
    block.SetPadding(10, 10)

    alignment_map = {'left':0 , 'center':1 , 'right':2 , 'top':3 ,'bottom':4 , 'custom':5}

    block.SetVerticalAlignment(alignment_map[horizontal_alignment.lower()])
    block.SetHorizontalAlignment(alignment_map[vertical_alignment.lower()])
    block.SetMargins(10, 10)

    brush = block.GetBrush()
    # brush.SetColor(255, 0, 0)
    # brush.SetOpacity(255)
    brush.SetColorF(0.7, 0.7, 0.7)
    pen = block.GetPen()
    pen.SetColor(0, 255, 0)
    pen.SetWidth(2)
    pen.SetOpacity(255)

    block.SetDimensions(0, 0, 0.5, 0.5)
    figure.GetScene().AddItem(block)


def figure(fig_size=(1280, 1024), title="VTK Chart", background_color="SlateGray"):
    """
    Creates and configures a VTK 2D chart figure in the same convention as matplotlib.
    Parameters:
        fig_size (tuple, optional): A tuple specifying the width and height of the
            figure in pixels. Defaults to (1280, 1024).
        title (str, optional): The title of the figure window. Defaults to 'VTK Chart'.
        background_color (str, optional): The background color of the figure in a named
            color format. Defaults to 'SlateGray'.
    Returns:
        vtk.vtkContextView: A configured VTK context view object representing the 2D
        chart figure.
    """

    # Set up a 2D scene, add an XY axes to it
    figure = vtk.vtkContextView()
    figure.GetRenderWindow().SetSize(fig_size[0], fig_size[1])
    figure.GetRenderWindow().SetWindowName(title)
    figure.GetRenderer().SetBackground(*color_to_RGB(background_color))
    figure.GetRenderer().SetBackgroundAlpha(0.2)

    figure.GetRenderWindow().SetMultiSamples(64)
    figure.GetRenderWindow().SetAlphaBitPlanes(1)
    figure.GetRenderWindow().SetStereoCapableWindow(1)
    figure.GetRenderWindow().SetPolygonSmoothing(True)
    figure.GetRenderWindow().SetLineSmoothing(True)
    figure.GetRenderWindow().SetPointSmoothing(True)

    figure.GetRenderWindow().Modified()

    return figure


def show(figure):
    """
    Displays a given figure using its interactor and render window.

    This function is designed to work in a similar way to matplotlib's `show()`
    function.

    This function initializes the interactor of the provided figure,
    renders the figure's render window, and starts the interactor to
    display the figure.

    Args:
        figure: An object representing the figure to be displayed. It is
                expected to have the methods `GetInteractor()`, `GetRenderWindow()`,
                and their respective sub-methods `Initialize()`, `Render()`, and
                `Start()`.
    Raises:
        AttributeError: If the provided figure does not have the required methods.
    """

    figure.GetInteractor().Initialize()
    figure.GetRenderWindow().Render()
    figure.GetInteractor().Start()


# Deprecated chart-actor helpers, re-exported for one release of overlap.
from .chart_legacy import (  # noqa: E402,F401
    ChartModeFilter, DraggableChartInteractorStyle, HybridInteractorStyle,
    add_chart_actor, install_chart_mode,
)
