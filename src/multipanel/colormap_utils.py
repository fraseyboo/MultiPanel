import numpy as np
import vtk
import logging

logger = logging.getLogger(__name__)

def make_colormap(c_range=(0,1), color='viridis', total_colors=100, invert=False, verbose=False):

    """Create ``(scalar, r, g, b)`` samples across *c_range*.

    Two values describe the endpoints directly.  Longer sequences are
    transfer-function knot positions, so their first and last values are the
    endpoints; intermediate knots must not collapse the colour-map extent.
    """
    from .optional import import_optional

    matplotlib = import_optional(
        "matplotlib", extra="scientific", purpose="named colour maps")
    total_colors = int(total_colors)
    if total_colors < 2:
        raise ValueError("total_colors must be at least 2")
    if len(c_range) < 2:
        raise ValueError("c_range must contain at least two scalar values")

    # Possible values are: 

    # Accent, Accent_r, Blues, Blues_r, BrBG, BrBG_r,
    # BuGn, BuGn_r, BuPu, BuPu_r, CMRmap, CMRmap_r, Dark2, Dark2_r, GnBu,
    # GnBu_r, Greens, Greens_r, Greys, Greys_r, OrRd, OrRd_r, Oranges, Oranges_r,
    # PRGn, PRGn_r, Paired, Paired_r, Pastel1, Pastel1_r, Pastel2, Pastel2_r,
    # PiYG, PiYG_r, PuBu, PuBuGn, PuBuGn_r, PuBu_r, PuOr, PuOr_r, PuRd, PuRd_r,
    # Purples, Purples_r, RdBu, RdBu_r, RdGy, RdGy_r, RdPu, RdPu_r, RdYlBu,
    # RdYlBu_r, RdYlGn, RdYlGn_r, Reds, Reds_r, Set1, Set1_r, Set2, Set2_r,
    # Set3, Set3_r, Spectral, Spectral_r, Wistia, Wistia_r, YlGn, YlGnBu,
    # YlGnBu_r, YlGn_r, YlOrBr, YlOrBr_r, YlOrRd, YlOrRd_r, afmhot, afmhot_r,
    # autumn, autumn_r, binary, binary_r, bone, bone_r, brg, brg_r, bwr, bwr_r,
    # cividis, cividis_r, cool, cool_r, coolwarm, coolwarm_r, copper, copper_r,
    # cubehelix, cubehelix_r, flag, flag_r, gist_earth, gist_earth_r, gist_gray,
    # gist_gray_r, gist_heat, gist_heat_r, gist_ncar, gist_ncar_r, gist_rainbow,
    # gist_rainbow_r, gist_stern, gist_stern_r, gist_yarg, gist_yarg_r, gnuplot,
    # gnuplot2, gnuplot2_r, gnuplot_r, gray, gray_r, hot, hot_r, hsv, hsv_r,
    # inferno, inferno_r, jet, jet_r, magma, magma_r, nipy_spectral,
    # nipy_spectral_r, ocean, ocean_r, pink, pink_r, plasma, plasma_r,
    # prism, prism_r, rainbow, rainbow_r, seismic, seismic_r, spring,
    # spring_r, summer, summer_r, tab10, tab10_r, tab20, tab20_r, tab20b,
    # tab20b_r, tab20c, tab20c_r, terrain, terrain_r, twilight, twilight_r,
    # twilight_shifted, twilight_shifted_r, viridis, viridis_r, winter, winter_r

    if verbose:
        if color is None:
            logger.debug('No colormap supplied, defaulting to Viridis')
        else:
            logger.debug("%s %s", 'Making colormap:', color)

    if verbose:
        logger.debug('Using Matplotlib color tables')
    mpl_data = matplotlib.colormaps.get_cmap(color)
    cm_data = np.zeros([total_colors, 3])
    for i, position in enumerate(np.linspace(0.0, 1.0, total_colors)):
        cm_data[i,:] = mpl_data(position)[0:3]

    colormap = np.asarray(cm_data)

    if invert:
        if verbose:
            logger.debug('Using inverted direction')
        colormap = np.flip(colormap, axis=0)

    scale = np.linspace(c_range[0], c_range[-1], num=colormap.shape[0])

    colormap = np.vstack([scale, colormap.T]).T

    if verbose:
        logger.debug('Colormap made')

    return colormap


def make_LUT(
    colormap="viridis",
    invert=False,
    verbose=False,
    c_range=(0, 1),
    nan_color=(1, 0, 0, 1),
    above_range_color=(1, 1, 1, 1),
    below_range_color=(0, 0, 0, 1),
    total_colors=100,
    scale_type="linear",
    set_outside_colors_to_edges=False,
):
    """
    Creates a VTK Lookup Table (LUT) based on the specified parameters.
    Parameters:
        colormap (str): The name of the colormap to use. Default is "viridis".
        invert (bool): Whether to invert the colormap. Default is False.
        verbose (bool): Whether to enable verbose output. Default is False.
        c_range (tuple): The range of values for the colormap (min, max).
            Default is (0, 1).
        nan_color (tuple): The RGBA color to use for NaN values.
            Default is (1, 0, 0, 1).
        total_colors (int): The total number of colors in the colormap.
            Default is 100.
        scale_type (str): The scale type for the LUT, either "linear" or "logarithmic".
            Default is "linear".
    Returns:
        vtkLookupTable: A VTK Lookup Table object configured with the specified
            parameters.
    Raises:
        TypeError: If there is an issue with the colormap data type during processing.
    Notes:
        - The function uses the `make_colormap` function to generate the colormap.
        - The `vtkColorSeries` and `vtkLookupTable` classes are used to build the LUT.
        - The LUT is configured with the specified scale type and NaN color.
    """

    colormap = make_colormap(
        c_range=c_range,
        color=colormap,
        invert=invert,
        total_colors=total_colors,
        verbose=verbose,
    )

    # if config.dark_mode:
    # colormap = colormap * [1, 0.1, 0.1, 0.1]

    colorSeries = vtk.vtkColorSeries()
    colorSeries.SetNumberOfColors(colormap.shape[0])
    try:
        for i, color in enumerate(colormap):
            color = (255 * color[1:4]).astype(int)
            vcolor = vtk.vtkColor3ub(color)
            colorSeries.SetColor(i, vcolor)
        lut = vtk.vtkLookupTable()
        colorSeries.BuildLookupTable(lut, colorSeries.ORDINAL)
        lut.SetNanColor(nan_color)
    except TypeError:
        for i, color in enumerate(colormap):
            color = (255 * color[1:4]).astype(int)
            vcolor = vtk.vtkColor3ub(color[0], color[1], color[2])
            colorSeries.SetColor(i, vcolor)
        lut = vtk.vtkLookupTable()
        colorSeries.BuildLookupTable(lut, colorSeries.ORDINAL)
        lut.SetNanColor(nan_color)
        lut.SetRange(c_range)

    if scale_type == "linear":
        lut.SetScaleToLinear()

    elif scale_type == "logarithmic":
        lut.SetScaleToLog10()


    lut.SetUseBelowRangeColor(True)
    lut.SetUseAboveRangeColor(True)

    if set_outside_colors_to_edges:
        lut.SetBelowRangeColor(colormap[0, 1:4].tolist() + [1])
        lut.SetAboveRangeColor(colormap[-1, 1:4].tolist() + [1])

    else:
        lut.SetAboveRangeColor(above_range_color)
        lut.SetBelowRangeColor(below_range_color)

    return lut

def generate_color_series(iterables=None, colormap_name="tab20", alpha=1.0):
    # import matplotlib.cm as cm
    """Execute the generate color series operation."""
    from .optional import import_optional

    matplotlib = import_optional(
        "matplotlib", extra="scientific", purpose="colour series")

    # color_map = cm.get_cmap('hsv', n_colors)

    color_map = [matplotlib.colors.to_rgb(c) for c in matplotlib.pyplot.rcParams['axes.prop_cycle'].by_key()['color']]

    # adding more colors after the default cycle is exhausted


    additional_colors = [
        (0.5, 0.0, 0.5),  # Purple
        (1.0, 0.65, 0.0),  # Orange
        (0.0, 0.5, 0.5),  # Teal
        (0.5, 0.5, 0.0),  # Olive
        (0.75, 0.75, 0.75),  # Light Gray
        (1.0, 0.75, 0.8),  # Pink
        (0.6, 0.4, 0.2),  # Brown
        (0.4, 0.6, 0.2),  # Lime Green
    ]

    color_map.extend(additional_colors)

    if iterables is not None:
        n_colors = len(iterables)
        if n_colors > len(color_map):
            # Repeat the color map if there are more iterables than colors
            color_map = (color_map * ((n_colors // len(color_map)) + 1))[:n_colors]
        else:
            color_map = color_map[:n_colors]

    # colors = []
    # for i in range(len(color_map)):
    #     color = color_map[i]
    #     colors.append((color[0], color[1], color[2]))  # Ignore alpha

    return color_map


def color_to_RGBA_255(color, opacity=1):
    """
    Converts a given color input into an RGBA tuple.

    Parameters:
        color (str, tuple, list, vtk.vtkColor3ub, vtk.vtkColor4ub,
            vtk.vtkUnsignedCharArray, vtk.vtkFloatArray, np.ndarray):
            The input color to be converted. It can be:
            - A string representing a named color (e.g., "red").
            - A tuple or list of int RGB values (e.g., (255, 0, 0)).
            - A tuple or list of float RGB values (e.g., (1.0, 0.0, 0.0)).
            - A vtk.vtkColor3ub or vtk.vtkColor4ub object.
            - A vtk.vtkUnsignedCharArray or vtk.vtkFloatArray containing color values.
            - A 1D numpy array with 3 (RGB) or 4 (RGBA) elements.
        opacity (float, optional):
            The opacity value to be applied to the color. Defaults to 1 (fully opaque).
            The value should be between 0 (fully transparent) and 1 (fully opaque).

    Returns:
        tuple:
            A tuple representing the color in RGBA format, where each component is an
            integer in the range [0, 255].

    Raises:
        ValueError:
            If the input color format is invalid or unsupported.

    Notes:
        - If the input color already contains an alpha channel, the provided `opacity`
            value will be ignored.
        - The function should automatically convert color values in the range [0, 1]
            to the range [0, 255].
        - For vtkUnsignedCharArray and vtkFloatArray, the function assumes the color
            data is stored in a flat array format.
    Examples:
        >>> convert_color_to_RGBA("red", 0.5)
            (255, 0, 0, 127)
        >>> convert_color_to_RGBA((0, 255, 0), 1)
            (0, 255, 0, 255)
        >>> convert_color_to_RGBA(np.array([0, 0, 255]), 0.8)
            (0, 0, 255, 204)
    """

    colors = vtk.vtkNamedColors()

    alpha = int(opacity * 255)

    if isinstance(color, tuple):
        color = np.array(color)

    if isinstance(color, str):
        RGBA_color = *colors.GetColor3ub(color), alpha
    elif isinstance(color, (list, tuple)):
        if all(cvalue < 1.00001 for cvalue in color):
            RGBA_color = (np.array(color) * 255).astype(np.uint8)

        if len(color) == 3:
            RGBA_color = color[0], color[1], color[2], alpha
        elif len(color) == 4:
            RGBA_color = color[0], color[1], color[2], color[3]

    elif isinstance(color, vtk.vtkColor3ub):
        RGBA_color = color.GetRed(), color.GetGreen(), color.GetBlue(), alpha
    elif isinstance(color, vtk.vtkColor4ub):
        RGBA_color = (
            color.GetRed(),
            color.GetGreen(),
            color.GetBlue(),
        )
        color.GetAlpha()
    elif isinstance(color, (vtk.vtkFloatArray, vtk.vtkUnsignedCharArray)):
        RGBA_color = color.GetPointer(0)
        if len(color) == 3:
            RGBA_color = color[0], color[1], color[2], alpha
        elif len(color) == 4:
            RGBA_color = color[0], color[1], color[2], color[3]
        else:
            raise ValueError("Invalid color format")
    elif isinstance(color, np.ndarray):
        if np.all(color < 1.00001):
            color = (color * 255).astype(np.uint8)

        if color.ndim == 1 and color.size == 3:
            RGBA_color = color[0], color[1], color[2], alpha
        elif color.ndim == 1 and color.size == 4:
            RGBA_color = color[0], color[1], color[2], color[3]
        else:
            raise ValueError("Invalid color format")

    return np.asarray([int(c) for c in RGBA_color])


def color_to_RGBA(color, opacity=1):
    """
    Converts a given color input into an RGBA tuple.

    Parameters:
        color (str, tuple, list, vtk.vtkColor3ub, vtk.vtkColor4ub,
            vtk.vtkUnsignedCharArray, vtk.vtkFloatArray, np.ndarray):
            The input color to be converted. It can be:
            - A string representing a named color (e.g., "red").
            - A tuple or list of RGB values (e.g., (255, 0, 0)).
            - A vtk.vtkColor3ub or vtk.vtkColor4ub object.
            - A vtk.vtkUnsignedCharArray or vtk.vtkFloatArray containing color values.
            - A 1D numpy array with 3 (RGB) or 4 (RGBA) elements.
        opacity (float, optional):
            The opacity value to be applied to the color. Defaults to 1 (fully opaque).
            The value should be between 0 (fully transparent) and 1 (fully opaque).

    Returns:
    """

    RGBA_color = color_to_RGBA_255(color, opacity=opacity)

    return (RGBA_color / 255).astype(float)


def color_to_RGB_255(color):
    """
    Converts a given color to its RGB representation.
    This function takes a color input, processes it to extract the
    Red, Green, and Blue (RGBA) components using convert_color_to_RGBA
    and returns only the RBG as a tuple.
    Args:
        color: The input color, which can be in a format compatible
               with the `convert_color_to_RGBA` function.
    Returns:
        tuple: A tuple containing the RGB components of the color
               as three values (R, G, B), each in the range [0, 1].
    """

    return color_to_RGBA_255(color)[:3]


def color_to_RGB(color):
    """
    Converts a given color to its RGB representation.
    This function takes a color input, processes it to extract the
    Red, Green, and Blue (RGBA) components using convert_color_to_RGBA
    and returns only the RBG as a tuple.
    Args:
        color: The input color, which can be in a format compatible
               with the `convert_color_to_RGBA` function.
    Returns:
        tuple: A tuple containing the RGB components of the color
               as three values (R, G, B), each in the range [0, 1].
    """

    RGBA_color = color_to_RGBA_255(color)

    return (RGBA_color[:3] / 255).astype(float)

def make_random_color():
    """
    Generates a random RGB color.

    Returns:
        tuple: A tuple containing three float values representing
               the Red, Green, and Blue components of the color,
               each in the range [0, 1].
    """
    return np.random.rand(3)
