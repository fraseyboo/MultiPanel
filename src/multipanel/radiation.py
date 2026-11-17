"""Radiation-detection and Compton-reconstruction helpers.

These helpers were previously defined in :mod:`multipanel.specialists` and
:mod:`multipanel.vtk_utils`, which still re-export them for compatibility
(until 1.0).  They are domain-specific rather than general UI, so new code
should import them from here.

Compton reconstruction itself lives in the host application.  Register the
module or object that provides it with :func:`set_reconstruction_backend`;
it must provide ``perform_compton_reconstruction``,
``perform_iterative_compton_reconstruction`` and
``compton_reconstruction_loop``.
"""

from ._widget_support import *
from ._widget_support import _mpl_utils, _vtk_utils
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "add_GEANT4_tracks",
    "calculate_compton_angle",
    "create_radiation_marker",
    "reconstruction_backend",
    "refresh_compton_widgets",
    "refresh_reconstruction_callback",
    "set_auto_reconstruction_callback",
    "set_reconstruction_backend",
    "set_reconstruction_selection_callback",
    "spectrum_button_callback",
]

_RECONSTRUCTION_BACKEND = None


def set_reconstruction_backend(backend):
    """Register the host's Compton reconstruction implementation.

    ``backend`` is typically the host's ``reconstruction_utils`` module.
    Pass ``None`` to clear it.
    """
    global _RECONSTRUCTION_BACKEND
    _RECONSTRUCTION_BACKEND = backend


def reconstruction_backend():
    """Return the registered reconstruction backend.

    Raises ``RuntimeError`` with setup instructions when none is registered.
    """
    if _RECONSTRUCTION_BACKEND is None:
        raise RuntimeError(
            "No Compton reconstruction backend is registered. Call "
            "multipanel.radiation.set_reconstruction_backend(module) with the "
            "host module that provides perform_compton_reconstruction, "
            "perform_iterative_compton_reconstruction and "
            "compton_reconstruction_loop.")
    return _RECONSTRUCTION_BACKEND


def calculate_compton_angle(e2, etot):

    """Calculate compton angle."""
    value = 1-(511 * ((1/e2)-(1/etot)))

    angle = np.arccos(value)

    return angle


def add_GEANT4_tracks(geant_data, source_position=None, glyph_type='lines', color=None, colormap='viridis', opacity=1.0, use_euclidean_as_weight=True, line_width=3):

    """Add geant4 tracks."""
    if geant_data.shape[1] != 6:
        starts = geant_data[:, 0:3]
        ends = geant_data[:, 4:7]

        locations = np.hstack(([starts, ends]))
        total_tracks = starts.shape[0]
    else:
        locations = geant_data
        total_tracks = geant_data.shape[0]

    if source_position is not None:
        source_repeat = np.tile(np.array(source_position), (total_tracks, 1))
        locations_prepend = np.hstack(([source_repeat, locations[:, 0:3]]))

        line_actor_1 = _vtk_utils().add_lines(locations_prepend, opacity=opacity, use_euclidean_as_weight=use_euclidean_as_weight, colormap=colormap, color=color, tube_radius=line_width)
        line_actor_2 = _vtk_utils().add_lines(locations, opacity=opacity, use_euclidean_as_weight=use_euclidean_as_weight, colormap=colormap, color=color, tube_radius=line_width)

        return [line_actor_1, line_actor_2]

    else:

        line_actor = _vtk_utils().add_lines(locations, opacity=opacity, use_euclidean_as_weight=use_euclidean_as_weight, render_type=glyph_type, colormap=colormap, color=color, tube_radius=line_width)

        return line_actor


def create_radiation_marker(position, text=None, ren=None, name='widgets/radiation_marker'):

    """Create radiation marker."""
    filepath = os.path.join('data', 'radiation_marker.glb')
    if not os.path.exists(filepath):
        raise FileNotFoundError(bcolors.FAIL + f'Radiation marker file not found at %s' % filepath + bcolors.ENDC)

    if ren is None:
        radiation_marker = _vtk_utils().load_gltf(filepath, translate=position, name=name, import_method='vtkGLTFReader')

    else:

        render_window = ren.GetRenderWindow()

        polydata_collection = _vtk_utils().load_gltf(filepath, render_window=render_window, name=name, rotate=(90, 0, 0))

        logger.debug("%s", polydata_collection)

        append_polydata = vtk.vtkAppendPolyData()
        for actor_name, polydata in polydata_collection.items():
            if isinstance(polydata, vtk.vtkPolyData):
                append_polydata.AddInputData(polydata)
            elif isinstance(polydata, vtk.vtkActor):
                polydata.GetMapper().Update()
                polydata_polydata = polydata.GetMapper().GetInput()
                if isinstance(polydata_polydata, vtk.vtkPolyData):
                    append_polydata.AddInputData(polydata_polydata)


        text_source = vtk.vtkVectorText()
        if text is not None:
            text_source.SetText(text)
        else:
            text_source.SetText('Radiation Marker')

        append_polydata.AddInputData(text_source.GetOutput())

        append_polydata.Update()

        polydata = append_polydata.GetOutput()

        logger.debug("%s %s", 'Radiation marker polydata:', polydata)

        radiation_marker = vtk.vtkFollower()
        radiation_marker.SetMapper(vtk.vtkPolyDataMapper())
        radiation_marker.GetMapper().SetInputData(polydata)
        radiation_marker.SetPosition(position)
        radiation_marker.SetOrientation(-90, 0, 0)
        radiation_marker.SetCamera(ren.GetActiveCamera())

        radiation_marker.Modified()

        ren.AddActor(radiation_marker)


    if not hasattr(ren, 'widgets'):
        ren.widgets = dict()
    ren.widgets.update({name: radiation_marker})

    return radiation_marker


def spectrum_button_callback(widget, event, selection='selection'):
    """Handle the spectrum button callback event."""
    value = widget.GetRepresentation().GetState()
    renwin = widget.GetCurrentRenderer().GetRenderWindow()

    logger.debug("%s %s", "Spectrum Button pressed!", value)

    Compton_Events = widget.renderer.Compton_Events

    if Compton_Events is None:
        logger.warning('No Compton events found, cannot plot spectrum')
        return




    renderer = widget.GetCurrentRenderer()


    logger.debug("%s %s", 'Total valid events in the full scene:', np.sum(Compton_Events.Event_Selection.initial_validity))

    logger.debug(f'{bcolors.OKCYAN}Selection applied to Compton events {bcolors.ENDC}')

    if selection == 'selection':

        logger.debug(f'Plotting current user selection, {np.sum(Compton_Events.Event_Selection.selection)} total events')

        if Compton_Events.Event_Selection.selection is None:
            logger.debug('No selection found, using full validity')
            plotted_events = Compton_Events.Event_Selection.initial_validity
        else:
            plotted_events = Compton_Events.Event_Selection.selection
            logger.debug("%s %s %s", 'Events found in selection:', np.sum(plotted_events), 'to be included in spectrum')

    elif selection == 'widget_selection':

        logger.debug(f'Plotting current widget selection, {np.sum(Compton_Events.events_in_widget_bounds)} total events')

        if Compton_Events.events_in_widget_bounds is None:
            logger.debug('No widget selection found, using full validity')
            return
        else:
            plotted_events = Compton_Events.events_in_widget_bounds

    if plotted_events is None:
        logger.warning('No valid events found, cannot plot spectrum')
        return
    if np.sum(plotted_events) == 0:
        logger.warning('No valid events found, cannot plot spectrum')
        return

    scatterer_energies = Compton_Events.scatterer_energies
    absorber_energies = Compton_Events.absorber_energies

    # valid_events = widget.renderer.spectral_data['valid_events']
    # scatterer_energies = widget.renderer.spectral_data['scatterer_energies']
    # absorber_energies = widget.renderer.spectral_data['absorber_energies']

    logger.debug("%s %s", 'Plotted events:', plotted_events.shape)
    logger.debug("%s %s", 'Scatterer energies:', scatterer_energies.shape)
    logger.debug("%s %s", 'Absorber energies:', absorber_energies.shape)

    _mpl_utils().plot_energy_spectrum(
        scatterer_energies, absorber_energies, plotted_events)

    return


def refresh_compton_widgets(ren):
    """
    Refreshes the Compton widgets in the renderer.
    This function is called when the Compton data is updated or reconstructed.
    It updates the visibility and properties of the Compton widgets.
    """

    volumes = ren.GetVolumes()

    if volumes is not None and volumes.GetNumberOfItems() > 0:

        for v, volume in enumerate(volumes):
            volume_name = volume.GetObjectName()
            if volume_name == 'widgets/compton_volume':

                compton_volume = volume


    if hasattr(ren, 'widgets'):
        for widget_name, widget in ren.widgets.items():
            if widget_name.startswith('widgets/compton_mesh'):

                logger.debug(f'{bcolors.OKCYAN}Refreshing widget: {widget_name}{bcolors.ENDC}')

                # new_compton_mesh = MeshProbeWidget(
                #     dataset=compton_volume,
                #     probe_mesh=widget.probe_mesh,
                #     renderer=ren,
                #     colormap=widget.colormap,
                #     probe_subdivisions=widget.probe_subdivisions,
                #     opacity=widget.opacity,
                #     name=widget_name,
                #     use_lighting=widget.use_lighting,
                #     include_RGB=widget.include_RGB,
                #     existing_probe=widget.existing_probe,
                #     enabled=True,  # Always refresh the widget as enabled
                #     replace_actor=True,  # Always replace the actor
                #     clip_to_bounds=False  # Do not clip to bounds
                # )

                widget.ReProbe(dataset=compton_volume.GetMapper().GetInput())

                # ren.widgets[widget_name] = new_compton_mesh

            elif widget_name.startswith('widgets/slice'):
                logger.debug(f'{bcolors.OKCYAN}Refreshing widget: {widget_name}{bcolors.ENDC}')

                slice_widget = ren.widgets[widget_name]
                slice_widget.SetInputData(compton_volume.GetMapper().GetInput())
                slice_widget.Modified()
                # slice_widget.UpdatePlacement()

            else:
                pass


def refresh_reconstruction_callback(widget, event):
    """Handle the refresh reconstruction callback event."""
    value = widget.GetRepresentation().GetState()
    # renwin = widget.GetCurrentRenderer().GetRenderWindow()
    renderer = widget.renderer

    logger.debug("%s %s", "Refresh Reconstruct Button pressed!", value)

    # if hasattr(widget.renderer, 'reconstruction'):
    #     reconstruction = widget.renderer.reconstruction
    #     if reconstruction is not None:
    #         return

    if hasattr(widget.renderer, 'Compton_Array'):
        Compton_Array = widget.renderer.Compton_Array
        Compton_Events = widget.renderer.Compton_Events

        bounds = Compton_Array.physical_bounds
        voxel_size = Compton_Array.voxel_size
        logger.debug('Re-reconstructing Compton data...')

        t0 = time.time()
        NewComptonArray = reconstruction_backend().compton_reconstruction_loop(bounds, voxel_size, Compton_Events, progressbar_enabled=progressbar_supported)
        t1 = time.time()

        logger.debug("%s", 'Re-reconstruction took %.2f seconds' % (t1 - t0))

        renderer.Compton_Array = NewComptonArray

    else:
        logger.debug('No Compton data found for reconstruction')

    buffer = 0.00001
    lower_bound = np.asarray([bounds[0] - buffer, bounds[2] - buffer, bounds[4] - buffer])
    upper_bound = np.asarray([bounds[1] + buffer, bounds[3] + buffer, bounds[5] + buffer])
    spacings = (np.asarray([1,1,1])/NewComptonArray.compton_array.shape) * (upper_bound - lower_bound)
    compton_volume = _vtk_utils().add_volume(NewComptonArray.compton_array, spacing=spacings, origin=lower_bound,
                                          c_range=(0,np.max(NewComptonArray.compton_array)/2), name='widgets/compton_volume',
                                          enabled=False)

    renderer.AddActor(compton_volume)


    refresh_compton_widgets(renderer)

    return


def set_auto_reconstruction_callback(widget, event):

    """Set auto reconstruction callback."""
    value = widget.GetRepresentation().GetState()


    if value == 1:
        widget.renderer.auto_reconstruct = True
    else:
        widget.renderer.auto_reconstruct = False

    return


def set_reconstruction_selection_callback(widget, event):

    """Set reconstruction selection callback."""
    value = widget.GetRepresentation().GetState()

    if hasattr(widget.renderer, 'invert_selection'):

        if value == 1:
            widget.renderer.invert_selection = True
        elif value == 0:
            widget.renderer.invert_selection = False
        elif value == 2:
            widget.renderer.invert_selection = None

        widget.renderer.Modified()

        logger.debug(f'Invert selection set to {widget.renderer.invert_selection}')

    return
