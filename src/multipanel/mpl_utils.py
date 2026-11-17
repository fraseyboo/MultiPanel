import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patheffects as PathEffects

import sys
import os
from matplotlib.widgets import CheckButtons
import logging

logger = logging.getLogger(__name__)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),"..")))

from . import vtk_utils

backends = plt.rcParams['backend']

# possible_backends = plt.rcsetup.all_backends


try:
    possible_backends = plt.rcsetup.all_backends
except AttributeError:
    possible_backends = None



plt.switch_backend('qtagg')

# new_backends = plt.rcParams['backend']

def plot_superpulse(superpulse_1, superpulse_2=None, superpulse_3=None, segments=19, auto_flatten=True, alpha=0.5):

    """Plot superpulse."""
    if auto_flatten:
        superpulse_1 = superpulse_1.flatten()

    x_values = np.linspace(0, segments, superpulse_1.shape[0]) - 0.5

    plt.figure(figsize=(12,6))
    if superpulse_2 is not None:
        ax1 = plt.subplot(211)
    # plt.plot(superpulse.T)
    plt.plot(x_values, superpulse_1, label='Query Signal', c='k', alpha=alpha)

    plt.xticks(np.arange(0,segments,1))
    plt.xticks(np.arange(-0.5,segments+0.5,1), minor=True)
    plt.grid(which='minor', axis='x')
    plt.xlim(-0.5, segments-0.5)

    if superpulse_2 is not None:

        if auto_flatten:
            superpulse_2 = superpulse_2.flatten()


        if superpulse_3 is None:

            plt.plot(x_values, superpulse_2, label='Closest match', alpha=alpha)
   
        
        else:
            if auto_flatten:
                superpulse_3 = superpulse_3.flatten()

            plt.plot(x_values, superpulse_2, label='Coarse Signal', alpha=alpha)
            plt.plot(x_values, superpulse_3, label='Fine Signal', alpha=alpha)
 

        plt.legend()


        plt.subplot(212, sharex = ax1)
        plt.plot([x_values[0], x_values[-1]], [0,0], c='k', label='Baseline', alpha=alpha)
        plt.plot(x_values, superpulse_1 - superpulse_2, label='Coarse Residual', alpha=alpha)
        if superpulse_3 is not None:
            plt.plot(x_values, superpulse_1 - superpulse_3, label='Fine Residual', alpha=alpha)
        plt.xticks(np.arange(0,segments,1))
        plt.xticks(np.arange(-0.5,segments+0.5,1), minor=True)
        plt.grid(which='minor', axis='x')
        plt.xlim(-0.5, segments-0.5)
        plt.legend()


    plt.tight_layout()
    plt.show()


def plot_deviations_matrix(segments, deviation_matrix, savename):

    """Plot deviations matrix."""
    plt.figure(figsize=(13,12))
    plt.imshow(deviation_matrix, cmap='viridis')
    plt.colorbar(label='Mean Deviation (mm)')
    plt.xlabel('Segment 1')
    plt.ylabel('Segment 2')
    plt.title('Deviations')
    plt.xticks(np.arange(segments.size + 1))
    plt.yticks(np.arange(segments.size + 1))
    plt.xlim(0.5, segments.size + 0.5)
    plt.ylim(0.5, segments.size + 0.5)

    ax = plt.gca()
    for (j,i),label in np.ndenumerate(deviation_matrix):
        if np.isnan(label):
            continue
        label_truncated = '%.2f' % label
        # ax.text(i,j, label_truncated, ha='center',va='center')
        txt = ax.text(i,j, label_truncated, ha='center', va='center', color='white')
        txt.set_path_effects([PathEffects.withStroke(linewidth=2, foreground='k')])




    plt.tight_layout()

    plt.savefig(savename)

def plot_execution_rates(segments, rates, savename='plots/EXHAUSTIVE/execution_rates.png', title='Execution Rates for PSA'):
    """Plot execution rates."""
    plt.figure(figsize=(13,12))
    plt.imshow(rates, cmap='viridis')
    plt.colorbar(label='Execution Rate (Hz)')
    plt.xlabel('Segment 1')
    plt.ylabel('Segment 2')
    plt.title(title)

    plt.xticks(np.arange(segments.size + 1))
    plt.yticks(np.arange(segments.size + 1))
    plt.xlim(0.5, segments.size + 0.5)
    plt.ylim(0.5, segments.size + 0.5)

    ax = plt.gca()
    for (j,i),label in np.ndenumerate(rates):
        if np.isnan(label):
            continue
        if label > 1000:
            label_truncated = '%.0f' % label
        elif label > 100:
            label_truncated = '%.1f' % label
        else:
            label_truncated = '%.2f' % label
        # ax.text(i,j, label_truncated, ha='center', va='center', color='white')
        txt = ax.text(i,j, label_truncated, ha='center', va='center', color='white')
        txt.set_path_effects([PathEffects.withStroke(linewidth=2, foreground='k')])


    plt.tight_layout()
    if savename is not None:
        plt.savefig(savename)
    else:
        plt.show()

def plot_figure_of_merit_histogram(test_segment_2, test_segment_1, predicted_deviations):
    """Plot figure of merit histogram."""
    plt.figure(figsize=(12, 8))
    plt.hist(predicted_deviations, bins=100, label='FoM Deviation')
    plt.xlabel('Figure of Merit Deviation (arb)')
    plt.ylabel('Frequency')
    plt.xlim(0, None)
    plt.legend()
    plt.tight_layout()
    plt.savefig('plots/EXHAUSTIVE/FOM_histogram-%i-%i.png' % (test_segment_1, test_segment_2))
            # plt.show()
    plt.close()

def plot_fraction_deviation_histogram(test_segment_2, test_segment_1, true_fractions, predicted_fractions):
    """Plot fraction deviation histogram."""
    plt.figure()
    fraction_deviation = true_fractions - predicted_fractions
    plt.hist(fraction_deviation, bins=100)
    plt.xlabel('Fraction Deviation')
    plt.ylabel('Frequency')
    plt.tight_layout()
    plt.savefig('plots/EXHAUSTIVE/fraction_deviation_histogram-%i-%i.png' % (test_segment_1, test_segment_2))
    plt.close()

def plot_euclidean_deviation_histograms(test_segment_2, test_segment_1, euclidean_deviations_1, euclidean_deviations_2):
    """Plot euclidean deviation histograms."""
    max_value = np.max([np.nanmax(euclidean_deviations_1), np.nanmax(euclidean_deviations_2)])

    plt.figure(figsize=(12, 8))
    plt.hist(euclidean_deviations_1, bins=100, range=(0, max_value), alpha=0.5, label='Segment %i Deviation' % test_segment_1)
    plt.hist(euclidean_deviations_2, bins=100, range=(0, max_value), alpha=0.5, label='Segment %i Deviation' % test_segment_2)
    plt.xlabel('Euclidean Deviation (mm)')
    plt.ylabel('Frequency')
    plt.xlim(0, None)
    plt.legend()
    plt.tight_layout()
    plt.savefig('plots/EXHAUSTIVE/deviation_histogram-%i-%i.png' % (test_segment_1, test_segment_2))
            # plt.show()
    plt.close()




def plot_positions(positions, positions_2=None, voxel_size=1, plotted_value=4, colormap='hsv', glyph_type='cube', color=None, show_SIGMA=True):

    """Plot positions."""
    ren, renwin, iren = vtk_utils.create_renderer()


    colors = [[255,0,0], [0,255,0], [0,0,255], [255,255,0], [0,255,255], [255,0,255]] #, [255,255,255], [0,0,0]]

    if isinstance(positions, list):

        for s, sub_positions in enumerate(positions):
            if sub_positions.shape[1] > 3:
                scalar_dict=sub_positions[:, plotted_value]
                sub_positions = sub_positions[:, :3]
            else:
                scalar_dict=None

            points_vtk = vtk_utils.add_polydata(sub_positions, scalar_dict=scalar_dict, glyph_type=glyph_type, glyph_scale=voxel_size, colormap=colormap, colors=colors[s], opacity=0.3)
            ren.AddActor(points_vtk)

    elif positions.shape[1] > 3:
        scalar_dict=positions[:, plotted_value]
        positions = positions[:, :3]
        points_vtk = vtk_utils.add_polydata(positions, scalar_dict=scalar_dict, glyph_type=glyph_type, glyph_scale=voxel_size, colormap=colormap, colors=color, opacity=0.3)

    else:

        scalar_dict=None
        points_vtk = vtk_utils.add_polydata(positions, scalar_dict=scalar_dict, glyph_type=glyph_type, glyph_scale=voxel_size, colormap=colormap, colors=color, opacity=0.3)


    

    if positions_2 is not None:


        if isinstance(positions_2, list):

            for s, sub_positions in enumerate(positions_2):
                logger.debug("%s", sub_positions.shape)
                if sub_positions.shape[1] > 3:
                    scalar_dict=sub_positions[:, plotted_value]
                    sub_positions = sub_positions[:, :3]
                else:
                    scalar_dict=None

                points_2_vtk = vtk_utils.add_polydata(sub_positions, scalar_dict=scalar_dict, glyph_type='sphere', glyph_scale=voxel_size, colormap=colormap, colors=colors[-s], opacity=0.3)
                ren.AddActor(points_2_vtk)


        elif positions_2.shape[1] > 3:
            scalar_dict_2=positions_2[:, plotted_value]
            positions_2 = positions_2[:, :3]
            points_2_vtk = vtk_utils.add_polydata(positions_2, scalar_dict=scalar_dict_2, glyph_type=glyph_type, glyph_scale=voxel_size, colormap=colormap, colors=[0,255,0], opacity=0.3)
            ren.AddActor(points_2_vtk)
        else:
            scalar_dict_2=None
            points_2_vtk = vtk_utils.add_polydata(positions_2, scalar_dict=scalar_dict_2, glyph_type=glyph_type, glyph_scale=voxel_size, colormap=colormap, colors=[0,255,0], opacity=0.3)
            ren.AddActor(points_2_vtk)




    if show_SIGMA:
        SIGMA_geometry = vtk_utils.add_stl('data/stls/sigma_volume.stl', opacity=0.2, mesh_color='Grey')
        ren.AddActor(SIGMA_geometry)

    axes = vtk_utils.add_axes(points_vtk, ren)

    ren.AddActor(points_vtk)
    ren.AddActor(axes)


    ren.ResetCamera()

    renwin.Render()

    iren.Start()

def plot_predictions_3D(true_positions, coarse_predictions, fine_predictions, coarse_set=None, fine_set=None, voxel_size=1, plotted_value=4, colormap='hsv'):

    """Plot predictions 3 d."""
    ren, renwin, iren = vtk_utils.create_renderer() 

    scalar_dict = dict()
    scalar_dict.update({'Index' : np.asarray([1,2])})

    true_points_vtk = vtk_utils.add_polydata(true_positions, scalar_dict=scalar_dict, glyph_type='sphere', glyph_scale=voxel_size, colors=[255,0,0], opacity=0.3)
    coarse_points_vtk = vtk_utils.add_polydata(coarse_predictions, scalar_dict=scalar_dict, glyph_scale=voxel_size, colors=[0,255,0], opacity=0.3)
    fine_points_vtk = vtk_utils.add_polydata(fine_predictions, scalar_dict=scalar_dict, glyph_scale=voxel_size, colors=[0,0,255], opacity=0.3)

    # axes = vtk_utils.add_axes(points_vtk, ren)
    SIGMA_geometry = vtk_utils.add_stl('data/stls/sigma_volume.stl', opacity=0.2, mesh_color='Grey')


    if fine_set is not None:
        fine_set_vtk = vtk_utils.add_polydata(fine_set, scalar_dict=None, glyph_scale=5, glyph_type='point', colors=[0,0,255], opacity=0.5)
        ren.AddActor(fine_set_vtk)

    if coarse_set is not None:
        coarse_set_vtk = vtk_utils.add_polydata(coarse_set, scalar_dict=None, glyph_scale=5, glyph_type='point', colors=[0,255,0], opacity=0.5)
        ren.AddActor(coarse_set_vtk)


    ren.AddActor(true_points_vtk)
    ren.AddActor(fine_points_vtk)
    ren.AddActor(coarse_points_vtk)
    # ren.AddActor(SIGMA_geometry)

    # ren.AddActor(points_vtk)
    # ren.AddActor(axes)

    ren.ResetCamera()

    renwin.Render()

    iren.Start()


def plot_compton_slice(compton_slice, aspect_ratio=1, title='Compton Slice', xlabel='Dimension 1', ylabel='Dimension 2'):

    """Plot compton slice."""
    fig = plt.figure(figsize=(10, 6))
    plt.title(title)
    plt.imshow(compton_slice, interpolation='none')
    plt.tight_layout()
    plt.gca().invert_yaxis()
    plt.gca().set_aspect(aspect_ratio)
    plt.colorbar(label='Overlaps')
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    return fig

def plot_compton_slices(compton_array, x_index=None, y_index=None, z_index=None, voxel_sizes=[1,1,1]):

    """Plot compton slices."""
    if isinstance(voxel_sizes, float):
        voxel_sizes = [voxel_sizes, voxel_sizes, voxel_sizes]

    hotspot_x, hotspot_y, hotspot_z = np.unravel_index(np.nanargmax(compton_array), compton_array.shape)

    if x_index is not None:
        hotspot_x = x_index
    if y_index is not None:
        hotspot_y = y_index
    if z_index is not None:
        hotspot_z = z_index


    xz_slice = compton_array[:,hotspot_y,:]
    xy_slice = compton_array[:,:,hotspot_z]
    yz_slice = compton_array[hotspot_x,:,:]


    # plt.savefig('plots/EXHAUSTIVE/XZ_slice-%i-%i-%i.png' % (hotspot_x, hotspot_y, hotspot_z))
    # plt.close()
    plot_compton_slice(xz_slice, aspect_ratio=voxel_sizes[0]/voxel_sizes[2],
                       title='X-Z Slice, Hotspot at (%i, %i, %i)' % (hotspot_x, hotspot_y, hotspot_z),
                       xlabel='X', ylabel='Z')

    # plt.figure()
    # plt.title('X-Y Slice, Hotspot at (%i, %i, %i)' % (hotspot_x, hotspot_y, hotspot_z))
    # plt.imshow(xy_slice)
    # plt.tight_layout()
    # plt.colorbar(label='Overlaps')
    # plt.gca().invert_yaxis()  
    # plt.gca().set_aspect(voxel_sizes[0] / voxel_sizes[1])  
    # plt.xlabel('X')
    # plt.ylabel('Y')
    # plt.savefig('plots/EXHAUSTIVE/XY_slice-%i-%i-%i.png' % (hotspot_x, hotspot_y, hotspot_z))
    # plt.close()


    plot_compton_slice(xy_slice, aspect_ratio=voxel_sizes[0]/voxel_sizes[1],
                       title='X-Y Slice, Hotspot at (%i, %i, %i)' % (hotspot_x, hotspot_y, hotspot_z),
                       xlabel='X', ylabel='Y')
    
    # plt.figure()
    # plt.title('Y-Z Slice, Hotspot at (%i, %i, %i)' % (hotspot_x, hotspot_y, hotspot_z))
    # plt.imshow(yz_slice)
    # plt.tight_layout()
    # plt.colorbar(label='Overlaps')
    # plt.gca().invert_yaxis()
    # plt.gca().set_aspect(voxel_sizes[1] / voxel_sizes[2])
    # plt.xlabel('Y')
    # plt.ylabel('Z')
    # plt.savefig('plots/EXHAUSTIVE/YZ_slice-%i-%i-%i.png' % (hotspot_x, hotspot_y, hotspot_z))
    # plt.close()

    plot_compton_slice(yz_slice, aspect_ratio=voxel_sizes[1]/voxel_sizes[2],
                       title='Y-Z Slice, Hotspot at (%i, %i, %i)' % (hotspot_x, hotspot_y, hotspot_z),
                       xlabel='Y', ylabel='Z')



    x_slice = compton_array[:, hotspot_y, hotspot_z]
    y_slice = compton_array[hotspot_x, :, hotspot_z]
    z_slice = compton_array[hotspot_x, hotspot_y,:]

    plt.figure()
    plt.title('X Slice, Hotspot at (%i, %i, %i)' % (hotspot_x, hotspot_y, hotspot_z))
    plt.plot(x_slice)
    plt.xlabel('X')
    plt.ylabel('Overlaps')
    plt.xlim(0, x_slice.shape[0])
    plt.tight_layout()

    plt.figure()
    plt.title('Y Slice, Hotspot at (%i, %i, %i)' % (hotspot_x, hotspot_y, hotspot_z))
    plt.plot(y_slice)
    plt.xlabel('Y')
    plt.ylabel('Overlaps')
    plt.xlim(0, y_slice.shape[0])
    plt.tight_layout()

    plt.figure()
    plt.title('Z Slice, Hotspot at (%i, %i, %i)' % (hotspot_x, hotspot_y, hotspot_z))
    plt.plot(z_slice)
    plt.xlabel('Z')
    plt.ylabel('Overlaps')
    plt.tight_layout()
    plt.xlim(0, z_slice.shape[0])
    # plt.show(block=False)
    plt.show()


def plot_cuttoff_validity(test_values, cutoff, cuttoff_type='over', show_plot=True, fail_color = 'red',
    pass_color = 'green', xlabel='Cutoff values', ylabel='Frequency'):

    """Plot cuttoff validity."""
    mean_value = np.mean(test_values)

    plt.figure()
    dist_hist, dist_bin_edges = np.histogram(test_values, bins=100)

    colors = []

    for bin_edge in dist_bin_edges:

        if cuttoff_type == 'over':
            if bin_edge < cutoff:
                colors.append(fail_color)

            elif bin_edge >= cutoff:
                colors.append(pass_color) 

        elif cuttoff_type == 'under':
            if bin_edge > cutoff:
                colors.append(fail_color)


            elif bin_edge <= cutoff:
                colors.append(pass_color)

        else:
            raise ValueError("cuttoff_type must be 'over' or 'under'")

    plt.bar(
        dist_bin_edges[:-1], 
        dist_hist, 
        width=np.diff(dist_bin_edges), 
        color=colors, 
        edgecolor='none'
    ) 
    plt.ylabel(ylabel)
    plt.xlabel(xlabel)

    plt.axvline(cutoff, color='k', linestyle='--', label='Cutoff (%.4f)' % cutoff)
    plt.axvline(mean_value, color='b', linestyle='--', label='Mean Value (%.4f)' % mean_value)
    plt.legend()
    plt.tight_layout()
    
    if show_plot:
        plt.show()


def plot_energy_spectrum(scatterer_energies, absorber_energies, validities=None, invert=False):


    """Plot energy spectrum."""
    energy_sum = scatterer_energies + absorber_energies

    if validities is not None:

        valid_indices = validities > 0
        logger.debug("%s %s", 'Total valid indices:', np.sum(valid_indices))

        if invert:
            selected_indices = np.logical_not(valid_indices)
            logger.debug('Plotting invalid events')
        else:
            selected_indices = valid_indices
            logger.debug('Plotting valid events')


        scatterer_energies = scatterer_energies[selected_indices]
        absorber_energies = absorber_energies[selected_indices]
        energy_sum = energy_sum[selected_indices]


    # def toggle_histograms(ax, hist_patches):
    #     def func(label):
    #         idx = labels.index(label)
    #         visible = not hist_patches[idx][0].get_visible()
    #         for patch in hist_patches[idx]:
    #             patch.set_visible(visible)
    #         plt.draw()
    #         # reset the axes to ensure the legend updates correctly
    #         ax.relim()
    #         ax.autoscale_view()
    #         # ax.legend()
    #     return func

    def on_pick(event):
        # On the pick event, find the original line corresponding to the legend
        # proxy line, and toggle its visibility.
        """Handle pick."""
        legend_line = event.artist

        # Do nothing if the source of the event is not a legend line.
        if legend_line not in map_legend_to_ax:
            return

        plot_element = map_legend_to_ax[legend_line]

        if hasattr(plot_element, 'get_visible'):
            visible = not plot_element.get_visible()
            plot_element.set_visible(visible)
        elif hasattr(plot_element, 'patches'):
            # If the plot element is a collection of patches (like a histogram),
            # toggle visibility for each patch.
            for patch in plot_element.patches:
                visible = not patch.get_visible()
                patch.set_visible(visible)
        # Change the alpha on the line in the legend, so we can see what lines
        # have been toggled.
        legend_line.set_alpha(1.0 if visible else 0.2)
        # Redraw the figure to reflect the changes and reset the axes.
        ax.relim()
        ax.autoscale_view()

        fig.canvas.draw()


    fig, ax = plt.subplots()
    binrange = [0, np.max(energy_sum)]
    bin_resolution = 400

    ax = plt.gca()
    h1, b1, hist1 = ax.hist(scatterer_energies, range=binrange, bins=bin_resolution, label='Scatter energies', alpha=0.5)
    h2, b2, hist2 = ax.hist(absorber_energies, range=binrange, bins=bin_resolution, label='Absorber energies', alpha=0.5)
    h3, b3, hist3 = ax.hist(energy_sum,  range=binrange, bins=bin_resolution, label='Summed energies', alpha=0.5)

    leg = ax.legend(fancybox=True, shadow=True)
    map_legend_to_ax = {}  # Will map legend lines to original lines.

    pickradius = 5  # Points (Pt). How close the click needs to be to trigger an event.

    plot_elements = [hist1, hist2, hist3]

 

    # Map all legend elements (lines and patches) to their corresponding plot elements
    legend_items = leg.get_lines() + leg.get_patches()
    for legend_item, ax_item in zip(legend_items, plot_elements):
        legend_item.set_picker(pickradius)  # Enable picking on the legend item.
        map_legend_to_ax[legend_item] = ax_item


    plt.xlabel('Energy (keV)')
    plt.ylabel('Frequency')

    plt.xlim(binrange[0], binrange[1])

    fig.canvas.mpl_connect('pick_event', on_pick)

    # rax = plt.axes([0.85, 0.85, 0.1, 0.1])
    # check = CheckButtons(rax, labels, [True, True, True])
    # check.on_clicked(toggle_histograms(ax, hist_patches))
    leg.set_draggable(True)

    plt.tight_layout()
    plt.show()
 

def plot_spherical_slice(input_coordinates, input_values):

    """Plot spherical slice."""
    import matplotlib.tri as tri 

    x = input_coordinates[:,0]
    y = input_coordinates[:,1]
    z = input_coordinates[:,2]

    r = np.sqrt(x**2 + y**2 + z**2)
    theta = np.arccos(z / r)
    phi = np.arctan2(y, x)

    # fig = plt.figure()
    # ax = fig.add_subplot(111, projection='3d')

    # ax.scatter(r, theta, phi, c=input_values, cmap='viridis')
    # plt.show()

    # plt.figure(figsize=(12, 6))
    # plt.tricontourf(phi, theta, input_values, cmap='viridis')
    # plt.colorbar(label='Values')
    # plt.xlabel('Phi')
    # plt.ylabel('Theta')
    # plt.title('Mercator Projection')
    # plt.tight_layout()
    # plt.show()

    triang = tri.Triangulation(phi, theta) 

    

    plt.figure(figsize=(13, 6))
    plt.gca().set_aspect('equal') 
    
    tri = plt.tripcolor(triang, input_values, 
                        shading ='gouraud', 
                        cmap = plt.cm.viridis, 
                        alpha = 1.0, 
                        edgecolors ='k') 
    
    plt.title('Spherical Projection') 
    plt.colorbar(tri, label ='Overlaps') 




    # plt.scatter(phi, theta, c=input_values, cmap='viridis')
    # plt.colorbar(label='Values')
    plt.xlim(-np.pi, np.pi)
    plt.ylim(0, np.pi)
    plt.xlabel('Phi')
    plt.ylabel('Theta')
    plt.tight_layout()
    plt.show()



